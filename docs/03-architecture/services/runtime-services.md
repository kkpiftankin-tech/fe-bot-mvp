# Runtime-сервисы (SVC-16..SVC-34)

Сервисы стадии Runtime: от создания сессии до экспорта артефактов. Полный пользовательский поток — в [UC-FE-02](../../02-system/use-cases/UC-FE-02-create-feature-set/use-case.md).

---

## SVC-16. Session Service

### Назначение

Создаёт и восстанавливает пользовательские runtime-сессии.

### Функции

Выпускает `conversation_id`, связывает сессию с пользователем и активной Knowledge Base, хранит текущую фазу и базовый статус.

### DTO

`UserSessionDTO`, `ContextMemoryDTO`, `AuditEventDTO`.

### Внешние участники

EXT-01 пользователь, EXT-06 Identity Provider.

### Соседние сервисы

SVC-02 API Gateway, SVC-17 ContextMemory, SVC-18 LangGraph Orchestrator, Conversation DB, SVC-15 KB Registry.

### Информационный обмен

С `SVC-02` — start/restore. С `SVC-15` — active KB version. С `SVC-17` — инициализация ContextMemory. С Conversation DB — session record.

### Входные данные

User id, project settings, active KB version, start command.

### Выходные данные

`UserSessionDTO`, `conversation_id`, начальная фаза, session status.

### Реализует фичи

[RUNTIME-01](../../02-system/features/RUNTIME-01-session.md). Агент: [SessionAgent](../../05-agents/session-agent.md).

---

## SVC-17. ContextMemory Service

### Назначение

Хранит структурированное состояние ML-проекта и диалога.

### Функции

Создаёт, обновляет, валидирует и версионирует `ContextMemory`. Гарантирует, что агенты работают с typed state, а не с хаотичной историей чата.

### DTO

`ContextMemoryDTO`, `FeatureSpecDTO`, `GenerationSpecDTO`, `ModelRecommendationDTO`, `AuditEventDTO`.

### Внешние участники

EXT-01 пользователь (косвенно), аудитор.

### Соседние сервисы

SVC-16 Session, SVC-18 LangGraph Orchestrator, SVC-19 Agent Runtime, SVC-28 Validation, Conversation DB, SVC-36 Audit, SVC-34 Export.

### Информационный обмен

С `SVC-18` — read/update state. С `SVC-19` — structured agent outputs. С `SVC-28` — статус валидности обновлений. С `SVC-34` — итоговый ContextMemory.

### Входные данные

Agent outputs, user decisions, validation reports, phase transitions, session metadata.

### Выходные данные

Обновлённый `ContextMemoryDTO`, state snapshot, change log, invalidation events.

### Реализует фичи

[RUNTIME-01](../../02-system/features/RUNTIME-01-session.md) (state-часть), все RUNTIME-фичи (косвенно). Агент: [ContextMemoryAgent](../../05-agents/context-memory-agent.md).

---

## SVC-18. LangGraph Orchestrator

### Назначение

Управляет фазами мультиагентного workflow.

### Функции

Определяет следующий шаг, вызывает нужных агентов, проверяет completion criteria, запускает repair loops, human review и переходы между фазами.

### DTO

`ContextMemoryDTO`, `AgentRequestDTO`, `AgentResponseDTO`, `ValidationReportDTO`, `ChatMessageDTO`.

### Внешние участники

EXT-01 пользователь (косвенно), EXT-07 LLM (через LLM Gateway).

### Соседние сервисы

SVC-02 API Gateway, SVC-16 Session, SVC-17 ContextMemory, SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-28 Validation, SVC-29 Human Review, SVC-36 Audit.

### Информационный обмен

С `SVC-02` — сообщение пользователя. С `SVC-17` — state. С `SVC-19` — вызов нужного агента. С `SVC-28` — validation report. С `SVC-29` — постановка в HITL.

### Входные данные

`ChatMessageDTO`, текущий ContextMemory, текущая фаза, validation state, user action.

### Выходные данные

