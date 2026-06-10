# Сущности

Объекты с identity, переживающие изменения состояния. Имя `Entity` означает: у объекта есть стабильный `id`, и две сущности с одинаковыми полями, но разными `id` — это разные сущности.

## SourceDocument

Загруженный пользователем документ. Корневой якорь любой traceability-цепочки.

- `source_document_id: UUID`
- `file_id: UUID` (Artifact)
- `original_name: str`
- `mime_type: str`
- `size_bytes: int`
- `checksum_sha256: str`
- `tags: list[str]`
- `uploaded_by: UserId`
- `uploaded_at: datetime`
- `status: SourceStatus` ∈ {`uploaded`, `parsed`, `processed`, `review_required`, `error`}
- Связи: `parsed_sections: 1..n ParsedSection`, `produced_cards: 0..n RAGCard`.

## ParsedSection

Извлечённая из исходника логическая секция.

- `section_id: UUID`
- `source_document_id: UUID`
- `parent_section_id: UUID | None`
- `heading: str`
- `raw_text: str`
- `normalized_text: str`
- `offsets: TextOffsets` (см. value-objects)
- `predicted_type: CardType`

## RAGCard

Типизированный документ знаний.

- `doc_id: str` (стабильный, уникальный)
- `version: SemVer`
- `doc_type: CardType` (см. value-objects)
- `title: str`
- `body: Markdown`
- `metadata: RAGMetadata` (см. value-objects)
- `source_document_ids: list[UUID]`
- `source_section_ids: list[UUID]`
- `confidence_level: ConfidenceLevel` ∈ {`high`, `medium`, `low`}
- `status: CardStatus` ∈ {`draft`, `review_required`, `approved`, `rejected`}
- `created_at: datetime`
- `last_validated_at: datetime`
- `last_used_at: datetime`

## RAGChunk

Извлекаемая единица, производная от карточки.

- `chunk_id: str` (стабильный)
- `doc_id: str` (родительская карточка)
- `chunk_type: ChunkType` (см. value-objects)
- `phase: Phase`
- `slot: str`
- `retrieval_purpose: list[str]`
- `embedding_text: str`
- `priority: int`
- `required_fields: list[str]`

## KnowledgeBaseVersion

Опубликованный снимок RAG-индекса.

- `kb_version: str`
- `index_version: str`
- `card_versions: dict[doc_id, version]`
- `published_at: datetime`
- `published_by: UserId`
- `previous_kb_version: str | None`
- `status: KBStatus` ∈ {`draft`, `active`, `superseded`}

## Conversation

Пользовательская сессия Runtime.

- `conversation_id: UUID`
- `kb_version: str` (привязка к моменту старта)
- `started_at: datetime`
- `current_phase: Phase`
- `state: ContextMemorySnapshot[]` (append-only история per-фаза)
- `status: ConversationStatus` ∈ {`active`, `completed`, `abandoned`, `restarted`}

## ContextMemory

Типизированное состояние диалога. Снимок персистится per-фаза.

См. контракт: [../07-contracts/context-memory.md](../07-contracts/context-memory.md).

## AgentRun

Один вызов агента.

- `agent_run_id: UUID`
- `conversation_id: UUID`
- `agent_name: str`
- `phase: Phase`
- `prompt_template_version: str`
- `llm_model: str`
- `llm_latency_ms: int`
- `confidence: float`
- `retrieved_doc_ids: list[str]`
- `validation_status: ValidationStatus`
- `repair_loop_count: int`
- `started_at: datetime`
- `finished_at: datetime`

## FeatureCandidate

Предложенный признак, ещё не валидированный.

- `feature_id: UUID`
- `name: str`
- `role: FeatureRole` (см. value-objects)
- `dtype: str`
- `description: str`
- `formula: str | None`
- `input_features: list[str]`
- `source_fields: list[str]`
- `evidence_doc_ids: list[str]`
- `risk_level: RiskLevel`

## FeatureSpec

Принятый признак с устойчивой identity внутри сессии.

Расширяет `FeatureCandidate` полями:

- `leakage_risk: RiskLevel`
- `validation_rules: list[str]`
- `status: FeatureStatus` ∈ {`approved`, `rejected`, `needs_review`}

## GenerationSpec

Спецификация синтетического датасета.

См. контракт: [../07-contracts/generation-spec.md](../07-contracts/generation-spec.md).

## GeneratedDataset

Произведённый Python-worker-ом датасет.

- `dataset_id: UUID`
- `conversation_id: UUID`
- `spec_version: str`
- `random_state: int`
- `X_artifact_id: UUID`
- `y_artifact_id: UUID`
- `metadata_artifact_id: UUID`
- `validation_report_id: UUID`
- `actual_class_distribution: dict[str, float]`
- `anomaly_mask_summary: dict`

## ModelRecommendation

Ранжированный список моделей + выбранная.

- `recommendation_id: UUID`
- `conversation_id: UUID`
- `recommended_model: str`
- `model_ranking: list[ModelRankItem]`
- `selected_model: str`
- `override_reason: str | None`
- `training_config: TrainingConfig`

## Artifact

Любой файл, произведённый системой.

- `artifact_id: UUID`
- `conversation_id: UUID | None` (None для Setup-артефактов)
- `kb_version: str | None`
- `kind: ArtifactKind`
- `bucket: str`
- `key: str`
- `size_bytes: int`
- `checksum_sha256: str`
- `created_at: datetime`
- `download_url_ttl: datetime | None`

## ExportManifest

Перечень артефактов экспорт-пакета.

См. контракт: `schemas/export_manifest.py`.

## AuditNode / AuditChain

Append-only события трассировки.

- `audit_node_id: UUID`
- `kind: AuditKind`
- `entity_id: UUID`
- `parent_id: UUID | None`
- `occurred_at: datetime`
- `payload_digest: str`

## Связанные документы

- [value-objects.md](value-objects.md)
- [domain-events.md](domain-events.md)
- [invariants.md](invariants.md)
- [../07-contracts/](../07-contracts/)
