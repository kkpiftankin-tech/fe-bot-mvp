# Качество RAG: валидация, evaluation, gates, observability

Документ задаёт **что и как мы проверяем** в RAG-слое: на этапе подготовки карточек, при индексации и в runtime. Также фиксирует acceptance criteria, при которых Knowledge Base может быть опубликована.

## Уровни проверок

```text
1. Validation       — статическая проверка карточек и chunks
2. Evaluation       — offline-проверка retrieval на golden dataset
3. Quality gates    — пороги, без которых нельзя publish KB / use evidence
4. Observability    — runtime-метрики качества и use rate
```

## 1. Validation

### 1.1. Валидация RAG-карточек

Проверяется детерминистически (`validators/rag_metadata_validator.py`):

```text
doc_id exists
doc_id unique по rag/cards/
doc_type ∈ document-types.md
source_files существуют
phase ∈ онтология
agent_targets ∈ AGENTS.md
retrieval_tags не пуст
status = approved до индексации
body_markdown не пуст
metadata следует metadata-schema.md
ontology values валидны (domain, data_source, task_type, feature_family)
```

### 1.2. Валидация chunks

```text
chunk_id уникален
doc_id существует
chunk_type ∈ закрытое множество
embedding_text не пуст
phase валиден
retrieval_purpose валиден
длина chunk в пределах (token budget)
source_section_id существует
```

### 1.3. Валидация vector index

```text
все approved chunks проиндексированы
embedding dimensions совпадают с моделью
metadata прикреплена к каждой точке
index_version создана и записана в DTO-16
коллекции доступны
retrieval smoke tests passed
```

## 2. Evaluation

### 2.1. Offline-evaluation (после индексации)

Запускается на golden dataset из `rag/eval/`. Метрики:

```text
recall@k
precision@k
MRR
nDCG
no_context_rate
wrong_domain_rate
wrong_doc_type_rate
stale_doc_rate
```

### 2.2. Golden dataset

Каждый случай — пара `(query, expected_doc_ids)`. Пример:

| Запрос | Ожидаемые документы |
| --- | --- |
| «оценка угрозы надводных контактов» | `task.surface_threat_evaluation.v1` |
| «признаки эффективности сенсора» | `analytics.sensor_analytics_T.v1` |
| «влияние погоды на радар» | `schema.external_conditions.v1`, `analytics.environment_analytics_T.v1` |
| «классификация сонарных целей» | `task.sonar_target_classification.v1` |

