# Глоссарий

Единый источник истины для терминов, используемых в документации, схемах, промптах и коде. Если термин есть в этом файле — пишите его именно так, не вводите синонимы.

## Стадии и входы/выходы системы

**Stage (стадия).** Одна из трёх пользовательских частей системы: **Setup**, **Runtime**, **Analytics**. У каждой свой UI и свои критерии приёмки. Не путать с *phase* (фаза Runtime-диалога) и *step* (шаг Setup-мастера).

**Setup.** Стадия 1: мастер из 11 шагов, превращающий загруженные документы в опубликованную базу знаний.

**Runtime.** Стадия 2: управляемый ML-диалог, превращающий описание задачи в экспортируемый пакет.

**Analytics.** Стадия 3: дашборды и audit trail поверх событий Setup и Runtime.

**Knowledge Base / KB (база знаний).** Опубликованная версия RAG-корпуса (`kb_version`): утверждённые RAG-карточки, их чанки и векторный индекс. Выход Setup и обязательное условие входа Runtime. Одна активная KB на проект.

**Setup Job.** Долгая операция подготовки базы знаний (`setup_job_id`) с собственным жизненным циклом статусов: `draft` → … → `ready` / `failed` / `cancelled`.

**Source Document (исходный документ).** Файл, загруженный пользователем в Setup (`md`, `txt`, `pdf`, `docx`, `xlsx`, `csv`, `json`) и зарегистрированный в реестре источников.

**Parsed Section (секция).** Смысловой фрагмент исходного документа, извлечённый парсером и классифицированный по дереву классов; единица, из которой генерируется RAG-карточка.

**Classifier Library (библиотека классификаторов).** Редактируемое дерево классов произвольной глубины, по которому LLM классифицирует секции документов ([SETUP-13](../02-system/features/SETUP-13-classifier-library.md)). Редактируется в UI Setup; не привязано к конкретному Setup Job.

**Metadata-хинты узла (`metadata_hints`).** Опциональный блок на узле дерева классификаторов: `doc_type_hint`, `domain_hint`, `task_type_hint`, `data_source_hint`, `entity_type_hint`, `phase_hint`, `agent_targets_hint`, `retrieval_purpose_hint`. Наследуются вниз по дереву, более специфичный узел перекрывает общий. Из них выводятся тип и онтологические поля карточки без участия LLM ([SETUP-13 §8](../02-system/features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов), [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)).

**Разрешённые хинты (`resolved_hints`).** Итог слияния хинтов по пути классификации секции, с указанием узла-источника каждого значения. Часть результата классификации (`classifier_result`).

**Retrieval smoke test.** Контрольный запрос к новому индексу, проверяющий, что возвращается ожидаемое семейство документов; результаты (recall@k, precision@k, no-context rate) гейтят публикацию KB.

**Knowledge Base ready.** Итоговый сигнал Setup: KB опубликована, индекс готов, Runtime можно запускать.

**Archive (`archive.zip`).** Итоговый выход Runtime: девять файлов (`features.json`, `generation_spec.json`, `X_train.csv`, `y_train.npy`, `training_config.yaml`, `pipeline.py`, `data_generator.py`, `metadata.json`, `validation_report.json`). Состав и назначение — в [system-overview.md](../02-system/system-overview.md#runtime-выход).

**Синтетический датасет.** Обучающая выборка, построенная Python-инструментом по `GenerationSpec` для описанных пользователем данных. Реальные данные пользователя в систему не загружаются.

## Базовые понятия

**Agent (агент).** Узкоспециализированный единица, потребляющая типизированный вход из `ContextMemory` (и опционально `EvidencePack`), возвращающая Pydantic-валидированный вывод и зарегистрированная в [AGENTS.md](../../AGENTS.md).

**Conversation (диалог).** Пользовательская сессия, идентифицируемая `conversation_id`. Несёт ровно одну `ContextMemory`.

**ContextMemory.** Типизированный сериализуемый объект состояния, передаваемый между узлами LangGraph. Определён в `schemas/context_memory.py`; документирован в [docs/07-contracts/context-memory.md](../07-contracts/context-memory.md).

**Phase (фаза).** Этап Runtime-workflow: `initialization`, `task_discovery`, `data_profiling`, `domain_context`, `feature_synthesis`, `data_generation`, `model_selection`, `export`. Всего восемь значений; пользователь видит семь (без `initialization`).

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
- [docs/04-domain/taxonomy.md](../04-domain/taxonomy.md) — иерархическая таксономия секций (SETUP-12; замещена SETUP-13)
