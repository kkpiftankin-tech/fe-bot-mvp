# SETUP-05. Автоматическая генерация RAG-карточек

## 1. Назначение фичи

**Краткое название фичи:**
SETUP-05. Автоматическая генерация RAG-карточек.

**Краткое описание:**
Фича преобразует смысловые секции исходных документов, полученные на этапе SETUP-04, в специальные RAG-файлы с машинно-читаемой metadata и человеко-читаемым Markdown-содержимым. Эти RAG-карточки становятся основным управляемым слоем знаний, из которого затем создаются chunks, embeddings и Evidence Pack для runtime-агентов.

**Какую проблему решает фича:**
Raw-документы и даже parsed sections ещё не являются полноценной RAG-базой. Parsed section — это только извлечённый смысловой фрагмент. Для качественного retrieval системе нужны документы с единым форматом, типом, metadata, source trace, retrieval tags, фазами применения, целевыми агентами и статусом качества.

Фича решает переход:

```text
ParsedSectionDTO
  → классифицированный смысловой блок
  → RAG Card Draft
  → RAGCardDTO
  → Markdown RAG file
  → metadata validation candidate
  → review_required / generated / ready_for_validation
```

**Для какого бизнес-процесса нужна:**
Фича входит в пользовательский процесс настройки Knowledge Base:

```text
SETUP-01. Пользовательский мастер настройки базы знаний
  → SETUP-02. Загрузка исходных документов через фронт
  → SETUP-03. Source Registry
  → SETUP-04. Парсинг документов и выделение смысловых секций
  → SETUP-05. Автоматическая генерация RAG-карточек
  → SETUP-06. Review RAG-карточек
  → SETUP-07. Валидация metadata
  → SETUP-08. Генерация chunks
  → SETUP-09. Embeddings и Vector DB
  → SETUP-10. Retrieval smoke tests
  → SETUP-11. Публикация Knowledge Base
```

Главный пользовательский результат:

```text
Пользователь видит, что по parsed sections созданы RAG-карточки,
может открыть каждую карточку,
посмотреть metadata, body preview, источник, связи, статус,
а карточки с низкой уверенностью помечаются как review_required.
```

---

## 2. Контекст и бизнес-цель

### 2.1. Бизнес-контекст

Фича используется после завершения парсинга документов и выделения смысловых секций. На входе уже есть `ParsedSectionDTO`, в котором указаны:

- section_id
- source_document_id
- title
- heading_path
- section_type
- raw_text
- normalized_text
- structural_payload
- confidence
- classification_method

Однако для дальнейшего RAG pipeline этого недостаточно. Нужно создать RAG-карточку, то есть управляемый документ знания:

- YAML front matter
- Markdown body
- source trace
- doc_id
- doc_type
- retrieval metadata
- status
- version

Примеры типов RAG-карточек:

- schema_card
- task_card
- analytics_card
- field_definition_card
- feature_pattern_card
- validation_rule_card
- question_template_card
- model_recommendation_card
- ontology_card
- relationship_card

Текущий pain point:

- parsed sections не имеют единого формата для retrieval;
- секции могут быть слишком близки к исходному тексту и недостаточно операциональны;
- metadata может отсутствовать или быть неполной;
- невозможно фильтровать контекст по фазам и агентам;
- невозможно автоматически понять, какая секция нужна DataProfilingAgent, а какая FeatureSynthesisAgent;
- невозможно контролировать качество до chunking и embedding;
- невозможно показать пользователю человеко-читаемую карточку знания.

Почему фича нужна сейчас:

- SETUP-08 Chunking должен работать с RAG-карточками, а не с raw sections;
- SETUP-09 Vector DB должна индексировать chunks, построенные из карточек;
- runtime-агенты должны искать знания по doc_type, phase, agent_targets, domain, data_source;
- RAG Card Review UI требует карточек со статусами;
- Knowledge Base не может быть опубликована без управляемого набора RAG-документов.

### 2.2. Бизнес-цель

Ожидаемый бизнес-эффект:

- ускорить подготовку RAG-базы из пользовательских документов;
- снизить ручную работу RAG-администратора;
- повысить точность retrieval за счёт metadata-aware карточек;
- улучшить трассируемость source section → RAG card → chunk → Evidence Pack;
- обеспечить human review только там, где низкая уверенность или ошибки;
- создать воспроизводимый процесс генерации базы знаний.

Метрики / KPI:

| Метрика | Целевое значение MVP |
| --- | ---: |
| Доля parsed sections, по которым создана хотя бы одна RAG-карточка | ≥ 80% для релевантных секций |
| Доля RAG-карточек с заполненным `doc_id` | 100% |
| Доля RAG-карточек с заполненным `doc_type` | 100% |
| Доля RAG-карточек с заполненными `source_files` и `source_sections` | 100% |
| Доля RAG-карточек с непустым Markdown body | ≥ 95% |
| Доля RAG-карточек с retrieval tags | ≥ 95% |
| Доля карточек, помеченных `review_required` при низкой уверенности | 100% |
| Доля карточек с machine-readable YAML front matter | 100% |
| Среднее время генерации карточки | зависит от LLM, отслеживается |
| Доля ошибок LLM-output schema validation | отслеживается, целевой ориентир ≤ 10% после настройки prompts |

Успешный результат внедрения:

```text
Система автоматически создаёт RAG-карточки из parsed sections,
каждая карточка имеет metadata, source trace, body, статус и validation report,
а пользователь может перейти к review и последующей валидации metadata.
```

### 2.3. Инициатор и заинтересованные стороны

**Инициатор фичи:**
Product Owner / архитектор RAG-платформы.

**Заинтересованные стороны:**

- пользователь-настройщик;
- RAG-администратор;
- предметный эксперт;
- системный аналитик;
- ML Engineer;
- архитектор;
- backend-разработчик;
- frontend-разработчик;
- QA-инженер;
- аудитор;
- DevOps / MLOps.

**Команды, затрагиваемые фичей:**

- RAG / Knowledge Engineering team;
- Backend team;
- Frontend team;
- ML/LLM team;
- QA team;
- Architecture team;
- Data Platform team.

**Кто принимает решение о запуске:**
Product Owner совместно с RAG Admin, Solution Architect и владельцем RAG-методологии.

---

## 3. Термины, определения и сокращения

| Термин / сокращение | Полное название | Определение | Комментарий |
| --- | --- | --- | --- |
| RAG Card | RAG-карточка | Структурированный Markdown-документ с YAML metadata | Основная единица знания до chunking |
| RAG Card Generator | Генератор RAG-карточек | Сервис, преобразующий parsed sections в RAG-карточки | Может использовать LLM |
| YAML Front Matter | YAML metadata-блок | Машинно-читаемый блок metadata в начале Markdown-файла | Используется для retrieval filtering |
| Markdown Body | Тело карточки | Человекочитаемое содержание карточки | Используется для review и chunking |
| Parsed Section | Извлечённая секция | Смысловой блок исходного документа | Вход для генерации карточки |
| Source Trace | Трассировка к источнику | Связь RAG-карточки с source document и parsed section | Обязательна |
| `doc_id` | Document ID | Уникальный идентификатор RAG-карточки | Например `task.surface_threat_evaluation.v1` |
| `doc_type` | Document Type | Тип RAG-карточки | `schema_card`, `task_card`, `analytics_card` и т.д. |
| `retrieval_tags` | Retrieval Tags | Теги для улучшения поиска | Используются retrieval policies |
| `agent_targets` | Target Agents | Агенты, которым полезна карточка | Например `FeatureSynthesisAgent` |
| `phase` | Workflow Phase | Фазы системы, где применяется карточка | Например `data_profiling`, `feature_synthesis` |
| `confidence_level` | Уровень уверенности | Оценка качества генерации карточки | `high`, `medium`, `low` |
| `review_required` | Требуется проверка | Статус карточки, требующей ручного review | Используется SETUP-06 |
| Metadata Extractor | Извлекатель metadata | Компонент извлечения полей metadata из секции | Может быть rule-based или LLM-assisted |
| Ontology Mapper | Маппер онтологии | Компонент нормализации значений по ontology | Проверяет domain, task_type, data_source |
| Prompt Template | Шаблон prompt | Инструкция для LLM по генерации карточки | Версионируется |
| LLM Gateway | Шлюз LLM | Сервис вызова локальной LLM/Ollama | Не должен сохранять решение без validation |
| Card Registry | Реестр карточек | Хранилище RAGCardDTO и статусов | Используется review, validation, chunking |
| Card Generation Job | Job генерации карточек | Принтонная операция генерации карточек по parsed sections | Имеет progress и статус |
| Draft Card | Черновая карточка | Карточка, созданная, но ещё не прошедшая validation/review | Не индексируется |
| Generated Card | Сгенерированная карточка | Карточка, прошедшая базовое сохранение | Может требовать validation |
| Card Validation Report | Отчёт проверки карточки | Проверка структуры, metadata и body | Полная metadata validation может быть в SETUP-07 |

