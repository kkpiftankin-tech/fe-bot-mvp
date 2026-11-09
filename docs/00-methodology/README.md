# Точка входа: что это за система и как читать документацию

Этот каталог описывает **как мы работаем** (методология). Эта страница — ещё и ответ на вопрос «что вообще строим»: прочитайте её первой, а затем идите по ссылкам.

## Система за минуту

**FE-Bot** (Feature Engineering Bot) — мультиагентная платформа, которая через диалог помогает ML-инженеру пройти путь от идеи до воспроизводимого ML-пакета: уточнить задачу, описать данные, подобрать признаки с опорой на доменные знания, сгенерировать синтетическую обучающую выборку, выбрать модель и экспортировать всё это как запускаемый проект.

Система работает в три стадии:

| Стадия | Что делает | На входе | На выходе |
| --- | --- | --- | --- |
| **1. Setup** | Строит базу знаний по домену | Документы (`md`, `txt`, `pdf`, `docx`, `xlsx`, `csv`, `json`), параметры проекта, решения по карточкам | Опубликованная версия базы знаний («Knowledge Base ready») |
| **2. Runtime** | Ведёт ML-диалог поверх базы знаний | Сообщения на естественном языке: задача, описание данных, подтверждения | `archive.zip`: признаки, синтетический датасет, `training_config.yaml`, `pipeline.py`, метаданные |
| **3. Analytics** | Показывает качество работы | События Setup и Runtime | Дашборды и audit trail |

Что система **не** делает: не принимает реальные датасеты пользователя (данные описываются в диалоге), не обучает и не хостит модели, не генерирует данные средствами LLM (датасет строит Python по `GenerationSpec`).

Подробно: [vision.md](../01-business/vision.md) — зачем и для кого; [system-overview.md](../02-system/system-overview.md) — что именно на входе и выходе каждой стадии.

## С чего начать

| Если вы... | Читайте по порядку |
| --- | --- |
| Хотите понять продукт | [vision.md](../01-business/vision.md) → [system-overview.md](../02-system/system-overview.md) → [UC-FE-01](../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md), [UC-FE-02](../02-system/use-cases/UC-FE-02-create-feature-set/use-case.md), [UC-FE-03](../02-system/use-cases/UC-FE-03-monitor-quality/use-case.md) → [glossary.md](../01-business/glossary.md) |
| Пришли разрабатывать | [CLAUDE.md](../../CLAUDE.md) → [development-process.md](development-process.md) → [repository-map.md](repository-map.md) → [feature-index.md](../02-system/features/feature-index.md) → файл нужной фичи |
| Занимаетесь агентами | [AGENTS.md](../../AGENTS.md) → [../05-agents/](../05-agents/) → [prompt-engineering-rules.md](prompt-engineering-rules.md) → [../07-contracts/](../07-contracts/) |
| Занимаетесь базой знаний (RAG) | [../06-rag/rag-overview.md](../06-rag/rag-overview.md) → [../06-rag/metadata-schema.md](../06-rag/metadata-schema.md) → [SETUP-01](../02-system/features/SETUP-01-setup-wizard.md) |
| Проектируете архитектуру | [../03-architecture/c4-context.md](../03-architecture/c4-context.md) → [c4-container.md](../03-architecture/c4-container.md) → [ADR](../03-architecture/adr/) → [сервисы](../03-architecture/services/README.md) |
| Пишете тесты | [../10-testing/testing-strategy.md](../10-testing/testing-strategy.md) → [../traceability/requirements-to-tests.md](../traceability/requirements-to-tests.md) |

## Карта документации

| Раздел | Что внутри | Отвечает на вопрос |
| --- | --- | --- |
| [00-methodology](.) | Процесс разработки, карта репозитория, шаблоны, правила traceability и промптов, governance таксономии | Как мы работаем? |
| [01-business](../01-business/) | Vision, цели и метрики успеха, стейкхолдеры, ограничения, глоссарий, каталог бизнес-требований, границы MVP и риски | Зачем система и для кого? |
| [02-system](../02-system/) | Обзор системы, акторы, FR/NFR, фичи (`SETUP-*`, `RUNTIME-*`, `ANALYTICS-*`, `PLATFORM-*`), use cases | Что система делает? |
| [03-architecture](../03-architecture/) | C4-виды, развёртывание, каталог сервисов SVC-01..38 и DTO, ADR | Из чего состоит? |
| [04-domain](../04-domain/) | Доменная модель, сущности, инварианты, события, таксономия | Какие сущности и правила? |
| [05-agents](../05-agents/) | Спецификация каждого агента | Что делает каждый агент? |
| [06-rag](../06-rag/) | Методология RAG, онтология, metadata, чанки, retrieval-политики, качество, безопасность | Как устроена база знаний? |
| [07-contracts](../07-contracts/) | Контракты структурированных выводов (зеркало `schemas/`) | В каком формате обмениваются данными? |
| [08-data](../08-data/) | Модели исходных, сгенерированных и feature-store данных, артефактов | Какие данные хранятся? |
| [09-langgraph](../09-langgraph/) | State machine, узлы, переходы, repair-loops, human-in-the-loop | Как течёт диалог? |
| [10-testing](../10-testing/) | Стратегия тестирования и руководства по слоям | Как проверяем? |
| [11-operations](../11-operations/) | Развёртывание, метрики, наблюдаемость, runbooks | Как эксплуатируем? |
| [traceability](../traceability/) | Матрицы покрытия между артефактами | Что от чего зависит? |
| [implementation-plan](../implementation-plan/) | Списки задач `T-*` по фичам | Что делаем дальше? |
| [observability](../observability/) | Определения дашбордов | Что мониторим? |
| [tech-debt](../tech-debt/) | Зафиксированный технический долг (`TD-*`) | Что отложено сознательно? |

## Документы этого каталога

| Файл | О чём |
| --- | --- |
| [development-process.md](development-process.md) | Порядок появления артефактов (docs → контракты → тесты → код), критерии «готово», работа с маленькой LLM |
| [repository-map.md](repository-map.md) | Где что лежит в репозитории и куда класть новое |
| [artifact-templates.md](artifact-templates.md) | Каркасы фичи, use case, спецификации агента, ADR, RAG-карточки, задачи, runbook |
| [traceability-rules.md](traceability-rules.md) | Что обязательно трассируется и какие матрицы поддерживаются |
| [prompt-engineering-rules.md](prompt-engineering-rules.md) | Структура и правила промптов для маленькой LLM, repair-loops |
| [taxonomy-governance.md](taxonomy-governance.md) | Жизненный цикл реестра иерархической таксономии SETUP-12: автоматическое выделение классов, версии, дрейф. SETUP-12 замещена SETUP-13 ([ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)); документ описывает сохранённую legacy-модель и, в конце, governance дерева SETUP-13 и его metadata-хинтов ([ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)) |

## Принципы в одной строке

Contract-first, state-first, RAG-first, test-first; вывод LLM — предположение, источник истины — детерминированные валидаторы. Полный список жёстких правил — в [CLAUDE.md](../../CLAUDE.md).
