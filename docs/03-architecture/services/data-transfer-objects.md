# Каталог DTO

Авторитетный реестр Data Transfer Objects системы. DTO здесь — это **контракт информационного обмена** между frontend, backend-сервисами, агентами, RAG-пайплайном, хранилищами, аналитикой и внешними участниками. DTO — это **формат обмена**, а не **формат хранения**: в БД содержимое может лежать в другом виде (JSONB, отдельные таблицы, столбцы).

Имя DTO стабильно; конкретная Pydantic-реализация лежит в [`schemas/`](../../../schemas/) (детальные контракты в [docs/07-contracts/](../../07-contracts/)).

Каталог покрывает три режима работы системы:

1. **Setup** — пользователь загружает документы, система формирует RAG-карточки, chunks, embeddings, vector index и публикует Knowledge Base.
2. **Runtime** — пользователь проходит диалоговый ML-workflow: Discovery, Data Profiling, Domain Context, Feature Synthesis, Data Generation, Model Selection, Export.
3. **Analytics** — система собирает метрики качества RAG, агентов, признаков, synthetic data, моделей и пользовательских сценариев.

Хранилища, упоминаемые в полях «Основное хранилище», описаны в [storage-conventions.md](storage-conventions.md).

## Структура каталога

| Раздел | DTO | Назначение |
| --- | --- | --- |
| [§1 Платформенные DTO](#1-платформенные-dto) | DTO-01..03 | Пользователь, токены, права |
| [§2 DTO сессии и диалога](#2-dto-сессии-и-диалога) | DTO-04..06 | UserSession, ChatMessage, ContextMemory |
| [§3 DTO настройки RAG-базы](#3-dto-настройки-rag-базы) | DTO-07..17 | Setup job, документы, секции, карточки, chunks, индекс, KB version |
| [§4 DTO retrieval и evidence](#4-dto-retrieval-и-evidence) | DTO-18..22 | Запросы, найденные chunks, EvidencePack, evaluation |
| [§5 DTO агентов и LLM](#5-dto-агентов-и-llm) | DTO-23..27 | AgentRequest/Response, Prompt, LLMResponse, NLU |
| [§6 DTO ML-задачи, профиля и домена](#6-dto-ml-задачи-профиля-и-домена) | DTO-28..29 | DataProfile, DomainContext |
| [§7 DTO признаков и валидации](#7-dto-признаков-и-валидации) | DTO-30..34 | FeatureCandidate, FeatureSpec, ValidationReport, HumanReview |
| [§8 DTO генерации данных и моделей](#8-dto-генерации-данных-и-моделей) | DTO-35..45 | GenerationSpec и под-DTO, DatasetArtifact, ModelRecommendation, TrainingConfig |
| [§9 DTO экспорта и артефактов](#9-dto-экспорта-и-артефактов) | DTO-46..47 | Artifact, ExportManifest |
| [§10 DTO аналитики, аудита и уведомлений](#10-dto-аналитики-аудита-и-уведомлений) | DTO-48..51 | AuditEvent, AnalyticsEvent, Notification, ProcessingReport |
| [§11 Domain Analytics DTO](#11-domain-analytics-dto) | DTO-52..53 | FeatureStoreTable, FeatureField |
| [§12 Сводная карта DTO → хранилище → сервисы](#12-сводная-карта-dto--хранилище--сервисы) | — | Сжатая матрица |
| [§13 Минимальный DTO-набор для MVP](#13-минимальный-dto-набор-для-mvp) | 26 DTO | Подмножество, покрывающее полный путь пользователя |

## Принципы

- DTO — **формат обмена**, не **формат хранения**. То же содержимое в БД может лежать в JSONB, отдельных таблицах или вектор-индексе.
- Версионирование DTO привязано к версии соответствующей Pydantic-схемы. Breaking changes требуют ADR в [docs/03-architecture/adr/](../adr/).
- Имена DTO в этом каталоге и в коде должны совпадать.
- Каждое поле «Основное хранилище» — рекомендуемое **основное** хранилище. Дополнительные хранилища (cache, поток, аналитика) перечислены отдельно.
- Любой DTO, переносящий персональные данные или секреты, должен идти через `Auth Service` и фиксироваться в audit-трейле.

---

## §1. Платформенные DTO

### DTO-01. UserProfileDTO

- **Назначение.** Описывает пользователя системы, его роль и базовые настройки доступа. Используется для авторизации действий в Setup, Runtime, Analytics и Export.
- **Основное хранилище.** PostgreSQL. Кеш — Redis. Источник истины может быть внешним: Identity Provider (EXT-Identity).
- **Использующие сервисы.** Auth Service (SVC-03), API Gateway (SVC-02), Frontend UI (SVC-01), Session Service (SVC-16), Audit Service (SVC-36), Artifact Storage Service (SVC-38), Knowledge Base Registry (SVC-15).
- **Ключевые поля.** `user_id`, `external_subject_id`, `display_name`, `email`, `roles[]`, `permissions[]`, `organization_id`, `created_at`, `last_login_at`, `status`.

### DTO-02. AuthTokenDTO

- **Назначение.** Передача данных авторизационного токена между frontend, API Gateway и Auth Service.
- **Основное хранилище.** Обычно не хранится. Для blacklist/refresh-state — Redis.
- **Использующие сервисы.** Frontend UI (SVC-01), API Gateway (SVC-02), Auth Service (SVC-03).
- **Ключевые поля.** `access_token`, `refresh_token`, `token_type`, `expires_at`, `issued_at`, `issuer`, `scopes[]`.

### DTO-03. PermissionDTO

- **Назначение.** Решение авторизации: может ли пользователь выполнить конкретное действие над конкретным ресурсом.
- **Основное хранилище.** PostgreSQL для политик. Решения кешируются в Redis.
- **Использующие сервисы.** Auth Service (SVC-03), API Gateway (SVC-02), Artifact Storage Service (SVC-38), Knowledge Base Registry (SVC-15), Frontend UI (SVC-01).
- **Ключевые поля.** `user_id`, `resource_type`, `resource_id`, `action`, `allowed`, `reason`, `evaluated_at`.

---

## §2. DTO сессии и диалога

### DTO-04. UserSessionDTO

- **Назначение.** Пользовательская сессия: setup-job, runtime-проект или analytics-просмотр.
- **Основное хранилище.** PostgreSQL. Кеш текущего состояния — Redis. События сессии — ClickHouse.
- **Использующие сервисы.** Session Service (SVC-16), API Gateway (SVC-02), Frontend UI (SVC-01), LangGraph Orchestrator (SVC-18), ContextMemory Service (SVC-17), Audit Service (SVC-36), Analytics Service (SVC-35).
- **Ключевые поля.** `session_id`, `conversation_id`, `setup_job_id`, `user_id`, `mode` (`setup`/`runtime`/`analytics`), `current_phase`, `active_kb_version`, `status`, `created_at`, `updated_at`, `completed_at`, `metadata`.

### DTO-05. ChatMessageDTO

- **Назначение.** Сообщение пользователя/системы в runtime-чате.
- **Основное хранилище.** PostgreSQL. Для аналитики — ClickHouse. Для streaming — опционально Kafka.
- **Использующие сервисы.** Frontend UI (SVC-01), API Gateway (SVC-02), LangGraph Orchestrator (SVC-18), Agent Runtime (SVC-19), NLU Agent (SVC-23), Conversation DB (внутри SVC-17), Analytics Service (SVC-35).
- **Ключевые поля.** `message_id`, `conversation_id`, `role` (`user`/`assistant`/`system`/`agent`/`tool`), `text`, `attachments[]`, `phase`, `agent_name`, `created_at`, `metadata`, `is_visible_to_user`.

### DTO-06. ContextMemoryDTO

- **Назначение.** Центральное структурированное состояние ML-проекта. Главный DTO runtime-контура: typed state, который читают и обновляют агенты. Полный контракт см. в [context-memory.md](../../07-contracts/context-memory.md).
- **Основное хранилище.** PostgreSQL. Активный slice — Redis. История изменений — ClickHouse или audit-таблица PostgreSQL.
- **Использующие сервисы.** ContextMemory Service (SVC-17), LangGraph Orchestrator (SVC-18), Agent Runtime (SVC-19), Data Profiling Agent (SVC-25), Feature Synthesis Agent (SVC-27), Data Generation Spec Agent (SVC-30), Model Selection Agent (SVC-33), Export Service (SVC-34), Audit Service (SVC-36).
- **Ключевые группы полей.**
  - **Идентификация:** `conversation_id`, `version`, `current_phase`.
  - **ML-задача:** `task_type`, `target_variable`, `required_latency`, `deployment_context`.
  - **Данные:** `data_source`, `data_type`, `data_volume`, `update_frequency`, `fields[]`, `missing_data_strategy`, `class_distribution`.
  - **Домен:** `domain`, `critical_factors[]`, `interpretability_requirement`, `temporal_importance`.
  - **Признаки:** `base_features[]`, `derived_features[]`, `interaction_features[]`, `final_features[]` (все — `FeatureSpecDTO`).
  - **Генерация:** `n_samples`, `class_imbalance_ratio`, `noise_level`, `anomaly_rate`, `generation_spec_id`, `dataset_artifact_id`.
  - **Модель:** `recommended_model`, `model_ranking[]`, `training_config_id`.
  - **Экспорт:** `artifact_package_id`.
  - **Обратная связь:** `user_feedback[]`, `created_at`, `updated_at`.

---

## §3. DTO настройки RAG-базы

### DTO-07. RAGSetupJobDTO

- **Назначение.** Job настройки RAG-базы: от загрузки документов до `Knowledge Base ready`.
- **Основное хранилище.** PostgreSQL. Прогресс — Redis. События — Kafka и ClickHouse.
- **Использующие сервисы.** Setup Orchestrator (SVC-04), Frontend UI (SVC-01), API Gateway (SVC-02), Notification Service (SVC-37), Analytics Service (SVC-35), Audit Service (SVC-36).
- **Ключевые поля.** `setup_job_id`, `user_id`, `project_name`, `status` (`draft`/`running`/`review_required`/`ready`/`failed`/`cancelled`), `current_step`, `progress_percent`, `source_document_ids[]`, `knowledge_base_version`, `error_count`, `warning_count`, `started_at`, `finished_at`, `metadata`.

### DTO-08. UploadFileDTO

- **Назначение.** Передача файла от frontend к backend во время загрузки. Сам DTO транзитен; бинарный поток уходит в Object Storage, метаданные — в `SourceDocumentDTO`.
- **Основное хранилище.** Не хранится. Бинарный файл — Object Storage; metadata — PostgreSQL.
- **Использующие сервисы.** Frontend UI (SVC-01), API Gateway (SVC-02), Document Upload Service (SVC-05), Artifact Storage Service (SVC-38).
- **Ключевые поля.** `file_name`, `content_type`, `size_bytes`, `binary_stream`, `user_tags[]`, `description`, `uploaded_by`, `setup_job_id`.

### DTO-09. SourceDocumentDTO

- **Назначение.** Исходный документ, загруженный пользователем.
- **Основное хранилище.** Metadata — PostgreSQL; файл — Object Storage; события статуса — ClickHouse.
- **Использующие сервисы.** Document Upload Service (SVC-05), Source Registry Service (SVC-06), Document Parser Service (SVC-07), RAG Card Generator (SVC-09), Audit Service (SVC-36), Analytics Service (SVC-35).
- **Ключевые поля.** `source_document_id`, `setup_job_id`, `filename`, `content_type`, `storage_path`, `size_bytes`, `checksum`, `status`, `detected_language`, `document_kind`, `uploaded_by`, `uploaded_at`, `parsed_at`, `error_message`, `metadata`.

### DTO-10. ParsedSectionDTO

- **Назначение.** Смысловая секция исходного документа после парсинга.
- **Основное хранилище.** PostgreSQL; крупные тексты — Object Storage.
- **Использующие сервисы.** Document Parser Service (SVC-07), Source Registry Service (SVC-06), RAG Card Generator (SVC-09), Analytics Service (SVC-35), Audit Service (SVC-36).
- **Ключевые поля.** `section_id`, `source_document_id`, `setup_job_id`, `title`, `section_path[]`, `section_type`, `raw_text`, `normalized_text`, `start_offset`, `end_offset`, `confidence`, `created_at`, `metadata`.

### DTO-11. RAGCardDTO

- **Назначение.** RAG-документ, который использует система для извлечения контекста.
- **Основное хранилище.** Metadata — PostgreSQL; markdown — Object Storage или docs-as-code Git-репозиторий; события использования — ClickHouse.
- **Использующие сервисы.** RAG Card Generator (SVC-09), RAG Card Review Service (SVC-10), Metadata Validation Service (SVC-08), Chunking Service (SVC-11), Knowledge Base Registry (SVC-15), RAG Retrieval Service (SVC-21), Audit Service (SVC-36).
- **Ключевые поля.** `doc_id`, `doc_type` (`schema_card`/`task_card`/`analytics_card`/`validation_rule_card`), `title`, `version`, `status`, `front_matter`, `body_markdown`, `source_document_ids[]`, `source_section_ids[]`, `confidence_level`, `created_by`, `reviewed_by`, `created_at`, `updated_at`, `published_at`.

### DTO-12. RAGMetadataDTO

- **Назначение.** Унифицированная metadata RAG-карточек и chunks. Полный контракт — [docs/06-rag/metadata-schema.md](../../06-rag/metadata-schema.md).
- **Основное хранилище.** PostgreSQL. Публикуется в Vector DB как metadata каждого chunk.
- **Использующие сервисы.** Ontology and Metadata Service (SVC-08), Metadata Validation Service (SVC-08), RAG Retrieval Service (SVC-21), Chunking Service (SVC-11), Vector Indexer Service (SVC-13).
- **Ключевые поля.** `doc_id`, `doc_type`, `domain[]`, `task_type[]`, `data_source[]`, `entity_type[]`, `phase[]`, `agent_targets[]`, `required_input_fields[]`, `output_fields[]`, `feature_tables[]`, `retrieval_tags[]`, `validation_rules[]`, `confidence_level`, `owner`, `last_verified_at`.

### DTO-13. RAGCardReviewDTO

- **Назначение.** Решение пользователя/эксперта по RAG-карточке (HITL-ревью).
- **Основное хранилище.** PostgreSQL. Audit events — ClickHouse и/или Kafka.
- **Использующие сервисы.** RAG Card Review Service (SVC-10), Audit Service (SVC-36), Knowledge Base Registry (SVC-15), Frontend UI (SVC-01).
- **Ключевые поля.** `review_id`, `doc_id`, `reviewer_id`, `decision` (`approve`/`reject`/`request_regeneration`/`edit`), `comment`, `changed_fields[]`, `before_version`, `after_version`, `created_at`.

### DTO-14. ChunkDTO

- **Назначение.** Логический chunk RAG-документа для индексации в Vector DB.
- **Основное хранилище.** Metadata — PostgreSQL; текст и embedding metadata — Vector DB; manifest — Object Storage.
- **Использующие сервисы.** Chunking Service (SVC-11), Embedding Service (SVC-12), Vector Indexer Service (SVC-13), RAG Retrieval Service (SVC-21), Analytics Service (SVC-35).
- **Ключевые поля.** `chunk_id`, `doc_id`, `chunk_type` (`summary`/`definition`/`formula`/`validation`/`example`/`agent_usage`), `section_title`, `chunk_text`, `embedding_text`, `metadata`, `priority`, `source_section_id`, `token_count`, `created_at`, `status`.

### DTO-15. EmbeddingDTO

- **Назначение.** Embedding-вектор для chunk.
- **Основное хранилище.** Vector DB. Metadata о построении — PostgreSQL; ошибки/метрики — ClickHouse.
- **Использующие сервисы.** Embedding Service (SVC-12), Vector Indexer Service (SVC-13), RAG Retrieval Service (SVC-21), Analytics Service (SVC-35).
- **Ключевые поля.** `embedding_id`, `chunk_id`, `doc_id`, `embedding_vector[]`, `embedding_model`, `dimension`, `index_version`, `created_at`, `status`, `error_message`.

### DTO-16. VectorIndexDTO

- **Назначение.** Версия векторного индекса Knowledge Base.
- **Основное хранилище.** PostgreSQL. Сам индекс — Vector DB. Статистика — ClickHouse.
- **Использующие сервисы.** Vector Indexer Service (SVC-13), Knowledge Base Registry (SVC-15), RAG Retrieval Service (SVC-21), Retrieval Evaluation Service (SVC-14), Analytics Service (SVC-35).
- **Ключевые поля.** `index_version`, `knowledge_base_version`, `collection_names[]`, `embedding_model`, `chunks_count`, `indexed_chunks_count`, `failed_chunks_count`, `status`, `created_at`, `published_at`, `metadata`.

### DTO-17. KnowledgeBaseVersionDTO

- **Назначение.** Опубликованная/готовящаяся версия базы знаний.
- **Основное хранилище.** PostgreSQL. Активная версия кешируется в Redis.
- **Использующие сервисы.** Knowledge Base Registry (SVC-15), Setup Orchestrator (SVC-04), RAG Retrieval Service (SVC-21), LangGraph Orchestrator (SVC-18), Analytics Service (SVC-35), Audit Service (SVC-36).
- **Ключевые поля.** `knowledge_base_version`, `setup_job_id`, `status` (`draft`/`testing`/`ready`/`active`/`deprecated`/`failed`), `rag_card_count`, `chunk_count`, `index_version`, `retrieval_test_report_id`, `published_by`, `published_at`, `is_active`, `metadata`.

---

## §4. DTO retrieval и evidence

### DTO-18. RetrievalQueryDTO

- **Назначение.** Запрос к RAG Retrieval Service.
- **Основное хранилище.** Логируется как событие в ClickHouse; может публиковаться в Kafka.
- **Использующие сервисы.** RAG Retrieval Service (SVC-21), Agent Runtime (SVC-19), Retrieval Evaluation Service (SVC-14), Analytics Service (SVC-35).
- **Ключевые поля.** `query_id`, `conversation_id`, `setup_job_id`, `agent_name`, `phase`, `query_text`, `metadata_filters`, `top_k`, `rerank_policy`, `knowledge_base_version`, `created_at`.

### DTO-19. RetrievedChunkDTO

- **Назначение.** Chunk, найденный RAG Retrieval Service.
- **Основное хранилище.** События retrieval — ClickHouse; оригинальные chunks — Vector DB и PostgreSQL metadata.
- **Использующие сервисы.** RAG Retrieval Service (SVC-21), Evidence Pack Builder (SVC-22), Agent Runtime (SVC-19), Analytics Service (SVC-35).
- **Ключевые поля.** `query_id`, `chunk_id`, `doc_id`, `score`, `rank`, `chunk_text`, `chunk_type`, `metadata`, `retrieval_reason`, `created_at`.

### DTO-20. EvidencePackDTO

- **Назначение.** Компактный RAG-контекст, передаваемый агенту. Полный контракт — [docs/06-rag/evidence-pack.md](../../06-rag/evidence-pack.md).
- **Основное хранилище.** PostgreSQL как часть agent trace; аналитика — ClickHouse; runtime cache — Redis.
- **Использующие сервисы.** Evidence Pack Builder (SVC-22), Agent Runtime (SVC-19), LLM Gateway (SVC-20), Audit Service (SVC-36), Analytics Service (SVC-35).
- **Ключевые поля.** `evidence_pack_id`, `conversation_id`, `agent_name`, `phase`, `query_ids[]`, `retrieved_chunks[]` (`RetrievedChunkDTO`), `evidence_doc_ids[]`, `summary`, `constraints[]`, `normalization_dictionary`, `validation_rules[]`, `created_at`.

### DTO-21. RetrievalEvaluationCaseDTO

- **Назначение.** Контрольный test-case для проверки качества RAG.
- **Основное хранилище.** PostgreSQL. Может храниться как файл в Object Storage/Git.
- **Использующие сервисы.** Retrieval Evaluation Service (SVC-14), RAG Analytics Service (SVC-35), Knowledge Base Registry (SVC-15).
- **Ключевые поля.** `case_id`, `query_text`, `expected_doc_ids[]`, `expected_chunk_ids[]`, `metadata_filters`, `domain`, `difficulty`, `created_by`, `created_at`.

### DTO-22. RetrievalEvaluationReportDTO

- **Назначение.** Результат проверки качества RAG retrieval.
- **Основное хранилище.** PostgreSQL. Метрики — ClickHouse. Отчёт — Object Storage.
- **Использующие сервисы.** Retrieval Evaluation Service (SVC-14), Setup Orchestrator (SVC-04), Knowledge Base Registry (SVC-15), Analytics Service (SVC-35), Frontend UI (SVC-01).
- **Ключевые поля.** `report_id`, `knowledge_base_version`, `index_version`, `cases_total`, `cases_passed`, `recall_at_5`, `precision_at_5`, `failed_cases[]`, `status`, `created_at`.

---

## §5. DTO агентов и LLM

### DTO-23. AgentRequestDTO

- **Назначение.** Унифицированный запрос на вызов агента.
- **Основное хранилище.** Логируется в ClickHouse как agent event; может сохраняться в PostgreSQL для audit trace.
- **Использующие сервисы.** LangGraph Orchestrator (SVC-18), Agent Runtime (SVC-19), LLM Gateway (SVC-20), Audit Service (SVC-36).
- **Ключевые поля.** `request_id`, `conversation_id`, `agent_name`, `phase`, `user_message`, `context_memory` (`ContextMemoryDTO`), `evidence_pack` (`EvidencePackDTO`), `output_schema_name`, `prompt_template_version`, `created_at`.

### DTO-24. AgentResponseDTO

- **Назначение.** Унифицированный ответ агента.
- **Основное хранилище.** PostgreSQL (agent trace). Метрики — ClickHouse. Событие — Kafka опционально.
- **Использующие сервисы.** Agent Runtime (SVC-19), LangGraph Orchestrator (SVC-18), Validation Service (SVC-28), ContextMemory Service (SVC-17), Analytics Service (SVC-35).
- **Ключевые поля.** `response_id`, `request_id`, `conversation_id`, `agent_name`, `structured_output`, `confidence`, `need_more_context`, `missing_slots[]`, `validation_status` (`valid`/`invalid`/`repair_required`), `errors[]`, `latency_ms`, `created_at`.

### DTO-25. PromptDTO

- **Назначение.** Prompt, отправляемый в LLM.
- **Основное хранилище.** Шаблоны — Object Storage/Git/PostgreSQL. Metadata вызовов — ClickHouse. По соображениям безопасности `user_prompt` обычно хранится частично.
- **Использующие сервисы.** LLM Gateway (SVC-20), Agent Runtime (SVC-19), Prompt Evaluation Service (внутри SVC-35), Analytics Service (SVC-35).
- **Ключевые поля.** `prompt_id`, `template_name`, `template_version`, `system_prompt`, `user_prompt`, `schema`, `model_name`, `parameters`, `created_at`.

### DTO-26. LLMResponseDTO

- **Назначение.** Ответ LLM до и после парсинга.
- **Основное хранилище.** Metadata — ClickHouse. Raw response — PostgreSQL или не хранится по политике безопасности.
- **Использующие сервисы.** LLM Gateway (SVC-20), Validation Service (SVC-28), Agent Runtime (SVC-19), Analytics Service (SVC-35).
- **Ключевые поля.** `llm_response_id`, `prompt_id`, `model_name`, `raw_text`, `parsed_json`, `finish_reason`, `input_tokens`, `output_tokens`, `latency_ms`, `validation_status`, `created_at`.

### DTO-27. NLUResultDTO

- **Назначение.** Результат NLU Agent: intent, entities, confidence.
- **Основное хранилище.** PostgreSQL как часть agent output. Метрики intent accuracy — ClickHouse.
- **Использующие сервисы.** NLU Agent (SVC-23), LangGraph Orchestrator (SVC-18), ContextMemory Service (SVC-17), Analytics Service (SVC-35).
- **Ключевые поля.** `nlu_result_id`, `conversation_id`, `intent`, `intent_confidence`, `entities`, `entity_confidences`, `missing_slots[]`, `normalized_terms`, `created_at`.

---

## §6. DTO ML-задачи, профиля и домена

### DTO-28. DataProfileDTO

- **Назначение.** Профиль данных, собранный на этапе Data Profiling.
- **Основное хранилище.** PostgreSQL внутри ContextMemory. Аналитика профилей — ClickHouse.
- **Использующие сервисы.** Data Profiling Agent (SVC-25), ContextMemory Service (SVC-17), Feature Synthesis Agent (SVC-27), Data Generation Spec Agent (SVC-30), Model Selection Agent (SVC-33).
- **Ключевые поля.** `data_profile_id`, `conversation_id`, `data_source`, `data_type`, `data_volume`, `update_frequency`, `fields[]`, `field_types`, `missing_data_strategy`, `class_distribution`, `temporal_importance`, `has_timestamp`, `entity_id_field`, `validation_status`.

### DTO-29. DomainContextDTO

- **Назначение.** Предметный контекст задачи.
- **Основное хранилище.** PostgreSQL внутри ContextMemory. События/аналитика — ClickHouse.
- **Использующие сервисы.** Domain Context Agent (SVC-26), Feature Synthesis Agent (SVC-27), Model Selection Agent (SVC-33), ContextMemory Service (SVC-17).
- **Ключевые поля.** `domain_context_id`, `conversation_id`, `domain`, `critical_factors[]`, `interpretability_requirement`, `allowed_feature_families[]`, `forbidden_feature_families[]`, `domain_constraints[]`, `evidence_doc_ids[]`, `created_at`.

---

## §7. DTO признаков и валидации

### DTO-30. FeatureCandidateDTO

- **Назначение.** Признак-кандидат, предложенный Feature Synthesis Agent.
- **Основное хранилище.** PostgreSQL. Метрики генерации — ClickHouse.
- **Использующие сервисы.** Feature Synthesis Agent (SVC-27), Feature Validation Service (SVC-28), Frontend Feature Review UI (SVC-01), ContextMemory Service (SVC-17), Analytics Service (SVC-35).
- **Ключевые поля.** `feature_candidate_id`, `conversation_id`, `name`, `role` (`base`/`derived`/`interaction`/`temporal`/`statistical`), `description`, `formula`, `input_fields[]`, `dtype`, `unit`, `feature_family`, `evidence_doc_ids[]`, `risk_level`, `confidence`, `status`.

### DTO-31. FeatureSpecDTO

- **Назначение.** Финальное/валидированное описание признака. Полный контракт — [feature-spec.md](../../07-contracts/feature-spec.md).
- **Основное хранилище.** PostgreSQL. Опционально публикуется в Feature Store. Аналитика — ClickHouse.
- **Использующие сервисы.** Feature Validation Service (SVC-28), ContextMemory Service (SVC-17), Data Generation Spec Agent (SVC-30), Export Service (SVC-34), Feature Store Service (внутри SVC-35).
- **Ключевые поля.** `feature_id`, `conversation_id`, `name`, `role`, `description`, `formula`, `source_fields[]`, `dtype`, `unit`, `null_policy`, `validation_rules[]`, `evidence_doc_ids[]`, `status`, `created_at`, `approved_by`.

### DTO-32. ValidationReportDTO

- **Назначение.** Универсальный отчёт проверки: metadata, features, GenerationSpec, dataset, training config. Полный контракт — [validation-report.md](../../07-contracts/validation-report.md).
- **Основное хранилище.** PostgreSQL. Метрики проверок — ClickHouse. Файловый отчёт — Object Storage.
- **Использующие сервисы.** Metadata Validation Service (SVC-08), Feature Validation Service (SVC-28), Dataset Validation Service (SVC-32), Model Config Validation Service (внутри SVC-33), Export Service (SVC-34), Frontend UI (SVC-01).
- **Ключевые поля.** `validation_report_id`, `target_type` (`rag_card`/`feature`/`dataset`/`generation_spec`), `target_id`, `status`, `checks[]`, `errors[]`, `warnings[]`, `repair_instruction`, `created_at`, `validator_name`.

### DTO-33. HumanReviewRequestDTO

- **Назначение.** Запрос на пользовательское/экспертное подтверждение.
- **Основное хранилище.** PostgreSQL. События — Kafka и ClickHouse.
- **Использующие сервисы.** Human Review Service (SVC-29), Frontend UI (SVC-01), LangGraph Orchestrator (SVC-18), Audit Service (SVC-36).
- **Ключевые поля.** `review_request_id`, `conversation_id`, `review_type` (`feature_review`/`rag_card_review`/`model_review`/`export_review`), `target_id`, `target_payload`, `reason`, `status`, `created_at`, `expires_at`.

### DTO-34. HumanReviewDecisionDTO

- **Назначение.** Решение пользователя по review-запросу.
- **Основное хранилище.** PostgreSQL. Audit — ClickHouse.
- **Использующие сервисы.** Human Review Service (SVC-29), ContextMemory Service (SVC-17), LangGraph Orchestrator (SVC-18), Audit Service (SVC-36).
- **Ключевые поля.** `decision_id`, `review_request_id`, `conversation_id`, `reviewer_id`, `decision` (`approve`/`reject`/`edit`/`request_changes`), `comment`, `updated_payload`, `created_at`.

---

## §8. DTO генерации данных и моделей

### DTO-35. GenerationSpecDTO

- **Назначение.** Спецификация генерации синтетической обучающей выборки. Маленькая LLM формирует именно этот DTO, а не строки данных. Полный контракт — [generation-spec.md](../../07-contracts/generation-spec.md).
- **Основное хранилище.** PostgreSQL. Файл спецификации — Object Storage. Метрики — ClickHouse.
- **Использующие сервисы.** Data Generation Spec Agent (SVC-30), Synthetic Data Generation Worker (SVC-31), Dataset Validation Service (SVC-32), Export Service (SVC-34), ContextMemory Service (SVC-17).
- **Ключевые поля.** `generation_spec_id`, `conversation_id`, `spec_version`, `generation_mode` (`tabular_classification`/`sequence_forecasting`/`radar_tensor_detection`), `n_samples`, `random_state`, `target` (`TargetSpecDTO`), `feature_specs[]` (`GeneratedFeatureSpecDTO`), `noise` (`NoiseSpecDTO`), `anomalies` (`AnomalySpecDTO`), `validation_expectations`, `created_at`, `status`.

### DTO-36. TargetSpecDTO

- **Назначение.** Целевая переменная в GenerationSpec.
- **Основное хранилище.** В составе `GenerationSpecDTO` (PostgreSQL/Object Storage).
- **Использующие сервисы.** Data Generation Spec Agent (SVC-30), Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32), Model Selection Agent (SVC-33).
- **Ключевые поля.** `name`, `type` (`binary`/`multiclass`/`regression`), `classes[]` (`TargetClassDTO`), `label_noise_rate`, `generation_logic`.

### DTO-37. TargetClassDTO

- **Назначение.** Один класс целевой переменной.
- **Основное хранилище.** В составе `GenerationSpecDTO`.
- **Использующие сервисы.** Data Generation Spec Agent (SVC-30), Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32).
- **Ключевые поля.** `id`, `name`, `prior`, `description`.

### DTO-38. GeneratedFeatureSpecDTO

- **Назначение.** Описание генерации конкретного признака.
- **Основное хранилище.** В составе `GenerationSpecDTO`.
- **Использующие сервисы.** Data Generation Spec Agent (SVC-30), Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32).
- **Ключевые поля.** `name`, `role` (`base`/`derived`/`interaction`), `dtype`, `distribution` (`DistributionSpecDTO`), `formula`, `input_features[]`, `constraints`, `evidence_doc_ids[]`.

### DTO-39. DistributionSpecDTO

- **Назначение.** Распределение признака при synthetic data generation.
- **Основное хранилище.** В составе `GenerationSpecDTO`.
- **Использующие сервисы.** Data Generation Spec Agent (SVC-30), Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32).
- **Ключевые поля.** `type` (`normal`/`uniform`/`lognormal`/`beta`/`poisson`/`categorical`), `params`, `conditioned_by_class`, `class_params`, `clip_min`, `clip_max`.

### DTO-40. NoiseSpecDTO

- **Назначение.** Модель шума в synthetic dataset.
- **Основное хранилище.** В составе `GenerationSpecDTO`.
- **Использующие сервисы.** Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32).
- **Ключевые поля.** `type` (`gaussian`/`uniform`/`none`), `std`, `std_fraction`, `applies_to[]`, `random_state`.

### DTO-41. AnomalySpecDTO

- **Назначение.** Модель аномалий в synthetic dataset.
- **Основное хранилище.** В составе `GenerationSpecDTO`.
- **Использующие сервисы.** Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32), Analytics Service (SVC-35).
- **Ключевые поля.** `rate`, `type` (`sensor_glitch`/`outlier`/`missingness`/`label_flip`), `affected_features[]`, `factor_min`, `factor_max`, `metadata_label`.

### DTO-42. DatasetArtifactDTO

- **Назначение.** Сгенерированная обучающая выборка и связанные файлы.
- **Основное хранилище.** Metadata — PostgreSQL; файлы — Object Storage; метрики качества — ClickHouse.
- **Использующие сервисы.** Synthetic Data Worker (SVC-31), Dataset Validation Service (SVC-32), Export Service (SVC-34), Artifact Storage Service (SVC-38), Analytics Service (SVC-35), Frontend UI (SVC-01).
- **Ключевые поля.** `dataset_id`, `conversation_id`, `generation_spec_id`, `X_path`, `y_path`, `metadata_path`, `n_samples`, `n_features`, `X_shape[]`, `y_shape[]`, `class_distribution_actual`, `validation_report_id`, `created_at`, `status`.

### DTO-43. ModelRecommendationDTO

- **Назначение.** Результат выбора модели и ранжирование моделей.
- **Основное хранилище.** PostgreSQL. Метрики рекомендаций — ClickHouse. Config — Object Storage.
- **Использующие сервисы.** Model Selection Agent (SVC-33), ContextMemory Service (SVC-17), Export Service (SVC-34), Frontend UI (SVC-01), Analytics Service (SVC-35).
- **Ключевые поля.** `model_recommendation_id`, `conversation_id`, `recommended_model`, `model_ranking[]` (`ModelRankingItemDTO`), `selection_reason`, `training_config` (`TrainingConfigDTO`), `evidence_doc_ids[]`, `created_at`, `selected_by_user`.

### DTO-44. ModelRankingItemDTO

- **Назначение.** Одна модель в ранжированном списке.
- **Основное хранилище.** В составе `ModelRecommendationDTO`.
- **Использующие сервисы.** Model Selection Agent (SVC-33), Frontend UI (SVC-01), Analytics Service (SVC-35).
- **Ключевые поля.** `rank`, `model_name`, `model_family` (`tree_boosting`/`linear`/`bayesian`/`neural`), `reason`, `pros[]`, `cons[]`, `interpretability`, `latency_estimate`, `recommended_metrics[]`.

### DTO-45. TrainingConfigDTO

- **Назначение.** Конфигурация обучения модели.
- **Основное хранилище.** PostgreSQL. Файл `config.yaml` — Object Storage. Опционально — Model Registry.
- **Использующие сервисы.** Model Selection Agent (SVC-33), Export Service (SVC-34), Model Registry (внешний EXT), ML Engineer (внешний).
- **Ключевые поля.** `training_config_id`, `model_name`, `task_type`, `hyperparameters`, `preprocessing`, `validation_strategy`, `metrics[]`, `class_weight`, `early_stopping`, `random_state`, `created_at`.

---

## §9. DTO экспорта и артефактов

### DTO-46. ArtifactDTO

- **Назначение.** Любой файл, созданный или загруженный системой.
- **Основное хранилище.** Metadata — PostgreSQL; файл — Object Storage; события скачивания — ClickHouse/Audit.
- **Использующие сервисы.** Artifact Storage Service (SVC-38), Export Service (SVC-34), Frontend UI (SVC-01), API Gateway (SVC-02), Audit Service (SVC-36).
- **Ключевые поля.** `artifact_id`, `conversation_id`, `setup_job_id`, `artifact_type` (`source_doc`/`rag_card`/`dataset`/`config`/`zip`/`report`), `filename`, `storage_path`, `content_type`, `size_bytes`, `checksum`, `created_by`, `created_at`, `ttl_expires_at`.

### DTO-47. ExportManifestDTO

- **Назначение.** Итоговый экспортированный ML-пакет.
- **Основное хранилище.** PostgreSQL. Manifest и archive — Object Storage. Событие — Kafka/ClickHouse.
- **Использующие сервисы.** Export Service (SVC-34), Artifact Storage Service (SVC-38), Frontend Download Manager (SVC-01), Audit Service (SVC-36), ContextMemory Service (SVC-17).
- **Ключевые поля.** `artifact_package_id`, `conversation_id`, `files[]` (`ArtifactDTO`), `archive_artifact_id`, `download_url`, `expires_at`, `created_at`, `created_by`, `status` (`created`/`ready`/`downloaded`/`expired`/`failed`).

---

## §10. DTO аналитики, аудита и уведомлений

### DTO-48. AuditEventDTO

- **Назначение.** Значимое действие пользователя/агента/сервиса.
- **Основное хранилище.** ClickHouse для аналитики и timeline. Критичные события дублируются в PostgreSQL. Поток — Kafka.
- **Использующие сервисы.** Audit Service (SVC-36); все backend-сервисы как producers; Frontend Audit UI (SVC-01); Analytics Service (SVC-35).
- **Ключевые поля.** `event_id`, `actor_type` (`user`/`agent`/`service`/`system`), `actor_id`, `event_type`, `entity_type`, `entity_id`, `conversation_id`, `setup_job_id`, `before_state`, `after_state`, `created_at`, `metadata`.

### DTO-49. AnalyticsEventDTO

- **Назначение.** Универсальное событие аналитики для dashboards и мониторинга.
- **Основное хранилище.** ClickHouse. Поток — Kafka. Некоторые агрегаты — Redis.
- **Использующие сервисы.** Analytics Service (SVC-35); Agent Runtime (SVC-19), RAG Retrieval Service (SVC-21), Setup Orchestrator (SVC-04), Synthetic Data Worker (SVC-31) как producers; Frontend Analytics Dashboard (SVC-01).
- **Ключевые поля.** `event_id`, `event_type` (`agent_call`/`rag_query`/`setup_step`/`validation`/`export`), `conversation_id`, `setup_job_id`, `agent_name`, `phase`, `metrics`, `dimensions`, `created_at`.

### DTO-50. NotificationDTO

- **Назначение.** Уведомление frontend о прогрессе и результате операций.
- **Основное хранилище.** Краткосрочно — Redis. История — PostgreSQL опционально. Поток — Kafka/WebSocket/SSE.
- **Использующие сервисы.** Notification Service (SVC-37), Frontend UI (SVC-01), Setup Orchestrator (SVC-04), Synthetic Data Worker (SVC-31), Export Service (SVC-34).
- **Ключевые поля.** `notification_id`, `user_id`, `channel` (`ui`/`email`/`websocket`/`sse`), `type` (`info`/`success`/`warning`/`error`/`progress`), `title`, `message`, `related_entity_type`, `related_entity_id`, `progress_percent`, `created_at`, `read_at`.

### DTO-51. ProcessingReportDTO

- **Назначение.** Сводный отчёт по длительной операции (Setup, indexing, generation, export).
- **Основное хранилище.** PostgreSQL. Файл отчёта — Object Storage. Метрики — ClickHouse.
- **Использующие сервисы.** Setup Orchestrator (SVC-04), Retrieval Evaluation Service (SVC-14), Synthetic Data Worker (SVC-31), Export Service (SVC-34), Frontend UI (SVC-01), Analytics Service (SVC-35).
- **Ключевые поля.** `report_id`, `report_type` (`rag_setup`/`indexing`/`data_generation`/`export`), `related_entity_id`, `status`, `summary`, `steps[]`, `errors[]`, `warnings[]`, `metrics`, `artifact_id`, `created_at`.

---

## §11. Domain Analytics DTO

### DTO-52. FeatureStoreTableDTO

- **Назначение.** Feature-store таблица (например, `sensor_analytics_T`, `object_analytics_T`, `environment_analytics_T`).
- **Основное хранилище.** Metadata — PostgreSQL; данные — Feature Store, ClickHouse или PostgreSQL.
- **Использующие сервисы.** Domain Analytics Service (внутри SVC-35), Feature Store Service (внутри SVC-35), RAG Card Generator (SVC-09), Analytics Service (SVC-35), Export Service (SVC-34).
- **Ключевые поля.** `feature_table_id`, `table_name`, `entity_type` (`sensor`/`object`/`weapon`/`environment`), `grain`, `keys[]`, `feature_fields[]` (`FeatureFieldDTO`), `source_tables[]`, `refresh_policy`, `owner`, `created_at`.

### DTO-53. FeatureFieldDTO

- **Назначение.** Одно поле feature-store таблицы.
- **Основное хранилище.** В составе `FeatureStoreTableDTO` в PostgreSQL.
- **Использующие сервисы.** Feature Store Service, Domain Analytics Service, Feature Synthesis Agent (SVC-27), RAG Card Generator (SVC-09).
- **Ключевые поля.** `field_name`, `dtype`, `description`, `formula`, `source_fields[]`, `unit`, `window`, `validation_rules[]`, `evidence_doc_ids[]`.

---

## §12. Сводная карта DTO → хранилище → сервисы

| DTO | Основное хранилище | Использующие сервисы |
| --- | --- | --- |
| DTO-01 UserProfileDTO | PostgreSQL, Redis | Auth, API, Frontend, Audit |
| DTO-02 AuthTokenDTO | Не хранится, Redis | Frontend, API, Auth |
| DTO-03 PermissionDTO | PostgreSQL, Redis | Auth, API, Artifact, KB Registry |
| DTO-04 UserSessionDTO | PostgreSQL, Redis, ClickHouse | Session, API, LangGraph, Analytics |
| DTO-05 ChatMessageDTO | PostgreSQL, ClickHouse | Frontend, API, LangGraph, Agent Runtime |
| DTO-06 ContextMemoryDTO | PostgreSQL, Redis | ContextMemory, LangGraph, Agents, Export |
| DTO-07 RAGSetupJobDTO | PostgreSQL, Redis, Kafka, ClickHouse | Setup, Frontend, Analytics |
| DTO-08 UploadFileDTO | Не хранится | Frontend, API, Upload |
| DTO-09 SourceDocumentDTO | PostgreSQL, Object Storage | Upload, Parser, Registry, RAG Generator |
| DTO-10 ParsedSectionDTO | PostgreSQL | Parser, RAG Generator |
| DTO-11 RAGCardDTO | PostgreSQL, Object Storage/Git | RAG Generator, Review, Chunking, Retrieval |
| DTO-12 RAGMetadataDTO | PostgreSQL, Vector DB | Metadata, Retrieval, Indexer |
| DTO-13 RAGCardReviewDTO | PostgreSQL, ClickHouse | Review, Audit, KB Registry |
| DTO-14 ChunkDTO | PostgreSQL, Vector DB, Object Storage | Chunking, Embedding, Retrieval |
| DTO-15 EmbeddingDTO | Vector DB, PostgreSQL | Embedding, Indexer, Retrieval |
| DTO-16 VectorIndexDTO | PostgreSQL, Vector DB | Indexer, KB Registry, Retrieval |
| DTO-17 KnowledgeBaseVersionDTO | PostgreSQL, Redis | KB Registry, Retrieval, LangGraph |
| DTO-18 RetrievalQueryDTO | ClickHouse, Kafka | Retrieval, Analytics |
| DTO-19 RetrievedChunkDTO | ClickHouse, Vector DB | Retrieval, Evidence Builder |
| DTO-20 EvidencePackDTO | PostgreSQL, Redis, ClickHouse | Evidence Builder, Agents, LLM |
| DTO-21 RetrievalEvaluationCaseDTO | PostgreSQL, Object Storage | RAG Evaluation |
| DTO-22 RetrievalEvaluationReportDTO | PostgreSQL, ClickHouse, Object Storage | Evaluation, Setup, Analytics |
| DTO-23 AgentRequestDTO | ClickHouse, PostgreSQL trace | LangGraph, Agent Runtime |
| DTO-24 AgentResponseDTO | PostgreSQL, ClickHouse | Agent Runtime, Validation, ContextMemory |
| DTO-25 PromptDTO | Object Storage/Git, ClickHouse | LLM Gateway, Prompt Eval |
| DTO-26 LLMResponseDTO | ClickHouse, PostgreSQL | LLM Gateway, Validation |
| DTO-27 NLUResultDTO | PostgreSQL, ClickHouse | NLU, LangGraph |
| DTO-28 DataProfileDTO | PostgreSQL, ClickHouse | Data Profiling, Feature Synthesis |
| DTO-29 DomainContextDTO | PostgreSQL, ClickHouse | Domain Agent, Feature Agent |
| DTO-30 FeatureCandidateDTO | PostgreSQL, ClickHouse | Feature Agent, Validation |
| DTO-31 FeatureSpecDTO | PostgreSQL, Feature Store, ClickHouse | Validation, Export, Data Generation |
| DTO-32 ValidationReportDTO | PostgreSQL, ClickHouse, Object Storage | All validators, Frontend |
| DTO-33 HumanReviewRequestDTO | PostgreSQL, Kafka, ClickHouse | Human Review, Frontend |
| DTO-34 HumanReviewDecisionDTO | PostgreSQL, ClickHouse | Human Review, ContextMemory |
| DTO-35 GenerationSpecDTO | PostgreSQL, Object Storage | Data Gen Agent, Worker, Export |
| DTO-36 TargetSpecDTO | В составе GenerationSpec | Data Gen Agent, Worker |
| DTO-37 TargetClassDTO | В составе GenerationSpec | Data Gen Agent, Worker |
| DTO-38 GeneratedFeatureSpecDTO | В составе GenerationSpec | Worker, Validator |
| DTO-39 DistributionSpecDTO | В составе GenerationSpec | Worker |
| DTO-40 NoiseSpecDTO | В составе GenerationSpec | Worker |
| DTO-41 AnomalySpecDTO | В составе GenerationSpec | Worker |
| DTO-42 DatasetArtifactDTO | PostgreSQL, Object Storage, ClickHouse | Worker, Export, Analytics |
| DTO-43 ModelRecommendationDTO | PostgreSQL, ClickHouse | Model Agent, Frontend |
| DTO-44 ModelRankingItemDTO | В составе ModelRecommendation | Model Agent, Analytics |
| DTO-45 TrainingConfigDTO | PostgreSQL, Object Storage, Model Registry | Model Agent, Export |
| DTO-46 ArtifactDTO | PostgreSQL, Object Storage | Artifact, Export, Frontend |
| DTO-47 ExportManifestDTO | PostgreSQL, Object Storage | Export, Frontend |
| DTO-48 AuditEventDTO | ClickHouse, Kafka, PostgreSQL | Audit, All services |
| DTO-49 AnalyticsEventDTO | ClickHouse, Kafka, Redis | Analytics, All services |
| DTO-50 NotificationDTO | Redis, PostgreSQL, Kafka | Notification, Frontend |
| DTO-51 ProcessingReportDTO | PostgreSQL, Object Storage, ClickHouse | Setup, Worker, Export |
| DTO-52 FeatureStoreTableDTO | PostgreSQL, Feature Store, ClickHouse | Domain Analytics, Feature Store |
| DTO-53 FeatureFieldDTO | PostgreSQL | Feature Store, RAG Generator |

Подробная матрица DTO → конкретный SVC — в [../../traceability/dto-to-service-map.md](../../traceability/dto-to-service-map.md).

---

## §13. Минимальный DTO-набор для MVP

Для MVP не обязательно реализовывать все 53 DTO. Достаточно 26, которые покрывают полный путь пользователя «загрузка → подготовка RAG → KB ready → диалог → признаки → synthetic data → выбор модели → экспорт → аналитика и аудит».

```text
UserSessionDTO              (DTO-04)
ChatMessageDTO              (DTO-05)
ContextMemoryDTO            (DTO-06)
RAGSetupJobDTO              (DTO-07)
SourceDocumentDTO           (DTO-09)
ParsedSectionDTO            (DTO-10)
RAGCardDTO                  (DTO-11)
ChunkDTO                    (DTO-14)
VectorIndexDTO              (DTO-16)
KnowledgeBaseVersionDTO     (DTO-17)
RetrievalQueryDTO           (DTO-18)
RetrievedChunkDTO           (DTO-19)
EvidencePackDTO             (DTO-20)
AgentRequestDTO             (DTO-23)
AgentResponseDTO            (DTO-24)
FeatureCandidateDTO         (DTO-30)
FeatureSpecDTO              (DTO-31)
ValidationReportDTO         (DTO-32)
GenerationSpecDTO           (DTO-35)
DatasetArtifactDTO          (DTO-42)
ModelRecommendationDTO      (DTO-43)
TrainingConfigDTO           (DTO-45)
ExportManifestDTO           (DTO-47)
AuditEventDTO               (DTO-48)
AnalyticsEventDTO           (DTO-49)
NotificationDTO             (DTO-50)
```

DTO-01..03 (Auth/Permission) включаются только при появлении многопользовательского режима. DTO-13/33/34 (Review) добавляются вместе с HITL-фазами. DTO-25/26 (Prompt/LLMResponse) — когда нужна prompt-аналитика. DTO-21/22 (Retrieval evaluation) — когда подключается автотестирование RAG. DTO-52/53 (Feature Store) — при подключении Domain Analytics. DTO-08/46/51 (UploadFile/Artifact/ProcessingReport) и под-DTO GenerationSpec (DTO-36..41, DTO-44) — желательны, но могут быть реализованы как inline-структуры внутри `GenerationSpecDTO` / `ModelRecommendationDTO` без отдельных таблиц.

---

## Связанные документы

- [storage-conventions.md](storage-conventions.md) — соглашения по хранилищам, упоминаемым в каталоге
- [README.md](README.md) — каталог сервисов
- [../../07-contracts/](../../07-contracts/) — детальные Pydantic-контракты
- [../../../schemas/](../../../schemas/) — реализация Pydantic-схем
- [../../traceability/dto-to-service-map.md](../../traceability/dto-to-service-map.md) — DTO → SVC матрица