## Словарь типов RAG-карточек

| `doc_type` | Назначение |
| --- | --- |
| `schema_card` | Описание структуры данных, сущностей, полей, источников |
| `task_card` | Описание ML-задачи, входов, выходов, моделей, метрик |
| `analytics_card` | Описание feature-store таблиц, агрегатов, аналитических признаков |
| `field_definition_card` | Описание отдельного поля, синонимов, единиц, типов |
| `feature_pattern_card` | Описание паттерна формирования признаков |
| `validation_rule_card` | Описание правила проверки |
| `question_template_card` | Шаблон вопроса пользователя |
| `model_recommendation_card` | Рекомендации по моделям для типа задачи |
| `ontology_card` | Описание элементов онтологии |
| `relationship_card` | Связи между задачами, схемами, признаками, моделями |

## Словарь статусов RAG-карточки

| Статус | Значение |
| --- | --- |
| `draft` | Карточка создана как черновик |
| `generated` | Карточка успешно сгенерирована |
| `generation_failed` | Ошибка генерации |
| `metadata_incomplete` | Обязательная metadata неполная |
| `body_empty` | Тело карточки пустое или невалидное |
| `low_confidence` | Карточка создана с низкой уверенностью |
| `review_required` | Требуется ручной review |
| `ready_for_metadata_validation` | Карточка готова к SETUP-07 |
| `rejected` | Карточка отклонена |
| `deprecated` | Карточка устарела |

## Словарь статусов Card Generation Job

| Статус | Значение |
| --- | --- |
| `created` | Job создан |
| `queued` | Job поставлен в очередь |
| `running` | Генерация выполняется |
| `partial_success` | Часть карточек создана, часть с ошибками |
| `completed` | Все карточки обработаны |
| `failed` | Job завершился критической ошибкой |
| `cancelled` | Job отменён |

---

## 4. Границы фичи

### 4.1. In Scope

Входит в реализацию:

- запуск генерации RAG-карточек по parsed sections;
- выбор parsed sections, пригодных для генерации;
- определение целевого doc_type;
- генерация doc_id;
- генерация YAML front matter;
- генерация Markdown body;
- извлечение и нормализация metadata;
- использование ontology для domain/task_type/data_source/entity_type;
- использование prompt templates;
- вызов LLM через LLM Gateway при необходимости;
- rule-based generation для простых карточек;
- сохранение RAG-карточек в Card Registry;
- сохранение Markdown-файлов в Artifact Storage;
- присвоение статусов карточкам;
- вычисление confidence;
- пометка карточек `review_required`;
- привязка карточки к source_document_id и source_section_id;
- обновление Source Registry lineage;
- отображение прогресса генерации во frontend;
- отображение списка созданных карточек;
- preview metadata и Markdown body;
- создание CardGenerationReportDTO;
- создание предварительного CardValidationReportDTO;
- audit и analytics events.

Поддерживаемые типы карточек в MVP:

- schema_card
- task_card
- analytics_card
- field_definition_card
- feature_pattern_card
- validation_rule_card
- question_template_card

Опционально или во второй итерации:

- model_recommendation_card
- ontology_card
- relationship_card

Поддерживаемые сценарии:

- генерация карточек по всем parsed sections setup job;
- генерация карточек по выбранным parsed sections;
- частичный успех генерации;
- повторная генерация failed sections;
- пометка low confidence карточек;
- просмотр карточек пользователем;
- отправка карточек на review;
- сохранение карточек как Markdown artifacts.

Затрагиваемые экраны:

- Knowledge Base Setup Page;
- RAG Card Generation Step;
- RAG Card Generation Progress;
- RAG Card List;
- RAG Card Preview Drawer;
- RAG Card Metadata Panel;
- RAG Card Source Trace Panel;
- RAG Card Errors Panel.

Затрагиваемые API:

- POST /api/setup/{setup_job_id}/rag-cards/generate
- GET /api/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}
- GET /api/setup/{setup_job_id}/rag-cards
- GET /api/setup/{setup_job_id}/rag-cards/{doc_id}
- GET /api/setup/{setup_job_id}/rag-cards/{doc_id}/preview
- POST /api/setup/{setup_job_id}/rag-cards/{doc_id}/regenerate

### 4.2. Out of Scope

Не входит в реализацию этой фичи:

- загрузка файлов;
- парсинг документов;
- ручной review карточек; это SETUP-06;
- полная валидация metadata; это SETUP-07;
- chunking карточек; это SETUP-08;
- embeddings и индексация Vector DB; это SETUP-09;
- retrieval smoke tests; это SETUP-10;
- публикация Knowledge Base; это SETUP-11;
- ручной Markdown-редактор карточек;
- полноценный workflow согласования несколькими экспертами;
- автоматическое исправление ontology;
- обучение модели классификации карточек;
- генерация финального Evidence Pack runtime-агентов.

Отложенные сценарии:

- multi-card generation из одной секции с разветвлением по сущностям;
- автоматическая генерация relationship graph;
- автоматическое слияние похожих карточек;
- semantic duplicate detection карточек;
- advanced prompt evaluation;
- auto-repair карточки по результатам SETUP-07;
- ручное редактирование YAML front matter в UI.

### 4.3. Ограничения реализации

Технические ограничения:

- RAG Card Generator не должен работать с raw-документами напрямую; вход — ParsedSectionDTO.
- LLM не является источником истины; её output должен проходить schema validation.
- Карточка без source_document_id и source_section_id не сохраняется как usable.
- Карточка без doc_id не может быть передана в SETUP-07.
- Карточка без doc_type не может быть передана в SETUP-08.
- Draft/review_required карточки не индексируются.
- Markdown body должен быть непустым.
- YAML front matter должен быть machine-readable.
- Generated markdown artifact должен быть связан с RAGCardDTO.
- Prompt template должен быть версионирован.
- LLM response должен сохраняться только в безопасном виде, если разрешено политикой.

Организационные ограничения:

- запуск генерации требует permission `kb.rag_card.generate`;
- просмотр карточек требует `kb.rag_card.read`;
- регенерация карточек требует `kb.rag_card.regenerate`;
- карточки с low confidence требуют review RAG-администратора или эксперта;
- в проектах с ограниченным доступом LLM fallback может быть выключен.

Временные ограничения MVP:

- основная генерация может использовать LLM для сложных карточек;
- для простых карточек допустим rule-based template generation;
- relationship_card может быть отложена;
- ручной редактор карточек может быть реализован в SETUP-06;
- prompt evaluation может быть базовой.

---

## 5. Пользовательские роли и внешние участники

### 5.1. Пользовательские роли

| Роль | Описание | Действия в рамках фичи |
| --- | --- | --- |
| Пользователь-настройщик | Запускает подготовку RAG-базы и наблюдает прогресс | Видит этап генерации и список карточек |
| RAG-администратор | Отвечает за качество RAG-корпуса | Анализирует карточки, low confidence, ошибки |
| Предметный эксперт | Проверяет смысл карточек | Просматривает body, metadata, source trace |
| Системный аналитик | Контролирует соответствие карточек требованиям и доменной структуре | Проверяет task/schema/analytics cards |
| ML Engineer | Использует карточки для последующей генерации признаков | Проверяет analytics/feature pattern cards |
| Аудитор | Проверяет трассируемость | Смотрит source_section_id, source_document_id, generation log |
| QA-инженер | Проверяет генерацию карточек по тестовому корпусу | Запускает tests и анализирует reports |

