"""LLMCardAdapter (SETUP-05 / T-S05-019).

Тонкая обёртка над ``LLMGateway.generate_structured`` для генерации
``RAGCardDraft``. Берёт на себя:

- Трансляцию gateway-ошибок в SETUP-05 ``RAGCardGenerationErrorCode``.
- Учёт ``timeout_sec`` (gateway уже встроен; здесь — конфигурация).
- Fallback на ``RAGCardFallbackGenerator`` при недоступности LLM.
- Режим ``mode="template"`` — обходит LLM полностью.
- Метрики (model, attempts, duration).

Schema validation и repair-retry уже реализованы внутри ``LLMGateway`` (см.
src/fe_bot/llm_gateway/client.py:103-180).
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from schemas.common.defaults import DEFAULT_LLM_MODEL

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import (
    InvalidLLMOutputError,
    LLMUnavailableError,
)
from fe_bot.setup.rag_card_generation.precheck import RAGCardDraft


class _PermissiveLLMJSON(BaseModel):
    """Permissive Pydantic-схема для structured-output LLM.

    Используется как ``schema`` в ``LLMGateway.generate_structured`` —
    gateway форсит ``format=json`` через Ollama и ретраит при невалидном
    JSON. Любые поля (включая лишние) принимаются и затем нормализуются
    в ``_normalize_llm_json`` под жёсткую схему ``RAGCardDraft``.
    """

    model_config = ConfigDict(extra="allow")

logger = logging.getLogger(__name__)

# Поля верхнего уровня, которые LLM регулярно возвращает (по промпту),
# но которых нет в RAGCardDraft schema. Эти поля переносятся в front_matter
# вместо отбрасывания/фейла.
_FRONT_MATTER_FIELDS = frozenset(
    {
        "version",
        "status",
        "domain",
        "task_type",
        "data_source",
        "entity_type",
        "phase",
        "agent_targets",
        "feature_tables",
        "required_input_fields",
        "output_fields",
        "validation_rules",
        "compatible_models",
        "examples",
        "tags",
    }
)

# Слабые модели (llama3.2) иногда выводят литеральные "\n" как ДВА символа
# текста вместо настоящего переноса строки, а из-за визуального сходства
# кириллической "н" и латинской "n" в русской раскладке иногда путают их,
# выдавая "\н" вместо "\n". Оба случая распознаём и заменяем на реальный \n.
_STRAY_NEWLINE_ESCAPE_RE = re.compile(r"\\[nн]")


def _fix_stray_escaped_newlines(text: str) -> str:
    return _STRAY_NEWLINE_ESCAPE_RE.sub("\n", text)


# Известные top-level имена RAGCardDraft (всё остальное → front_matter).
_DRAFT_TOP_FIELDS = frozenset(
    {
        "doc_id",
        "doc_type",
        "title",
        "body_markdown",
        "front_matter",
        "source_files",
        "source_sections",
        "retrieval_tags",
        "confidence",
        "warnings",
    }
)


def _normalize_llm_json(
    payload: dict[str, Any],
    *,
    doc_type_hint: str,
    section_title_hint: str | None = None,
) -> dict[str, Any]:
    """Приводит сырой LLM JSON к виду, валидному для RAGCardDraft.

    - Лишние top-level поля (domain, phase, version и т.п.) переносятся
      в front_matter, чтобы не терять полезные данные от LLM.
    - Если body_markdown пустой/отсутствует — синтезируется placeholder
      из title и доступных metadata (carda помечается как low confidence
      через MISSING_BODY warning).
    - Если doc_type невалидный — используется hint от orchestrator.
    - phase / domain / agent_targets нормализуются: строка → list[1].
    """
    out: dict[str, Any] = {"front_matter": {}}
    raw_fm = payload.get("front_matter")
    if isinstance(raw_fm, dict):
        out["front_matter"].update(raw_fm)

    for key, value in payload.items():
        if key == "front_matter":
            continue
        if key in _DRAFT_TOP_FIELDS:
            out[key] = value
        elif key in _FRONT_MATTER_FIELDS or value is not None:
            # Любые лишние поля сохраняем в front_matter (включая custom).
            # Сначала нормализуем string → list для известных multi-value полей.
            multi_value_fields = {
                "domain", "task_type", "data_source", "entity_type", "phase", "agent_targets",
            }
            if key in multi_value_fields and isinstance(value, str):
                value = [value]
            out["front_matter"][key] = value

    # doc_type fallback
    if not out.get("doc_type") or out.get("doc_type") in {"unknown", "", None}:
        out["doc_type"] = doc_type_hint

    # title fallback
    if not out.get("title"):
        out["title"] = section_title_hint or "Карточка без заголовка"
    out["title"] = _fix_stray_escaped_newlines(str(out["title"]))

    # body_markdown fallback — синтез из доступных полей (LLM иногда
    # забывает body, но возвращает summary).
    body = out.get("body_markdown")
    if not body or not str(body).strip():
        summary = payload.get("summary")
        if isinstance(summary, list):
            summary = " ".join(str(s) for s in summary)
        if summary:
            out["body_markdown"] = (
                f"# {out['title']}\n\n## Описание\n\n{summary}\n"
            )
        else:
            # Минимальный placeholder — потом review_required отметит.
            out["body_markdown"] = (
                f"# {out['title']}\n\n## Описание\n\n"
                "Содержимое body не было извлечено LLM из исходной секции. "
                "Требуется ручное редактирование на шаге Review.\n"
            )

    out["body_markdown"] = _fix_stray_escaped_newlines(str(out["body_markdown"]))

    # source_files / source_sections — оставляем как есть, orchestrator override.
    out.setdefault("source_files", payload.get("source_files", []) or [])
    out.setdefault("source_sections", payload.get("source_sections", []) or [])
    out.setdefault("retrieval_tags", payload.get("retrieval_tags", []) or [])

    # Precheck (см. precheck.py:_front_matter_valid) требует, чтобы
    # front_matter содержал doc_id и doc_type. LLM кладёт их только на
    # верхнем уровне — зеркалируем их в front_matter.
    fm = out.setdefault("front_matter", {})
    if isinstance(fm, dict):
        fm.setdefault("doc_id", out.get("doc_id"))
        fm.setdefault("doc_type", out.get("doc_type"))

    return out


class LLMCardGenerationFailed(Exception):
    """Ошибка генерации карточки через LLM. error_code — RAGCardGenerationErrorCode.value."""

    def __init__(self, error_code: str, reason: str) -> None:
        self.error_code = error_code
        self.reason = reason
        super().__init__(f"{error_code}: {reason}")


@dataclass(slots=True)
class LLMGenerationResult:
    """Результат генерации draft + метрики."""

    draft: RAGCardDraft
    attempts: int
    duration_ms: int
    model: str
    used_fallback: bool


class FallbackGenerator:
    """Контракт fallback-генератора (для ``mode='template'`` или при недоступности LLM).

    В MVP — простая реализация на template; продакшен может подменить на
    rule-based generator с детерминированными правилами.
    """

    def generate_draft(self, prompt: str, *, doc_type: str) -> RAGCardDraft:
        raise NotImplementedError


def _force_fallback_env() -> bool:
    return os.environ.get("FE_BOT_FORCE_FALLBACK", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


class LLMCardAdapter:
    """Адаптер над LLMGateway для генерации RAGCardDraft.

    Поддерживает три режима:
    - ``llm`` (default): вызывает LLMGateway; при недоступности → fallback (если задан).
    - ``template``: всегда использует fallback (LLM не вызывается).
    - ``hybrid`` (alias для ``llm``): резервируется для будущих policies.
    """

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        fallback_generator: FallbackGenerator | None = None,
        model: str = DEFAULT_LLM_MODEL,
        timeout_sec: int = 60,
    ) -> None:
        self._gateway = llm_gateway
        self._fallback = fallback_generator
        self._model = model
        self._timeout_sec = timeout_sec

    @property
    def model(self) -> str:
        return self._model

    def generate(
        self,
        prompt: str,
        *,
        doc_type: str,
        mode: str = "llm",
    ) -> LLMGenerationResult:
        """Генерирует RAGCardDraft. Возвращает draft + метрики.

        Raises:
            LLMCardGenerationFailed: с ``error_code`` ∈ {LLM_GATEWAY_UNAVAILABLE,
              LLM_TIMEOUT, INVALID_LLM_OUTPUT, INVALID_GENERATION_MODE}.
        """
        if mode not in {"llm", "template", "hybrid"}:
            raise LLMCardGenerationFailed(
                "INVALID_GENERATION_MODE",
                f"Unknown generation_mode: {mode!r}",
            )

        # Template mode или global force fallback → bypass LLM.
        if mode == "template" or _force_fallback_env():
            return self._invoke_fallback(prompt, doc_type=doc_type)

        # SETUP-05 v2 lenient path: вызываем generate_structured с
        # permissive-схемой (extra=allow). Gateway форсит format=json в
        # Ollama и сам ретраит при невалидном JSON. После получения
        # payload — нормализуем под жёсткую RAGCardDraft (extra=forbid),
        # перенося лишние LLM-поля в front_matter вместо отбрасывания.
        start = time.perf_counter()
        try:
            result = self._gateway.generate_structured(
                prompt=prompt,
                schema=_PermissiveLLMJSON,
                model=self._model,
                temperature=0.0,
            )
        except LLMUnavailableError as exc:
            logger.warning("LLM unavailable, attempting fallback: %s", exc)
            if self._fallback is not None:
                return self._invoke_fallback(prompt, doc_type=doc_type)
            raise LLMCardGenerationFailed(
                "LLM_GATEWAY_UNAVAILABLE", str(exc)
            ) from exc
        except InvalidLLMOutputError as exc:
            logger.warning(
                "LLM produced invalid JSON after retries: %s", exc
            )
            if self._fallback is not None:
                return self._invoke_fallback(prompt, doc_type=doc_type)
            raise LLMCardGenerationFailed(
                "INVALID_LLM_OUTPUT", str(exc)
            ) from exc
        except TimeoutError as exc:
            raise LLMCardGenerationFailed("LLM_TIMEOUT", str(exc)) from exc

        # Gateway вернул валидный JSON (под permissive schema). Извлекаем
        # сырой payload и нормализуем под RAGCardDraft.
        payload: dict[str, Any] = result.parsed.model_dump()
        normalized = _normalize_llm_json(payload, doc_type_hint=doc_type)
        try:
            draft = RAGCardDraft.model_validate(normalized)
        except ValidationError as exc:
            logger.warning(
                "Normalized draft validation failed: %s — falling back",
                exc.errors()[:3],
            )
            if self._fallback is not None:
                return self._invoke_fallback(prompt, doc_type=doc_type)
            raise LLMCardGenerationFailed(
                "INVALID_LLM_OUTPUT",
                f"Normalized draft validation failed: {exc.errors()[:3]}",
            ) from exc

        duration_ms = max(int((time.perf_counter() - start) * 1000), 0)
        return LLMGenerationResult(
            draft=draft,
            attempts=result.call.attempts,
            duration_ms=duration_ms,
            model=result.call.model_name,
            used_fallback=False,
        )

    def _invoke_fallback(self, prompt: str, *, doc_type: str) -> LLMGenerationResult:
        if self._fallback is None:
            raise LLMCardGenerationFailed(
                "LLM_GATEWAY_UNAVAILABLE",
                "LLM unavailable and no fallback configured",
            )
        start = time.perf_counter()
        draft = self._fallback.generate_draft(prompt, doc_type=doc_type)
        duration_ms = max(int((time.perf_counter() - start) * 1000), 0)
        return LLMGenerationResult(
            draft=draft,
            attempts=1,
            duration_ms=duration_ms,
            model="fallback_template",
            used_fallback=True,
        )


# Re-export для удобства orchestrator.
__all__ = [
    "FallbackGenerator",
    "LLMCardAdapter",
    "LLMCardGenerationFailed",
    "LLMGenerationResult",
    "RAGCardDraft",
]
