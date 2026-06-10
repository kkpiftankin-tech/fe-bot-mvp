# AGENTS.md

Авторитетный реестр агентов мультиагентной системы FE-Bot. У каждого перечисленного здесь агента ОБЯЗАНЫ быть:

- спецификация в [docs/05-agents/](docs/05-agents/),
- output-схема в [schemas/agent_outputs.py](schemas/agent_outputs.py) или отдельном файле под [schemas/](schemas/),
- шаблон промпта в [prompts/](prompts/),
- детерминированный валидатор в [validators/](validators/) (где применимо),
- component-тесты в [tests/component/](tests/component/),
- строка в [docs/traceability/agent-to-contract-map.md](docs/traceability/agent-to-contract-map.md).

## Реестр агентов

| Агент | Фаза | Назначение | Вход | Выход |
| --- | --- | --- | --- | --- |
| `SessionAgent` | initialization | Создание/восстановление пользовательской сессии и `ContextMemory` | Запрос на старт, `conversation_id` | Активная сессия |
| `NLUAgent` | all | Парсинг сообщения пользователя в intent + entities | `UserMessage`, `ContextMemory` | `ParsedUserInput` |
| `RAGRetrievalAgent` | all | Извлечение релевантного контекста по metadata-фильтрам | Запрос, текущая фаза, фильтры | `EvidencePack` |
| `DialogueOrchestratorAgent` | all | Маршрутизация переходов между фазами (LangGraph) | `ParsedUserInput`, `ContextMemory` | Следующая фаза, действие |
| `ContextMemoryAgent` | all | Поддержание типизированного состояния диалога | Извлечённые сущности, ответы пользователя | Обновлённый `ContextMemory` |
| `TaskDiscoveryAgent` | task_discovery | Определение ML-задачи, target, классов | `ParsedUserInput`, `EvidencePack` | `TaskDiscoveryResult` |
| `DataProfilingAgent` | data_profiling | Сбор профиля данных (поля, объём, распределение) | `ContextMemory`, `EvidencePack` | `DataProfile` |
| `DomainContextAgent` | domain_context | Извлечение критичных доменных факторов | `ContextMemory`, RAG evidence | `DomainContext` |
| `FeatureSynthesisAgent` | feature_synthesis | Генерация кандидатов признаков | `ContextMemory`, `EvidencePack` | `FeatureCandidateSet` |
| `FeatureCriticAgent` | feature_synthesis | Валидация кандидатов признаков по правилам | `FeatureCandidateSet` | `ValidationReport` |
| `MulticollinearityAgent` | feature_synthesis | Проверка корреляций / VIF между признаками | Кандидаты + (синтетические) данные | `MulticollinearityReport` |
| `DataGenerationSpecAgent` | data_generation | Формирование `GenerationSpec` для синтетического датасета | `FeatureSpec`, `ContextMemory` | `GenerationSpec` |
| `ModelSelectionAgent` | model_selection | Ранжирование моделей + формирование training config | `ContextMemory`, `EvidencePack` | `ModelRecommendation` |
| `ExportAgent` | export | Сборка пакета артефактов + manifest | `ContextMemory` | `ExportManifest` |
| `FeedbackAgent` | all | Обработка пользовательских подтверждений и изменений | Действия пользователя | Маршрутизация / подтверждение |
| `AuditAgent` | all | Запись событий и решений в audit trail | Изменения state, выводы агентов | Audit record |

## Глобальные правила агентов

- **Только JSON** там, где ожидается схема. Свободный текст — только вне узлов структурированного вывода.
- Всегда включать `confidence` в `[0.0, 1.0]`.
- Всегда включать `evidence_doc_ids`, когда ответ зависит от RAG.
- Установить `need_more_context: true`, если evidence недостаточно — не выдумывать факты молча.
- Никогда не выдумывать значения `fields`, `doc_id` или `chunk_id`.
- Не выходить за пределы входных данных — не лезть в RAG-документы, которых нет в `EvidencePack`.

## Шаблон контракта агента

Каждая спецификация в `docs/05-agents/<agent-name>.md` ОБЯЗАНА содержать:

1. `Purpose` — назначение.
2. `Phase` — фаза.
3. `Input` — поля, читаемые из `ContextMemory` + слоты `EvidencePack`.
4. `Output` — ссылка на схему.
5. `Tools` — Python-инструменты, доступные агенту.
6. `RAG Policy` — `phase`, `doc_type`, `domain`, фильтры.
7. `Hard Rules` — что агент не должен делать никогда.
8. `Failure Modes` — что делать, когда входа недостаточно.

## Соответствие сервисному каталогу

Каждый агент соответствует конкретному SVC-XX из [docs/03-architecture/services/runtime-services.md](docs/03-architecture/services/runtime-services.md):

| Агент | SVC | Файл |
| --- | --- | --- |
| `SessionAgent` | SVC-16 | [Session Service](docs/03-architecture/services/runtime-services.md#svc-16-session-service) |
| `NLUAgent` | SVC-23 | [NLU Agent Service](docs/03-architecture/services/runtime-services.md#svc-23-nlu-agent-service) |
| `RAGRetrievalAgent` | SVC-21 + SVC-22 | RAG Retrieval Service + Evidence Pack Builder |
| `DialogueOrchestratorAgent` | SVC-18 | LangGraph Orchestrator |
| `ContextMemoryAgent` | SVC-17 | ContextMemory Service |
| `TaskDiscoveryAgent` | SVC-24 | Task Discovery Agent Service |
| `DataProfilingAgent` | SVC-25 | Data Profiling Agent Service |
| `DomainContextAgent` | SVC-26 | Domain Context Agent Service |
| `FeatureSynthesisAgent` | SVC-27 | Feature Synthesis Agent Service |
| `FeatureCriticAgent` | SVC-28 (часть) | Feature Validation / Critic Service |
| `MulticollinearityAgent` | SVC-28 (часть) | Feature Validation / Critic Service |
| `DataGenerationSpecAgent` | SVC-30 | Data Generation Spec Agent Service |
| `ModelSelectionAgent` | SVC-33 | Model Selection Agent Service |
| `ExportAgent` | SVC-34 | Export Service |
| `FeedbackAgent` | SVC-29 | Human Review Service |
| `AuditAgent` | SVC-36 | Audit and Traceability Service |

## Добавление нового агента

1. Добавить строку в таблицу выше.
2. Создать `docs/05-agents/<agent-name>.md` из шаблона.
3. Добавить output-схему в `schemas/agent_outputs.py`.
4. Добавить шаблон промпта в `prompts/<agent_name>.md`.
5. Добавить валидатор (если применимо) в `validators/`.
6. Добавить component-тест в `tests/component/test_<agent_name>.py`.
7. Подключить к LangGraph в `src/fe_bot/graph/`.
8. Обновить [docs/traceability/agent-to-contract-map.md](docs/traceability/agent-to-contract-map.md).