### 5.2. Внешние участники

| Участник | Тип | Роль во взаимодействии | Интерфейс |
| --- | --- | --- | --- |
| Пользователь-настройщик | Пользователь | Наблюдает этап генерации и результат | UI |
| Предметный эксперт | Пользователь | Просматривает и оценивает карточки | UI |
| Администратор RAG | Пользователь | Контролирует качество, запускает regenerate | UI |
| Локальная LLM / Ollama | Внешняя система | Генерирует или дополняет RAG-карточки | API |
| Embedding Model | Внешняя система | Не используется напрямую в SETUP-05 | — |
| Object Storage | Инфраструктурная система | Хранит Markdown-файлы карточек | API |
| Identity Provider | Внешняя система | Подтверждает пользователя и роли | OAuth/OIDC/API |

### 5.3. Права доступа

Кто может инициировать сценарий:

- владелец setup job;
- пользователь с permission `kb.rag_card.generate`;
- RAG-администратор;
- admin.

Кто может просматривать результат:

- владелец setup job;
- RAG-администратор;
- предметный эксперт с доступом к проекту;
- ML Engineer с доступом к KB setup;
- аудитор в read-only режиме;
- admin.

Необходимые permissions / scopes:

- kb.source.read
- kb.section.read
- kb.rag_card.generate
- kb.rag_card.read
- kb.rag_card.regenerate
- kb.rag_card.preview
- kb.rag_card.status.read
- kb.rag_card.lineage.read
- kb.processing_log.read
- kb.audit.read

Ограничения:

- пользователь не может генерировать карточки по секциям чужого setup job;
- пользователь не может регенерировать approved карточки без отдельного разрешения;
- пользователь не может изменить system metadata карточки через эту фичу;
- карточки не могут перейти в indexed/published в рамках SETUP-05.

---

## 6. Сервисы и системы-участники

### 6.1. Внутренние сервисы

| Сервис | Роль в фиче | Тип взаимодействия |
| --- | --- | --- |
| Frontend RAG Card Generation Step | Показывает этап генерации, progress, список карточек | sync + streaming |
| API Backend | Предоставляет API запуска генерации и просмотра карточек | sync |
| Auth Service | Проверяет права доступа | sync |
| Setup Orchestrator | Запускает generation step в SetupGraph | async orchestration |
| RAG Card Generator | Основной сервис генерации карточек | async |
| RAG Card Registry | Сохраняет RAGCardDTO, статусы, metadata | sync/async |
| Parsed Section Registry | Отдаёт ParsedSectionDTO | sync |
| Source Registry Service | Отдаёт source trace и обновляет lineage | sync/async |
| Metadata Extractor | Извлекает metadata из parsed section | sync/LLM-assisted |
| Ontology Mapper | Нормализует domain/task_type/data_source/entity_type/doc_type | sync |
| Prompt Template Registry | Хранит prompt templates для разных doc_type | sync |
| LLM Gateway | Вызывает Ollama/local LLM и возвращает structured output | sync/async |
| Card Validation Precheck Service | Выполняет базовую проверку структуры карточки | sync |
| Artifact Storage Service | Сохраняет Markdown RAG-файлы | sync |
| Processing Log Service | Пишет generation logs | async |
| Notification Service | Отправляет progress events во frontend | async/streaming |
| Audit Service | Пишет audit events | async |
| Analytics Service | Собирает метрики генерации | async |

### 6.2. Внешние системы

| Система | Назначение | Канал интеграции | Критичность |
| --- | --- | --- | --- |
| Ollama / Local LLM | Генерация YAML front matter и Markdown body | API/local runtime | High для LLM-режима |
| PostgreSQL | Хранение RAGCardDTO, job, statuses | SQL | High |
| Object Storage | Хранение Markdown-файлов карточек | API | High |
| Redis | Progress state, locks, job state cache | API | Medium |
| Kafka / Event Bus | События генерации карточек | Event | Medium |
| ClickHouse | Метрики генерации и ошибок | SQL/Event ingest | Medium |
| Identity Provider | Авторизация | OAuth/OIDC/API | Medium |

### 6.3. Хранилища и инфраструктурные компоненты

PostgreSQL:

- rag_card_generation_jobs
- rag_card_generation_job_sections
- rag_cards
- rag_card_metadata
- rag_card_generation_logs
- rag_card_validation_reports
- rag_card_source_links
- rag_card_versions
- parsed_sections
- source_documents
- source_document_lineage

Object Storage:

- rag/cards/{setup_job_id}/{doc_id}.md
- rag/cards/{setup_job_id}/{doc_id}.metadata.json
- rag/cards/{setup_job_id}/{doc_id}.generation_report.json

Redis:

- rag_card_generation_job_progress:{job_id}
- rag_card_generation_lock:{section_id}
- rag_card_generation_status:{doc_id}

Kafka / Event Bus:

- rag_card_generation.job.created
- rag_card_generation.job.started
- rag_card.generated
- rag_card.generation_failed
- rag_card.review_required
- rag_card_generation.job.completed

ClickHouse:

- rag_card_generation_events
- rag_card_generation_metrics
- llm_card_generation_metrics
- rag_card_quality_metrics

---

## 7. Пользовательские сценарии

### 7.1. Основной сценарий

#### Предусловия

- пользователь авторизован;
- существует setup job;
- SETUP-04 завершён полностью или частично;
- есть parsed sections со статусом ready_for_rag_card_generation;
- Source Registry доступен;
- Parsed Section Registry доступен;
- Ontology доступна;
- Prompt templates доступны;
- LLM Gateway доступен, если выбран LLM-режим;
- пользователь имеет permission `kb.rag_card.generate`.

#### Триггер сценария

Пользователь в мастере настройки базы знаний нажимает «Продолжить» после этапа парсинга, или система внутри SetupGraph переходит к этапу «Генерация RAG-карточек».

Также возможен ручной запуск: «Сгенерировать RAG-карточки».

#### Пошаговый happy path

1. Пользователь запускает генерацию RAG-карточек.
2. Frontend показывает этап «Генерация RAG-карточек».
3. API Backend проверяет права пользователя.
4. Setup Orchestrator создаёт `RAGCardGenerationJobDTO`.
5. RAG Card Generator получает список parsed sections.
6. Для каждой секции определяется целевой `doc_type`.
7. Metadata Extractor извлекает candidate metadata.
8. Ontology Mapper нормализует domain, task_type, data_source, entity_type, phase, agent_targets, retrieval_tags.
9. Prompt Template Registry выбирает шаблон по `doc_type` и `section_type`.
10. RAG Card Generator формирует prompt input.
11. LLM Gateway вызывает локальную LLM/Ollama.
12. LLM возвращает structured output (front_matter, body_markdown, confidence, warnings).
13. Card Validation Precheck Service проверяет базовые требования (doc_id, doc_type, source_files, source_sections, body, retrieval_tags).
14. Если карточка валидна, она сохраняется в RAG Card Registry.
15. Markdown-файл карточки сохраняется в Artifact Storage.
16. Source Registry обновляет lineage source_document → parsed_section → rag_card.
17. Система присваивает статус (generated / ready_for_metadata_validation).
18. Если confidence низкий или есть warning, статус: review_required.
19. Frontend получает progress events (cards generated: N / total).
20. После завершения job пользователь видит список карточек.
21. Пользователь открывает карточку и видит metadata, Markdown body preview, source document, source section, status, confidence, warnings.
22. SetupGraph переходит к SETUP-06 или SETUP-07 в зависимости от политики.

#### Ожидаемый результат

