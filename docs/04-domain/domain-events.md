# Доменные события

События — это факты, произошедшие в системе. Они append-only и являются источником истины для audit trail ([ANALYTICS-09](../02-system/features/ANALYTICS-09-audit-trail.md)).

## Setup-события

| Имя | Producer | Полезная нагрузка |
| --- | --- | --- |
| `SourceDocumentUploaded` | Upload Handler | `source_document_id`, `file_id`, `checksum_sha256`, `uploaded_by` |
| `SourceDocumentParsed` | Document Parser | `source_document_id`, `section_count` |
| `RAGCardGenerated` | RAG Card Generator | `doc_id`, `doc_type`, `source_section_ids`, `confidence_level` |
| `RAGCardReviewed` | Review Controller | `doc_id`, `action`, `decided_by`, `reason` |
| `RAGCardValidated` | Metadata Validator | `doc_id`, `severity`, `errors[]` |
| `RAGChunkBuilt` | Chunking Service | `chunk_id`, `doc_id`, `chunk_type` |
| `RAGChunkIndexed` | Vector DB Indexer | `chunk_id`, `index_version`, `collection` |
| `RetrievalEvalRan` | Retrieval Evaluation Runner | `index_version`, `recall@k`, `precision@k`, `passed` |
| `KnowledgeBasePublished` | Publication Controller | `kb_version`, `index_version`, `published_by` |

## Runtime-события

| Имя | Producer | Полезная нагрузка |
| --- | --- | --- |
| `SessionStarted` | SessionAgent | `conversation_id`, `kb_version`, `started_at` |
| `UserTurnReceived` | API Backend | `conversation_id`, `text` (PII-фильтрация на стороне фронта) |
| `AgentRunStarted` | Agent Runtime | `agent_run_id`, `agent_name`, `phase`, `prompt_template_version` |
| `AgentRunFinished` | Agent Runtime | `agent_run_id`, `validation_status`, `confidence`, `llm_latency_ms`, `repair_loop_count` |
| `RAGRetrievalExecuted` | RAG Retriever | `rag_query_id`, `phase`, `filters`, `retrieved_doc_ids` |
| `PhaseAdvanced` | LangGraph Orchestrator | `conversation_id`, `from_phase`, `to_phase` |
| `FeatureCandidateProposed` | FeatureSynthesisAgent | `feature_id`, `role`, `formula`, `evidence_doc_ids` |
| `FeatureValidated` | FeatureCriticAgent | `feature_id`, `decision`, `reason` |
| `FeaturesConfirmed` | Human Review Controller | `conversation_id`, `final_feature_ids` |
| `GenerationSpecEmitted` | DataGenerationSpecAgent | `conversation_id`, `spec_version`, `n_samples` |
| `DatasetGenerated` | DataGenerationWorker | `dataset_id`, `X_shape`, `y_shape`, `validation_passed` |
| `ModelRecommended` | ModelSelectionAgent | `recommendation_id`, `top1`, `model_ranking` |
| `ModelSelected` | Human action | `recommendation_id`, `selected_model`, `override_reason` |
| `ArtifactExported` | Export Service | `artifact_id`, `kind`, `conversation_id`, `checksum_sha256` |
| `ArtifactDownloaded` | Download Manager | `artifact_id`, `conversation_id`, `at` |
| `SessionRestarted` | NLUAgent (intent=restart) | `conversation_id`, `new_conversation_id` |

## Cross-cutting

| Имя | Producer | Полезная нагрузка |
| --- | --- | --- |
| `ValidationFailed` | Validation Worker | `target_id`, `validator_name`, `errors[]` |
| `RepairTriggered` | Repair Loop | `agent_run_id`, `attempt`, `max_retries` |
| `NeedMoreContextEmitted` | любой агент | `agent_run_id`, `missing_slots` |
| `KnowledgeBaseBound` | SessionAgent | `conversation_id`, `kb_version` |

## Свойства события

Каждое событие сериализуется в `AuditNode`:

```python
class AuditNode(BaseModel):
    audit_node_id: UUID
    kind: AuditKind
    entity_id: UUID
    parent_id: UUID | None
    occurred_at: datetime
    payload: dict
    payload_digest: str  # sha256 от payload
```

`parent_id` строит DAG между событиями (например, `AgentRunFinished` → `parent_id = AgentRunStarted.id`).

## Принципы

- События append-only. Корректировка — это новое событие, а не правка старого.
- События не несут крупный binary payload; ссылаются через `entity_id` на сущности.
- Сериализация — JSON с детерминированной сортировкой ключей; `payload_digest` стабилен.

## Связанные документы

- [entities.md](entities.md)
- [invariants.md](invariants.md)
- [../02-system/features/ANALYTICS-09-audit-trail.md](../02-system/features/ANALYTICS-09-audit-trail.md)
