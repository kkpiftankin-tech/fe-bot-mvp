"""RAG Card Generator (T-S01-020).

Вход: ParsedSection.
Выход: (RAGCard, RAGMetadata) — карточка + согласованная metadata.

Логика confidence:
- confidence >= HIGH_CONFIDENCE_THRESHOLD И confidence_level=HIGH → status=GENERATED
- иначе → status=REVIEW_REQUIRED (HITL)

LLM-агент возвращает RAGCardDraft (см. draft.py); генератор:
1. Конструирует детерминированный doc_id из doc_type + slug(title) + version.
2. Назначает version="1.0", created_at, created_by.
3. Собирает RAGCard.body_markdown из summary + body_markdown.
4. Собирает RAGMetadata.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime

from schemas.common.defaults import DEFAULT_LLM_MODEL
from schemas.rag.ontology import ConfidenceLevel, DocType, Phase
from schemas.rag.rag_card import CardStatus, RAGCard
from schemas.rag.rag_metadata import RAGMetadata
from schemas.setup.parsed_section import ParsedSection, SectionType

from fe_bot.llm_gateway.client import LLMGateway
from fe_bot.llm_gateway.exceptions import InvalidLLMOutputError, LLMUnavailableError
from fe_bot.setup.card_generator.draft import RAGCardDraft

logger = logging.getLogger(__name__)

# Порог уверенности, выше которого карточка идёт сразу в metadata_validated,
# минуя review_required.
HIGH_CONFIDENCE_THRESHOLD = 0.7

# Максимальный объём текста секции, передаваемый в LLM.
SECTION_TEXT_CHAR_BUDGET = 6000


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """Простой slug: lowercased, не-alpha-num → '_', обрезается до 64 символов."""
    s = _SLUG_RE.sub("_", text.lower()).strip("_")
    return s[:64] or "untitled"


def _make_doc_id(
    draft: RAGCardDraft,
    version: str = "v1",
    *,
    unique_suffix: str | None = None,
) -> str:
    """`<doc_type>.<slug(title)>.<version>` — стабильный человекочитаемый id.

    Когда два setup_job в одном registry генерируют карточки с одинаковым
    title (типично для fallback), нужен per-job uniquifier — передавай
    `unique_suffix` (обычно tail setup_job_id).
    """
    base = f"{draft.doc_type.value}.{_slug(draft.title)}"
    if unique_suffix:
        suffix_safe = _slug(unique_suffix)[:12]
        return f"{base}.{suffix_safe}.{version}"
    return f"{base}.{version}"


def _section_text_for_prompt(section: ParsedSection) -> str:
    text = section.normalized_text or section.raw_text
    if len(text) > SECTION_TEXT_CHAR_BUDGET:
        text = text[:SECTION_TEXT_CHAR_BUDGET] + "\n…[TRUNCATED]"
    return text


def _build_prompt(section: ParsedSection) -> str:
    text = _section_text_for_prompt(section)
    section_path = " > ".join(section.section_path) if section.section_path else "(root)"
    return f"""Ты — генератор RAG-карточек для FE-Bot. Преобразуй секцию документа
в одну RAG-карточку.

ИСХОДНАЯ СЕКЦИЯ:
- Заголовок: {section.title}
- Путь: {section_path}
- Тип секции (эвристика): {section.section_type.value}

ТЕКСТ:
\"\"\"
{text}
\"\"\"

ТРЕБОВАНИЯ:
1. Выбери doc_type из закрытого списка (ontology_card, domain_profile,
   schema_card, field_definition_card, task_card, feature_pattern_card,
   analytics_card, validation_rule_card, question_template_card,
   model_recommendation_card, glossary_term, example_card, bad_example_card).
2. title — человекочитаемое название карточки.
3. summary — 1-2 предложения, что карточка описывает.
4. body_markdown — структурированное содержимое карточки (Markdown).
5. retrieval_tags — минимум 1 тег (низкорегистровые слова/фразы).
6. phase — минимум 1 фаза workflow.
7. confidence ∈ [0.0, 1.0]: твоя уверенность, что секция хорошо
   укладывается в выбранный doc_type. confidence_level (high/medium/low) —
   согласуй с confidence.