Следующая фаза, agent request, ответ пользователю, updated ContextMemory, repair instruction, review request.

### Реализует фичи

[PLATFORM-02](../../02-system/features/PLATFORM-02-langgraph-orchestrator.md). Агент: [DialogueOrchestratorAgent](../../05-agents/dialogue-orchestrator-agent.md). См. [docs/09-langgraph/state-machine.md](../../09-langgraph/state-machine.md).

---

## SVC-19. Agent Runtime

### Назначение

Исполняет специализированных агентов системы.

### Функции

Вызывает NLU Agent, Task Discovery Agent, Data Profiling Agent, Domain Context Agent, Feature Synthesis Agent, Feature Critic Agent, Generation Spec Agent, Model Selection Agent, Export Agent.

### DTO

`AgentRequestDTO`, `AgentResponseDTO`, `EvidencePackDTO`, `ContextMemoryDTO`, `FeatureCandidateDTO`, `GenerationSpecDTO`.

### Внешние участники

EXT-07 локальная LLM (через LLM Gateway).

### Соседние сервисы

SVC-18 LangGraph Orchestrator, SVC-20 LLM Gateway, SVC-21 RAG Retrieval, SVC-28 Validation, SVC-17 ContextMemory, SVC-36 Audit.

### Информационный обмен

С `SVC-18` — команды вызвать конкретного агента. С `SVC-21` — Evidence Pack. С `SVC-20` — prompt ↔ structured response. С `SVC-28` — output на проверку. С `SVC-17` — валидный output.

### Входные данные

Agent request, context slice, evidence pack, prompt template, output schema.

### Выходные данные

Agent response, structured output, confidence, errors, `need_more_context` flag.

### Реализует фичи

Все runtime-фичи (косвенно). См. [c4-component-agent-runtime.md](../c4-component-agent-runtime.md).

---

## SVC-20. LLM Gateway

### Назначение

Изолирует систему от конкретного LLM runtime и обеспечивает structured output.

### Функции

Формирует prompt, вызывает Ollama, применяет JSON schema, повторяет запрос при невалидном JSON, логирует latency и версию prompt template.

### DTO

