# Каталог сервисов

Этот каталог — детализация C4-уровня Container ([../c4-container.md](../c4-container.md)) до уровня логических сервисов. 38 сервисов (`SVC-01..SVC-38`), сгруппированных по стадиям. Используется для:

- планирования MVP (см. [mvp-service-set.md](mvp-service-set.md) — какие сервисы можно сгруппировать в один процесс),
- ревизии границ ответственности (`SVC-XX → DTO → external actors → service neighbours`),
- проверки покрытия фичами (каждая фича в [docs/02-system/features/](../../02-system/features/) опирается на как минимум один SVC).

## Группы

| Группа | Сервисы | Файл |
| --- | --- | --- |
| Внешние участники и системы | EXT-01..EXT-13 | [external-actors-and-systems.md](external-actors-and-systems.md) |
| Каталог DTO | DTO-01..DTO-53 | [data-transfer-objects.md](data-transfer-objects.md) |
| Соглашения по хранилищам | — | [storage-conventions.md](storage-conventions.md) |
| Пользовательский слой | SVC-01..SVC-03 | [user-frontend.md](user-frontend.md) |
| Сервисы настройки RAG-базы | SVC-04..SVC-15 | [setup-services.md](setup-services.md) |
| Runtime-сервисы мультиагентной системы | SVC-16..SVC-34 | [runtime-services.md](runtime-services.md) |
| Аналитика и эксплуатация | SVC-35..SVC-38 | [analytics-and-ops-services.md](analytics-and-ops-services.md) |
| Краткая схема взаимодействий | — | [service-interactions.md](service-interactions.md) |
| Минимальный набор для MVP | — | [mvp-service-set.md](mvp-service-set.md) |

## Шаблон описания сервиса

Каждый SVC описан по 8 секциям:

1. **Назначение.** Зачем существует.
2. **Функции.** Что именно делает.
3. **DTO сервиса.** Какие DTO потребляет/возвращает.
4. **Внешние участники.** Кто из людей/внешних систем взаимодействует.
5. **Соседние сервисы.** Какие SVC ходят к этому и куда ходит он.
6. **Состав информационного обмена.** Что и с кем меняется по содержанию.
7. **Входные данные.** Что приходит.
8. **Выходные данные.** Что отдаёт.

## Связь с другими уровнями документации

| SVC-XX | Соответствие на C4-уровне |
| --- | --- |
| SVC-01 Frontend UI | в составе `Web UI` контейнера [c4-container.md](../c4-container.md) |
| SVC-02 API Gateway / Backend API | контейнер `API Backend` |
| SVC-03 Auth Service | компонент API Backend (`Auth`) |
| SVC-04 Setup Orchestrator | контейнер [c4-component-setup-orchestrator.md](../c4-component-setup-orchestrator.md) |
| SVC-05..SVC-15 | компоненты внутри RAG Service / Setup Orchestrator (см. [c4-component-rag-service.md](../c4-component-rag-service.md)) |
| SVC-16..SVC-22 | компоненты Agent Runtime / LangGraph Orchestrator / RAG Service (см. [c4-component-agent-runtime.md](../c4-component-agent-runtime.md)) |
| SVC-23..SVC-30 | конкретные агентные реализации из [AGENTS.md](../../../AGENTS.md) |
| SVC-31..SVC-34 | Data Generation Worker / Validation Worker / Export Service |
| SVC-35..SVC-38 | сквозные сервисы (`Analytics`, `Audit`, `Notification`, `Artifact Storage`) |

## Принцип использования

- На уровне **C4 Container** мы группируем эти SVC в развёртываемые контейнеры (для laptop-MVP — практически в один Python-процесс).
- На уровне **C4 Component** мы описываем компоненты внутри контейнеров с акцентом на коллаборацию.
- На уровне **этого каталога** мы перечисляем все логические сервисы и их обязанности; при росте системы каждая SVC-запись может стать отдельным контейнером без изменений в обязанностях.

## Связанные документы

- [../c4-context.md](../c4-context.md)
- [../c4-container.md](../c4-container.md)
- [../c4-component-agent-runtime.md](../c4-component-agent-runtime.md)
- [../c4-component-rag-service.md](../c4-component-rag-service.md)
- [../c4-component-setup-orchestrator.md](../c4-component-setup-orchestrator.md)
- [../../02-system/features/feature-index.md](../../02-system/features/feature-index.md)
- [../../traceability/dto-to-service-map.md](../../traceability/dto-to-service-map.md) — карта DTO → SVC
- [../../../AGENTS.md](../../../AGENTS.md)