8. agent_targets — только известные имена агентов FE-Bot (SessionAgent,
   NLUAgent, RAGRetrievalAgent, DialogueOrchestratorAgent, ContextMemoryAgent,
   TaskDiscoveryAgent, DataProfilingAgent, DomainContextAgent,
   FeatureSynthesisAgent, FeatureCriticAgent, MulticollinearityAgent,
   DataGenerationSpecAgent, ModelSelectionAgent, ExportAgent, FeedbackAgent,
   AuditAgent) — или пустой список.

Верни ТОЛЬКО валидный JSON, соответствующий схеме.
"""


def _draft_to_card_and_metadata(
    draft: RAGCardDraft,
    *,
    section: ParsedSection,
    created_by: str,
    unique_suffix: str | None = None,
) -> tuple[RAGCard, RAGMetadata]:
    doc_id = _make_doc_id(draft, unique_suffix=unique_suffix)
    now = datetime.now(tz=UTC)

    # Решаем status карточки.
    is_high_confidence = (
        draft.confidence >= HIGH_CONFIDENCE_THRESHOLD
        and draft.confidence_level == ConfidenceLevel.HIGH
    )
    status = CardStatus.GENERATED if is_high_confidence else CardStatus.REVIEW_REQUIRED

    body = f"# {draft.title}\n\n{draft.summary.strip()}\n\n{draft.body_markdown.strip()}\n"

    card = RAGCard(
        doc_id=doc_id,
        doc_type=draft.doc_type,
        title=draft.title,
        version="1.0",
        status=status,
        front_matter={"doc_id": doc_id, "doc_type": draft.doc_type.value, "version": "1.0"},
        body_markdown=body,
        source_document_ids=[section.source_document_id],
        source_section_ids=[section.section_id],
        confidence_level=draft.confidence_level.value,
        created_by=created_by,
        reviewed_by=None,
        created_at=now,
        updated_at=now,
        published_at=None,
    )
    metadata = RAGMetadata(
        doc_id=doc_id,
        doc_type=draft.doc_type,
        domain=draft.domain,
        task_type=draft.task_type,
        data_source=draft.data_source,
        entity_type=draft.entity_type,
        phase=draft.phase,
        agent_targets=draft.agent_targets,
        required_input_fields=draft.required_input_fields,
        output_fields=draft.output_fields,
        retrieval_tags=draft.retrieval_tags,
        confidence_level=draft.confidence_level,
        owner=created_by,
        last_verified_at=None,
    )
    return card, metadata


class RAGCardGeneratorResult:
    """Результат генерации одной карточки + использованный fallback-флаг."""

    __slots__ = ("card", "metadata", "used_fallback", "attempts")

    def __init__(
        self,
        *,
        card: RAGCard,
        metadata: RAGMetadata,
        used_fallback: bool,
        attempts: int,
    ) -> None:
        self.card = card
        self.metadata = metadata
        self.used_fallback = used_fallback
        self.attempts = attempts


class RAGCardGenerator:
    """Генерирует RAG-карточки через LLM Gateway.

    При недоступности LLM или невалидном output после retry — переключается
    на fallback (если включён), иначе пробрасывает ошибку.
    """

    def __init__(
        self,
        *,
        llm_gateway: LLMGateway,
        fallback_generator: RAGCardFallbackGenerator | None = None,
        created_by: str = "rag_card_generator",
        model: str = DEFAULT_LLM_MODEL,
    ) -> None:
        self._gateway = llm_gateway
        self._fallback = fallback_generator
        self._created_by = created_by
        self._model = model

    def generate(self, section: ParsedSection) -> RAGCardGeneratorResult:
        prompt = _build_prompt(section)
        try:
            result = self._gateway.generate_structured(
                prompt=prompt,
                schema=RAGCardDraft,
                model=self._model,
                temperature=0.0,
            )
        except (LLMUnavailableError, InvalidLLMOutputError) as exc:
            logger.warning("LLM card generation failed: %s", exc)
            if self._fallback is None:
                raise
            return self._fallback.generate(section)

        card, metadata = _draft_to_card_and_metadata(
            result.parsed, section=section, created_by=self._created_by
        )
        return RAGCardGeneratorResult(
            card=card,
            metadata=metadata,
            used_fallback=False,
            attempts=result.call.attempts,
        )

    def generate_many(self, sections: list[ParsedSection]) -> list[RAGCardGeneratorResult]:
        return [self.generate(s) for s in sections]


# ---------- T-S01-021. Fallback (без LLM) ----------

# Эвристика section_type → doc_type.
_SECTION_TO_DOC_TYPE: dict[SectionType, DocType] = {
    SectionType.TASK: DocType.TASK_CARD,
    SectionType.SCHEMA: DocType.SCHEMA_CARD,
    SectionType.ANALYTICS: DocType.ANALYTICS_CARD,
    SectionType.GLOSSARY: DocType.GLOSSARY_TERM,
    SectionType.VALIDATION: DocType.VALIDATION_RULE_CARD,
    SectionType.DOMAIN_PROFILE: DocType.DOMAIN_PROFILE,
    SectionType.OTHER: DocType.EXAMPLE_CARD,  # неклассифицированное — пример
}


class RAGCardFallbackGenerator:
    """Шаблонная генерация без LLM. Все карточки → review_required."""

    DEFAULT_PHASES = ()  # подставляется ниже

    def __init__(self, *, created_by: str = "rag_card_fallback") -> None:
        self._created_by = created_by

    def generate(self, section: ParsedSection) -> RAGCardGeneratorResult:

        doc_type = _SECTION_TO_DOC_TYPE.get(section.section_type, DocType.EXAMPLE_CARD)
        # Подбираем default phase под doc_type.
        default_phase = _default_phase_for(doc_type)
        title = section.title.strip() or f"section_{uuid.uuid4().hex[:8]}"

        tags = _extract_tags(section.title, section.section_type.value)

        draft = RAGCardDraft(
            doc_type=doc_type,
            title=title,
            summary=f"Auto-generated stub from section '{title}' (fallback, no LLM).",
            body_markdown=(section.normalized_text or section.raw_text or "(empty)").strip(),
            domain=[],
            task_type=[],
            data_source=[],
            entity_type=[],
            phase=[default_phase],
            agent_targets=[],
            required_input_fields=[],
            output_fields=[],
            retrieval_tags=tags or ["fallback"],
            confidence_level=ConfidenceLevel.LOW,
            confidence=0.2,
        )
        card, metadata = _draft_to_card_and_metadata(
            draft,
            section=section,
            created_by=self._created_by,
            unique_suffix=section.setup_job_id,
        )
        return RAGCardGeneratorResult(card=card, metadata=metadata, used_fallback=True, attempts=0)


def _default_phase_for(doc_type: DocType) -> Phase:
    return {
        DocType.TASK_CARD: Phase.TASK_DISCOVERY,
        DocType.SCHEMA_CARD: Phase.DATA_PROFILING,
        DocType.FIELD_DEFINITION_CARD: Phase.DATA_PROFILING,
        DocType.ANALYTICS_CARD: Phase.FEATURE_SYNTHESIS,
        DocType.FEATURE_PATTERN_CARD: Phase.FEATURE_SYNTHESIS,
        DocType.VALIDATION_RULE_CARD: Phase.VALIDATION,
        DocType.DOMAIN_PROFILE: Phase.DOMAIN_CONTEXT,
        DocType.MODEL_RECOMMENDATION_CARD: Phase.MODEL_SELECTION,
        DocType.QUESTION_TEMPLATE_CARD: Phase.NLU,
    }.get(doc_type, Phase.DATA_PROFILING)


def _extract_tags(title: str, section_type: str) -> list[str]:
    """Базовый tag extractor: title words + section_type."""
    words = re.findall(r"[a-zа-я0-9]+", title.lower())
    tags = [w for w in words if len(w) >= 3][:8]
    tags.append(section_type)
    # Уникальные с сохранением порядка.
    seen: set[str] = set()
    out: list[str] = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