- по parsed sections созданы RAG-карточки;
- карточки имеют YAML front matter и Markdown body;
- карточки имеют doc_id, doc_type, source_files, source_sections;
- карточки связаны с source_document_id и section_id;
- пользователь видит список карточек и статусы;
- low-confidence карточки помечены review_required;
- карточки готовы к review и metadata validation.

### 7.2. Альтернативные сценарии

#### A1. Одна parsed section создаёт несколько RAG-карточек

Некоторые секции содержат сразу несколько смысловых объектов. Например, секция «Сенсор» может породить:

- analytics.sensor_analytics_T.v1
- field.sensor.status.v1
- validation.sensor_uptime_ratio.v1

В MVP можно ограничиться одной основной карточкой на секцию, но архитектура DTO должна допускать `ParsedSection 1 → N RAGCard`.

#### A2. Несколько parsed sections объединяются в одну карточку

Например, несколько коротких glossary-секций могут быть объединены в одну `glossary.radar_terms.v1`. В MVP такой сценарий может быть отключён или выполняться только rule-based.

#### A3. LLM недоступна

Возможны политики:

- job failed;
- карточки создаются rule-based template mode;
- секции помечаются generation_failed;
- job получает partial_success.

Для MVP рекомендуется: если doc_type поддерживает template generation → создать карточку rule-based; иначе → generation_failed.

#### A4. Metadata неполная

Если карточка создана, но metadata неполная: `status = metadata_incomplete`. Карточка сохраняется как draft, но не может перейти к chunking.

#### A5. Body пустой или слишком короткий

Если LLM вернула пустое body: `status = body_empty`, `generation_error = BODY_EMPTY`. Система может сделать retry.

#### A6. Низкая уверенность

Если confidence ниже threshold: `status = review_required`. Пользователь увидит карточку в SETUP-06.

#### A7. Частичный успех job

Если часть карточек создана, а часть failed: `RAGCardGenerationJob.status = partial_success`. Пользователь может продолжить с созданными карточками, повторить generation для failed sections, отправить failed sections на ручную обработку или исключить failed sections.

#### A8. Повторная генерация карточки

Если карточка уже существует, regenerate может: создать новую версию карточки, пометить старую deprecated/stale, сохранить обе версии для audit, сохранить generation reason. В MVP рекомендуется: создавать новую версию card_version и не удалять старую.

### 7.3. Негативные сценарии

#### N1. Нет parsed sections

Если нет секций для генерации: `error_code = NO_PARSED_SECTIONS`. UI показывает «Нет секций для генерации RAG-карточек. Сначала выполните парсинг документов».

#### N2. Parsed section невалидна

Если секция не содержит текста или structural payload: `status = generation_failed`, `error_code = EMPTY_SECTION`.

#### N3. Ontology недоступна

Если Ontology Mapper не может нормализовать metadata: `status = metadata_incomplete`, `error_code = ONTOLOGY_UNAVAILABLE`.

#### N4. Prompt template отсутствует

Если нет шаблона для `doc_type`: `status = generation_failed`, `error_code = PROMPT_TEMPLATE_NOT_FOUND`.

#### N5. LLM вернула невалидный JSON

`error_code = INVALID_LLM_OUTPUT`. Система выполняет repair/retry, но не доверяет output.

#### N6. LLM сгенерировала неизвестный doc_type

`error_code = INVALID_DOC_TYPE`. Карточка не переходит в `ready_for_metadata_validation`.

#### N7. Ошибка сохранения Markdown-файла

Если RAGCardDTO сохранён, но artifact не сохранён: `status = generation_failed`, `error_code = CARD_ARTIFACT_SAVE_FAILED`. Нужна compensation.

#### N8. Конфликт doc_id

Если уже существует карточка с таким `doc_id`: `error_code = DOC_ID_CONFLICT`. Возможные действия: создать новую версию, сгенерировать другой doc_id, отправить на review.

#### N9. Пользователь не имеет прав

API возвращает `403`.

#### N10. Повторный запрос generation

Если пользователь отправил запрос повторно: вернуть существующий running job, или создать новый только при explicit regenerate.

### 7.4. Постусловия

После успешного завершения:

- создан RAGCardGenerationJobDTO;
- созданы RAGCardDTO;
- созданы Markdown artifacts;
- карточки имеют metadata и body;
- карточки связаны с parsed sections и source documents;
- Source Registry lineage обновлён;
- Processing Log содержит generation events;
- UI показывает список карточек;
- карточки со статусом review_required передаются в SETUP-06;
- карточки ready_for_metadata_validation передаются в SETUP-07.

Создаются / обновляются:

- rag_card_generation_jobs
- rag_card_generation_job_sections
- rag_cards
- rag_card_metadata
- rag_card_versions
- rag_card_source_links
- rag_card_validation_reports
- source_document_lineage
- parsed_section_lineage
- processing_logs
- audit_events
- analytics_events

Публикуются события:

- rag_card_generation.job.created
- rag_card_generation.job.started
- rag_card.generated
- rag_card.generation_failed
- rag_card.review_required
- rag_card_generation.job.completed
- rag_card_generation.job.partial_success

---

## 8. Диаграмма последовательности: система и внешние участники

(см. mermaid в исходной спеке; основные lifeline: User, Expert, Browser, System, LLM)

Ключевые шаги:

1. User → Browser: открыть мастер настройки базы знаний.
2. Browser → System: запросить setup job и parsed sections summary.
3. System → Browser: setup job + sections summary.
4. User → Browser: нажать «Генерировать RAG-карточки».
5. Browser → System: POST /rag-cards/generate.
6. System → Browser: Card generation job created.
7. Browser → User: показать этап «Генерация RAG-карточек».
8. System → System: получить parsed sections, определить doc_type и metadata candidates, сопоставить с ontology.
9. (alt) System → LLM: сгенерировать YAML front matter и Markdown body. LLM → System: structured output.
10. (alt) System → System: сгенерировать карточку по шаблону.
11. System → System: precheck карточки, сохранить RAG-карточку и artifact.
12. System → Browser: progress event (card generated).
13. (alt low confidence) System → Browser: status=review_required.
14. (alt completed) System → Browser: generation completed; partial_success; failed.
15. Expert → Browser: открыть карточку. Browser → System: GET /rag-cards/{doc_id}. System → Browser: metadata + Markdown preview + source trace.

---

## 9. Диаграмма последовательности: взаимодействие сервисов системы

Lifelines: UI Frontend, API Backend, Auth, Setup Orchestrator, RAG Card Generator, Parsed Section Registry, Source Registry, Metadata Extractor, Ontology Mapper, Prompt Template Registry, LLM Gateway, Card Validation Precheck, RAG Card Registry, Artifact Storage, Notification, Audit, Analytics.

Ключевые шаги:

1. UI → API: POST /api/setup/{setup_job_id}/rag-cards/generate.
2. API → Auth: authorize(kb.rag_card.generate).
3. API → Setup Orchestrator: startRAGCardGeneration(setup_job_id).
4. Setup → RAG Card Registry: create RAGCardGenerationJobDTO.
5. Setup → Parsed Section Registry: list sections ready_for_rag_card_generation.
6. Setup → Generator: generateCards(job_id, section_ids).
7. Generator → Notification: rag_card_generation.job.started.
8. Per section: Generator → Parsed Section Registry; → Source Registry; → Metadata Extractor; → Ontology Mapper; → Prompt Template Registry; → LLM Gateway (alt) или builtin template; → Precheck.
9. Если card валидна: Generator → RAG Card Registry (save RAGCardDTO + version); → Artifact Storage (markdown); → Source Registry (lineage); → Notification (rag_card.generated); → Analytics.
10. Иначе: Generator → RAG Card Registry (save failure); → Notification (rag_card.generation_failed); → Analytics.
11. Generator → RAG Card Registry: update generation job status.
12. Generator → Audit/Notification: rag_card_generation.job.completed.
13. API → UI: generation_job_id.

Идемпотентность:

