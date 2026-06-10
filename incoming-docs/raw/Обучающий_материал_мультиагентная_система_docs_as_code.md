# Обучающий материал: разработка мультиагентной системы Feature Engineering Bot в стиле docs-as-code

> Версия: 0.2  
> Назначение: обучающий материал для команды, разрабатывающей мультиагентную систему формирования признаков для ML-моделей.  
> Подход: docs-as-code + contract-first + state-first + RAG-first + test-first.  
> Целевой стек: Python, FastAPI, LangGraph, Ollama, малая LLM, RAG, Vector DB, Pydantic, Docker Compose.

---

## 0. Что изменено относительно исходного материала

Исходный материал был хорошей заготовкой по разработке проекта в стиле docs-as-code: он задавал цепочку от бизнес-требований к системному анализу, архитектуре, доменной модели, sequence diagrams, контрактам, данным, implementation tasks, коду, тестам, Docker, деплою и runbook. Однако значительная часть примеров была ориентирована на торговую систему, batch clearing, Kafka `fills`, PostgreSQL `floworders`, ClickHouse `batchresults` и сервисы matching/risk/ledger.

В этой версии материал скорректирован под другой предмет: **мультиагентную систему, которая через диалог, RAG и LangGraph формирует признаки, synthetic data, training config и ML pipeline**.

Главные изменения:

1. Убраны торговые примеры `F-04 Batch Clearing`, `FlowOrder`, `BatchResult`, `FillEvent`.
2. Добавлены фичи, use cases и контракты для мультиагентного Feature Engineering Bot.
3. Добавлены разделы по агентам, LangGraph, ContextMemory, RAG-документам, RAG-чонкам, metadata, prompts и validators.
4. Добавлены отдельные тесты для RAG retrieval, prompts, structured outputs и graph transitions.
5. Docker/Compose примеры заменены на стек: FastAPI, LangGraph app, Ollama, Vector DB, PostgreSQL, MinIO, workers.
6. `CLAUDE.md` дополнен `AGENTS.md`, `.claude/skills/`, `rag/`, `schemas/`, `prompts/`, `validators/`.
7. Главный принцип изменён с:

```text
требование → feature → use case → sequence diagrams → contracts → data → implementation task → code
```

на:

```text
требование
  → feature
  → use case
  → C4 architecture
  → agent design
  → ContextMemory schema
  → RAG ontology/cards/chunks
  → structured output contracts
  → LangGraph workflow
  → validators/tools
  → implementation task
  → code
  → tests
  → Docker
  → deploy
  → observability/runbook
```

---

## 1. Главная идея разработки мультиагентной системы

Мультиагентная система не должна разрабатываться как «один чат с LLM». Она должна разрабатываться как **stateful workflow**, где:

```text
LangGraph управляет процессом;
ContextMemory хранит состояние;
RAG предоставляет проверяемые знания;
маленькая LLM выполняет узкие задачи;
Pydantic задаёт контракты;
validators проверяют результаты;
Python tools выполняют вычисления;
Export Service создаёт файлы.
```

Целевая система проходит 7 фаз:

```text
0. Initialization
1. Task Discovery
2. Data Profiling
3. Domain Context
4. Feature Synthesis
5. Data Generation
6. Model Selection
7. Export
```

Главный результат системы:

```text
описание ML-задачи
  → ContextMemory
  → Evidence Pack
  → FeatureSpec
  → GenerationSpec
  → X_train.csv / y_train.npy
  → training_config.yaml
  → pipeline.py
  → metadata.json
  → archive.zip
```

---

## 2. Роль Claude Code в таком проекте

Claude Code используется не как «генератор кода по просьбе», а как инженерный помощник, который помогает поддерживать сквозную трассируемость:

```text
бизнес-требования
  → системные требования
  → C4-архитектура
  → агенты
  → RAG-документы
  → схемы состояния
  → structured output contracts
  → validators
  → implementation tasks
  → код
  → тесты
  → runbooks
```

Правильная роль Claude Code:

```text
- читать и актуализировать docs-as-code;
- генерировать черновики артефактов;
- создавать Pydantic-схемы по спецификациям;
- готовить implementation tasks;
- писать код только после документов и контрактов;
- запускать тесты и валидаторы;
- проверять consistency между docs, schemas, code и tests.
```

Неправильная роль Claude Code:

```text
- “напиши весь проект”;
- “сделай агента” без схемы входа/выхода;
- “сгенерируй RAG” без metadata schema;
- “напиши LangGraph” без state machine;
- “создай данные” без GenerationSpec и validators.
```

---

## 3. Базовые принципы проекта

### 3.1. Docs-as-code

Все существенные решения хранятся в Markdown/YAML/JSON/Python-файлах репозитория.

```text
docs/     → требования, архитектура, use cases, агенты, RAG, тесты
schemas/  → Pydantic / JSON Schema контракты
rag/      → RAG-карточки, metadata, chunks, ontology
prompts/  → prompt templates для агентов
src/      → код
validators/ → deterministic checks
tests/    → тесты всех уровней
```

### 3.2. State-first

Перед кодом нужно определить `ContextMemory`.

```text
Если нет схемы состояния, LangGraph быстро превращается в хаотичный набор узлов.
```

### 3.3. RAG-first

Перед сложными агентами нужно определить:

```text
- ontology;
- doc types;
- metadata schema;
- chunk schema;
- retrieval policies;
- evidence pack format;
- retrieval tests.
```

### 3.4. Contract-first

Каждый агент возвращает строго типизированный результат.

Примеры контрактов:

```text
TaskDiscoveryResult
DataProfile
DomainContext
FeatureCandidate
FeatureSpec
ValidationReport
GenerationSpec
ModelRecommendation
ExportManifest
```

### 3.5. Test-first

Для каждого агента, RAG policy, validator и LangGraph transition должны быть тесты.

```text
Не только unit tests для кода, но и:
- RAG retrieval tests;
- prompt golden tests;
- schema validation tests;
- graph transition tests;
- synthetic data validation tests.
```

---

## 4. Рекомендуемая структура репозитория

