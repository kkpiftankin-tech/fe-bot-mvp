# RAG-методология проекта

Этот документ — методологический манифест RAG-слоя FE-Bot. Он описывает **что такое RAG в проекте**, **зачем он нужен**, **в каких трёх режимах работает** и **как связан с агентами, ContextMemory и LLM**. Конкретные нормативы (схемы метаданных, статусы, retrieval-политики, evaluation) вынесены в отдельные документы — этот файл задаёт принципы, на которых они держатся.

## Главный тезис

RAG в этом проекте — это **не «поиск похожих текстов»**, а **управляемая, версионируемая, проверяемая база знаний**, которая связывает исходные документы, агентные решения, признаки, валидацию, модели, обучающие данные и экспортируемые артефакты.

Маленькая LLM (`llama3.2` через Ollama) не должна «помнить» предметную область внутри себя. Вместо этого система обязана:

1. Получать знания из загруженных пользователем документов.
2. Преобразовывать эти знания в структурированные RAG-карточки.
3. Индексировать карточки и chunks в векторной БД.
4. Извлекать релевантный контекст под конкретную фазу и агента.
5. Передавать агенту не сырой документ, а компактный `EvidencePack` (см. [evidence-pack.md](evidence-pack.md)).
6. Требовать, чтобы важные решения агентов ссылались на `evidence_doc_ids`.

## Полный жизненный цикл RAG

```text
загрузка пользовательского контента
  → нормализация источников
  → генерация RAG-карточек
  → metadata-разметка
  → chunking
  → embeddings
  → vector DB
  → retrieval policies
  → evidence pack
  → agent usage
  → evaluation
  → governance
  → analytics
```

## RAG как часть reasoning

Архитектура retrieval в этом проекте сознательно сложнее, чем «top-K по similarity»:

```text
user action / agent phase
  → workflow state (ContextMemory)
  → retrieval policy (agent + phase)
  → metadata filter (deterministic)
  → semantic search
  → reranking
  → graph expansion (related docs)
  → evidence pack (compact, slot-aware)
  → structured agent output
  → validation
  → ContextMemory update
```

Формально:

$$
\text{RAGResult} = f(\text{phase}, \text{agent}, \text{ContextMemory}, \text{metadata filters}, \text{semantic query}, \text{graph relationships})
$$

Retrieval является частью reasoning-процесса, а не отдельной чёрной коробкой.

## Три режима RAG

### Setup RAG

Пользовательский этап настройки базы знаний (видимый workflow через frontend, не скрытая backend-задача):

```text
Пользователь загружает документы
  → система формирует RAG-карточки
  → строит chunks
  → строит embeddings
  → создаёт vector index
  → запускает retrieval smoke tests
  → сообщает «Knowledge Base ready»
```

Покрывается фичами SETUP-01..SETUP-11 ([feature-index.md](../02-system/features/feature-index.md)).

### Runtime RAG

Использование базы знаний агентами во время диалога:

```text
NLU Agent
Data Profiling Agent
Domain Context Agent
Feature Synthesis Agent
Feature Critic Agent
Data Generation Spec Agent
Model Selection Agent
Export Agent
```

Каждый агент имеет собственную retrieval-политику ([retrieval-policies.md](retrieval-policies.md)).

### Analytics RAG

Анализ качества RAG-слоя:

- какие запросы не нашли контекст;
- какие документы часто используются;
- какие chunks не используются;
- какие карточки дают плохие retrieval results;
- где нужны новые RAG-карточки;
- какие agent outputs не имеют evidence.

Метрики и пороги — в [rag-quality.md](rag-quality.md).

## Роль RAG в жизненном цикле системы

### Настройка

RAG отвечает за превращение загруженных документов в управляемую базу знаний:

```text
source documents
  → parsed sections
  → RAG cards
  → approved RAG cards
  → chunks
  → embeddings
  → vector index
  → published Knowledge Base
```

Полная цепочка — в [ingestion-pipeline.md](ingestion-pipeline.md).

### Функционирование

RAG отвечает за то, чтобы каждый агент получал только релевантный контекст. Пример: если пользователь говорит «нужно оценивать угрозу от надводных целей по данным радара», RAG должен найти:

```text
task.surface_threat_evaluation
schema.tracks_fused
schema.tactical_object
analytics.object_analytics_T
analytics.environment_analytics_T
validation.requires_track_kinematics
```