- generation job должен быть идемпотентным по generation_request_id;
- один section_id не должен порождать дубли без new version;
- LLM-вызов может иметь retry;
- save markdown artifact должен быть идемпотентным по doc_id + version;
- source lineage link должен быть идемпотентным.

Точки отказа:

- Parsed Section Registry / Source Registry / Ontology Mapper / Prompt Template недоступны;
- LLM Gateway timeout;
- невалидный LLM output;
- RAG Card Registry / Artifact Storage недоступен;
- conflict doc_id;
- event bus недоступен.

---

## 10. Frontend Scope

### 10.1. Изменения в UI

Новые / изменяемые элементы:

```text
KnowledgeBaseSetupPage
  → RAGCardGenerationStep
  → RAGCardGenerationProgress
  → RAGCardGenerationSummary
  → RAGCardList
  → RAGCardPreviewDrawer
  → RAGCardMetadataPanel
  → RAGCardBodyPreview
  → RAGCardSourceTracePanel
  → RAGCardStatusBadge
  → RAGCardGenerationErrorsPanel
  → LowConfidenceCardsPanel
  → RegenerateCardButton
```

#### RAGCardGenerationStep

Показывает этап «Генерация RAG-карточек»; количество parsed sections; processed sections; created cards; failed cards; review_required cards; current doc_type; current section; progress bar.

#### RAGCardList

Колонки: doc_id, title, doc_type, status, confidence_level, source_document, source_section, phase, agent_targets, retrieval_tags_count, errors/warnings, actions.

Действия: открыть preview, открыть source section, показать metadata, показать body, regenerate, отправить на review.

#### RAGCardPreviewDrawer

Вкладки: Overview, YAML Metadata, Markdown Body, Source Trace, Validation / Precheck, Generation Log, Related Artifacts.

#### RAGCardMetadataPanel

Показывает doc_id, doc_type, title, version, source_files, source_sections, domain, task_type, data_source, entity_type, phase, agent_targets, retrieval_tags, confidence_level, status.

#### RAGCardBodyPreview

Markdown preview: # Title, описание карточки, разделы, формулы, примеры, комментарии для агентов.

#### LowConfidenceCardsPanel

Показывает карточки: status=review_required; confidence_level=low; warnings not empty.

### 10.2. Клиентская логика

Валидации:

- нельзя запустить генерацию, если нет parsed sections;
- нельзя открыть карточку без doc_id;
- нельзя перейти к chunking, если есть critical failed cards;
- нельзя regenerate карточку без права `kb.rag_card.regenerate`;
- нельзя редактировать generated metadata в SETUP-05, если editing вынесен в SETUP-06.

Управление состоянием: generationJob, generationProgress, ragCards, selectedRAGCard, cardPreview, cardMetadata, cardBody, cardErrors, lowConfidenceCards, filters, pagination, sort, permissions, loadingStates, errorStates.

Фильтры: doc_type, status, confidence_level, source_document, phase, agent_targets, has_errors, review_required.

Отображение ошибок: no parsed sections, LLM unavailable, prompt template not found, metadata incomplete, doc_id conflict, artifact save failed, partial success, generation failed.

Feature flags: enable_llm_card_generation, enable_template_card_generation, enable_card_preview, enable_card_regeneration, enable_low_confidence_review, enable_relationship_card_generation, enable_model_recommendation_card_generation.

### 10.3. UX / UI требования

- пользователь должен видеть, что генерация идёт по parsed sections;
- длительная генерация не должна блокировать UI;
- progress должен обновляться во frontend;
- карточки должны быть доступны для preview сразу после создания;
- review_required карточки должны быть визуально выделены;
- failed sections/cards должны иметь понятное объяснение;
- partial_success должен быть понятен пользователю;
- пользователь должен понимать, можно ли перейти к следующему этапу;
- карточки должны фильтроваться по типу и статусу;
- metadata и Markdown body должны отображаться отдельно;
- source trace должен быть доступен из карточки.

---

## 11. Backend Scope

### 11.1. Изменения в сервисах

#### API Backend

Добавить handlers:

- POST /api/setup/{setup_job_id}/rag-cards/generate
- GET /api/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}
- GET /api/setup/{setup_job_id}/rag-cards
- GET /api/setup/{setup_job_id}/rag-cards/{doc_id}
- GET /api/setup/{setup_job_id}/rag-cards/{doc_id}/preview
- POST /api/setup/{setup_job_id}/rag-cards/{doc_id}/regenerate

#### Setup Orchestrator

Use cases: start_rag_card_generation_step; select sections ready for card generation; determine next step after generation; route to SETUP-06 if review_required exists; route to SETUP-07 if cards ready for validation; handle partial_success.

#### RAG Card Generator

Use cases: generate_cards_for_setup_job; generate_card_for_section; determine_doc_type; extract_metadata_candidates; normalize_metadata_with_ontology; choose_prompt_template; call_llm_gateway; parse_llm_output; build_card_markdown; build_card_front_matter; calculate_confidence; run_card_precheck; persist_card; mark_review_required; create_generation_report.

#### Metadata Extractor

Use cases: extract_domain; extract_task_type; extract_data_source; extract_entity_type; extract_feature_tables; extract_output_fields; extract_required_input_fields; extract_retrieval_tags.

#### Ontology Mapper

normalize ontology values; validate known enum values; map synonyms; detect unknown terms; produce warnings.

#### Prompt Template Registry

Шаблоны: schema_card_generation_prompt, task_card_generation_prompt, analytics_card_generation_prompt, field_definition_card_generation_prompt, feature_pattern_card_generation_prompt, validation_rule_card_generation_prompt, question_template_card_generation_prompt.

#### RAG Card Registry

Use cases: create_generation_job; save_card; save_card_metadata; save_card_version; update_card_status; attach_artifact; list_cards; get_card; get_card_preview; save_generation_error.

#### Artifact Storage Service

save_rag_card_markdown; save_rag_card_metadata_snapshot; save_generation_report.

### 11.2. Изменения в данных

Новые таблицы:

- rag_card_generation_jobs (generation_job_id, setup_job_id, requested_by, status, total_sections, processed_sections, generated_cards, failed_sections, review_required_cards, started_at, finished_at, created_at, updated_at, error_code, error_message, config_json)
- rag_card_generation_job_sections (generation_job_section_id, generation_job_id, section_id, source_document_id, status, target_doc_type, generated_doc_id, confidence_level, started_at, finished_at, duration_ms, error_code, error_message, metadata_json)
- rag_cards (doc_id, setup_job_id, card_version, doc_type, title, status, confidence_level, markdown_artifact_id, source_document_id, primary_source_section_id, created_by_type, created_by_id, created_at, updated_at, review_required_reason, error_code, error_message, metadata_json)
- rag_card_metadata (doc_id, card_version, front_matter_json, domain, task_type, data_source, entity_type, phase, agent_targets, retrieval_tags, required_input_fields, output_fields, feature_tables, validation_rules, compatible_models, owner, last_verified_at, metadata_schema_version)
- rag_card_source_links (source_link_id, doc_id, card_version, source_document_id, source_section_id, relation_type, created_at, metadata_json)
- rag_card_artifacts (artifact_link_id, doc_id, card_version, artifact_id, artifact_type, created_at)

### 11.3. Интеграционные изменения

Новые события:

- rag_card_generation.job.created
- rag_card_generation.job.started
- rag_card.generated
- rag_card.review_required
- rag_card.generation_failed
- rag_card_generation.job.completed
- rag_card_generation.job.partial_success

Изменения контрактов:

- ParsedSectionDTO должен быть входом RAG Card Generator;
- Source Registry должен поддерживать lineage parsed_section → rag_card;
- SETUP-07 должен принимать RAGCardDTO;
- SETUP-08 должен принимать только карточки, прошедшие validation/review policy.

---

## 12. Бизнес-правила и ограничения

Правила принятия решений:

- Генерировать карточки можно только по ParsedSectionDTO со статусом ready_for_rag_card_generation или classified.
- ParsedSectionDTO со статусом invalid или ignored не используется.
- Каждый RAGCardDTO должен иметь source_document_id и source_section_id.
- doc_id должен быть уникален в пределах setup job и card_version.
- doc_type должен входить в допустимый enum.
- Карточки без body не допускаются к следующему этапу.
- Карточки без required metadata получают status=metadata_incomplete.
- Карточки с low confidence получают status=review_required.
- LLM output не принимается без schema validation.
- Draft/review_required карточки не индексируются.
- RAG Card Generator не должен создавать карточки напрямую в active KB.

Ограничения по статусам:

- parsed section → generation_started → generated / generation_failed;
- generated card → ready_for_metadata_validation;
- generated card + warnings → review_required;
- generation_failed → может быть regenerated;
- review_required → SETUP-06;
- ready_for_metadata_validation → SETUP-07;
- rejected → не участвует в SETUP-08;
- deprecated → не используется downstream.

Ограничения по ролям:

- запуск generation job требует `kb.rag_card.generate`;
- просмотр карточки требует `kb.rag_card.read`;
- regenerate требует `kb.rag_card.regenerate`;
- просмотр source trace требует `kb.rag_card.lineage.read`;
- просмотр generation log требует `kb.processing_log.read`.

Ограничения по времени / датам:

- generation job должен иметь started_at/finished_at;
- каждая секция в job должна иметь duration_ms;
- LLM timeout задаётся конфигурацией;
- prompt template version фиксируется в generation metadata.

Правила повторной обработки:

- повторная генерация карточки создаёт новую card_version;
- старая версия не удаляется;
- regenerate должен иметь reason;
- regenerate не должен менять source trace;
- regenerate может изменить metadata/body/status;
- повторная генерация по тому же section_id не должна создавать дубликат без новой версии.

Приоритеты и разрешение конфликтов:

- ontology values имеют приоритет над LLM-предложениями;
- source trace имеет приоритет над сгенерированным summary;
- deterministic metadata extraction имеет приоритет над LLM metadata, если confidence выше;
- ручной review в SETUP-06 имеет приоритет над автоматической генерацией;
- doc_id conflict решается через versioning или review_required.

---

## 13. Входные данные и источники

### 13.1. Входные данные

| Поле | Тип | Обязательность | Источник | Правила валидации |
| --- | --- | --- | --- | --- |
| `setup_job_id` | string | Required | UI/API | Должен существовать |
| `generation_request_id` | string | Recommended | UI/API | Для идемпотентности |
| `section_ids` | list[string] | Optional | UI/API | Если пусто → все ready sections |
| `source_document_ids` | list[string] | Optional | UI/API | Фильтр по документам |
| `ParsedSectionDTO` | object | Required | Parsed Section Registry | Должен быть valid/classified |
| `section_type` | string | Required | SETUP-04 | Должен входить в enum или unknown |
| `normalized_text` | string | Required | SETUP-04 | Не пустой для text-based карточек |
| `structural_payload` | dict | Optional | SETUP-04 | Таблицы/JSON/code blocks |
| `ontology_version` | string | Required | Ontology Service | Должна существовать |
| `metadata_schema_version` | string | Required | Config | Должна существовать |
| `prompt_template_version` | string | Required | Prompt Registry | Должна существовать |
| `generation_mode` | string | Optional | UI/config | `llm`, `template`, `hybrid` |
| `llm_model` | string | Optional | config | Например `llama3.2:latest` |
| `confidence_threshold` | float | Optional | config | Нижний порог review_required |
| `domain_context` | dict | Optional | Setup Context | Используется для metadata |

### 13.2. Источники данных

- Parsed Section Registry
- Source Registry
- Ontology Registry
- Metadata Schema Registry
- Prompt Template Registry
- Domain Context
- Document Parse Report
- LLM Gateway / Ollama
- RAG methodology
- generation rules
- allowed doc_type registry

### 13.3. Предварительные проверки

Обязательности: setup_job_id существует; есть parsed sections; parsed sections принадлежат setup job; parsed sections имеют source_document_id; ontology доступна; metadata schema доступна; prompt templates доступны.

Форматные: section_type допустим; generation_mode допустим; confidence_threshold в диапазоне 0–1; prompt_template_version существует; metadata_schema_version существует.

Существования: source_document_id существует; source_section_id существует; PromptTemplate найден; Ontology values загружены; RAGCardGenerationJob не дублирует running job.

Доступа: kb.section.read; kb.rag_card.generate; kb.rag_card.read; kb.processing_log.write.

---

## 14. Выходные данные и результаты обработки

### 14.1. Ответ пользователю / клиенту

После запуска job:

```json
{
  "generation_job_id": "rag_gen_job_001",
  "setup_job_id": "setup_001",
  "status": "queued",
  "total_sections": 24,
  "message": "Генерация RAG-карточек запущена"
}
```

Progress response, итоговый response, список карточек — см. §14.1 спеки.

### 14.2. Побочные эффекты

Создаются / обновляются:

- RAGCardGenerationJobDTO
- RAGCardGenerationJobSectionDTO
- RAGCardDTO
- RAGCardMetadataDTO
- RAGCardVersionDTO
- RAGCardArtifactLinkDTO
- RAGCardSourceLinkDTO
- CardValidationReportDTO
- CardGenerationReportDTO
- source_document_lineage
- parsed_section_lineage
- audit_events
- analytics_events

Публикуются события: rag_card_generation.job.created/started/completed/partial_success/failed, rag_card.generated/review_required/generation_failed.

Уведомления: генерация карточек запущена; карточка создана; карточка требует review; часть карточек не создана; генерация завершена; можно перейти к review или metadata validation.

### 14.3. Результирующее состояние

При полном успехе: RAGCardGenerationJob.status = completed; RAGCard.status = ready_for_metadata_validation или review_required; SetupGraph переходит к SETUP-06 (если review_required) или SETUP-07.

При частичном успехе: RAGCardGenerationJob.status = partial_success; часть карточек создана; часть секций generation_failed; UI предлагает retry или продолжить.

При ошибке: RAGCardGenerationJob.status = failed; failed sections имеют error_code; UI показывает retry; SetupGraph не переходит к chunking.

---

## 15. DTO и модели данных

### 15.1. Входные DTO

#### GenerateRAGCardsRequest

```json
{
  "setup_job_id": "setup_001",
  "generation_request_id": "rag_gen_req_001",
  "section_ids": ["sec_001", "sec_002"],
  "source_document_ids": [],
  "generation_mode": "hybrid",
  "ontology_version": "ontology_v1",
  "metadata_schema_version": "rag_metadata_v1",
  "prompt_template_version": "rag_card_prompts_v1",
  "llm_model": "llama3.2:latest",
  "options": {
    "confidence_threshold": 0.75,
    "allow_multiple_cards_per_section": false,
    "mark_low_confidence_as_review_required": true,
    "save_llm_trace": false
  }
}
```

#### GenerateRAGCardForSectionCommand, RAGCardGenerationPromptInputDTO — см. §15.1.

### 15.2. Выходные DTO

#### RAGCardGenerationJobDTO

```json
{
  "generation_job_id": "rag_gen_job_001",
  "setup_job_id": "setup_001",
  "requested_by": "user_001",
  "status": "running",
  "total_sections": 24,
  "processed_sections": 12,
  "generated_cards": 11,
  "failed_sections": 1,
  "review_required_cards": 3,
  "started_at": "2026-06-05T13:00:00Z",
  "finished_at": null,
  "created_at": "2026-06-05T12:59:59Z",
  "updated_at": "2026-06-05T13:02:00Z"
}
```

#### RAGCardDTO

```json
{
  "doc_id": "analytics.sensor_analytics_T.v1",
  "setup_job_id": "setup_001",
  "card_version": "1.0",
  "doc_type": "analytics_card",
  "title": "Sensor analytics feature table",
  "status": "review_required",
  "confidence_level": "medium",
  "markdown_artifact_id": "artifact_rag_card_001",
  "source_document_id": "src_001",
  "primary_source_section_id": "sec_005",
  "created_by_type": "service",
  "created_by_id": "rag-card-generator",
  "created_at": "2026-06-05T13:01:00Z",
  "updated_at": "2026-06-05T13:01:00Z",
  "review_required_reason": "Некоторые metadata поля имеют medium confidence",
  "error_code": null,
  "error_message": null
}
```

