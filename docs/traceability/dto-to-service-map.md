# DTO → SVC (карта)

Связывает 53 DTO из [docs/03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md) с конкретными сервисами SVC-01..SVC-38 из [docs/03-architecture/services/README.md](../03-architecture/services/README.md). Используется для ответа на вопрос «какие сервисы трогает изменение этого DTO».

В таблице ниже указаны **producers** (сервисы, которые создают/изменяют DTO) и **consumers** (сервисы, которые читают). Один SVC может быть и producer, и consumer одновременно.

## Платформенные DTO

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-01 UserProfileDTO | SVC-03 Auth Service, EXT-Identity Provider | SVC-01, SVC-02, SVC-15, SVC-16, SVC-36, SVC-38 |
| DTO-02 AuthTokenDTO | SVC-03 Auth Service | SVC-01, SVC-02 |
| DTO-03 PermissionDTO | SVC-03 Auth Service | SVC-01, SVC-02, SVC-15, SVC-38 |

## Сессия и диалог

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-04 UserSessionDTO | SVC-16 Session Service | SVC-01, SVC-02, SVC-17, SVC-18, SVC-35, SVC-36 |
| DTO-05 ChatMessageDTO | SVC-01 Frontend, SVC-19 Agent Runtime | SVC-02, SVC-17, SVC-18, SVC-23, SVC-35 |
| DTO-06 ContextMemoryDTO | SVC-17 ContextMemory Service | SVC-18, SVC-19, SVC-25, SVC-26, SVC-27, SVC-28, SVC-29, SVC-30, SVC-33, SVC-34, SVC-36 |

## Настройка RAG-базы

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-07 RAGSetupJobDTO | SVC-04 Setup Orchestrator | SVC-01, SVC-02, SVC-35, SVC-36, SVC-37 |
| DTO-08 UploadFileDTO | SVC-01 Frontend | SVC-02, SVC-05, SVC-38 |
| DTO-09 SourceDocumentDTO | SVC-05 Document Upload Service | SVC-06, SVC-07, SVC-09, SVC-35, SVC-36, SVC-38 |
| DTO-10 ParsedSectionDTO | SVC-07 Document Parser | SVC-06, SVC-08, SVC-09, SVC-35, SVC-36 |
| DTO-54 ParseJobDTO | SVC-07 Document Parser | SVC-01, SVC-04, SVC-36 |
| DTO-55 ParseJobDocumentDTO | SVC-07 Document Parser | SVC-01, SVC-04, SVC-36 |
| DTO-56 SectionClassificationDTO | SVC-07 Document Parser | SVC-08, SVC-09, SVC-36 |
| DTO-57 DocumentParseReportDTO | SVC-07 Document Parser | SVC-01, SVC-04, SVC-36 |
| DTO-58 ParseErrorDTO | SVC-07 Document Parser, SVC-02 API Gateway | SVC-01, SVC-04 |
| DTO-11 RAGCardDTO | SVC-09 RAG Card Generator | SVC-08, SVC-10, SVC-11, SVC-15, SVC-21, SVC-36 |
| DTO-12 RAGMetadataDTO | SVC-08 Metadata Validation Service | SVC-09, SVC-11, SVC-13, SVC-21 |
| DTO-13 RAGCardReviewDTO | SVC-10 RAG Card Review | SVC-15, SVC-36, SVC-01 |
| DTO-14 ChunkDTO | SVC-11 Chunking Service | SVC-12, SVC-13, SVC-21, SVC-35 |
| DTO-15 EmbeddingDTO | SVC-12 Embedding Service | SVC-13, SVC-21, SVC-35 |
| DTO-16 VectorIndexDTO | SVC-13 Vector Indexer | SVC-14, SVC-15, SVC-21, SVC-35 |
| DTO-17 KnowledgeBaseVersionDTO | SVC-15 KB Registry | SVC-04, SVC-18, SVC-21, SVC-35, SVC-36 |

## Retrieval и evidence

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-18 RetrievalQueryDTO | SVC-19 Agent Runtime, SVC-14 RAG Evaluation | SVC-21, SVC-35 |
| DTO-19 RetrievedChunkDTO | SVC-21 RAG Retrieval Service | SVC-22, SVC-19, SVC-35 |
| DTO-20 EvidencePackDTO | SVC-22 Evidence Pack Builder | SVC-19, SVC-20, SVC-35, SVC-36 |
| DTO-21 RetrievalEvaluationCaseDTO | SVC-14 RAG Evaluation | SVC-15, SVC-35 |
| DTO-22 RetrievalEvaluationReportDTO | SVC-14 RAG Evaluation | SVC-04, SVC-15, SVC-35, SVC-01 |