```text
repo/
├── CLAUDE.md
├── AGENTS.md
├── README.md
├── pyproject.toml
├── Makefile
│
├── incoming-docs/
│   ├── index.md
│   └── raw/
│
├── docs/
│   ├── 00-methodology/
│   │   ├── repository-map.md
│   │   ├── development-process.md
│   │   ├── document-ingestion.md
│   │   ├── artifact-templates.md
│   │   ├── traceability-rules.md
│   │   └── prompt-engineering-rules.md
│   │
│   ├── 01-business/
│   │   ├── vision.md
│   │   ├── goals.md
│   │   ├── stakeholders.md
│   │   ├── constraints.md
│   │   └── glossary.md
│   │
│   ├── 02-system/
│   │   ├── system-overview.md
│   │   ├── actors.md
│   │   ├── functional-requirements.md
│   │   ├── non-functional-requirements.md
│   │   ├── features/
│   │   └── use-cases/
│   │
│   ├── 03-architecture/
│   │   ├── c4-context.md
│   │   ├── c4-container.md
│   │   ├── c4-component-agent-runtime.md
│   │   ├── c4-component-rag-service.md
│   │   ├── deployment-view.md
│   │   └── adr/
│   │
│   ├── 04-domain/
│   │   ├── domain-model.md
│   │   ├── entities.md
│   │   ├── value-objects.md
│   │   ├── domain-events.md
│   │   └── invariants.md
│   │
│   ├── 05-agents/
│   │   ├── agent-index.md
│   │   ├── nlu-agent.md
│   │   ├── rag-query-planner-agent.md
│   │   ├── data-profiling-agent.md
│   │   ├── domain-context-agent.md
│   │   ├── feature-synthesis-agent.md
│   │   ├── feature-critic-agent.md
│   │   ├── data-generation-spec-agent.md
│   │   ├── model-selection-agent.md
│   │   └── export-agent.md
│   │
│   ├── 06-rag/
│   │   ├── rag-overview.md
│   │   ├── ontology.md
│   │   ├── document-types.md
│   │   ├── metadata-schema.md
│   │   ├── chunk-schema.md
│   │   ├── retrieval-policies.md
│   │   ├── evidence-pack.md
│   │   └── ingestion-pipeline.md
│   │
│   ├── 07-contracts/
│   │   ├── context-memory.md
│   │   ├── structured-outputs.md
│   │   ├── feature-spec.md
│   │   ├── generation-spec.md
│   │   └── validation-report.md
│   │
│   ├── 08-data/
│   │   ├── source-data-model.md
│   │   ├── generated-data-model.md
│   │   ├── artifact-model.md
│   │   └── feature-store-model.md
│   │
│   ├── 09-langgraph/
│   │   ├── graph-overview.md
│   │   ├── state-machine.md
│   │   ├── nodes.md
│   │   ├── edges.md
│   │   ├── repair-loops.md
│   │   └── human-in-the-loop.md
│   │
│   ├── 10-testing/
│   │   ├── testing-strategy.md
│   │   ├── unit-tests.md
│   │   ├── component-tests.md
│   │   ├── integration-tests.md
│   │   ├── rag-evaluation.md
│   │   ├── prompt-evaluation.md
│   │   └── e2e-tests.md
│   │
│   ├── 11-operations/
│   │   ├── observability.md
│   │   ├── metrics.md
│   │   ├── runbook.md
│   │   └── deployment.md
│   │
│   ├── traceability/
│   │   ├── source-to-artifact-map.md
│   │   ├── requirements-to-tests.md
│   │   ├── agent-to-contract-map.md
│   │   └── rag-coverage-matrix.md
│   │
│   └── implementation-plan/
│       ├── README.md
│       └── FE-BOT-MVP.tasks.md
│
├── rag/
│   ├── ontology/
│   ├── cards/
│   │   ├── domain_profiles/
│   │   ├── schema_cards/
│   │   ├── feature_patterns/
│   │   ├── analytics_cards/
│   │   ├── validation_rules/
│   │   ├── question_templates/
│   │   └── examples/
│   ├── manifests/
│   │   ├── document_index.json
│   │   └── chunk_manifest.jsonl
│   └── relationships/
│       ├── graph_relationships.yaml
│       └── retrieval_policies.yaml
│
├── schemas/
│   ├── context_memory.py
│   ├── agent_outputs.py
│   ├── feature_spec.py
│   ├── generation_spec.py
│   ├── validation_report.py
│   └── export_manifest.py
│
├── prompts/
│   ├── nlu_agent.md
│   ├── data_profiling_agent.md
│   ├── feature_synthesis_agent.md
│   ├── feature_critic_agent.md
│   ├── generation_spec_agent.md
│   └── model_selection_agent.md
│
├── validators/
│   ├── context_validator.py
│   ├── feature_validator.py
│   ├── generation_spec_validator.py
│   ├── generated_data_validator.py
│   └── rag_metadata_validator.py
│
├── src/
│   └── fe_bot/
│       ├── api/
│       ├── graph/
│       ├── agents/
│       ├── rag/
│       ├── tools/
│       ├── data_generation/
│       ├── export/
│       └── observability/
│
├── tests/
│   ├── unit/
│   ├── component/
│   ├── integration/
│   ├── e2e/
│   ├── rag_eval/
│   └── prompt_eval/
│
├── infra/
│   ├── compose/
│   └── docker/
│
├── scripts/
│   ├── docs/
│   ├── rag/
│   ├── smoke/
│   └── dev/
│
└── .claude/
    └── skills/
        ├── ingest-docs/
        ├── generate-rag-cards/
        ├── generate-agent-contracts/
        ├── validate-traceability/
        └── create-implementation-plan/
```

---

## 5. CLAUDE.md для мультиагентной системы

`CLAUDE.md` — это постоянная проектная память для AI coding assistant. В ней должны быть правила, которые не нужно повторять в каждом запросе.

Пример:

```markdown
# CLAUDE.md

## Project

Feature Engineering & Data Generation Multi-Agent Platform.

Goal:
Help users define ML tasks, profile data, retrieve domain context, synthesize features, generate synthetic datasets, recommend models, and export ML artifacts.

## Core Principles

- Do not write production code before requirements, contracts, and tests exist.
- Use docs-as-code.
- Use contract-first development.
- Use state-first LangGraph design.
- Use RAG-first agent design.
- Use deterministic validators for correctness.
- LLM outputs are suggestions; validators are source of truth.

## Architecture

Main stack:
- Python
- FastAPI
- LangGraph
- Ollama local LLM
- Vector DB
- PostgreSQL
- MinIO or local artifact storage
- Pydantic
- Docker Compose

## Hard Rules

- Never invent database columns.
- Never invent RAG metadata.
- Every agent output must follow a Pydantic schema.
- Every feature must cite evidence_doc_ids.
- Every derived feature must list input_features.
- Every temporal feature must require timestamp and entity_id.
- Generated datasets are created by Python tools, not by LLM text generation.
- Do not bypass validators.

## Repository Rules

- Business requirements go to docs/01-business/.
- System features and use cases go to docs/02-system/.
- C4 architecture goes to docs/03-architecture/.
- Agent specs go to docs/05-agents/.
- RAG methodology goes to docs/06-rag/.
- Schemas go to schemas/.
- Prompt templates go to prompts/.
- RAG cards go to rag/cards/.
- LangGraph implementation goes to src/fe_bot/graph/.
- Agent implementation goes to src/fe_bot/agents/.

## Development Flow

1. Update docs.
2. Update contracts.
3. Update tests.
4. Implement code.
5. Run validators.
6. Update traceability.

## Do Not

- Do not create src/ code before docs and schemas.
- Do not generate large datasets in LLM responses.
- Do not use one giant prompt for the whole system.
- Do not create generic RAG documents without metadata.
```