#### RAGCardMetadataDTO

```json
{
  "doc_id": "analytics.sensor_analytics_T.v1",
  "card_version": "1.0",
  "front_matter": {
    "doc_id": "analytics.sensor_analytics_T.v1",
    "doc_type": "analytics_card",
    "title": "Sensor analytics feature table",
    "version": "1.0",
    "status": "generated",
    "source_files": ["analytics.md"],
    "source_sections": ["sec_005"],
    "domain": ["naval"],
    "task_type": ["classification", "ranking"],
    "data_source": ["radar", "tracks_fused"],
    "entity_type": ["sensor"],
    "phase": ["feature_synthesis", "validation"],
    "agent_targets": ["FeatureSynthesisAgent", "FeatureCriticAgent"],
    "retrieval_tags": ["sensor", "analytics", "uptime", "detection probability"]
  },
  "metadata_schema_version": "rag_metadata_v1"
}
```

(остальные DTO: RAGCardMarkdownDTO, RAGCardGenerationSectionResultDTO, CardGenerationReportDTO — см. §15.2)

### 15.3. Доменные сущности

RAGCardGenerationJob; RAGCardGenerationJobSection; RAGCard; RAGCardMetadata; RAGCardSourceLink; RAGCardArtifact — атрибуты и связи описаны в §15.3.

Связи:

- RAGCardGenerationJob 1 → N RAGCardGenerationJobSection
- ParsedSection 1 → N RAGCard
- SourceDocument 1 → N RAGCard
- RAGCard 1 → 1 MarkdownArtifact
- RAGCard 1 → 1 RAGCardMetadata
- RAGCard 1 → N RAGCardSourceLink
- RAGCard 1 → N RAGCardValidationReport

### 15.4. Версионирование

- GenerateRAGCardsRequest v1, RAGCardGenerationJobDTO v1, RAGCardDTO v1, RAGCardMetadataDTO v1, RAGCardMarkdownDTO v1, CardGenerationReportDTO v1.
- doc_id идентифицирует логическую карточку; card_version идентифицирует конкретную версию; regenerate создаёт новую версию; старые версии не удаляются; deprecated версия не участвует в новых индексах; published версия immutable.

Backward compatibility: добавление optional metadata fields допустимо; изменение обязательных metadata fields требует новой metadata_schema_version; изменение doc_type enum требует миграции UI и generator.

---

## 16. API contracts / event contracts / integration contracts

### 16.1. REST / gRPC API

| Интерфейс | Метод | URL / RPC | Назначение | Кто вызывает |
| --- | --- | --- | --- | --- |
| Start card generation | POST | `/api/setup/{setup_job_id}/rag-cards/generate` | Запустить генерацию RAG-карточек | Frontend / Setup Orchestrator |
| Get generation job | GET | `/api/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}` | Получить статус generation job | Frontend |
| List RAG cards | GET | `/api/setup/{setup_job_id}/rag-cards` | Получить список карточек | Frontend |
| Get RAG card | GET | `/api/setup/{setup_job_id}/rag-cards/{doc_id}` | Получить карточку | Frontend |
| Get RAG card preview | GET | `/api/setup/{setup_job_id}/rag-cards/{doc_id}/preview` | Получить metadata/body preview | Frontend |
| Regenerate card | POST | `/api/setup/{setup_job_id}/rag-cards/{doc_id}/regenerate` | Повторно сгенерировать карточку | Frontend / RAG Admin |
| Internal generate cards | RPC/Event | `RAGCardGenerator.generateCards` | Запустить worker | Setup Orchestrator |
| Internal save card | RPC | `RAGCardRegistry.saveCard` | Сохранить RAGCardDTO | Generator |

POST `/api/setup/{setup_job_id}/rag-cards/generate` — request/responses см. §16.1.

### 16.2. События

См. таблицу в §16.2: rag_card_generation.job.created/started/completed/partial_success, rag_card.generated/review_required/generation_failed, rag_card.markdown_saved — at-least-once.

### 16.3. Контрактные требования

Идемпотентность: generation_request_id; section_id + generation_job_id уникальны; doc_id + card_version уникальны; повторное сохранение карточки не создаёт дубликат без новой версии; lineage link идемпотентен; regenerate требует explicit regenerate_request_id.

Таймауты: API возвращает 202 Accepted; LLM Gateway timeout задаётся конфигурацией; каждый LLM prompt имеет max duration; artifact save имеет timeout; generation job имеет общий timeout.

Ретраи: invalid JSON → repair prompt / retry; LLM timeout → retry with backoff; Artifact Storage save failed → retry; Ontology Mapper unavailable → retry или metadata_incomplete; RAG Card Registry save failed → retry; event publish failed → outbox.

---

## 17. Нефункциональные требования

Производительность: запуск generation job должен быстро возвращать job_id; генерация выполняется асинхронно; progress должен быть доступен через polling/stream; LLM-вызовы должны выполняться batch/queue-controlled; генерация одной карточки должна иметь configurable timeout; карточки должны сохраняться по мере готовности.

Доступность: UI должен восстанавливать generation job после refresh; частичный успех должен сохранять созданные карточки; сбой Notification Service не должен ломать generation job; сбой LLM для одной секции не должен обязательно ломать весь job.

Масштабируемость: RAG Card Generator должен поддерживать worker pool; LLM calls должны быть ограничены rate limit; generation jobs должны масштабироваться по очереди; карточки и generation logs должны иметь pagination.

Безопасность: проверка доступа к setup job; проверка доступа к parsed sections; prompt injection из parsed section не должен восприниматься как инструкция системе; LLM prompt должен явно отделять source content от instructions; storage paths не раскрываются напрямую; карточки в restricted KB не должны уходить во внешние LLM; raw LLM output не должен публиковаться пользователю без очистки.

Аудит: кто запустил generation job; какие sections использовались; какой prompt_template_version использовался; какая LLM model использовалась; какие карточки созданы; какие карточки требуют review; какие карточки failed; кто запустил regenerate.

Наблюдаемость: метрики rag_card_generation_jobs_total, rag_cards_generated_total, rag_cards_failed_total, rag_cards_review_required_total, rag_cards_by_doc_type, rag_card_generation_duration_ms, llm_card_generation_calls_total, llm_invalid_output_total, llm_timeout_total, metadata_incomplete_total, doc_id_conflicts_total.

Логи: generation_job_id, setup_job_id, section_id, doc_id, doc_type, prompt_template_version, ontology_version, llm_model, confidence_level, status, error_code, duration_ms.

Трассировка: setup_job_id, source_document_id, source_section_id, generation_job_id, doc_id, card_version, artifact_id.

Лимиты: max_sections_per_generation_job; max_cards_per_section; max_llm_calls_per_job; max_prompt_tokens; max_card_body_length; max_generation_job_duration; max_concurrent_generation_jobs.

---

## 18. Ошибки и обработка исключений

### 18.1. Ошибки валидации

Формат:

```json
{
  "error_code": "NO_SECTIONS_READY_FOR_CARD_GENERATION",
  "message": "Нет секций, готовых для генерации RAG-карточек",
  "details": {"setup_job_id": "setup_001"}
}
```

Коды: SETUP_JOB_NOT_FOUND (404), NO_SECTIONS_READY_FOR_CARD_GENERATION (400), SECTION_NOT_FOUND (404), SECTION_NOT_READY (409), INVALID_GENERATION_MODE (400), ONTOLOGY_VERSION_NOT_FOUND (400), METADATA_SCHEMA_NOT_FOUND (400), PROMPT_TEMPLATE_NOT_FOUND (400), RAG_CARD_GENERATION_ALREADY_RUNNING (409), INSUFFICIENT_PERMISSIONS (403).

### 18.2. Системные ошибки