Хранится в `rag/eval/rag_eval_dataset.yaml`. Соответствующий DTO — [DTO-21 RetrievalEvaluationCaseDTO](../03-architecture/services/data-transfer-objects.md#dto-21-retrievalevaluationcasedto).

### 2.3. Runtime evaluation

В runtime для каждого retrieval-вызова логируется:

```text
query_text
metadata_filters
retrieved_doc_ids
retrieved_chunk_ids
agent_name
phase
evidence_doc_ids_used  (какие из retrieved попали в agent output)
agent_output_valid
user_feedback
```

Это собирается в [DTO-22 RetrievalEvaluationReportDTO](../03-architecture/services/data-transfer-objects.md#dto-22-retrievalevaluationreportdto) и [DTO-49 AnalyticsEventDTO](../03-architecture/services/data-transfer-objects.md#dto-49-analyticseventdto).

## 3. Quality gates

### 3.1. Перед публикацией Knowledge Base

`KnowledgeBaseVersion.status = ready` ⇒ можно publish. Гейты:

```text
- все required cards = approved
- metadata validation passed
- chunk validation passed
- vector indexing completed
- retrieval smoke tests passed (≥ thresholds в rag/eval/)
- нет критичных пропусков doc_type для целевого домена
- нет deprecated cards в активном индексе
```

Пороги по умолчанию:

| Метрика | Минимум |
| --- | --- |
| `recall@5` | 0.85 |
| `precision@5` | 0.7 |
| `no_context_rate` (на golden) | ≤ 0.05 |
| `wrong_doc_type_rate` | ≤ 0.05 |

Пороги могут переопределяться per-domain в `rag/eval/thresholds.yaml`.

### 3.2. Перед agent usage

Агент может использовать `EvidencePack`, только если:

```text
- evidence_pack непустой
- evidence_doc_ids присутствуют
- docs активны (status = published, не deprecated)
- metadata совпадает с current phase
- retrieval score выше threshold ИЛИ сработал fallback
```

При недостаточном evidence агент возвращает `need_more_context: true`.

### 3.3. Перед финальным выводом

Финальный признак, модель или GenerationSpec должны содержать:

```text
evidence_doc_ids
validation_status
source fields
agent name
context snapshot version
```

Это гарантирует traceability «решение → evidence → исходный документ».

## 4. Observability

### 4.1. Что логируется в runtime

```text
query_id
conversation_id
setup_job_id
agent_name
phase
knowledge_base_version
index_version
query_text
metadata_filters
top_k
retrieved_doc_ids
retrieved_chunk_ids
scores
rerank_scores
evidence_pack_id
agent_output_id
validation_status
latency_ms
```

DTO: [DTO-18 RetrievalQueryDTO](../03-architecture/services/data-transfer-objects.md#dto-18-retrievalquerydto), [DTO-19 RetrievedChunkDTO](../03-architecture/services/data-transfer-objects.md#dto-19-retrievedchunkdto), [DTO-20 EvidencePackDTO](../03-architecture/services/data-transfer-objects.md#dto-20-evidencepackdto).

### 4.2. Метрики

```text
rag_queries_total
rag_latency_ms_p50
rag_latency_ms_p95
no_context_rate
wrong_doc_type_rate
retrieval_eval_recall_at_5
retrieval_eval_precision_at_5
evidence_coverage_rate
features_without_evidence_rate
unused_docs_30d
deprecated_docs_used_total
```

Складываются в ClickHouse и доступны через Analytics Service (SVC-35).

## RAG acceptance criteria

RAG считается готовым к работе, если:

```text
1. Все исходные документы зарегистрированы.
2. Все релевантные секции извлечены.
3. Все RAG-карточки имеют metadata.
4. Все обязательные карточки approved.
5. Chunks созданы и валидны.
6. Embeddings построены.
7. Vector DB проиндексирована.
8. Retrieval smoke tests пройдены.
9. Knowledge Base опубликована.
10. Frontend показывает «Knowledge Base ready».
```

## Команды разработки

`Makefile` должен содержать:

```makefile
rag-generate:    python scripts/rag/generate_cards.py
rag-validate:    python scripts/rag/validate_cards.py
rag-chunk:       python scripts/rag/build_chunks.py
rag-embed:       python scripts/rag/build_embeddings.py
rag-index:       python scripts/rag/index_vector_db.py
rag-eval:        python scripts/rag/evaluate_retrieval.py
rag-publish:     python scripts/rag/publish_kb.py
rag-reindex:     python scripts/rag/reindex.py
```

## Test strategy

### Unit tests

```text
metadata schema validation
chunk schema validation
ontology normalization
doc_id uniqueness
```

### Component tests

```text
parser → sections
section → RAG card
RAG card → chunks
chunks → embeddings
embeddings → vector DB
```

### Retrieval tests

```text
query → expected doc
query → expected chunk
wrong domain filtering
deprecated doc exclusion
metadata filter correctness
```

### E2E Setup test

```text
upload 3 documents
  → generate cards
  → approve cards
  → chunk
  → embed
  → index
  → eval
  → publish
  → Knowledge Base ready
```

### E2E Runtime test

```text
user asks ML task
  → retrieval
  → evidence pack
  → feature synthesis
  → feature validation
  → final feature has evidence_doc_ids
```

## Связанные документы

- [rag-methodology.md](rag-methodology.md)
- [rag-lifecycle.md](rag-lifecycle.md)
- [rag-failure-modes.md](rag-failure-modes.md)
- [retrieval-policies.md](retrieval-policies.md)
- [evidence-pack.md](evidence-pack.md)
- [../10-testing/testing-strategy.md](../10-testing/testing-strategy.md)
- [../11-operations/observability.md](../11-operations/observability.md)
- [../03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md)