`AgentRequestDTO`, `AgentResponseDTO`, `PromptDTO`, `LLMResponseDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-07 Ollama / локальная LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-28 Validation, Observability, SVC-36 Audit.

### Информационный обмен

С `SVC-19` — prompt request. С `EXT-07` — prompt ↔ raw response. С `SVC-28` — structured output на проверку. С Observability — latency/error metrics.

### Входные данные

Prompt template, context, evidence pack, JSON schema, model parameters.

### Выходные данные

Raw LLM response, parsed JSON, validation status, retry result, token/latency metrics.

### Реализует фичи

[PLATFORM-03](../../02-system/features/PLATFORM-03-structured-output-contracts.md). См. [ADR-002](../adr/ADR-002-ollama-default-llm.md).

---

## SVC-21. RAG Retrieval Service

### Назначение

Извлечение релевантного контекста из активной Knowledge Base для агентов.

### Функции

Применяет metadata filters, semantic search, rerank, graph expansion; формирует Evidence Pack.

### DTO

`RetrievalQueryDTO`, `RetrievedChunkDTO`, `EvidencePackDTO`, `ContextMemoryDTO`.

### Внешние участники

EXT-09 Vector DB.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-15 KB Registry, EXT-09 Vector DB, SVC-08 Ontology, SVC-22 Evidence Pack Builder, SVC-35 Analytics.

### Информационный обмен

С `SVC-19` — retrieval request. С `SVC-15` — active KB version. С `EXT-09` — vector search query ↔ chunks. С `SVC-08` — metadata filter rules. С `SVC-35` — retrieval logs.

### Входные данные

Query text, phase, agent name, metadata filters, top_k, ContextMemory slice.

### Выходные данные

Retrieved chunks, evidence doc ids, Evidence Pack, retrieval scores, no-context signal.

### Реализует фичи

Поддерживает [RUNTIME-05](../../02-system/features/RUNTIME-05-domain-context.md) и все runtime-фичи. Агент: [RAGRetrievalAgent](../../05-agents/rag-retrieval-agent.md). См. [docs/06-rag/retrieval-policies.md](../../06-rag/retrieval-policies.md).

---

## SVC-22. Evidence Pack Builder

### Назначение

Превращает retrieved chunks в компактный пакет контекста для агента.

### Функции

Удаляет дубли, группирует документы по типу, выделяет constraints, нормализационные словари, source fields, validation rules, evidence ids.

### DTO

`RetrievedChunkDTO`, `EvidencePackDTO`, `RAGMetadataDTO`.

### Внешние участники

Нет прямых.

### Соседние сервисы

SVC-21 RAG Retrieval, SVC-19 Agent Runtime, SVC-35 Analytics.

### Информационный обмен

С `SVC-21` — chunks. С `SVC-19` — Evidence Pack. С `SVC-35` — статистика evidence usage.

### Входные данные

Retrieved chunks, agent name, phase, context slice.

### Выходные данные

Evidence Pack, evidence summaries, constraints, `evidence_doc_ids`.

### Реализует фичи

См. [docs/06-rag/evidence-pack.md](../../06-rag/evidence-pack.md).

---

## SVC-23. NLU Agent Service

### Назначение

Извлекает intent и entities из сообщения пользователя.

### Функции

Классифицирует намерение, извлекает слоты, нормализует термины через RAG, оценивает confidence и определяет `missing_slots`.

### DTO

`ChatMessageDTO`, `AgentRequestDTO`, `AgentResponseDTO`, `ContextMemoryDTO`.

### Внешние участники

EXT-01 пользователь, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-20 LLM Gateway, SVC-21 RAG Retrieval, SVC-17 ContextMemory, SVC-28 Validation.

### Информационный обмен

С `SVC-21` — glossary / domain context. С `SVC-20` — prompt на извлечение intent / entities. С `SVC-17` — валидные slots.

### Входные данные

User message, текущая фаза, ContextMemory, glossary evidence.

### Выходные данные

Intent, entities, confidence, missing slots, normalized values.

### Реализует фичи

[RUNTIME-02](../../02-system/features/RUNTIME-02-nlu.md). Агент: [NLUAgent](../../05-agents/nlu-agent.md).

---

## SVC-24. Task Discovery Agent Service

### Назначение

Определяет постановку ML-задачи.

### Функции

Уточняет `task_type`, `target_variable`, `domain`, `data_source`, классы, latency, deployment context.

### DTO

`ContextMemoryDTO`, `AgentRequestDTO`, `AgentResponseDTO`, `EvidencePackDTO`.

### Внешние участники

EXT-01 пользователь, EXT-03 SME, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-20 LLM Gateway, SVC-17 ContextMemory, SVC-18 LangGraph Orchestrator.

### Информационный обмен

С `SVC-21` — task cards. С `SVC-20` — structured task discovery output. С `SVC-17` — task section. С `SVC-18` — completion status.

### Входные данные

User task description, NLU entities, task-related evidence, current ContextMemory.

### Выходные данные

`task_type`, `target_variable`, `domain`, `data_source`, открытые вопросы.

### Реализует фичи

[RUNTIME-03](../../02-system/features/RUNTIME-03-task-discovery.md). Агент: [TaskDiscoveryAgent](../../05-agents/task-discovery-agent.md).

---

## SVC-25. Data Profiling Agent Service

### Назначение

Собирает профиль данных пользователя.

### Функции

Выясняет `data_volume`, `data_type`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance`.

### DTO

