# UC-FE-02. Создание набора признаков и экспорт ML-pipeline

## Фичи

- [RUNTIME-01..RUNTIME-12](../../features/feature-index.md) — все runtime-фазы.
- Опорные: [PLATFORM-02](../../features/PLATFORM-02-langgraph-orchestrator.md), [PLATFORM-03](../../features/PLATFORM-03-structured-output-contracts.md), [PLATFORM-04](../../features/PLATFORM-04-artifact-storage.md).

## Основной актор

ML-инженер / data scientist / аналитик.

## Поддерживающие акторы

- Локальная LLM (Ollama, `llama3.2`) — внутри NLU, Task Discovery, Data Profiling, Domain Context, Feature Synthesis, GenerationSpec, Model Selection.
- RAG Retrieval Service поверх активной KB.
- DataGenerationWorker (Python) — генерация датасета.
- Validation Workers — валидаторы признаков, спецификации, датасета.

## Предусловия

- Активная Knowledge Base существует (`UC-FE-01` завершён успешно).
- У пользователя есть представление о доменной задаче (текстовая формулировка достаточна).

## Триггер

Пользователь открывает чат и пишет, например: *«Нужен классификатор типа морской цели по данным РЛС»*.

## Основной поток

1. **Initialization.** `SessionAgent` создаёт `conversation_id`, инициализирует пустую `ContextMemory` со ссылкой на активную `kb_version`, ставит `current_phase = task_discovery`. UI показывает welcome + первый prompt.
2. **Task Discovery (RUNTIME-02 + RUNTIME-03).** `NLUAgent` распарсивает шаг в `intent=describe_task` + entities. `TaskDiscoveryAgent` фиксирует `task_type=classification`, `domain=naval`, `data_source=radar`, `target_variable=target_type`. Задаёт уточнение: *«Какие классы целей различать?»* Пользователь отвечает `civilian_ship, military_ship, submarine, aircraft`.
3. **Data Profiling (RUNTIME-04).** `DataProfilingAgent` через серию шагов собирает `data_volume=50000`, `data_type=tabular`, `fields=[range, azimuth, elevation, rcs, snr, doppler]`, `missing_data_strategy=none`, `class_distribution={civilian_ship: 0.4, military_ship: 0.3, submarine: 0.2, aircraft: 0.1}`, `temporal_importance=false`.
4. **Domain Context (RUNTIME-05).** `DomainContextAgent` + `RAGRetrievalAgent` поднимают `domain_profile` и `analytics_card`-ы naval-radar, предлагают `critical_factors=[range, rcs, snr, doppler, radar_performance_factor, jamming_level]`, `interpretability_requirement=high`. Пользователь подтверждает.
5. **Feature Synthesis (RUNTIME-06).** `FeatureSynthesisAgent` эмитит 19 кандидатов признаков (6 base + 8 derived + 5 interaction) с `evidence_doc_ids` для каждого.
6. **Feature Validation (RUNTIME-07).** `FeatureCriticAgent` + `MulticollinearityAgent` отвергают временные признаки (т. к. `temporal_importance=false`), помечают дубли по корреляции, проверяют формулы и existence input-полей.
7. **Human Review (RUNTIME-08).** Пользователь видит итоговый набор; жмёт **Confirm**. `ContextMemory.final_features` фиксируется.
8. **GenerationSpec (RUNTIME-09).** `DataGenerationSpecAgent` собирает `GenerationSpec` с `n_samples=100000`, `random_state=42`, `noise_level=0.01`, `anomaly_rate=0.02`, class priors и distributions per feature. `generation_spec_validator` подтверждает.
9. **Data Generation (RUNTIME-10).** `DataGenerationWorker` производит `X_train.csv` (100k × 19), `y_train.npy`, `metadata.json`. `generated_data_validator` подтверждает.
10. **Model Selection (RUNTIME-11).** `ModelSelectionAgent` рекомендует `XGBoostClassifier` (top-1), `RandomForestClassifier`, `BayesianNetwork` (с обоснованием каждой). Пользователь принимает top-1. Эмитится `training_config.yaml` с `f1_macro`, stratified 5-fold CV, `class_weight: balanced`.
11. **Export (RUNTIME-12).** `ExportAgent` собирает 9 артефактов, `export_manifest_validator` подтверждает, Export Service пакует `archive.zip` и кладёт в conversation-scoped MinIO.
12. Пользователь видит ссылку **Download** в Download Manager и скачивает архив.
13. Audit Service фиксирует цепочку от исходных документов KB до `archive.zip`.

## Альтернативные потоки

### A1. NLU вернул низкий confidence

`NLUAgent` эмитит `need_more_context=true` + конкретный уточняющий вопрос (например, *«Это классификация или регрессия?»*). Оркестратор не продвигает фазу.

### A2. Data Profiling: неизвестное поле

Пользователь ввёл `СНРМ` (вместо `SNR`). Schema-карточки не находят канонического имени. Поле сохраняется как `custom_field` с `requires_review=true`, агент задаёт уточняющий вопрос с примерами из glossary.

### A3. Feature Critic отверг ≥ 50 % признаков

Оркестратор возвращает в `FeatureSynthesisAgent` с приложенным `ValidationReport` (repair loop, `max_retries=3`). После исчерпания retry система предлагает пользователю отредактировать `temporal_importance` или `fields`.

### A4. Пользователь редактирует признаки

В Human Review пользователь удаляет два признака и добавляет один новый. Действие триггерит мини-цикл synthesis + validation для добавленного. `final_features` фиксируется после повторного **Confirm**.

### A5. Generated dataset не прошёл валидацию

Например, фактическое class distribution отклонилось от запрошенного > 1 %. `GeneratedDataValidator` фейлит. Pipeline возвращается в `DataGenerationSpecAgent` для коррекции (например, увеличить `n_samples`).

### A6. Пользователь хочет другую модель

В RUNTIME-11 пользователь жмёт **Override**, выбирает `RandomForestClassifier`. Действие фиксируется в audit; `training_config.yaml` перегенерируется под выбранную модель.

### A7. `restart`

В любой момент пользователь пишет *«Начнём с начала»*. `NLUAgent` распознаёт intent `restart`. Текущая `ContextMemory` сбрасывается, создаётся новый `conversation_id`, прежняя сессия остаётся в audit.

## Постусловия

- `ContextMemory` для `conversation_id` сохраняет `final_features`, `generation_spec`, `recommended_model`, `training_config`, `artifacts`, `export_manifest`.
- `archive.zip` лежит в conversation-scoped MinIO; download-ссылка валидна до TTL.
- Audit-цепочка от source documents → cards → chunks → evidence pack → agents → features → dataset → model → archive — построена.

## Связанные агенты

`SessionAgent`, `NLUAgent`, `RAGRetrievalAgent`, `TaskDiscoveryAgent`, `DataProfilingAgent`, `DomainContextAgent`, `FeatureSynthesisAgent`, `FeatureCriticAgent`, `MulticollinearityAgent`, `DataGenerationSpecAgent`, `ModelSelectionAgent`, `ExportAgent`, `AuditAgent`.

## Связанные контракты

`ParsedUserInput`, `TaskDiscoveryResult`, `DataProfile`, `DomainContext`, `EvidencePack`, `FeatureCandidateSet`, `ValidationReport`, `MulticollinearityReport`, `FeatureSpec`, `GenerationSpec`, `GeneratedDataset`, `ModelRecommendation`, `TrainingConfig`, `ExportManifest`.
