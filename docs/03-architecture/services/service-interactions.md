# Краткая схема взаимодействий

Высокоуровневая «лестница» вызовов между сервисами по стадиям. Подробности — в файлах per-сервис ([setup-services.md](setup-services.md), [runtime-services.md](runtime-services.md), [analytics-and-ops-services.md](analytics-and-ops-services.md)).

## Пользовательский слой

```text
Frontend UI (SVC-01)
  → API Gateway (SVC-02)
  → Auth Service (SVC-03)
```

Все остальные обращения к backend идут только через `SVC-02`.

## Setup-стадия

```text
API Gateway (SVC-02)
  → Setup Orchestrator (SVC-04)
       ├─→ Document Upload Service (SVC-05) ──► Artifact Storage (SVC-38)
       ├─→ Source Registry Service (SVC-06)
       ├─→ Document Parser Service (SVC-07)
       ├─→ RAG Card Generator (SVC-09) ──► LLM Gateway (SVC-20)
       ├─→ RAG Card Review Service (SVC-10) ◄── Frontend (SVC-01)
       ├─→ Ontology and Metadata Service (SVC-08)
       ├─→ Chunking Service (SVC-11)
       ├─→ Embedding Service (SVC-12) ──► EXT-08 Embedding Model
       ├─→ Vector Indexer Service (SVC-13) ──► EXT-09 Vector DB
       ├─→ Retrieval Evaluation Service (SVC-14)
       └─→ Knowledge Base Registry (SVC-15)
  → Notification Service (SVC-37)
  → Audit Service (SVC-36)
```

Внешний сигнал готовности: `kb_ready` → разблокировка Runtime.

## Runtime-стадия

```text
API Gateway (SVC-02)
  → Session Service (SVC-16) ──► ContextMemory Service (SVC-17)
  → LangGraph Orchestrator (SVC-18)
       ├─→ Agent Runtime (SVC-19)
       │    ├─→ NLU Agent (SVC-23)
       │    ├─→ Task Discovery Agent (SVC-24)
       │    ├─→ Data Profiling Agent (SVC-25)
       │    ├─→ Domain Context Agent (SVC-26)
       │    ├─→ Feature Synthesis Agent (SVC-27)
       │    ├─→ Feature Validation / Critic Service (SVC-28)
       │    ├─→ Data Generation Spec Agent (SVC-30)
       │    └─→ Model Selection Agent (SVC-33)
       ├─→ RAG Retrieval Service (SVC-21) ──► EXT-09 Vector DB
       │      └─→ Evidence Pack Builder (SVC-22)
       ├─→ LLM Gateway (SVC-20) ──► EXT-07 Ollama / LLM
       ├─→ Human Review Service (SVC-29) ◄── Frontend (SVC-01)
       └─→ Synthetic Data Worker (SVC-31)
              └─→ Dataset Validation Service (SVC-32)
                     └─► Artifact Storage (SVC-38)
  → Export Service (SVC-34) ──► Artifact Storage (SVC-38)
  → Notification Service (SVC-37)
  → Audit Service (SVC-36)
```

## Analytics-стадия

```text
Все runtime- и setup-сервисы
  ──► Analytics Service (SVC-35)
  ──► Audit and Traceability Service (SVC-36)
         └─► Frontend Analytics Dashboard (SVC-01)
```

## Сквозные направления

- **API Gateway** видим только из Frontend и тестов; внутрь стека ходит он, никто не ходит в Frontend «снизу».
- **LLM Gateway** — единственная точка контакта с локальной LLM. Никто не зовёт Ollama напрямую.
- **Artifact Storage Service** — единственная точка контакта с EXT-10. Никто не пишет в S3 напрямую.
- **Vector DB** — только через RAG Retrieval (Runtime) и Vector Indexer (Setup).
- **Audit Service** — пишут все важные сервисы; читают Analytics и Audit UI.

## Связанные документы

- [README.md](README.md)
- [setup-services.md](setup-services.md)
- [runtime-services.md](runtime-services.md)
- [analytics-and-ops-services.md](analytics-and-ops-services.md)
- [../c4-container.md](../c4-container.md)