`ContextMemoryDTO`, `AgentRequestDTO`, `AgentResponseDTO`, `EvidencePackDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-01 пользователь, EXT-03 SME, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-20 LLM Gateway, SVC-17 ContextMemory, SVC-28 Validation, SVC-01 Frontend Data Profile Panel.

### Информационный обмен

С `SVC-21` — schema cards и field glossary. С `SVC-20` — нормализация пользовательских полей. С `SVC-28` — проверка профиля. С `SVC-17` — data profile.

### Входные данные

Ответы пользователя о данных, task context, RAG schema evidence.

### Выходные данные

Data profile, нормализованные поля, missing data policy, temporal flag, validation report.

### Реализует фичи

[RUNTIME-04](../../02-system/features/RUNTIME-04-data-profiling.md). Агент: [DataProfilingAgent](../../05-agents/data-profiling-agent.md).

---

## SVC-26. Domain Context Agent Service

### Назначение

Уточняет доменные факторы и ограничения.

### Функции

Извлекает critical factors, domain constraints, `interpretability_requirement`, разрешённые/запрещённые feature families.

### DTO

`ContextMemoryDTO`, `EvidencePackDTO`, `AgentResponseDTO`.

### Внешние участники

EXT-01 пользователь, EXT-03 SME, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-20 LLM Gateway, SVC-17 ContextMemory.

### Информационный обмен

С `SVC-21` — domain cards, schema cards, analytics cards. С `SVC-20` — structured domain context. С `SVC-17` — critical factors.

### Входные данные

Domain, data source, task type, RAG evidence, пользовательские уточнения.

### Выходные данные

Critical factors, interpretability requirement, domain constraints, feature family policy.

### Реализует фичи

[RUNTIME-05](../../02-system/features/RUNTIME-05-domain-context.md). Агент: [DomainContextAgent](../../05-agents/domain-context-agent.md).

---

## SVC-27. Feature Synthesis Agent Service

### Назначение

Генерирует candidate-признаки.

### Функции

Формирует base, derived, interaction features; связывает каждый признак с evidence и формулой.

### DTO

`FeatureCandidateDTO`, `FeatureSpecDTO`, `ContextMemoryDTO`, `EvidencePackDTO`, `AgentResponseDTO`.

### Внешние участники

EXT-01 пользователь, EXT-03 SME, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-20 LLM Gateway, SVC-28 Validation, SVC-17 ContextMemory, SVC-01 Frontend Feature Review UI.

### Информационный обмен

С `SVC-21` — feature pattern и analytics cards. С `SVC-20` — candidate features. С `SVC-28` — на проверку. С `SVC-17` — кандидаты. С `SVC-01` — показ пользователю.

### Входные данные

Fields, data profile, domain context, critical factors, evidence pack.

### Выходные данные

Candidate features, formulas, explanations, `evidence_doc_ids`.

### Реализует фичи

[RUNTIME-06](../../02-system/features/RUNTIME-06-feature-synthesis.md). Агент: [FeatureSynthesisAgent](../../05-agents/feature-synthesis-agent.md).

---

## SVC-28. Feature Validation / Critic Service

### Назначение

Проверяет признаки на вычислимость, корректность и соответствие ограничениям.

### Функции

Проверяет наличие source fields, корректность formula, temporal constraints, evidence, дубли, feature family policy, validation rules.

### DTO

`FeatureCandidateDTO`, `FeatureSpecDTO`, `ValidationReportDTO`, `ContextMemoryDTO`.

### Внешние участники

EXT-03 SME, EXT-01 пользователь при human review.

### Соседние сервисы

SVC-27 Feature Synthesis, SVC-17 ContextMemory, SVC-29 Human Review, SVC-18 LangGraph Orchestrator, SVC-36 Audit.

### Информационный обмен

С `SVC-27` — candidate features. С `SVC-17` — data profile, domain constraints. С `SVC-29` — risky features. С `SVC-18` — pass/repair decision.

### Входные данные

Candidate features, fields, `temporal_importance`, evidence doc ids, validation rules.

### Выходные данные

Approved features, rejected features, warnings, validation report, repair instructions.

### Реализует фичи

[RUNTIME-07](../../02-system/features/RUNTIME-07-feature-validation.md). Агенты: [FeatureCriticAgent](../../05-agents/feature-critic-agent.md), [MulticollinearityAgent](../../05-agents/multicollinearity-agent.md).

---

## SVC-29. Human Review Service

### Назначение

Управляет пользовательским подтверждением критичных решений.

### Функции

Ставит workflow на паузу, показывает пользователю решение, принимает approve/reject/edit, фиксирует выбор и возвращает управление LangGraph.

### DTO

`FeatureSpecDTO`, `ValidationReportDTO`, `ContextMemoryDTO`, `AuditEventDTO`.

### Внешние участники

EXT-01 пользователь, EXT-03 SME, EXT-02 RAG admin (при настройке).

### Соседние сервисы

SVC-18 LangGraph Orchestrator, SVC-01 Frontend, SVC-17 ContextMemory, SVC-36 Audit, SVC-28 Validation.

### Информационный обмен

С `SVC-18` — review request. С `SVC-01` — review payload. С `SVC-17` — решение. С `SVC-36` — review event.

### Входные данные

Review request, candidate features, validation report, user decision.

### Выходные данные

Review decision, updated status, audit record, resume signal.

### Реализует фичи

[RUNTIME-08](../../02-system/features/RUNTIME-08-feature-review.md), [RUNTIME-11](../../02-system/features/RUNTIME-11-model-selection.md) (model review). Агент: [FeedbackAgent](../../05-agents/feedback-agent.md).

---

## SVC-30. Data Generation Spec Agent Service

### Назначение

Формирует `GenerationSpec` для синтетической обучающей выборки.

### Функции

Определяет generation mode, target distribution, feature distributions, formulas, noise, anomaly model и validation expectations.

### DTO

`GenerationSpecDTO`, `FeatureSpecDTO`, `ContextMemoryDTO`, `AgentResponseDTO`, `EvidencePackDTO`.

### Внешние участники

EXT-01 пользователь, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-20 LLM Gateway, SVC-21 RAG Retrieval, SVC-17 ContextMemory, SVC-28 Validation (GenerationSpec validation), SVC-31 Synthetic Data Worker.

### Информационный обмен

С `SVC-21` — distribution и feature evidence. С `SVC-20` — structured GenerationSpec. С `SVC-28` — проверка GenerationSpec. С `SVC-31` — валидная спецификация.

### Входные данные

Final features, `n_samples`, `class_distribution`, `noise_level`, `anomaly_rate`, data type, task type.

### Выходные данные

`GenerationSpec`, validation status, repair instruction.

### Реализует фичи

[RUNTIME-09](../../02-system/features/RUNTIME-09-generation-spec.md). Агент: [DataGenerationSpecAgent](../../05-agents/data-generation-spec-agent.md). См. [ADR-004](../adr/ADR-004-llm-generates-spec-not-data.md).

---

## SVC-31. Synthetic Data Generation Worker

### Назначение

Исполняет `GenerationSpec` и создаёт обучающую выборку.

### Функции

Генерирует base features, derived features, interaction features, target, добавляет шум и аномалии, сохраняет данные.

### DTO

`GenerationSpecDTO`, `DatasetArtifactDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-04 Data Scientist (косвенно через UI).