---

## 6. AGENTS.md

`AGENTS.md` фиксирует список агентов, их ответственность, входы, выходы, tools и RAG policies.

```markdown
# AGENTS.md

## Agent Registry

| Agent | Phase | Purpose | Input | Output |
|---|---|---|---|---|
| NLUAgent | all | Parse user message | UserMessage + ContextMemory | ParsedUserInput |
| TaskDiscoveryAgent | discovery | Define task | ParsedUserInput + EvidencePack | TaskDiscoveryResult |
| DataProfilingAgent | data_profiling | Build data profile | ContextMemory + EvidencePack | DataProfile |
| DomainContextAgent | domain_context | Define domain factors | ContextMemory + RAG | DomainContext |
| FeatureSynthesisAgent | feature_synthesis | Generate feature candidates | ContextMemory + EvidencePack | FeatureCandidateSet |
| FeatureCriticAgent | feature_synthesis | Validate feature candidates | FeatureCandidateSet | ValidationReport |
| DataGenerationSpecAgent | data_generation | Create GenerationSpec | FeatureSpec + ContextMemory | GenerationSpec |
| ModelSelectionAgent | model_selection | Rank models | ContextMemory + EvidencePack | ModelRecommendation |
| ExportAgent | export | Build artifacts | ContextMemory | ExportManifest |

## Global Agent Rules

- Return JSON only when schema is expected.
- Include confidence.
- Include evidence_doc_ids where applicable.
- Set need_more_context=true if evidence is insufficient.
- Do not silently invent facts.
```

---

## 7. Шаг 1. Bootstrap проекта

Первый запрос к Claude Code должен создать не код, а проектную систему работы.

### 7.1. Запрос к Claude Code

```text
Проанализируй текущий репозиторий и подготовь bootstrap docs-as-code структуры для мультиагентной системы Feature Engineering Bot.

Сначала покажи план изменений и список файлов.
Код не генерируй.

Создать или обновить:
- CLAUDE.md
- AGENTS.md
- docs/00-methodology/
- docs/traceability/
- docs/implementation-plan/
- incoming-docs/index.md
- .claude/skills/ingest-docs/SKILL.md
- .claude/skills/generate-rag-cards/SKILL.md
- .claude/skills/generate-agent-contracts/SKILL.md

Правило:
не создавать src/ до появления business requirements, system features, use cases, C4 architecture, agent specs, RAG schemas, ContextMemory schema, structured output contracts и tests.
```

### 7.2. Что должно появиться

```text
CLAUDE.md
AGENTS.md
docs/00-methodology/repository-map.md
docs/00-methodology/development-process.md
docs/00-methodology/artifact-templates.md
docs/00-methodology/traceability-rules.md
docs/00-methodology/prompt-engineering-rules.md
docs/traceability/source-to-artifact-map.md
docs/traceability/coverage-matrix.md
docs/implementation-plan/README.md
.claude/skills/ingest-docs/SKILL.md
.claude/skills/generate-rag-cards/SKILL.md
.claude/skills/generate-agent-contracts/SKILL.md
```

### 7.3. Проверка результата

Человек проверяет:

```text
- структура репозитория соответствует целевой архитектуре;
- есть запрет на преждевременный код;
- есть отдельный AGENTS.md;
- есть правила RAG и contracts;
- есть traceability.
```

---

## 8. Шаг 2. Бизнес-требования

### 8.1. Цель

Ответить на вопрос:

```text
Зачем существует мультиагентная система и какую бизнес-ценность она даёт?
```

### 8.2. Артефакты

```text
docs/01-business/vision.md
docs/01-business/goals.md
docs/01-business/stakeholders.md
docs/01-business/constraints.md
docs/01-business/glossary.md
```

### 8.3. Запрос к Claude Code

```text
Сформируй бизнес-артефакты для мультиагентной системы Feature Engineering Bot.

Контекст:
Система должна через диалог помогать пользователю определить ML-задачу, собрать профиль данных, извлечь RAG-контекст, сформировать признаки, сгенерировать synthetic dataset, рекомендовать модель и экспортировать ML pipeline.

Создай:
- docs/01-business/vision.md
- docs/01-business/goals.md
- docs/01-business/stakeholders.md
- docs/01-business/constraints.md
- docs/01-business/glossary.md

Пока не создавай код.
В конце покажи вопросы и недостающие бизнес-решения.
```

### 8.4. Что проверять человеку

```text
- миссия понятна;
- целевые пользователи указаны;
- KPI измеримы;
- ограничения маленькой LLM явно зафиксированы;
- RAG и validators обозначены как обязательные части;
- термины ContextMemory, EvidencePack, FeatureSpec, GenerationSpec определены.
```

---

## 9. Шаг 3. Системный анализ

### 9.1. Цель

Ответить:

```text
Что система должна делать?
```

### 9.2. Артефакты

```text
docs/02-system/system-overview.md
docs/02-system/actors.md
docs/02-system/functional-requirements.md
docs/02-system/non-functional-requirements.md
docs/02-system/features/
docs/02-system/use-cases/
```

### 9.3. Запрос к Claude Code

```text
На основе бизнес-документов сформируй системный анализ для мультиагентной системы.

Создай:
- system-overview.md
- actors.md
- functional-requirements.md
- non-functional-requirements.md
- feature-index.md
- отдельные feature-файлы в docs/02-system/features/
- use case skeletons в docs/02-system/use-cases/

Каждая feature должна иметь:
- purpose
- business value
- related requirements
- related agents
- related RAG docs
- related contracts
- acceptance criteria
- source fragments

Код не создавать.
```

### 9.4. Пример feature-файла

```text
docs/02-system/features/F-04-feature-synthesis.md
```

