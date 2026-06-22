"""OntologyMapper (SETUP-05 / T-S05-013).

Загружает ontology v1 YAML (rag/ontology/ontology_v1.yaml), нормализует значения
metadata-полей RAG-карточки через canonical values + synonyms map. Неизвестные
значения возвращают warnings (не блокируют создание карточки), но в orchestrator
вызывают ``confidence_level`` понижение и ``review_required`` маркер.

Подход:
1. Канонические значения хранятся в `domain.values` / `task_type.values` / etc.
2. Synonyms — это плоский map `synonym (lower-cased) → canonical`. Поддерживает
   русские и английские варианты написания.
3. ``normalize_X(value: str)`` возвращает ``(canonical | None, warnings)``.
4. ``validate_card_metadata(dict)`` — пакетная проверка front matter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

_DEFAULT_ONTOLOGY_PATH = (
    Path(__file__).resolve().parents[4] / "rag" / "ontology" / "ontology_v1.yaml"
)


@dataclass(frozen=True, slots=True)
class OntologyWarning:
    """Non-blocking предупреждение нормализации."""

    field: str
    raw_value: str
    code: str  # ONTOLOGY_UNKNOWN_TERM | ONTOLOGY_EMPTY_VALUE
    message: str


@dataclass(slots=True)
class NormalizationResult:
    """Результат normalize_<field>: canonical (если найдено) + список warnings."""

    canonical: str | None = None
    warnings: list[OntologyWarning] = field(default_factory=list)


class OntologyLoadError(RuntimeError):
    """Ontology YAML не загружается или невалиден."""


class OntologyMapper:
    """Нормализует metadata через ontology_v1.yaml.

    Поля: domain, task_type, data_source, entity_type, phase, agent_targets,
    doc_type. Для каждого поддерживается ``normalize_<field>(value: str)``.

    Расширения добавляются через bump до ontology_v2 — внутренний код
    OntologyMapper остаётся стабильным.
    """

    _FIELDS = (
        "domain",
        "task_type",
        "data_source",
        "entity_type",
        "phase",
        "agent_targets",
        "doc_type",
    )

    def __init__(self, *, ontology_path: Path | None = None) -> None:
        path = ontology_path or _DEFAULT_ONTOLOGY_PATH
        try:
            with path.open("r", encoding="utf-8") as f:
                self._data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise OntologyLoadError(f"Failed to load ontology from {path}: {exc}") from exc

        self._ontology_version = str(self._data.get("ontology_version", "ontology_v1"))
        # field → set of canonical values (case preserved).
        self._values: dict[str, set[str]] = {}
        # field → synonym (lower-cased) → canonical.
        self._synonyms: dict[str, dict[str, str]] = {}

        for fld in self._FIELDS:
            block = self._data.get(fld, {})
            if not isinstance(block, dict):
                continue
            raw_values = block.get("values", [])
            values: set[str] = set()
            if isinstance(raw_values, list):
                values = {str(v) for v in raw_values if isinstance(v, (str, int, float))}
            self._values[fld] = values

            syn_map: dict[str, str] = {}
            raw_syn = block.get("synonyms", {})
            if isinstance(raw_syn, dict):
                for synonym, canonical in raw_syn.items():
                    if not isinstance(canonical, str):
                        continue
                    syn_map[str(synonym).lower().strip()] = canonical
            # Self-canonical: каждое canonical — синоним самого себя (case-insensitive).
            for canonical in values:
                syn_map.setdefault(canonical.lower(), canonical)
            self._synonyms[fld] = syn_map

    @property
    def ontology_version(self) -> str:
        return self._ontology_version

    def allowed_values(self, field: str) -> set[str]:
        """Все canonical values для поля (для prompt templating)."""
        return set(self._values.get(field, set()))

    # ----- normalize_<field> -----

    def normalize(self, field: str, value: str) -> NormalizationResult:
        """Универсальная нормализация. Используется в ``normalize_*`` обёртках."""
        if field not in self._FIELDS:
            raise ValueError(f"Unknown ontology field: {field}")
        result = NormalizationResult()
        if not isinstance(value, str) or not value.strip():
            result.warnings.append(
                OntologyWarning(
                    field=field,
                    raw_value=str(value),
                    code="ONTOLOGY_EMPTY_VALUE",
                    message=f"Empty {field} value",
                )
            )
            return result
        key = value.lower().strip()
        canonical = self._synonyms.get(field, {}).get(key)
        if canonical is None:
            result.warnings.append(
                OntologyWarning(
                    field=field,
                    raw_value=value,
                    code="ONTOLOGY_UNKNOWN_TERM",
                    message=f"Unknown {field} value: {value!r}",
                )
            )
            return result
        result.canonical = canonical
        return result

    def normalize_domain(self, value: str) -> NormalizationResult:
        return self.normalize("domain", value)

    def normalize_task_type(self, value: str) -> NormalizationResult:
        return self.normalize("task_type", value)

    def normalize_data_source(self, value: str) -> NormalizationResult:
        return self.normalize("data_source", value)

    def normalize_entity_type(self, value: str) -> NormalizationResult:
        return self.normalize("entity_type", value)

    def normalize_phase(self, value: str) -> NormalizationResult:
        return self.normalize("phase", value)

    def normalize_agent_targets(self, value: str) -> NormalizationResult:
        return self.normalize("agent_targets", value)

    def normalize_doc_type(self, value: str) -> NormalizationResult:
        return self.normalize("doc_type", value)

    # ----- batch -----

    def normalize_list(
        self, field: str, values: list[str]
    ) -> tuple[list[str], list[OntologyWarning]]:
        """Нормализует list[str]; неизвестные — пропускаются и попадают в warnings."""
        canonicals: list[str] = []
        warnings: list[OntologyWarning] = []
        for v in values:
            res = self.normalize(field, v)
            if res.canonical is not None:
                canonicals.append(res.canonical)
            warnings.extend(res.warnings)
        return canonicals, warnings

    def validate_card_metadata(self, metadata: dict[str, Any]) -> list[OntologyWarning]:
        """Проверка front matter dict. Возвращает все warnings из enum-полей.

        Не модифицирует metadata; orchestrator вызывает ``normalize_list`` для
        каждого поля отдельно, чтобы получить canonical + warnings.
        """
        warnings: list[OntologyWarning] = []
        for fld in (
            "domain",
            "task_type",
            "data_source",
            "entity_type",
            "phase",
            "agent_targets",
        ):
            raw = metadata.get(fld)
            if isinstance(raw, list):
                _, w = self.normalize_list(fld, [str(v) for v in raw])
                warnings.extend(w)
            elif isinstance(raw, str):
                warnings.extend(self.normalize(fld, raw).warnings)
        # doc_type обычно скалярный.
        doc_type_raw = metadata.get("doc_type")
        if isinstance(doc_type_raw, str):
            warnings.extend(self.normalize("doc_type", doc_type_raw).warnings)
        return warnings
