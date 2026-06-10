# Жизненный цикл RAG-карточек и Knowledge Base

Документ задаёт **статусы** карточек, **версионирование** артефактов RAG (карточка / chunk / embedding / vector index / KB) и **правила governance** (кто что подтверждает, когда карточка deprecated).

## Статусы карточки

Каждая RAG-карточка проходит через закрытый набор статусов:

```text
draft
  → generated
  → metadata_validated
  → review_required
  → approved
  → chunked
  → embedded
  → indexed
  → published
  → deprecated
```

### Значения

| Статус | Смысл |
| --- | --- |
| `draft` | Карточка создана, но не проверена |
| `generated` | Карточка сгенерирована автоматически (RAG Card Generator) |
| `metadata_validated` | Metadata прошла `validators/rag_metadata_validator.py` |
| `review_required` | Нужно экспертное подтверждение (HITL) |
| `approved` | Карточка подтверждена |
| `chunked` | Созданы chunks |
| `embedded` | Созданы embeddings |
| `indexed` | Chunks добавлены в vector DB |
| `published` | Карточка входит в активную Knowledge Base |
| `deprecated` | Карточка устарела и не используется в retrieval |

### Переходы

Допустимы только переходы вперёд по цепочке. Возврат назад возможен только в двух случаях:

1. **review_required → draft** — пользователь отклонил карточку и хочет регенерации.
2. **approved/indexed → review_required** — экспертная переоценка после изменения онтологии или появления новых данных.

`deprecated` — терминальный статус. Из него можно только породить **новую версию** карточки (см. ниже).

## Версионирование

Версионируется каждый артефакт пайплайна:

```text
source_document.v1
  → parsed_section.v1
  → rag_card.v1
  → chunk_manifest.v1
  → embeddings.v1
  → vector_index.v1
  → knowledge_base.v1
```

### Правила

- Все ID — SemVer-подобные (`v1.0`, `v1.1`, `v2.0`).
- Версия `doc_id` указывается в имени файла карточки: `feature_pattern.signal_quality.v1.md`.
- При смене **любого** из следующих компонентов требуется reindex и новая `index_version`:
  - текст карточки;
  - chunking policy;
  - embedding model;
  - metadata schema;
  - онтология.
- Активная `KnowledgeBaseVersion` (см. [DTO-17](../03-architecture/services/data-transfer-objects.md#dto-17-knowledgebaseversiondto)) **иммутабельна**: правки идут через новую версию.
- Runtime использует только `KnowledgeBaseVersion.status = active` (одновременно активна одна версия на проект).

### Связь версий

```text
source_document.v1 → parsed_section.v1 → rag_card.v1 → chunk_manifest.v1 →
  embeddings.v1 → vector_index.v1 → knowledge_base.v1 (active)
```

При появлении `rag_card.v2` цепочка строится заново начиная с `chunk_manifest`.

## Governance

### Роли владельцев

| Роль | Зона ответственности |
| --- | --- |
| RAG Admin | Жизненный цикл карточек, публикация KB, deprecation |
| Domain Expert | Доменная корректность `analytics_card`, `task_card`, критичные факторы |
| ML Engineer | Корректность формул `feature_pattern_card`, `validation_rule_card` |
| System Analyst | `schema_card`, `field_definition_card`, источники данных |
| Product Owner | `question_template_card`, бизнес-формулировки |

### Review policy

Кто подтверждает карточку перед `approved`:

| Тип карточки | Кто подтверждает |
| --- | --- |
| `schema_card` | System Analyst / Data Engineer |
| `task_card` | System Analyst / Domain Expert |
| `analytics_card` | Domain Expert / ML Engineer |
| `validation_rule_card` | ML Engineer / Architect |
| `model_recommendation_card` | Data Scientist |
| `question_template_card` | Product Owner / Analyst |
| `field_definition_card` | System Analyst |
| `feature_pattern_card` | ML Engineer |
| `ontology_card` | RAG Admin + Domain Expert |
| `glossary_term`, `example_card`, `bad_example_card` | RAG Admin |

Полная цепочка HITL — в [evidence-pack.md](evidence-pack.md) и [RUNTIME-08 feature-review](../02-system/features/RUNTIME-08-feature-review.md).

## Deprecation policy

Карточка переводится в `deprecated`, если:

- источник устарел (новая версия исходного документа);
- появилась новая версия карточки (`vN+1`), и пользователь промоутил её в `published`;
- карточка даёт плохой retrieval (см. метрики в [rag-quality.md](rag-quality.md));
- эксперт отклонил содержание;
- изменилась онтология ([ontology.md](ontology.md));
- изменилась схема данных, и карточка ссылается на удалённые поля.

Deprecated-карточки **не попадают** в активный vector index и не используются в retrieval. Они остаются в `rag/cards/` для аудита.

## Что должно версионироваться

```text
source document
parsed section
RAG card
chunk
embedding
vector index
knowledge base
retrieval policy
ontology
prompt template
```

Каждое изменение фиксируется в audit-трейле ([DTO-48 AuditEventDTO](../03-architecture/services/data-transfer-objects.md#dto-48-auditeventdto)).

## Связанные документы

- [rag-methodology.md](rag-methodology.md)
- [document-types.md](document-types.md)
- [metadata-schema.md](metadata-schema.md)
- [ingestion-pipeline.md](ingestion-pipeline.md)
- [rag-quality.md](rag-quality.md)
- [../03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md)