```markdown
# F-04. Feature Synthesis

## Purpose

Сформировать набор ML-признаков на основе профиля данных, доменного контекста и RAG-документов.

## Business Value

Сократить время первичного feature engineering и получить объяснимый набор признаков, пригодный для прототипирования ML-модели.

## Related Requirements

- FR-Feature-001. Система должна предложить base features.
- FR-Feature-002. Система должна предложить derived features.
- FR-Feature-003. Система должна предложить interaction features.
- FR-Feature-004. Каждый признак должен иметь evidence_doc_ids.
- FR-Feature-005. Каждый признак должен пройти FeatureCriticAgent и deterministic validators.

## Related Agents

- FeatureSynthesisAgent
- FeatureCriticAgent
- RAGQueryPlannerAgent
- DataProfilingAgent

## Related Contracts

- FeatureCandidate
- FeatureSpec
- ValidationReport

## Related RAG Docs

- feature_pattern cards
- schema cards
- analytics cards
- validation_rule cards

## Acceptance Criteria

- final_features не пустой.
- Все признаки имеют name, role, dtype, description.
- Производные признаки имеют formula и input_features.
- Все input_features существуют в fields или уже рассчитанных признаках.
- Temporal features отклоняются, если temporal_importance=false.
- Каждый approved feature содержит evidence_doc_ids.
```

---

## 10. Шаг 4. Use cases

### 10.1. Цель

Ответить:

```text
Как пользователь проходит конкретный сценарий через систему?
```

### 10.2. Пример use case

```text
docs/02-system/use-cases/UC-FE-01-create-feature-set/use-case.md
```

```markdown
# UC-FE-01. Create Feature Set for ML Task

## Feature

- F-01 Task Discovery
- F-02 Data Profiling
- F-03 Domain Context
- F-04 Feature Synthesis

## Primary Actor

ML engineer / analyst.

## Supporting Actors

- RAG Knowledge Base Admin
- Domain Expert
- Data Scientist

## Preconditions

- Система запущена.
- RAG index построен.
- Пользователь готов описать ML-задачу.

## Trigger

Пользователь пишет:

```text
Нужен классификатор для определения типа морских целей по данным РЛС.
```

## Main Flow

1. NLUAgent извлекает task_type, domain, data_source.
2. TaskDiscoveryAgent уточняет target_variable и classes.
3. DataProfilingAgent собирает data_volume, data_type, fields, missing_data_strategy, class_distribution, temporal_importance.
4. DomainContextAgent извлекает critical_factors и interpretability_requirement.
5. RAGQueryPlannerAgent формирует retrieval plan.
6. RAGRetriever получает schema, feature_pattern, analytics и validation_rule cards.
7. EvidencePackBuilder собирает compact evidence pack.
8. FeatureSynthesisAgent генерирует FeatureCandidateSet.
9. FeatureCriticAgent проверяет признаки.
10. Пользователь подтверждает final_features.

## Alternative Flows

### A1. Недостаточно данных о fields

DataProfilingAgent задаёт уточняющий вопрос.

### A2. RAG evidence недостаточен

Агент возвращает need_more_context=true и просит уточнить домен или источник данных.

### A3. Признак требует temporal data

FeatureCriticAgent отклоняет признак или запрашивает timestamp/track_id.

## Postconditions

- ContextMemory содержит final_features.
- ValidationReport сохранён.
- Evidence doc ids сохранены.
- Можно переходить к Data Generation.

## Related Agents

- NLUAgent
- DataProfilingAgent
- DomainContextAgent
- FeatureSynthesisAgent
- FeatureCriticAgent

## Related Contracts

- ContextMemory
- DataProfile
- EvidencePack
- FeatureCandidateSet
- ValidationReport
```

---

## 11. Шаг 5. C4-архитектура

### 11.1. Цель

Ответить:

```text
Как система устроена на уровнях Context, Container, Component, Code?
```

### 11.2. Артефакты

```text
docs/03-architecture/c4-context.md
docs/03-architecture/c4-container.md
docs/03-architecture/c4-component-agent-runtime.md
docs/03-architecture/c4-component-rag-service.md
docs/03-architecture/deployment-view.md
docs/03-architecture/adr/
```

### 11.3. Запрос к Claude Code

```text
Сформируй C4-архитектуру мультиагентной системы Feature Engineering Bot.

Создай:
- c4-context.md
- c4-container.md
- c4-component-agent-runtime.md
- c4-component-rag-service.md
- deployment-view.md
- ADR для ключевых решений

Учесть контейнеры:
- Web Chat UI
- FastAPI Backend
- LangGraph Orchestrator
- Agent Runtime
- RAG Service
- LLM Gateway
- Data Generation Worker
- Validation Worker
- Export Service
- Conversation DB
- Vector DB
- Artifact Storage
- Observability

Код не создавать.
```

### 11.4. Пример ADR

```text
docs/03-architecture/adr/ADR-001-langgraph-as-orchestrator.md
```

```markdown
# ADR-001. Use LangGraph as Workflow Orchestrator

## Status

Accepted

## Context

Система проходит 7 фаз и должна поддерживать branching, repair loops, human review, persistence и typed state.

## Decision

Использовать LangGraph StateGraph как основной оркестратор.

## Consequences

- Все агенты работают через ContextMemory.
- Переходы между фазами задаются явно.
- Repair loops ограничены max_retries.
- Human-in-the-loop возможен через interrupt points.
```

---

## 12. Шаг 6. Доменная модель

### 12.1. Цель

Ответить:

```text
Какие основные понятия существуют в системе?
```

### 12.2. Артефакты

```text
docs/04-domain/domain-model.md
docs/04-domain/entities.md
docs/04-domain/value-objects.md
docs/04-domain/domain-events.md
docs/04-domain/invariants.md
```

### 12.3. Пример доменных сущностей

```text
Conversation
ContextMemory
EvidencePack
RAGDocument
RAGChunk
AgentRun
FeatureCandidate
FeatureSpec
ValidationReport
GenerationSpec
GeneratedDataset
ModelRecommendation
ExportManifest
```

### 12.4. Пример инвариантов

```text
ContextMemory.conversation_id обязателен.
FeatureSpec.name уникален внутри final_features.
FeatureSpec.input_features должны существовать.
FeatureSpec.evidence_doc_ids не пустой для approved features.
GenerationSpec.n_samples должен быть > 0.
Class priors должны суммироваться к 1.0 ± tolerance.
Generated dataset не должен содержать NaN/inf, если missing_data_strategy=none.
```

---

## 13. Шаг 7. Agent design

### 13.1. Цель

Ответить:

```text
Какие агенты есть, за что они отвечают, какие схемы используют?
```

### 13.2. Артефакты

```text
docs/05-agents/agent-index.md
docs/05-agents/*.md
AGENTS.md
schemas/agent_outputs.py
prompts/*.md
```

