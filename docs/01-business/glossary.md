# Глоссарий

Единый источник истины для терминов, используемых в документации, схемах, промптах и коде. Если термин есть в этом файле — пишите его именно так, не вводите синонимы.

## Базовые понятия

**Agent (агент).** Узкоспециализированный единица, потребляющая типизированный вход из `ContextMemory` (и опционально `EvidencePack`), возвращающая Pydantic-валидированный вывод и зарегистрированная в [AGENTS.md](../../AGENTS.md).

**Conversation (диалог).** Пользовательская сессия, идентифицируемая `conversation_id`. Несёт ровно одну `ContextMemory`.

**ContextMemory.** Типизированный сериализуемый объект состояния, передаваемый между узлами LangGraph. Определён в `schemas/context_memory.py`; документирован в [docs/07-contracts/context-memory.md](../07-contracts/context-memory.md).

**Phase (фаза).** Этап workflow: `initialization`, `task_discovery`, `data_profiling`, `domain_context`, `feature_synthesis`, `data_generation`, `model_selection`, `export`.

**EvidencePack.** Компактный, agent-scoped срез RAG-результатов, собранный `EvidencePackBuilder` для конкретной фазы. Агенты читают именно его, а не сырые карточки.

**RAGCard.** Типизированный документ знаний в `rag/cards/<family>/<card_id>.yaml`. Имеет обязательную metadata. Семейства: ontology, schema, task, feature pattern, analytics, validation rule, question template, example, bad example.

**RAGChunk.** Извлекаемая единица, производная от карточки (определение / пример / правило / формула). Хранится со своим `chunk_id` и metadata; индексируется в векторном хранилище.

**FeatureCandidate.** Предложенный признак, ещё не прошедший валидацию.

**FeatureSpec.** Валидированное принятое определение признака с `evidence_doc_ids` и `input_features`.

**GenerationSpec.** Типизированное описание синтетического датасета. Потребляется Python-worker-ом; никогда — LLM.

**ValidationReport.** Типизированный машиночитаемый список находок валидатора (`passed`, `failed`, `warnings`), эмитируемый `validators/`.

**ExportManifest.** Типизированный список артефактов, произведённых `ExportAgent`.

## Роли признаков

**Base feature (базовый признак).** Берётся напрямую из исходного поля в `ContextMemory.fields`. Без формулы.

**Derived feature (производный признак).** Вычисляется из одного или нескольких существующих признаков по формуле. Перечисляет `input_features`.

**Interaction feature (признак взаимодействия).** Производный признак, чьи входы сами по себе базовые/производные и чья цель — захватить cross-feature сигнал.

**Temporal feature (временной признак).** Признак, чьё вычисление зависит от `timestamp` и `entity_id` (например, скользящее среднее по последним N событиям).

**Statistical feature (статистический признак).** Сводка по окну или группе (mean, std, count), не являющаяся строго временной.

## Агенты (кратко)

Полный реестр — в [AGENTS.md](../../AGENTS.md). Имена приведены здесь только для перекрёстных ссылок:

- `SessionAgent`, `NLUAgent`, `RAGRetrievalAgent`, `DialogueOrchestratorAgent`, `ContextMemoryAgent`, `TaskDiscoveryAgent`, `DataProfilingAgent`, `DomainContextAgent`, `FeatureSynthesisAgent`, `FeatureCriticAgent`, `MulticollinearityAgent`, `DataGenerationSpecAgent`, `ModelSelectionAgent`, `ExportAgent`, `FeedbackAgent`, `AuditAgent`.

## Примитивы workflow

**Node (узел).** Узел LangGraph — вызываемое, принимающее `ContextMemory` и возвращающее частичное обновление.

**Edge (переход).** Переход LangGraph, возможно условный.

**Repair loop (петля исправления).** Ограниченная петля, в которой неудачная валидация перезаходит в агента-производителя с приложенным отчётом валидатора; ограничена `max_retries`.

**Human-in-the-loop (HITL).** Точка прерывания, где пользователь ревьюит или редактирует state перед переходом (например, утверждает `final_features`).

## Данные / хранилище

**Vector DB.** Qdrant в MVP. Хранит embedded-чанки RAG с metadata-фильтрами.

**Conversation DB.** PostgreSQL. Хранит сериализованную `ContextMemory` по `conversation_id`.

**Artifact Storage.** MinIO (S3-совместимое). Хранит `archive.zip`, `X_train.csv`, `y_train.npy`, `pipeline.py` и т. д.

## Эталонный домен (Naval / Radar)

Используется как сквозной пример. Записи здесь описательные, а не нормативные для системы.

- **Range.** Дальность от РЛС до контакта (km или nm).
- **Azimuth.** Пеленг на контакт (градусы).
- **RCS.** Radar Cross-Section (м²). Мера обнаруживаемости объекта радаром.
- **SNR.** Отношение сигнал/шум (дБ).
- **Track.** Упорядоченная по времени серия обнаружений одного контакта, идентифицируемая `track_id`.
- **Классы контактов (пример).** `civilian_ship`, `military_ship`, `submarine`, `aircraft`.

## Аббревиатуры

- **FE-Bot.** Feature Engineering Bot — кодовое имя системы.
- **FR / NFR.** Functional Requirement / Non-Functional Requirement.
- **C4.** Виды архитектуры Context / Container / Component / Code.
- **ADR.** Architectural Decision Record.
- **RAG.** Retrieval-Augmented Generation.
- **LLM.** Large Language Model.
- **CV.** Cross-Validation (в `training_config`).

## Связанные документы

- [vision.md](vision.md)
- [constraints.md](constraints.md)
- [docs/04-domain/entities.md](../04-domain/entities.md)
