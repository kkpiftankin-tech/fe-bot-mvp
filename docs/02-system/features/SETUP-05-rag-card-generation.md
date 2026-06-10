# SETUP-05. Генерация RAG-карточек

## Назначение

Превратить parsed-секции в типизированные RAG-карточки (`schema`, `task`, `analytics`, `feature_pattern`, `validation_rule`, `question_template`, `glossary`, `example`, `bad_example`) с полной metadata. Карточки — это единицы, которые будут извлекать Runtime-агенты.

## Бизнес-ценность

Типизированная карточка с metadata извлекаема по фильтрам `doc_type`, `phase`, `domain` и `task_type`; generic-чанк — нет. SETUP-05 — место, где обеспечивается соблюдение онтологии.

## Пользовательский сценарий

1. Мастер переходит в фазу **Card generation**.
2. Per-секция LLM-генератор (через `LLM Gateway`) черновикует одну карточку, соответствующую predicted-type секции, заполняет metadata из секции + онтологии и записывает черновик.
3. UI показывает счётчики по семейству карточек («12 schema cards, 5 feature patterns, 8 analytics cards, 7 validation rules, 4 question templates, 23 glossary terms»).
4. Каждая карточка несёт `confidence_level`; low-confidence карточки заранее помечаются `review_required` для [SETUP-06](SETUP-06-rag-card-review.md).

## Связанные требования

- BR-FR-Setup-051..054 (per-type генерация, полнота metadata, привязка к источнику, confidence scoring).
- Схема metadata карточки определена в [../../06-rag/metadata-schema.md](../../06-rag/metadata-schema.md).

## Связанные сервисы

- RAG Card Generator, LLM Gateway (Ollama, `llama3.2`), Metadata Extractor, Ontology Mapper, Artifact Storage, RAG Card Registry.

## Связанные контракты

- `RAGCardDraft` (`schemas/rag_cards.py`): полный YAML front matter карточки + тело, плюс `source_section_ids`, `source_document_ids`, `confidence_level`, `status`.

## Связанные RAG-документы

- Сгенерированные артефакты попадают в [../../../rag/cards/](../../../rag/cards/) под соответствующий подкаталог семейства.

## Критерии приёмки

- Каждая сгенерированная карточка ОБЯЗАНА иметь непустые `doc_id`, `doc_type`, `source_document_ids`, `retrieval_tags`, `confidence_level`.
- Карточки, сгенерированные из temporal-секции (например, `range_rate`), ОБЯЗАНЫ установить `requires_temporal_sequence: true`.
- Сбои генерации ОБЯЗАНЫ показывать в мастере секцию + ошибку, а не тихо терять её.
- Тесты: `tests/component/test_setup_card_generation.py`, `tests/prompt_eval/setup_card_generation_cases.yaml`.

## Вне scope

- Карточки, написанные руками (они идут прямо в [SETUP-06](SETUP-06-rag-card-review.md)).