### 13.3. Шаблон описания агента

```markdown
# FeatureSynthesisAgent

## Purpose

Generate feature candidates using ContextMemory and EvidencePack.

## Phase

PHASE_4_FEATURE_SYNTHESIS

## Input

- ContextMemory.fields
- ContextMemory.data_type
- ContextMemory.domain
- ContextMemory.temporal_importance
- EvidencePack.feature_patterns
- EvidencePack.schema_cards
- EvidencePack.validation_rules

## Output

FeatureCandidateSet

## Tools

- search_rag
- get_schema_card
- validate_feature_formula

## RAG Policy

```yaml
phase: feature_synthesis
doc_type:
  - feature_pattern
  - analytics_card
  - validation_rule
domain: current.domain
data_source: current.data_source
```

## Hard Rules

- Do not invent fields.
- Do not create temporal features without timestamp and entity_id.
- Every feature must cite evidence_doc_ids.
- Return JSON only.
```

---

## 14. Шаг 8. RAG design

### 14.1. Цель

Ответить:

```text
Какие знания нужны агентам и как они извлекаются?
```

### 14.2. Артефакты

```text
docs/06-rag/rag-overview.md
docs/06-rag/ontology.md
docs/06-rag/document-types.md
docs/06-rag/metadata-schema.md
docs/06-rag/chunk-schema.md
docs/06-rag/retrieval-policies.md
docs/06-rag/evidence-pack.md
docs/06-rag/ingestion-pipeline.md
rag/ontology/
rag/cards/
rag/manifests/
rag/relationships/
```

### 14.3. Основные типы RAG-документов

```text
ontology_card
schema_card
task_card
feature_pattern_card
analytics_card
validation_rule_card
question_template_card
example_card
bad_example_card
```

### 14.4. Пример RAG metadata schema

```yaml
doc_id: feature_pattern.signal_quality.v1
doc_type: feature_pattern
title: Signal quality feature pattern
phase:
  - feature_synthesis
  - validation
domain:
  - naval
data_source:
  - radar
task_type:
  - classification
feature_family: signal_quality
requires_fields:
  - snr
output_features:
  - signal_quality
validation_rules:
  - validation.snr_numeric.v1
  - validation.snr_range.v1
retrieval_tags:
  - radar
  - snr
  - signal quality
  - feature synthesis
confidence_level: high
version: 1.0
owner: ml_knowledge_team
```

### 14.5. Пример chunk metadata

```yaml
chunk_id: feature_pattern.signal_quality.v1.definition
doc_id: feature_pattern.signal_quality.v1
chunk_type: definition
phase: feature_synthesis
slot: derived_features
retrieval_purpose:
  - synthesize_features
  - explain_feature
canonical_feature: signal_quality
required_fields:
  - snr
embedding_text: "Signal quality feature for radar SNR. Normalize snr into signal_quality."
priority: 80
```

### 14.6. Запрос к Claude Code

```text
Создай RAG design документы для мультиагентной системы.

Нужно описать:
- ontology
- document types
- metadata schema for documents
- metadata schema for chunks
- retrieval policies by agent and phase
- evidence pack format
- ingestion pipeline
- validation rules for RAG docs

Код не создавать.
```

---

## 15. Шаг 9. ContextMemory schema

### 15.1. Цель

Ответить:

```text
Какое состояние передаётся между узлами LangGraph?
```

### 15.2. Артефакты

```text
docs/07-contracts/context-memory.md
schemas/context_memory.py
tests/unit/test_context_memory_schema.py
```

### 15.3. Минимальная структура

```yaml
conversation_id: string
current_phase: string
user_request: string

# Discovery
task_type: string | null
target_variable: string | null
domain: string | null
data_source: string | null

# Data Profiling
data_type: string | null
data_volume: int | string | null
fields: list
missing_data_strategy: string | null
class_distribution: dict | null
temporal_importance: bool | string | null

# Domain Context
critical_factors: list
interpretability_requirement: high | medium | low | null

# RAG
rag_queries: list
retrieved_docs: list
evidence_pack: dict | null

# Features
base_features: list
derived_features: list
interaction_features: list
final_features: list

# Data Generation
n_samples: int
noise_level: float
anomaly_rate: float
generation_spec: dict | null
generated_dataset: dict | null

# Model Selection
recommended_model: string | null
model_ranking: list
training_config: dict | null

# Export
artifacts: list
export_manifest: dict | null

# Control
errors: list
validation_reports: list
user_feedback: list
iteration: int
```

### 15.4. Запрос к Claude Code

```text
На основе docs/07-contracts/context-memory.md создай Pydantic-схему schemas/context_memory.py.

Перед кодом покажи план.
После кода создай unit tests:
- valid minimal state
- invalid phase
- invalid class_distribution sum
- invalid feature references
- downstream invalidation when fields changed
```

---

## 16. Шаг 10. Structured output contracts

### 16.1. Цель

Ответить:

```text
Какие JSON/Pydantic-ответы возвращают агенты?
```

### 16.2. Артефакты

```text
docs/07-contracts/structured-outputs.md
schemas/agent_outputs.py
schemas/feature_spec.py
schemas/generation_spec.py
schemas/validation_report.py
```

### 16.3. Пример FeatureSpec

```python
from pydantic import BaseModel, Field
from typing import Literal

class FeatureSpec(BaseModel):
    name: str
    role: Literal["base", "derived", "interaction", "temporal", "statistical"]
    dtype: str
    description: str
    formula: str | None = None
    input_features: list[str] = Field(default_factory=list)
    source_fields: list[str] = Field(default_factory=list)
    evidence_doc_ids: list[str]
    leakage_risk: Literal["low", "medium", "high"] = "low"
    validation_rules: list[str] = Field(default_factory=list)
    status: Literal["candidate", "approved", "rejected", "needs_review"] = "candidate"
```

### 16.4. Правило

```text
Любой агентный output без схемы считается недопустимым.
```

---

## 17. Шаг 11. LangGraph workflow

### 17.1. Цель

Ответить:

```text
Как агенты соединены в state machine?
```

### 17.2. Артефакты

```text
docs/09-langgraph/graph-overview.md
docs/09-langgraph/state-machine.md
docs/09-langgraph/nodes.md
docs/09-langgraph/edges.md
docs/09-langgraph/repair-loops.md
docs/09-langgraph/human-in-the-loop.md
src/fe_bot/graph/build_graph.py
```

### 17.3. Базовый граф

