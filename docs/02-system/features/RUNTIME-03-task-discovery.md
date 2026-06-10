# RUNTIME-03. Task Discovery

## Назначение

Превратить свободнотекстовую формулировку проблемы пользователя в типизированное определение ML-задачи: `task_type`, `target_variable`, `classes` (для классификации), `domain`, `data_source`, `required_latency`, `deployment_context`. Якорь для каждой последующей фазы.

## Бизнес-ценность

Нижестоящие агенты (data profiling, feature synthesis, model selection) ветвятся по этим слотам. Без них остальной workflow не на что опереть RAG retrieval или генерацию признаков.

## Пользовательский сценарий

1. После того как [RUNTIME-02](RUNTIME-02-nlu.md) извлёк начальные слоты, `TaskDiscoveryAgent` дозаполняет остальное.
2. Для эталонного radar-входа: `task_type=classification`, `target_variable=target_type`, `domain=naval`, `data_source=radar`. Затем агент спрашивает: *«Какие классы вы хотите различать?»*
3. Пользователь отвечает именами классов; агент их фиксирует и продвигается к `data_profiling`.

## Связанные требования

- BR-FR-050..052 (task type, target variable, domain, data source).
- BR-FR-Conv-004 (конкретные уточняющие вопросы при отсутствии слотов).
- Поддерживаемые значения `task_type`: `classification`, `regression`, `clustering`, `anomaly_detection`, `ranking`.
- Поддерживаемые значения `deployment_context`: `edge_device`, `shipboard_server`, `cloud`, `offline_research`, `operator_decision_support`.

## Связанные агенты

- `TaskDiscoveryAgent`, `NLUAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `TaskDiscoveryResult` (`schemas/agent_outputs.py`).
- Слоты `ContextMemory`: `task_type`, `target_variable`, `classes`, `domain`, `data_source`, `required_latency`, `deployment_context`.

## Связанные RAG-документы

- `domain_profile`-карточки — снимают неоднозначность доменного языка и подсказывают типичные списки классов.
- `question_template`-карточки — clarification-промпты per-missing-slot.

## Критерии приёмки

- Для эталонного radar-входа discovery завершается за 1–2 шага пользователя.
- Когда `target_variable` не выводится, агент ОБЯЗАН эмитнуть точечное уточнение, не угадывая.
- Выход ОБЯЗАН проходить Pydantic-валидацию `TaskDiscoveryResult`; продвижение фазы иначе блокируется.
- Тест: `tests/component/test_task_discovery_agent.py`.