### Соседние сервисы

SVC-30 Data Generation Spec Agent, SVC-32 Dataset Validation, SVC-38 Artifact Storage, SVC-17 ContextMemory, SVC-37 Notification.

### Информационный обмен

С `SVC-30` — GenerationSpec. С `SVC-32` — X/y на проверку. С `SVC-38` — CSV/NPY/metadata. С `SVC-17` — dataset artifact references. С `SVC-37` — `generation_completed`.

### Входные данные

GenerationSpec, random seed, output paths, generation parameters.

### Выходные данные

`X_train.csv`, `y_train.npy`, `metadata.json`, dataset artifact id, generation logs.

### Реализует фичи

[RUNTIME-10](../../02-system/features/RUNTIME-10-data-generation.md).

---

## SVC-32. Dataset Validation Service

### Назначение

Проверяет качество сгенерированной обучающей выборки.

### Функции

Проверяет shape, NaN, Inf, допустимость классов, соответствие class distribution, имена признаков, фактический anomaly rate.

### DTO

`DatasetArtifactDTO`, `GenerationSpecDTO`, `ValidationReportDTO`.

### Внешние участники

EXT-04 Data Scientist, EXT-04 ML Engineer (косвенно).

### Соседние сервисы

SVC-31 Synthetic Data Worker, SVC-38 Artifact Storage, SVC-35 Analytics, SVC-17 ContextMemory.