```text
START
  → NLUAgent
  → RAGQueryPlannerAgent
  → RAGRetriever
  → EvidencePackBuilder
  → route_by_phase
      ├─ TaskDiscoveryAgent
      ├─ DataProfilingAgent
      ├─ DomainContextAgent
      ├─ FeatureSynthesisAgent
      ├─ DataGenerationSpecAgent
      ├─ ModelSelectionAgent
      └─ ExportAgent
```

### 17.4. Repair loops

```text
FeatureSynthesisAgent
  → FeatureCriticAgent
  → ValidationWorker
  → if failed: FeatureSynthesisAgent
  → if passed: DataGenerationSpecAgent
```

```text
DataGenerationSpecAgent
  → GenerationSpecValidator
  → if failed: DataGenerationSpecAgent
  → if passed: DataGenerationWorker
```

### 17.5. Запрос к Claude Code

```text
Создай docs/09-langgraph/state-machine.md и предложи LangGraph graph skeleton.

Не реализуй агентов пока.
Сначала опиши:
- state schema
- nodes
- edges
- conditional routing
- repair loops
- max retries
- human review points
```

---

## 18. Шаг 12. Prompt templates

### 18.1. Цель

Создать короткие, стабильные prompts для маленькой LLM.

### 18.2. Артефакты

```text
prompts/nlu_agent.md
prompts/data_profiling_agent.md
prompts/feature_synthesis_agent.md
prompts/feature_critic_agent.md
prompts/generation_spec_agent.md
prompts/model_selection_agent.md
```

### 18.3. Пример prompt

```markdown
# FeatureSynthesisAgent Prompt

SYSTEM:
You are FeatureSynthesisAgent.
Your task is to generate ML feature candidates using ONLY provided ContextMemory and EvidencePack.
Return valid JSON only.

RULES:
1. Do not invent fields.
2. Every feature must include evidence_doc_ids.
3. Derived features must reference existing input_features.
4. If temporal_importance=false, do not create temporal features.
5. If evidence is insufficient, return need_more_context=true.

INPUT:
ContextMemory:
{context_memory}

EvidencePack:
{evidence_pack}

OUTPUT SCHEMA:
{feature_candidate_set_schema}
```

---

## 19. Шаг 13. Validators and tools

### 19.1. Цель

LLM не должна быть источником истины. Всё критичное проверяется кодом.

### 19.2. Артефакты

```text
validators/context_validator.py
validators/feature_validator.py
validators/generation_spec_validator.py
validators/generated_data_validator.py
validators/rag_metadata_validator.py
src/fe_bot/tools/
```

### 19.3. Минимальные validators

```text
ContextMemoryValidator
FeatureReferenceValidator
TemporalFeatureValidator
RAGMetadataValidator
GenerationSpecValidator
GeneratedDataValidator
ExportManifestValidator
```

### 19.4. Пример правил FeatureReferenceValidator

```text
- FeatureSpec.name unique.
- For derived features, input_features must exist.
- For interaction features, all referenced features must exist.
- Temporal feature requires timestamp and entity_id.
- Feature status=approved requires non-empty evidence_doc_ids.
```

---

## 20. Шаг 14. Data Generation

### 20.1. Принцип

Маленькая LLM не генерирует строки данных. Она генерирует `GenerationSpec`.

```text
LLM → GenerationSpec
Python Worker → X_train.csv, y_train.npy, metadata.json
Validator → ValidationReport
```

### 20.2. Артефакты

```text
docs/07-contracts/generation-spec.md
schemas/generation_spec.py
src/fe_bot/data_generation/generator.py
validators/generation_spec_validator.py
validators/generated_data_validator.py
```

### 20.3. Пример GenerationSpec

```json
{
  "generation_mode": "tabular_classification",
  "n_samples": 100000,
  "random_state": 42,
  "target": {
    "name": "target_class",
    "type": "multiclass",
    "classes": [
      {"id": 0, "name": "civilian_ship", "prior": 0.4},
      {"id": 1, "name": "military_ship", "prior": 0.3},
      {"id": 2, "name": "submarine", "prior": 0.2},
      {"id": 3, "name": "aircraft", "prior": 0.1}
    ]
  },
  "feature_specs": [
    {
      "name": "range",
      "role": "base",
      "distribution": {"type": "uniform", "min": 0, "max": 200}
    },
    {
      "name": "rcs_normalized",
      "role": "derived",
      "formula": "log1p(rcs)",
      "input_features": ["rcs"]
    }
  ],
  "noise": {"type": "gaussian", "std": 0.01},
  "anomalies": {"rate": 0.02, "type": "multiplicative_sensor_glitch"},
  "validation": {
    "expected_checks": ["no_nan", "no_inf", "class_distribution_balanced"]
  }
}
```

### 20.4. Тесты

```text
tests/unit/test_generation_spec_schema.py
tests/unit/test_generation_spec_validator.py
tests/component/test_data_generation_worker.py
tests/integration/test_data_generation_flow.py
```

---

## 21. Шаг 15. Model Selection

### 21.1. Цель

Выбрать top-N моделей и training config на основе ContextMemory.

### 21.2. Артефакты

```text
docs/02-system/features/F-06-model-selection.md
docs/05-agents/model-selection-agent.md
schemas/model_recommendation.py
prompts/model_selection_agent.md
```

### 21.3. Пример output

```json
{
  "recommended_model": "XGBoostClassifier",
  "model_ranking": [
    {
      "rank": 1,
      "model": "XGBoostClassifier",
      "reason": "Strong baseline for tabular multiclass classification",
      "pros": ["high accuracy", "feature importance"],
      "cons": ["requires tuning"]
    },
    {
      "rank": 2,
      "model": "RandomForestClassifier",
      "reason": "Robust and interpretable baseline"
    }
  ],
  "training_config": {
    "metrics": ["f1_macro", "balanced_accuracy", "confusion_matrix"],
    "validation": {"strategy": "stratified_k_fold", "n_splits": 5},
    "class_weight": "balanced",
    "random_state": 42
  }
}
```

---

## 22. Шаг 16. Export

### 22.1. Цель

Собрать результаты в воспроизводимый пакет.

### 22.2. Артефакты

```text
features.json
generation_spec.json
X_train.csv
y_train.npy
training_config.yaml
pipeline.py
data_generator.py
metadata.json
validation_report.json
archive.zip
```

### 22.3. ExportManifest

```json
{
  "conversation_id": "conv_001",
  "artifacts": [
    {"name": "features.json", "type": "feature_spec"},
    {"name": "generation_spec.json", "type": "generation_spec"},
    {"name": "X_train.csv", "type": "dataset_X"},
    {"name": "y_train.npy", "type": "dataset_y"},
    {"name": "training_config.yaml", "type": "training_config"},
    {"name": "pipeline.py", "type": "python_pipeline"},
    {"name": "metadata.json", "type": "metadata"}
  ]
}
```