### Аналитика

RAG поставляет данные для оценки качества:

```text
retrieval recall / precision
no_context_rate
evidence coverage
stale docs
unused docs
low-confidence docs
agent hallucination rate
```

## Разделение raw и normalized

Сырые документы и нормализованные карточки **не должны жить в одной директории**:

```text
incoming-docs/           — raw, непроверенные, неструктурированные материалы
rag/cards/               — структурированные RAG-карточки
rag/chunks/              — логические chunks для retrieval
rag/manifests/           — индексы документов, chunks и связей
rag/eval/                — тесты retrieval
rag/ontology/            — доменная онтология
rag/relationships/       — граф связей между карточками
```

## Принципы маленькой LLM

Маленькая LLM **не должна получать**:

- весь документ;
- десятки chunks;
- шумные фрагменты;
- противоречивые карточки;
- deprecated knowledge;
- непроверенные draft-карточки.

Маленькая LLM **должна получать**:

- короткий Evidence Pack;
- строгую задачу;
- structured output schema;
- список разрешённых полей;
- список `evidence_doc_ids`;
- validation rules;
- `missing_context` policy (`need_more_context: true` если evidence недостаточно).

Принцип качества:

$$
\text{LLM quality} \approx \text{small task} + \text{clean evidence} + \text{strict schema} + \text{validation}
$$

## RAG и ContextMemory

RAG-запросы строятся не из сырого текста пользователя, а из `ContextMemory` ([context-memory.md](../07-contracts/context-memory.md)). Например, если в ContextMemory:

```json
{
  "domain": "naval",
  "task_type": "classification",
  "data_source": "radar",
  "data_type": "tabular",
  "fields": ["range", "bearing", "course", "speed", "CPA", "TCPA"],
  "temporal_importance": true
}
```

то Feature Synthesis Agent выпускает запрос:

```text
doc_type ∈ {analytics_card, feature_pattern_card}
domain = naval
data_source = radar
phase = feature_synthesis
required_input_fields intersects fields
```

## Какие RAG-источники подходят для проекта

В `incoming-docs/raw/` могут попадать:

- Markdown, PDF, DOCX, XLSX, CSV, JSON;
- data dictionaries и схемы БД;
- описания задач;
- feature-store каталоги;
- регламенты, domain manuals;
- протоколы встреч, экспорт Jira;
- аналитические отчёты.

Эти материалы превращаются в карточки разных типов ([document-types.md](document-types.md)): `ontology_card`, `schema_card`, `task_card`, `analytics_card`, `feature_pattern_card`, `field_definition_card`, `validation_rule_card`, `question_template_card`, `model_recommendation_card`, `glossary_term`, `example_card`.

## Итоговая формула качества

$$
\text{RAG Quality} = \text{Ontology} + \text{Metadata} + \text{Chunking} + \text{Embeddings} + \text{Retrieval Policies} + \text{Evaluation} + \text{Governance}
$$

Практический итог:

```text
Без RAG агенты будут гадать.
С плохим RAG агенты будут уверенно ошибаться.
С правильным RAG маленькая LLM сможет стабильно выполнять узкие задачи,
потому что каждый её вывод будет опираться на проверяемый Evidence Pack.
```

## Связанные документы

- [rag-overview.md](rag-overview.md) — индекс RAG-документации
- [ontology.md](ontology.md) — словари доменов, задач, источников
- [document-types.md](document-types.md) — типы карточек
- [metadata-schema.md](metadata-schema.md) — нормативная схема metadata
- [chunk-schema.md](chunk-schema.md) — нормативная схема chunks
- [retrieval-policies.md](retrieval-policies.md) — per-agent retrieval policies
- [evidence-pack.md](evidence-pack.md) — формат пакета для агента
- [ingestion-pipeline.md](ingestion-pipeline.md) — Setup-пайплайн
- [rag-lifecycle.md](rag-lifecycle.md) — статусы, версионирование, governance
- [rag-quality.md](rag-quality.md) — валидация, evaluation, quality gates, observability
- [rag-failure-modes.md](rag-failure-modes.md) — failure handling
- [rag-security.md](rag-security.md) — доступ, изоляция, redaction
- [../07-contracts/context-memory.md](../07-contracts/context-memory.md)