LLM_GATEWAY_UNAVAILABLE; LLM_TIMEOUT; INVALID_LLM_OUTPUT; INVALID_DOC_TYPE; DOC_ID_CONFLICT; CARD_BODY_EMPTY; FRONT_MATTER_INVALID; ONTOLOGY_MAPPER_UNAVAILABLE; CARD_REGISTRY_UNAVAILABLE; ARTIFACT_STORAGE_SAVE_FAILED; SOURCE_LINEAGE_UPDATE_FAILED; DATABASE_UNAVAILABLE; EVENT_BUS_UNAVAILABLE.

### 18.3. Поведение системы

Ретраи: invalid LLM JSON → repair prompt → retry; LLM timeout → retry with backoff; artifact save failed → retry; registry save failed → retry; event publish failed → outbox.

Compensation: если RAGCardDTO сохранён, но Markdown artifact не сохранён, карточка получает generation_failed; если artifact сохранён, но registry save failed, artifact помечается orphaned и попадает в cleanup; если lineage update failed, карточка получает warning или failed.

Dead letter queue: rag_card.generated/generation_failed events; lineage update events; artifact save events; LLM failure events.

Ручная обработка: RAG admin может открыть failed sections; regenerate; эксперт review в SETUP-06; admin reject/deprecate.

---

## 19. Acceptance Criteria

Запуск генерации:

- AC-01..AC-05 (см. §19).

Выбор секций:

- AC-06..AC-09.

Генерация карточек:

- AC-10: определяется target doc_type;
- AC-11: генерация doc_id;
- AC-12: YAML front matter;
- AC-13: Markdown body;
- AC-14: source_document_id;
- AC-15: source_section_id;
- AC-16: непустой body;
- AC-17: doc_type ∈ enum.

Metadata и ontology:

- AC-18..AC-22.

LLM output:

- AC-23..AC-27.

Статусы и review:

- AC-28..AC-31.

Сохранение и lineage:

- AC-32..AC-36.

UI и progress:

- AC-37..AC-42.

Частичный успех и retry:

- AC-43..AC-46.

События и аудит:

- AC-47..AC-51.

---

## 20. Definition of Done

(см. полный список в спеке: API, DTO, миграции, RAG Card Generator, MetadataExtractor, OntologyMapper, PromptTemplateRegistry, LLM Gateway integration, structured output validation, Card Validation Precheck, Markdown artifact save, source lineage, Frontend RAGCardGenerationStep / List / Preview / Metadata / Body / Source Trace / Low Confidence panels, audit events, analytics events, unit/integration/contract/E2E tests, prompt evaluation, security review, documentation updates).

---

## 21. Тесты

Unit tests: определение doc_type; генерация doc_id; уникальность doc_id; metadata extraction; ontology mapping; prompt template selection; assembly prompt input; parsing LLM output; schema validation; YAML front matter assembly; Markdown body assembly; precheck; confidence threshold logic; status assignment; versioning logic; RAGCardDTO validation; RAGCardMetadataDTO validation.

Integration tests: API → Setup Orchestrator → RAG Card Generator; Generator → registries; Generator → Ontology Mapper; Generator → LLM Gateway fake; Generator → Artifact Storage; Generator → Notification/Audit/Analytics.

Contract tests: OpenAPI schema endpoints; RAGCardDTO/RAGCardMetadataDTO schema; events; backward compatibility doc_type enum.

Prompt evaluation tests: каждый шаблон возвращает валидный JSON и соответствует ожидаемым полям; prompt не выполняет инструкции из source content; output содержит source_sections; output содержит retrieval_tags; output не придумывает unavailable source documents.

E2E / UI tests: happy path; partial success.

Negative / resilience tests: LLM Gateway unavailable; LLM timeout; invalid LLM output; prompt template missing; ontology unavailable; metadata schema missing; Artifact Storage unavailable; RAG Card Registry unavailable; doc_id conflict; repeated generation request; event bus unavailable; source lineage update failed; prompt injection attempt inside parsed section.

---

## 22. Риски, допущения, открытые вопросы

Риски: некорректная metadata от LLM; правдоподобный, но необоснованный output; prompt injection из parsed section; слишком общие или слишком дробные карточки; ошибки doc_id; изменение metadata schema после генерации; LLM Gateway как bottleneck; слишком много review_required карточек; рассинхрон artifact и registry.

Допущения: SETUP-04 уже создаёт ParsedSectionDTO; ParsedSectionDTO содержит normalized_text; Source Registry содержит source_document_id и filename; Ontology Registry доступна; Metadata schema определена; Prompt templates существуют; локальная LLM/Ollama доступна или включён template fallback; RAG-карточки сохраняются как Markdown artifacts; полная validation metadata выполняется в SETUP-07; ручной review выполняется в SETUP-06.

Открытые вопросы:

- какие doc_type входят в MVP?
- нужно ли разрешить несколько карточек из одной секции в MVP?
- какая политика doc_id conflict?
- какой confidence threshold использовать для review_required?
- нужно ли сохранять raw LLM response?
- какой формат Markdown body считается обязательным для каждого doc_type?
- нужно ли relationship_card в MVP?
- можно ли продолжать pipeline при partial_success?
- должна ли карточка без retrieval_tags сохраняться как draft или failed?
- нужно ли auto-repair карточек после SETUP-07?

---

## 23. Связанные документы и артефакты

Связанные feature-документы: SETUP-01..SETUP-11, ANALYTICS-02, ANALYTICS-04, ANALYTICS-09, PLATFORM-01, PLATFORM-02.

Связанные документы: docs/06-rag/rag-methodology.md; docs/06-rag/metadata-schema.md; docs/06-rag/card-schema.md; docs/06-rag/chunk-schema.md; docs/06-rag/retrieval-policies.md; docs/06-rag/evidence-pack.md; docs/07-contracts/dto-catalog.md; docs/07-contracts/api-contracts.md; docs/07-contracts/event-contracts.md; docs/07-contracts/storage-mapping.md; docs/03-architecture/service-catalog.md; docs/03-architecture/integration-map.md; docs/09-langgraph/setup-graph.md; docs/10-testing/SETUP-05-test-plan.md; docs/11-operations/rag-card-generation-runbook.md; docs/traceability/source-to-artifact-map.md.

Связанные DTO: GenerateRAGCardsRequest; GenerateRAGCardForSectionCommand; RAGCardGenerationPromptInputDTO; RAGCardGenerationJobDTO; RAGCardGenerationJobSectionDTO; RAGCardDTO; RAGCardMetadataDTO; RAGCardMarkdownDTO; RAGCardGenerationSectionResultDTO; CardGenerationReportDTO; CardValidationReportDTO; ParsedSectionDTO; SourceDocumentDTO; AuditEventDTO; AnalyticsEventDTO; NotificationDTO.

Связанные сервисы: Frontend RAG Card Generation Step; API Backend; Auth Service; Setup Orchestrator; RAG Card Generator; RAG Card Registry; Parsed Section Registry; Source Registry Service; Metadata Extractor; Ontology Mapper; Prompt Template Registry; LLM Gateway; Card Validation Precheck Service; Artifact Storage Service; Processing Log Service; Notification Service; Audit Service; Analytics Service.

Связанные UX-артефакты: Knowledge Base Setup Page; RAG Card Generation Step; RAG Card Generation Progress; RAG Card List; RAG Card Preview Drawer; RAG Card Metadata Panel; RAG Card Body Preview; RAG Card Source Trace Panel; Low Confidence Cards Panel; Generation Errors Panel.

Связанные схемы БД: rag_card_generation_jobs; rag_card_generation_job_sections; rag_cards; rag_card_metadata; rag_card_versions; rag_card_artifacts; rag_card_source_links; rag_card_generation_logs; rag_card_validation_reports; source_document_lineage; parsed_sections.

Operational artifacts: RAG Card Generation Runbook; Prompt Template Registry Guide; Prompt Injection Mitigation Guide; RAG Card Status Policy; RAG Card Versioning Policy; Card Generation Monitoring Dashboard; LLM Gateway Timeout and Retry Policy.