---

## 23. Шаг 17. Implementation plan

### 23.1. Цель

Перед кодом получить список задач с трассировкой.

### 23.2. Где хранить

```text
docs/implementation-plan/FE-BOT-MVP.tasks.md
```

### 23.3. Запрос к Claude Code

```text
Создай implementation tasks для MVP мультиагентной системы.

Не меняй src/.

Задачи должны ссылаться на:
- feature document
- use case
- C4 component
- agent spec
- ContextMemory schema
- structured output schema
- RAG docs
- validators
- tests
- acceptance criteria
```

### 23.4. Пример tasks

```markdown
# Implementation Tasks: FE Bot MVP

## T-MA-001. Define ContextMemory schema

Target:
- docs/07-contracts/context-memory.md
- schemas/context_memory.py
- tests/unit/test_context_memory_schema.py

Acceptance:
- Pydantic schema validates minimal and full state.
- Invalid phase is rejected.
- class_distribution validation is implemented.

## T-MA-002. Implement RAG metadata validator

Target:
- validators/rag_metadata_validator.py
- tests/unit/test_rag_metadata_validator.py

Acceptance:
- doc_id required.
- doc_type must be allowed.
- phase and retrieval_purpose validated.
- chunk_id unique.

## T-MA-003. Implement DataProfilingAgent

Target:
- src/fe_bot/agents/data_profiling_agent.py
- prompts/data_profiling_agent.md
- tests/component/test_data_profiling_agent.py

Acceptance:
- extracts data_volume, data_type, fields, missing_data_strategy.
- normalizes field names using EvidencePack.
- returns DataProfile schema.

## T-MA-004. Implement FeatureSynthesisAgent

Target:
- src/fe_bot/agents/feature_synthesis_agent.py
- prompts/feature_synthesis_agent.md
- tests/component/test_feature_synthesis_agent.py

Acceptance:
- returns FeatureCandidateSet.
- all features cite evidence_doc_ids.
- no temporal features if temporal_importance=false.

## T-MA-005. Implement DataGenerationWorker

Target:
- src/fe_bot/data_generation/generator.py
- validators/generated_data_validator.py
- tests/component/test_data_generation_worker.py

Acceptance:
- creates X_train.csv and y_train.npy.
- validation report passes no_nan, no_inf, class balance checks.
```

---

## 24. Шаг 18. Написание кода с Claude Code

### 24.1. Хороший запрос

```text
Реализуй T-MA-003 из docs/implementation-plan/FE-BOT-MVP.tasks.md.

Перед изменениями:
1. прочитай связанные документы;
2. покажи план;
3. перечисли файлы, которые будешь менять.

После изменений:
1. запусти unit и component tests;
2. покажи diff summary;
3. обнови traceability matrix.
```

### 24.2. Плохой запрос

```text
Сделай мультиагентную систему.
```

Почему плохо:

```text
- нет границ задачи;
- нет связи с контрактами;
- нет тестов;
- нет RAG constraints;
- нет проверки LangGraph state.
```

---

## 25. Шаг 19. Тестирование

### 25.1. Unit tests

Проверяют чистые функции и схемы.

```text
schemas/context_memory.py
schemas/feature_spec.py
validators/feature_validator.py
validators/generation_spec_validator.py
```

Команды:

```bash
pytest tests/unit
```

### 25.2. Component tests

Проверяют одного агента или один service component.

```text
DataProfilingAgent + fake EvidencePack
FeatureSynthesisAgent + fake LLM output
GenerationSpecAgent + schema validation
RAGRetriever + fake vector store
```

Команды:

```bash
pytest tests/component
```

### 25.3. RAG evaluation tests

Проверяют retrieval quality.

Примеры:

```text
Запрос: "дальность, азимут, RCS, SNR"
Ожидается: radar field glossary + field definition cards.

Запрос: "признаки для сенсора"
Ожидается: sensor_analytics_T card.

Запрос: "оценка угрозы надводных контактов"
Ожидается: surface threat evaluation task card.
```

Команды:

```bash
pytest tests/rag_eval
```

### 25.4. Prompt evaluation tests

Проверяют, что маленькая LLM возвращает валидный JSON по schema.

```text
prompt_eval/data_profiling_agent_cases.yaml
prompt_eval/feature_synthesis_agent_cases.yaml
prompt_eval/generation_spec_agent_cases.yaml
```

Команды:

```bash
pytest tests/prompt_eval
```

### 25.5. Integration tests

Проверяют полный backend flow.

```text
FastAPI → LangGraph → RAG → Ollama mock → Validators → Artifact Storage
```

Команды:

```bash
pytest tests/integration
```

### 25.6. E2E tests

Проверяют пользовательский happy path.

```text
User starts chat
→ task discovery
→ data profiling
→ feature synthesis
→ data generation
→ model selection
→ export
```

Команды:

```bash
pytest tests/e2e
```

---

## 26. Шаг 20. Локальная инфраструктура Docker Compose

### 26.1. MVP stack

```text
FastAPI Backend
LangGraph app
Ollama
Vector DB
PostgreSQL
MinIO
Prometheus/Grafana optional
```

### 26.2. Compose пример

```yaml
services:
  postgres:
    image: postgres:16
    profiles: ["infra"]
    environment:
      POSTGRES_DB: fe_bot
      POSTGRES_USER: fe_bot
      POSTGRES_PASSWORD: fe_bot
    ports:
      - "5432:5432"

  qdrant:
    image: qdrant/qdrant:latest
    profiles: ["infra"]
    ports:
      - "6333:6333"

  minio:
    image: minio/minio:latest
    profiles: ["infra"]
    command: server /data --console-address ":9001"
    ports:
      - "9000:9000"
      - "9001:9001"

  ollama:
    image: ollama/ollama:latest
    profiles: ["llm"]
    ports:
      - "11434:11434"

  api:
    build:
      context: ../..
      dockerfile: infra/docker/api.Dockerfile
    profiles: ["app"]
    environment:
      DATABASE_URL: postgresql://fe_bot:fe_bot@postgres:5432/fe_bot
      VECTOR_DB_URL: http://qdrant:6333
      OLLAMA_BASE_URL: http://ollama:11434
      ARTIFACT_STORE_ENDPOINT: http://minio:9000
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - qdrant
      - ollama
      - minio
```

### 26.3. Запуск

```bash
docker compose -f infra/compose/docker-compose.yml --profile infra --profile llm up -d
```

```bash
make up-infra
```

Полный стек:

```bash
docker compose -f infra/compose/docker-compose.yml --profile infra --profile llm --profile app up --build
```

---

## 27. Шаг 21. Observability и runbooks

### 27.1. Что логировать

```text
conversation_id
agent_name
phase
node_name
trace_id
rag_query_id
retrieved_doc_ids
prompt_template_version
llm_model
llm_latency_ms
validation_status
artifact_id
```

### 27.2. Метрики

```text
fe_bot_requests_total
fe_bot_agent_runs_total
fe_bot_agent_latency_ms
fe_bot_rag_retrieval_latency_ms
fe_bot_rag_topk_hit_rate
fe_bot_llm_invalid_json_total
fe_bot_validation_failures_total
fe_bot_repair_loop_count
fe_bot_generated_datasets_total
fe_bot_export_success_total
```

### 27.3. Runbook

```text
docs/11-operations/runbook.md
```

Пример:

```markdown
# Runbook: Feature Synthesis returns invalid features

## Symptoms

- FeatureValidator rejects many features.
- Features reference unknown fields.
- temporal features appear when temporal_importance=false.

## Checks

1. Check ContextMemory.fields.
2. Check retrieved EvidencePack.
3. Check feature_synthesis_agent prompt version.
4. Check RAG retrieval policy for feature_synthesis.
5. Check validator logs.

## Actions

- Re-run RAG retrieval with stricter metadata filters.
- Ask user for missing fields.
- Mark feature as rejected with reason.
- Update RAG card if evidence is missing.
```

---

## 28. Makefile для мультиагентной системы

```makefile
.PHONY: docs-validate rag-validate rag-index test-unit test-component test-rag test-prompt test-integration test-e2e up-infra up-local-stack down logs smoke

docs-validate:
	python scripts/docs/validate_traceability.py

rag-validate:
	python scripts/rag/validate_rag_cards.py rag/cards rag/manifests/chunk_manifest.jsonl

rag-index:
	python scripts/rag/build_index.py --cards rag/cards --manifest rag/manifests/chunk_manifest.jsonl

test-unit:
	pytest tests/unit

test-component:
	pytest tests/component

test-rag:
	pytest tests/rag_eval

test-prompt:
	pytest tests/prompt_eval

test-integration:
	pytest tests/integration

test-e2e:
	pytest tests/e2e

up-infra:
	docker compose -f infra/compose/docker-compose.yml --profile infra --profile llm up -d

up-local-stack:
	docker compose -f infra/compose/docker-compose.yml --profile infra --profile llm --profile app up --build

down:
	docker compose -f infra/compose/docker-compose.yml down -v

logs:
	docker compose -f infra/compose/docker-compose.yml logs -f $(SERVICE)

smoke:
	bash scripts/smoke/smoke-local.sh
```

---

## 29. Daily workflow с Claude Code

### 29.1. Правило одна сессия — одна задача

Хорошо:

```text
Реализуй T-MA-004 FeatureSynthesisAgent.
Перед изменениями прочитай agent spec, prompt, schema и tests.
Сначала покажи план.
```

Плохо:

```text
Сделай всех агентов.
```

### 29.2. Перед каждой задачей

```text
1. Проверить git status.
2. Выбрать одну implementation task.
3. Передать Claude Code task id.
4. Попросить план.
5. Принять или поправить план.
6. Разрешить изменения.
7. Запустить tests.
8. Проверить diff.
9. Обновить traceability.
```

### 29.3. Стандартный запрос

```text
Выполни T-MA-002.

Контекст:
- docs/implementation-plan/FE-BOT-MVP.tasks.md
- docs/05-agents/rag-query-planner-agent.md
- docs/06-rag/retrieval-policies.md
- schemas/agent_outputs.py

Сначала:
1. прочитай документы;
2. покажи план;
3. перечисли файлы для изменения.

Затем:
1. внеси изменения;
2. запусти pytest для связанных тестов;
3. покажи diff summary;
4. обнови traceability.
```

---

## 30. 8-дневная учебная последовательность

### День 1. Bootstrap

```text
1. Создать repo.
2. Установить VS Code, Claude Code, Docker.
3. Создать CLAUDE.md.
4. Создать AGENTS.md.
5. Создать docs structure.
6. Создать базовые skills.
```

### День 2. Бизнес и система

```text
1. vision.md
2. goals.md
3. stakeholders.md
4. functional requirements
5. non-functional requirements
6. feature index
7. use case skeletons
```

### День 3. Архитектура и домен

```text
1. C4 context
2. C4 container
3. C4 component Agent Runtime
4. C4 component RAG Service
5. ADR
6. domain entities
7. invariants
```

### День 4. Агенты и ContextMemory

```text
1. agent registry
2. individual agent specs
3. ContextMemory schema
4. structured output schemas
5. prompt templates
```

### День 5. RAG

```text
1. ontology
2. document types
3. metadata schema
4. chunk schema
5. retrieval policies
6. evidence pack
7. RAG cards MVP
8. RAG evaluation tests
```

### День 6. LangGraph и validators

```text
1. state machine
2. nodes
3. edges
4. repair loops
5. validators
6. graph transition tests
```

### День 7. Реализация MVP

```text
1. FastAPI start/chat endpoints
2. LangGraph skeleton
3. NLUAgent mock/real
4. DataProfilingAgent
5. FeatureSynthesisAgent
6. DataGenerationWorker
7. ExportService
```

### День 8. Интеграция и эксплуатация

```text
1. Docker Compose stack
2. RAG index build
3. integration tests
4. e2e happy path
5. smoke tests
6. observability
7. runbook
```

---

## 31. Главные правила обучения команды

1. Не начинать с кода.
2. Не делать одного огромного агента.
3. Не писать RAG-документы без metadata.
4. Не принимать LLM output без Pydantic validation.
5. Не генерировать данные токенами LLM.
6. Не хранить состояние в истории чата.
7. Не смешивать разные фазы в одном prompt.
8. Не использовать один generic retrieval для всех агентов.
9. Не считать prompt engineering заменой validators.
10. Не пропускать traceability.

---

## 32. Итоговая формула процесса

```text
Business Need
  → System Feature
  → Use Case
  → C4 Architecture
  → Agent Spec
  → ContextMemory Contract
  → RAG Ontology + Cards
  → Structured Output Schema
  → Prompt Template
  → Validator
  → LangGraph Node
  → Tests
  → Code
  → Docker
  → Observability
  → Runbook
```

Именно такой порядок позволяет маленькой LLM работать устойчиво: она не решает всю задачу целиком, а выполняет маленькие строго определённые операции внутри контролируемого графа.

