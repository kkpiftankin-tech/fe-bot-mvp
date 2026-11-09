# TD-HTC-004 — Дублирование классификации в генерации RAG-карточек

## Status

Open. Целевой дизайн принят в [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md); код ему не соответствует.

## Context

Шаг 3 (SETUP-13) классифицирует секцию по дереву и сохраняет `ParsedSection.classifier_result`. Шаг 4 (SETUP-05) этот результат не читает и определяет то же самое ещё двумя способами: `DocTypeDetector` (по `section_type`) и LLM-промпт (онтологические поля по сырому тексту). В режиме `FE_BOT_TAXONOMY_MODE=llm` `ClassifierTreeSectionClassifier` всегда записывает `section_type = OTHER`, поэтому `DocTypeDetector` не находит сигнала (кроме случайного слова-маркера вроде «определение» в заголовке) и секция завершается `INVALID_DOC_TYPE`.

## Что нужно изменить

| Область | Сейчас | Должно быть |
| --- | --- | --- |
| `schemas/classifier/node.py` | `ClassifierNode` без хинтов | Блок `metadata_hints: ClassifierMetadataHints \| None` |
| `schemas/classifier/classification_result.py` | Путь и confidence | Добавлено `resolved_hints: ResolvedMetadataHints` |
| `fe_bot/classifier/tree_service.py` | CRUD дерева | `resolve_hints(path)`; валидация хинтов по онтологии при сохранении узла |
| API и UI SETUP-13 | Редактирование имени, описания, промпта | Редактирование хинтов; показ унаследованных значений и источника |
| `fe_bot/setup/rag_card_generation/doc_type_detector.py` | Источник `doc_type` по `section_type` | Заменён `ClassificationMetadataResolver`; остаётся только как переходный fallback при отсутствии `classifier_result` |
| `prompts/rag_card/*.txt`, `RAGCardDraft` (`rag_card_generation/precheck.py`) | LLM возвращает `doc_type`, `domain`, `task_type`, `data_source`, `entity_type`, `phase`, `agent_targets` | LLM получает классификацию как контекст и возвращает только содержимое и content-confidence; `RAGCardDraft.doc_type` выставляет резолвер |
| `card_generator/service.py::_build_prompt` (legacy `RAGCardGenerator`, используется только `SetupPipeline`) | LLM выбирает `doc_type` из 13 значений, `phase`, `agent_targets`; `section_type` подан как «эвристика» | Не развивать. Либо удалить вместе с monolith-`SetupPipeline`, либо привести к той же схеме; решение — при обработке этого TD |
| `ConfidenceCalculator` | Штраф за незавершённую классификацию читается из legacy `ClassificationState` (SETUP-12) | Классификационная уверенность берётся из `classifier_result.overall_confidence` |
| `RAGCardGenerationErrorCode` | Только `INVALID_DOC_TYPE` | Добавлен `DOC_TYPE_HINT_MISSING` |
| Чанкинг (SETUP-08) | Эвристика, `phase` / `retrieval_purpose` не заданы в описании | `phase` и `retrieval_purpose` из metadata карточки, полученной из хинтов |

## Порядок работ

Сначала контракты и тесты, затем код ([CLAUDE.md](../../CLAUDE.md), «Поток разработки»): схемы `ClassifierMetadataHints` / `ResolvedMetadataHints` → unit-тесты слияния хинтов → `resolve_hints` и API → `ClassificationMetadataResolver` → перевод промптов и `RAGCardDraft` → `ConfidenceCalculator` → чанкинг.

## Влияние на качество, пока не сделано

- В `llm`-режиме генерация карточек отказывает почти на всех секциях, прошедших классификацию SETUP-13 (проходят лишь секции со словом-маркером в заголовке, которые детектор отправляет в `field_definition_card`).
- Даже при ручном обходе онтологические поля карточки остаются догадкой маленькой LLM, расходящейся с `classifier_result`.

## Триггеры на пересмотр

- Любой запуск генерации карточек в режиме `FE_BOT_TAXONOMY_MODE=llm` на реальном документе.
- Решение по судьбе `rule_based`-режима ([ADR-HTC-10, вопрос 1](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md#открытые-вопросы)).

## Owner

TBD.

## Related

- [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)
- [SETUP-13](../02-system/features/SETUP-13-classifier-library.md), [SETUP-05](../02-system/features/SETUP-05-rag-cards-generation.md)
- [TD-HTC-001](TD-HTC-001-reclassification-after-version-bump.md) — относится к legacy-таксономии SETUP-12
