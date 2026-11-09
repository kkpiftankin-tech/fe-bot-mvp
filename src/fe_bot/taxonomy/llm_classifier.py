"""LLMClassifier — обёртка над LLMGateway для одного уровня (SETUP-12 / T-S12-031).

Делает один вызов LLM для классификации секции на уровне k.
Возвращает ``Decision`` (EXISTING / NEW / UNKNOWN).

Стратегия валидации:
- gateway вызывается с permissive JSON-схемой (extra=allow), чтобы LLM
  имел свободу формы — затем normalize+validate под жёсткий ``Decision``;
- если confidence у NEW ниже ``MIN_NEW_CLASS_CONF`` — переинтерпретация
  как UNKNOWN (см. ADR-HTC-04);
- если bit-индексы у EXISTING не из candidates — переинтерпретация
  как UNKNOWN (LLM галлюцинировал индекс);
- если LLMGateway возвращает InvalidLLMOutputError / TimeoutError —
  возвращаем UNKNOWN с reason'ом (cascading-stop ловится в orchestrator'е).

Не делает запись в registry / не выставляет биты — это работа
HierarchicalClassifier (S4).
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from schemas.taxonomy.decision import (
    Decision,
    DecisionKind,
    ExistingSelection,
    NewClassProposal,
)
from schemas.taxonomy.registry import TaxonomyBitRegistryEntry

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)
from fe_bot.taxonomy.config import AutoAllocatorConfig
from fe_bot.taxonomy.prompt_renderer import (
    ClassificationPromptInput,
    ClassificationPromptRenderer,
)

logger = logging.getLogger(__name__)


class LLMClassifierError(Exception):
    """Поднимается только при unrecoverable ошибках (LLM gateway down)."""


class _PermissiveLLMJSON(BaseModel):
    """Permissive-схема для structured-output LLM (см. ADR-HTC-04).

    Gateway форсит ``format=json`` через Ollama; затем нормализуем
    payload под жёсткий ``Decision`` вручную.
    """

    model_config = ConfigDict(extra="allow")


class LLMClassifier:
    """Stateless классификатор одного уровня."""

    def __init__(
        self,
        *,
        gateway: LLMGateway,
        renderer: ClassificationPromptRenderer | None = None,
        config: AutoAllocatorConfig | None = None,
    ) -> None:
        self._gateway = gateway
        self._renderer = renderer or ClassificationPromptRenderer()
        self._config = config or AutoAllocatorConfig()

    @property
    def config(self) -> AutoAllocatorConfig:
        return self._config

    def classify(
        self,
        *,
        level: int,
        parent_path: str,
        candidates: list[TaxonomyBitRegistryEntry],
        section_text: str,
        free_slots_count: int,
        primary_l0_slug: str | None = None,
        primary_l0_display_ru: str | None = None,
        primary_l1_slug: str | None = None,
        primary_l1_display_ru: str | None = None,
        also_applies_l0: list[str] | None = None,
    ) -> Decision:
        """Один LLM-вызов → Decision. Не бросает на «нормальные» отказы
        LLM (invalid output, timeout) — возвращает UNKNOWN с reason.
        Бросает только LLMClassifierError при unrecoverable LLM-сбое.
        """
        params = ClassificationPromptInput(
            level=level,
            parent_path=parent_path,
            candidates=list(candidates),
            section_text=section_text,
            free_slots_count=free_slots_count,
            primary_l0_slug=primary_l0_slug,
            primary_l0_display_ru=primary_l0_display_ru,
            primary_l1_slug=primary_l1_slug,
            primary_l1_display_ru=primary_l1_display_ru,
            also_applies_l0=list(also_applies_l0 or []),
            max_classes_per_level=self._config.classes_per_level,
        )
        prompt = self._renderer.render(params)

        try:
            result = self._gateway.generate_structured(
                prompt=prompt,
                schema=_PermissiveLLMJSON,
                model=self._config.llm_model,
                temperature=self._config.llm_temperature,
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unavailable at level=%d: %s", level, exc)
            raise LLMClassifierError(
                f"LLM gateway unavailable at level {level}: {exc}"
            ) from exc
        except InvalidLLMOutputError as exc:
            logger.warning(
                "LLM returned invalid JSON after retries at level=%d: %s",
                level,
                exc,
            )
            return _unknown(
                "LLM returned invalid JSON after gateway retries: "
                f"{exc}"
            )
        except TimeoutError as exc:
            logger.warning("LLM timeout at level=%d: %s", level, exc)
            return _unknown(f"LLM timeout at level {level}: {exc}")

        payload: dict[str, Any] = result.parsed.model_dump()
        return self._normalize(payload, candidates=candidates, level=level)

    # ------------------------------------------------------------------
    # Normalisation: permissive payload → strict Decision
    # ------------------------------------------------------------------

    def _normalize(
        self,
        payload: dict[str, Any],
        *,
        candidates: list[TaxonomyBitRegistryEntry],
        level: int,
    ) -> Decision:
        decision_str = str(payload.get("decision", "")).lower().strip()
        overall_raw = payload.get("overall_confidence", 0.0)
        overall_conf = _clamp_confidence(overall_raw)
        reason = str(payload.get("reason", "") or "")

        if decision_str == "unknown":
            return _unknown(reason or "LLM said unknown")

        if decision_str == "new":
            return self._normalize_new(
                payload, overall_conf=overall_conf, reason=reason
            )

        if decision_str == "existing":
            return self._normalize_existing(
                payload,
                candidates=candidates,
                overall_conf=overall_conf,
                reason=reason,
                level=level,
            )

        # Unknown decision-string → переинтерпретация как UNKNOWN
        return _unknown(
            f"LLM returned unrecognised decision={decision_str!r}; "
            f"raw_reason={reason}"
        )

    def _normalize_new(
        self,
        payload: dict[str, Any],
        *,
        overall_conf: float,
        reason: str,
    ) -> Decision:
        if overall_conf < self._config.min_new_class_conf:
            return _unknown(
                f"LLM new-class confidence {overall_conf:.2f} below threshold "
                f"{self._config.min_new_class_conf:.2f}; treating as UNKNOWN"
            )
        proposal_raw = payload.get("proposal")
        if not isinstance(proposal_raw, dict):
            return _unknown(
                f"LLM decision=new but proposal payload missing/invalid: "
                f"{type(proposal_raw).__name__}"
            )
        try:
            proposal = NewClassProposal(**proposal_raw)
        except ValidationError as exc:
            logger.warning(
                "Proposal validation failed: %s", exc.errors()[:3]
            )
            return _unknown(
                f"LLM proposal validation failed: {exc.errors()[:2]}"
            )
        try:
            return Decision(
                kind=DecisionKind.NEW,
                selected=[],
                proposal=proposal,
                overall_confidence=overall_conf,
                reason=reason,
            )
        except ValidationError as exc:  # pragma: no cover - safety net
            logger.warning(
                "Decision(NEW) construction failed: %s", exc.errors()[:3]
            )
            return _unknown(f"Decision(NEW) construction failed: {exc}")

    def _normalize_existing(
        self,
        payload: dict[str, Any],
        *,
        candidates: list[TaxonomyBitRegistryEntry],
        overall_conf: float,
        reason: str,
        level: int,
    ) -> Decision:
        valid_bits = {c.bit_index for c in candidates}
        raw_selected = payload.get("selected") or []
        if not isinstance(raw_selected, list):
            return _unknown(
                f"LLM decision=existing but selected payload not a list "
                f"({type(raw_selected).__name__})"
            )
        normalized: list[ExistingSelection] = []
        seen_bits: set[int] = set()
        rejected_bits: list[int] = []
        for item in raw_selected:
            if not isinstance(item, dict):
                continue
            bit = item.get("bit")
            if not isinstance(bit, int):
                continue
            if bit not in valid_bits:
                rejected_bits.append(bit)
                continue
            if bit in seen_bits:
                # Дубликат — игнорируем (Decision validator всё равно
                # отвергнет).
                continue
            seen_bits.add(bit)
            conf = _clamp_confidence(item.get("confidence", 0.0))
            sel_reason = str(item.get("reason", "") or "")
            normalized.append(
                ExistingSelection(
                    bit=bit, confidence=conf, reason=sel_reason
                )
            )
        if rejected_bits:
            logger.warning(
                "LLM at level=%d proposed bits not in candidates: %s "
                "(dropped)",
                level,
                rejected_bits,
            )
        if not normalized:
            return _unknown(
                "LLM decision=existing but no valid bits in selected "
                f"(rejected={rejected_bits})"
            )
        try:
            return Decision(
                kind=DecisionKind.EXISTING,
                selected=normalized,
                proposal=None,
                overall_confidence=overall_conf,
                reason=reason,
            )
        except ValidationError as exc:  # pragma: no cover - safety net
            logger.warning(
                "Decision(EXISTING) construction failed: %s",
                exc.errors()[:3],
            )
            return _unknown(
                f"Decision(EXISTING) construction failed: {exc}"
            )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _clamp_confidence(value: Any) -> float:
    try:
        x = float(value)
    except (TypeError, ValueError):
        return 0.0
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _unknown(reason: str) -> Decision:
    return Decision(
        kind=DecisionKind.UNKNOWN,
        selected=[],
        proposal=None,
        overall_confidence=0.0,
        reason=reason or "LLM produced no actionable classification",
    )