### Информационный обмен

С `SVC-31` — данные и GenerationSpec. С `SVC-38` — сохранение validation report. С `SVC-35` — data quality metrics. С `SVC-17` — validation status.

### Входные данные

Generated X, generated y, GenerationSpec, feature names, expected shape.

### Выходные данные

Validation report, quality metrics, pass/fail status, repair recommendations.

### Реализует фичи

[RUNTIME-10](../../02-system/features/RUNTIME-10-data-generation.md) (валидация), [ANALYTICS-06](../../02-system/features/ANALYTICS-06-dataset-quality.md).

---

## SVC-33. Model Selection Agent Service

### Назначение

Рекомендует ML-модель и training config.

### Функции

Анализирует task type, data type, volume, features, interpretability, latency и формирует top-N моделей с аргументацией.

### DTO

`ModelRecommendationDTO`, `ContextMemoryDTO`, `EvidencePackDTO`, `AgentResponseDTO`.

### Внешние участники

EXT-01 пользователь, EXT-04 Data Scientist, EXT-04 ML Engineer, EXT-07 LLM.

### Соседние сервисы

SVC-19 Agent Runtime, SVC-21 RAG Retrieval, SVC-20 LLM Gateway, SVC-17 ContextMemory, SVC-01 Frontend Model Selection UI, SVC-28 Validation.

### Информационный обмен

С `SVC-21` — model recommendation cards. С `SVC-20` — model ranking. С `SVC-28` — проверка training config. С `SVC-17` — selected model. С `SVC-01` — показ рекомендаций.

### Входные данные

Task type, data type, final features, dataset metadata, interpretability, latency, RAG evidence.

### Выходные данные

Recommended model, model ranking, training config, metrics, preprocessing config.

### Реализует фичи

[RUNTIME-11](../../02-system/features/RUNTIME-11-model-selection.md). Агент: [ModelSelectionAgent](../../05-agents/model-selection-agent.md).

---

## SVC-34. Export Service

### Назначение

Формирует итоговый ML-пакет.

### Функции

Создаёт `features.json`, `generation_spec.json`, `config.yaml`, `pipeline.py`, `data_generator.py`, `metadata.json`, `validation_report.json`, `archive.zip`.

### DTO

`ContextMemoryDTO`, `FeatureSpecDTO`, `GenerationSpecDTO`, `DatasetArtifactDTO`, `ModelRecommendationDTO`, `ExportManifestDTO`.

### Внешние участники

EXT-01 пользователь, EXT-04 Data Scientist, EXT-04 ML Engineer.

### Соседние сервисы

SVC-17 ContextMemory, SVC-38 Artifact Storage, SVC-32 Dataset Validation, SVC-33 Model Selection, SVC-01 Frontend Download Manager, SVC-36 Audit.

### Информационный обмен

С `SVC-17` — итоговый state. С `SVC-38` — dataset files, сохранение export files. С `SVC-01` — download manifest. С `SVC-36` — export event.

### Входные данные

Final ContextMemory, features, GenerationSpec, dataset artifacts, training config, validation reports.

### Выходные данные

`ExportManifest`, generated files, archive path, download URL.

### Реализует фичи

[RUNTIME-12](../../02-system/features/RUNTIME-12-export.md). Агент: [ExportAgent](../../05-agents/export-agent.md).

---

## Связанные документы

- [README.md](README.md)
- [../c4-component-agent-runtime.md](../c4-component-agent-runtime.md)
- [../../05-agents/agent-index.md](../../05-agents/agent-index.md)
- [../../02-system/use-cases/UC-FE-02-create-feature-set/use-case.md](../../02-system/use-cases/UC-FE-02-create-feature-set/use-case.md)
- [../../09-langgraph/state-machine.md](../../09-langgraph/state-machine.md)