## Агенты и LLM

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-23 AgentRequestDTO | SVC-18 LangGraph Orchestrator | SVC-19, SVC-20, SVC-36 |
| DTO-24 AgentResponseDTO | SVC-19 Agent Runtime | SVC-17, SVC-18, SVC-28, SVC-35 |
| DTO-25 PromptDTO | SVC-19 Agent Runtime, SVC-20 LLM Gateway | SVC-20, SVC-35 |
| DTO-26 LLMResponseDTO | SVC-20 LLM Gateway | SVC-19, SVC-28, SVC-35 |
| DTO-27 NLUResultDTO | SVC-23 NLU Agent | SVC-17, SVC-18, SVC-35 |

## ML-задача, профиль, домен

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-28 DataProfileDTO | SVC-25 Data Profiling Agent | SVC-17, SVC-27, SVC-30, SVC-33 |
| DTO-29 DomainContextDTO | SVC-26 Domain Context Agent | SVC-17, SVC-27, SVC-33 |

## Признаки и валидация

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-30 FeatureCandidateDTO | SVC-27 Feature Synthesis Agent | SVC-17, SVC-28, SVC-01, SVC-35 |
| DTO-31 FeatureSpecDTO | SVC-28 Validation Service | SVC-17, SVC-30, SVC-34, SVC-35 |
| DTO-32 ValidationReportDTO | SVC-08, SVC-28, SVC-32, SVC-33 | SVC-01, SVC-04, SVC-34 |
| DTO-33 HumanReviewRequestDTO | SVC-29 Human Review Service | SVC-01, SVC-18, SVC-36 |
| DTO-34 HumanReviewDecisionDTO | SVC-29 Human Review Service | SVC-17, SVC-18, SVC-36 |

## Генерация данных и моделей

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-35 GenerationSpecDTO | SVC-30 DataGenerationSpecAgent | SVC-17, SVC-31, SVC-32, SVC-34 |
| DTO-36..41 (TargetSpec, TargetClass, GeneratedFeatureSpec, DistributionSpec, NoiseSpec, AnomalySpec) | SVC-30 (как часть GenerationSpec) | SVC-31, SVC-32 |
| DTO-42 DatasetArtifactDTO | SVC-31 Synthetic Data Worker | SVC-32, SVC-34, SVC-38, SVC-35, SVC-01 |
| DTO-43 ModelRecommendationDTO | SVC-33 Model Selection Agent | SVC-17, SVC-34, SVC-01, SVC-35 |
| DTO-44 ModelRankingItemDTO | SVC-33 (как часть ModelRecommendation) | SVC-01, SVC-35 |
| DTO-45 TrainingConfigDTO | SVC-33 Model Selection Agent | SVC-34, EXT-Model Registry |

## Экспорт и артефакты

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-46 ArtifactDTO | SVC-38 Artifact Storage, SVC-34 Export Service | SVC-01, SVC-02, SVC-36 |
| DTO-47 ExportManifestDTO | SVC-34 Export Service | SVC-17, SVC-38, SVC-01, SVC-36 |

## Аналитика, аудит и уведомления

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-48 AuditEventDTO | SVC-36 Audit Service + все backend-сервисы | SVC-01, SVC-35 |
| DTO-49 AnalyticsEventDTO | SVC-04, SVC-19, SVC-21, SVC-31 как producers | SVC-35, SVC-01 |
| DTO-50 NotificationDTO | SVC-37 Notification Service | SVC-01, SVC-04, SVC-31, SVC-34 |
| DTO-51 ProcessingReportDTO | SVC-04, SVC-14, SVC-31, SVC-34 | SVC-01, SVC-35 |

## Domain Analytics

| DTO | Producer SVC | Consumer SVC |
| --- | --- | --- |
| DTO-52 FeatureStoreTableDTO | SVC-35 (Domain Analytics) | SVC-09, SVC-27, SVC-34 |
| DTO-53 FeatureFieldDTO | SVC-35 (Domain Analytics) | SVC-09, SVC-27 |

## Правила

- При добавлении нового DTO — добавить строку сюда с producer и consumer.
- При добавлении нового SVC — пройтись по DTO, которые он создаёт или потребляет.
- Висячая ссылка на отсутствующий DTO или SVC — это баг.
- Внешние участники (EXT-XX) перечислены в [docs/03-architecture/services/external-actors-and-systems.md](../03-architecture/services/external-actors-and-systems.md); здесь они упоминаются именами для краткости.

## Связанные документы

- [feature-to-service-map.md](feature-to-service-map.md) — фича → SVC
- [agent-to-contract-map.md](agent-to-contract-map.md) — агент → контракт
- [coverage-matrix.md](coverage-matrix.md) — общее покрытие
- [../03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md) — DTO-каталог
- [../03-architecture/services/storage-conventions.md](../03-architecture/services/storage-conventions.md) — слои хранения
- [../03-architecture/services/README.md](../03-architecture/services/README.md) — каталог SVC
