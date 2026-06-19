# SETUP-05. Автоматическая генерация RAG-карточек

## 1. Назначение фичи

**Краткое название:** SETUP-05. Автоматическая генерация RAG-карточек.

**Краткое описание:**
Фича преобразует смысловые секции исходных документов, полученные на этапе SETUP-04, в структурированные RAG-файлы с машинно-читаемой YAML-metadata и человекочитаемым Markdown-содержимым. Каждая RAG-карточка содержит `doc_id`, `doc_type`, YAML front matter, Markdown body, source trace, retrieval tags, фазы применения и целевые агенты. Карточки становятся основным управляемым слоем знаний, из которого затем создаются chunks, embeddings и Evidence Pack для runtime-агентов.

**Какую проблему решает:**
`ParsedSection` — смысловой фрагмент без единого формата для retrieval. Для качественного RAG-pipeline нужен документ с типом, metadata, source trace и статусом качества. Фича реализует переход:

```
ParsedSectionDTO
  → классифицированный смысловой блок
  → RAG Card Draft
  → RAGCardDTO (DTO-66)
  → Markdown RAG file (DTO-62)
  → metadata validation candidate
  → review_required / generated / ready_for_metadata_validation
```

**Позиция в пайплайне:**

```
SETUP-01 Мастер настройки
  → SETUP-02 Загрузка документов
  → SETUP-03 Source Registry
  → SETUP-04 Парсинг документов
  → SETUP-05 Генерация RAG-карточек  ← текущая фича
  → SETUP-06 Review RAG-карточек
  → SETUP-07 Валидация metadata
  → SETUP-08 Генерация chunks
  → SETUP-09 Embeddings и Vector DB
  → SETUP-10 Retrieval smoke tests
  → SETUP-11 Публикация Knowledge Base
```

---

## 2. Контекст и бизнес-цель

### 2.1. Бизнес-контекст

После завершения SETUP-04 в системе существуют `ParsedSectionDTO` с полями `section_id`, `source_document_id`, `title`, `heading_path`, `section_type`, `raw_text`, `normalized_text`, `structural_payload`, `confidence`, `classification_method`. Однако для RAG-pipeline этого недостаточно: нет единого формата, нет типа карточки, нет retrieval tags, нет source trace в управляемом виде, нет статуса качества.

Pain points без SETUP-05:

- parsed sections не имеют единого формата для retrieval;
- невозможно фильтровать контекст по фазам и агентам;
- невозможно понять, какая секция нужна `DataProfilingAgent`, а какая `FeatureSynthesisAgent`;
- невозможно контролировать качество до chunking и embedding;
- невозможно показать пользователю человекочитаемую карточку знания.

SETUP-08 Chunking и SETUP-09 Vector DB должны работать с RAG-карточками, а не с raw sections.

### 2.2. Бизнес-цель и KPI

| Метрика | Целевое значение MVP |
| --- | ---: |
| Доля parsed sections, по которым создана хотя бы одна RAG-карточка | ≥ 80% для релевантных секций |
| Доля RAG-карточек с заполненным `doc_id` | 100% |
| Доля RAG-карточек с заполненным `doc_type` | 100% |
| Доля RAG-карточек с `source_files` и `source_sections` | 100% |
| Доля RAG-карточек с непустым Markdown body | ≥ 95% |
| Доля RAG-карточек с retrieval tags | ≥ 95% |
| Доля карточек, помеченных `review_required` при низкой уверенности | 100% |
| Доля карточек с machine-readable YAML front matter | 100% |
| Среднее время генерации карточки | зависит от LLM, отслеживается |
| Доля ошибок LLM-output schema validation | целевой ориентир ≤ 10% после настройки prompts |

Успешный результат: система автоматически создаёт RAG-карточки из parsed sections; каждая карточка имеет metadata, source trace, body, статус и validation report; пользователь может перейти к review и последующей валидации metadata.

### 2.3. Инициатор и заинтересованные стороны

**Инициатор:** Product Owner / архитектор RAG-платформы.

**Заинтересованные стороны:** пользователь-настройщик, RAG-администратор, предметный эксперт, системный аналитик, ML Engineer, архитектор, backend-разработчик, frontend-разработчик, QA-инженер, аудитор, DevOps/MLOps.

---

## 3. Термины, определения, сокращения

| Термин / сокращение | Полное название | Определение |
| --- | --- | --- |
| RAG Card | RAG-карточка | Структурированный Markdown-документ с YAML metadata — основная единица знания до chunking |
| YAML Front Matter | YAML metadata-блок | Машинно-читаемый блок metadata в начале Markdown-файла; используется для retrieval filtering |
| Markdown Body | Тело карточки | Человекочитаемое содержание карточки; используется для review и chunking |
| Parsed Section | Извлечённая секция | Смысловой блок исходного документа (вход для генерации карточки) |
| Source Trace | Трассировка к источнику | Связь RAG-карточки с source document и parsed section; обязательна |
| `doc_id` | Document ID | Уникальный идентификатор RAG-карточки, например `task.surface_threat_evaluation.v1` |
| `doc_type` | Document Type | Тип RAG-карточки: `schema_card`, `task_card`, `analytics_card` и т.д. |
| `retrieval_tags` | Retrieval Tags | Теги для улучшения поиска; используются retrieval policies |
| `agent_targets` | Target Agents | Агенты, которым полезна карточка, например `FeatureSynthesisAgent` |
| `phase` | Workflow Phase | Фазы системы, где применяется карточка |
| `confidence_level` | Уровень уверенности | Оценка качества генерации: `high`, `medium`, `low` |
| `confidence_threshold` | Порог уверенности | Нижний порог, ниже которого карточка помечается `review_required`; дефолт 0.7 |
| `review_required` | Требуется проверка | Статус карточки, требующей ручного review в SETUP-06 |
| Card Generation Job | Job генерации карточек | Оркестрированная операция генерации карточек по parsed sections |
| Draft Card | Черновая карточка | Карточка, созданная, но ещё не прошедшая validation/review |
| Ontology Mapper | Маппер онтологии | Компонент нормализации значений по ontology v1 |
| LLM Gateway | Шлюз LLM | Переиспользуемый сервис вызова локальной LLM/Ollama |
| `FE_BOT_FORCE_FALLBACK` | Флаг принудительного fallback | Env-переменная для bypass LLM; уже введена в SETUP-04 |
| `GENERATED_FROM` | Lineage relation type | Тип связи `parsed_section → rag_card` в Source Lineage; расширяет SETUP-03 |
| `card_version` | Версия карточки | Монотонно возрастающий номер версии (`"1.0"`, `"2.0"`, ...); повторная генерация инкрементирует |

### Словарь типов RAG-карточек (MVP scope)

| `doc_type` | Назначение |
| --- | --- |
| `schema_card` | Описание структуры данных, сущностей, полей, источников |
| `task_card` | Описание ML-задачи, входов, выходов, моделей, метрик |
| `analytics_card` | Описание feature-store таблиц, агрегатов, аналитических признаков |
| `field_definition_card` | Описание отдельного поля, синонимов, единиц, типов |
| `feature_pattern_card` | Описание паттерна формирования признаков |
| `validation_rule_card` | Описание правила проверки |
| `question_template_card` | Шаблон уточняющего вопроса пользователя |

Out of scope MVP: `model_recommendation_card`, `ontology_card`, `relationship_card`.

### Словарь статусов RAG-карточки

| Статус | Значение |
| --- | --- |
| `draft` | Карточка создана как черновик |
| `generated` | Карточка успешно сгенерирована |
| `generation_failed` | Ошибка генерации |
| `metadata_incomplete` | Обязательная metadata неполная |
| `body_empty` | Тело карточки пустое или невалидное |
| `low_confidence` | Карточка создана с низкой уверенностью |
| `review_required` | Требуется ручной review (SETUP-06) |
| `ready_for_metadata_validation` | Карточка готова к SETUP-07 |
| `rejected` | Карточка отклонена |
| `deprecated` | Карточка устарела |

### Словарь статусов Card Generation Job

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

- запуск генерации RAG-карточек по parsed sections одного setup job;
- определение целевого `doc_type` rule-based маппингом `section_type → doc_type`;
- детерминированная генерация `doc_id` по схеме `{doc_type_short}.{slug(title)}.v{N}`;
- генерация YAML front matter и Markdown body через `LLMGateway` + fallback на rule-based `RAGCardFallbackGenerator`;
- извлечение и нормализация metadata через `MetadataExtractor` + `OntologyMapper`;
- использование `ontology_v1.yaml` (rag/ontology/ontology_v1.yaml) для domain, task_type, data_source, entity_type, phase, agent_targets;
- версионирование prompt templates через `PromptTemplateRegistry`;
- базовый precheck структуры карточки (`CardValidationPrecheck`);
- сохранение `RAGCardDTO` (DTO-66) в `RAGCardRegistry`;
- сохранение Markdown-файла в `ArtifactStorage` по пути `rag/cards/{setup_job_id}/{doc_id}.md`;
- присвоение статусов; вычисление `confidence`; пометка `review_required` при `confidence < threshold`;
- lineage `parsed_section → rag_card` через `GENERATED_FROM` в `SourceLifecycleService`;
- создание `CardGenerationReportDTO` (DTO-64) и `CardValidationReportDTO` (DTO-65);
- публикация событий через `EventBus`;
- отображение прогресса, списка карточек и preview во frontend;
- поддержка `FE_BOT_FORCE_FALLBACK=1` для bypass LLM.

**Поддерживаемые `doc_type` в MVP:** `schema_card`, `task_card`, `analytics_card`, `field_definition_card`, `feature_pattern_card`, `validation_rule_card`, `question_template_card`.

**Генерация выполняется синхронно in-process** (как `DocumentParserOrchestrator.run` в SETUP-04). Асинхронный режим с очередями — отдельный инкремент.

**Стратегия section→card в MVP: один-к-одному.** Архитектура DTO допускает 1→N в будущем.

### 4.2. Out of Scope

- загрузка файлов и парсинг документов (SETUP-02, SETUP-04);
- ручной review карточек (SETUP-06);
- полная валидация metadata (SETUP-07);
- chunking карточек (SETUP-08);
- embeddings и индексация Vector DB (SETUP-09);
- retrieval smoke tests (SETUP-10);
- публикация Knowledge Base (SETUP-11);
- ручной Markdown-редактор карточек в UI (отложен в SETUP-06);
- multi-card generation из одной секции с разветвлением;
- автоматическая генерация relationship graph;
- semantic duplicate detection карточек;
- auto-repair карточки по результатам SETUP-07;
- типы `model_recommendation_card`, `ontology_card`, `relationship_card`.

### 4.3. Ограничения реализации

**Технические:**
- вход `RAGCardGenerator` — только `ParsedSectionDTO`; не raw-документы;
- LLM output проходит schema validation перед сохранением; не является источником истины;
- карточка без `source_document_id` и `source_section_id` не сохраняется как usable;
- карточка без `doc_id` не передаётся в SETUP-07; без `doc_type` не передаётся в SETUP-08;
- `draft` / `review_required` карточки не индексируются;
- Markdown body должен быть непустым; YAML front matter должен быть machine-readable;
- raw LLM response не сохраняется (security); сохраняются только parsed/validated данные;
- все репозитории MVP — in-memory (Protocol + Lock + `snapshot()/restore()`) аналогично SETUP-04.

**Организационные:**
- запуск генерации требует permission `kb.rag_card.generate`;
- просмотр требует `kb.rag_card.read`; регенерация требует `kb.rag_card.regenerate`;
- карточки `low_confidence` требуют review RAG-администратора или эксперта.

**Принятые решения (2026-06-19):**
- `confidence_threshold` дефолт 0.7; переопределяется через `GenerateRAGCardsRequest.options`;
- `doc_id` deterministic из `{doc_type_short}.{slug(title)}.v{N}`; конфликт — новая `card_version`;
- lineage использует `GENERATED_FROM` — расширение существующего `LineageRelationType`;
- существующие `RAGCardGenerator` и `RAGCardFallbackGenerator` переиспользуются под капотом нового оркестратора; legacy-path `SetupPipeline._generate_cards` сохраняется для обратной совместимости.

---

## 5. Пользовательские роли и внешние участники

### 5.1. Пользовательские роли

| Роль | Описание | Действия в рамках фичи |
| --- | --- | --- |
| Пользователь-настройщик | Запускает подготовку RAG-базы и наблюдает прогресс | Запускает генерацию, видит прогресс и список карточек |
| RAG-администратор | Отвечает за качество RAG-корпуса | Анализирует карточки, low confidence, ошибки; запускает regenerate |
| Предметный эксперт | Проверяет смысл карточек | Просматривает body, metadata, source trace |
| Системный аналитик | Контролирует соответствие карточек требованиям | Проверяет task/schema/analytics cards |
| ML Engineer | Использует карточки для генерации признаков | Проверяет analytics/feature_pattern cards |
| Аудитор | Проверяет трассируемость | Смотрит source trace, generation log |
| QA-инженер | Тестирует генерацию по тестовому корпусу | Запускает тесты и анализирует отчёты |

### 5.2. Внешние участники (EXT)

| Участник | Тип | Роль | Интерфейс |
| --- | --- | --- | --- |
| Пользователь-настройщик | EXT-User | Наблюдает этап генерации и результат | UI |
| Предметный эксперт | EXT-Expert | Просматривает и оценивает карточки | UI |
| RAG-администратор | EXT-Admin | Контролирует качество, запускает regenerate | UI |
| Локальная LLM / Ollama | EXT-LLM | Генерирует YAML front matter и Markdown body | Local API |
| Object Storage | EXT-Storage | Хранит Markdown-файлы карточек | S3-compatible API |
| Identity Provider | EXT-IdP | Подтверждает пользователя и роли | OAuth/OIDC |

### 5.3. Права доступа

**Permissions:**

| Permission | Действие |
| --- | --- |
| `kb.rag_card.generate` | Запуск generation job |
| `kb.rag_card.read` | Просмотр списка карточек и деталей |
| `kb.rag_card.regenerate` | Повторная генерация карточки |
| `kb.rag_card.preview` | Просмотр metadata/body preview |
| `kb.rag_card.lineage.read` | Просмотр source trace |
| `kb.processing_log.read` | Просмотр generation log |

**Role-permission матрица:**

| Роль | generate | read | regenerate | preview | lineage_read |
| --- | --- | --- | --- | --- | --- |
| USER | + | + | — | + | — |
| DOMAIN_EXPERT | + | + | + | + | + |
| RAG_ADMIN | + | + | + | + | + |
| AUDITOR | — | + | — | + | + |

**Ограничения:**
- пользователь не может генерировать карточки по секциям чужого setup job;
- regenerate approved карточек требует отдельного permission;
- карточки не могут перейти в `indexed`/`published` в рамках SETUP-05.

---

## 6. Сервисы и системы-участники

### 6.1. Внутренние сервисы (SVC)

| Сервис | SVC | Роль в фиче | Тип взаимодействия |
| --- | --- | --- | --- |
| Frontend RAG Card Generation Step | SVC-01 | Показывает этап, progress, список карточек | sync + polling |
| API Backend | SVC-02 | Endpoints запуска и просмотра | sync REST |
| Auth Service | SVC-03 | Проверка прав доступа | sync |
| Setup Orchestrator | SVC-04 | Запускает generation step в SetupGraph | sync orchestration |
| RAG Card Generation Service | SVC-09 | Основной сервис генерации (`RAGCardGenerationOrchestrator`) | sync |
| RAG Card Registry | SVC-15 | Сохраняет `RAGCardDTO`, metadata, версии | sync |
| Parsed Section Registry | SVC-06 | Отдаёт `ParsedSectionDTO` | sync |
| Source Registry Service | SVC-05 | Отдаёт source trace; обновляет lineage | sync |
| LLM Gateway | SVC-07 | Вызывает Ollama/local LLM (переиспользуется) | sync |
| Artifact Storage Service | SVC-38 | Сохраняет Markdown RAG-файлы | sync |
| Event Bus | SVC-32 | Публикация событий генерации | async |
| Audit Service | SVC-36 | Audit events | async |
| Analytics Service | SVC-35 | Метрики генерации | async |
| Notification Service | SVC-33 | Progress events во frontend | async/streaming |

**Переиспользуемые компоненты из предыдущих SETUP-фич:**
- `LLMGateway` (SETUP-01), `EventBus` (SETUP-01), `ArtifactStorage` (SETUP-01);
- `RAGCardGenerator` + `RAGCardFallbackGenerator` (SETUP-01, переиспользуются под капотом);
- `SourceLifecycleService` (SETUP-03);
- `DocumentParserOrchestrator` — структурный аналог для нового `RAGCardGenerationOrchestrator`.

### 6.2. Внешние системы

| Система | Назначение | Канал | Критичность |
| --- | --- | --- | --- |
| Ollama / Local LLM | Генерация YAML front matter и Markdown body | Local API | High (LLM-режим) |
| PostgreSQL | Хранение `RAGCardDTO`, job, statuses | SQL | High |
| Object Storage (MinIO) | Markdown-файлы карточек | S3 API | High |
| Redis | Progress state, locks, job state cache | API | Medium |
| Kafka / Event Bus | События генерации | Event | Medium |
| ClickHouse | Метрики генерации | SQL/Event ingest | Medium |
| Identity Provider | Авторизация | OAuth/OIDC | Medium |

### 6.3. Хранилища и инфраструктурные компоненты

**PostgreSQL (таблицы):**
- `rag_card_generation_jobs`
- `rag_card_generation_job_sections`
- `rag_cards`
- `rag_card_metadata`
- `rag_card_source_links`
- `rag_card_artifacts`
- `rag_card_validation_reports`
- `parsed_sections` (SETUP-04, read-only)
- `source_documents` (SETUP-03, read-only)
- `source_document_lineage`

**Object Storage:**
- `rag/cards/{setup_job_id}/{doc_id}.md`
- `rag/cards/{setup_job_id}/{doc_id}.metadata.json`
- `rag/cards/{setup_job_id}/{doc_id}.generation_report.json`

**Redis:**
- `rag_card_generation_job_progress:{job_id}`
- `rag_card_generation_lock:{section_id}`

**Kafka / Event Bus (topics):**
- `rag_card_generation.job.created`
- `rag_card_generation.job.started`
- `rag_card.generated`
- `rag_card.generation_failed`
- `rag_card.review_required`
- `rag_card_generation.job.completed`
- `rag_card_generation.job.partial_success`

---

## 7. Пользовательские сценарии

### 7.1. Основной сценарий (happy path)

**Предусловия:**
- пользователь авторизован с permission `kb.rag_card.generate`;
- существует setup job с завершённым SETUP-04;
- есть parsed sections со статусом, пригодным для генерации (`classified`, `ready_for_rag_card_generation`);
- Source Registry доступен; Parsed Section Registry доступен;
- `ontology_v1.yaml` загружен; prompt templates доступны;
- LLM Gateway доступен (или `FE_BOT_FORCE_FALLBACK=1` включён).

**Триггер:** пользователь нажимает «Продолжить» после этапа парсинга в мастере, или система внутри SetupGraph переходит к этапу «Генерация RAG-карточек», или пользователь нажимает «Сгенерировать RAG-карточки» вручную.

**Пошаговый happy path:**

1. Пользователь запускает генерацию RAG-карточек через UI или API.
2. Frontend показывает этап «Генерация RAG-карточек».
3. API Backend проверяет права пользователя через Auth Service.
4. Setup Orchestrator создаёт `RAGCardGenerationJob` (DTO-59) со статусом `created`.
5. Orchestrator получает список parsed sections через Parsed Section Registry.
6. Для каждой секции: `DocTypeDetector` определяет целевой `doc_type` по `section_type`.
7. `MetadataExtractor` извлекает candidate metadata из `structural_payload` и `raw_text`.
8. `OntologyMapper` нормализует domain, task_type, data_source, entity_type, phase, agent_targets, retrieval_tags по `ontology_v1.yaml`.
9. `PromptTemplateRegistry` выбирает шаблон по `doc_type` и `section_type`.
10. `LLMCardAdapter` формирует prompt и вызывает LLM Gateway (или `RAGCardFallbackGenerator` если `FE_BOT_FORCE_FALLBACK=1`).
11. LLM возвращает structured output: front_matter, body_markdown, confidence, warnings.
12. `MarkdownBuilder` собирает YAML front matter + sanitized Markdown body.
13. `CardValidationPrecheck` проверяет базовые требования: `doc_id`, `doc_type`, `source_files`, `source_sections`, body, retrieval_tags.
14. `ConfidenceCalculator` вычисляет `confidence_level` и проверяет `score < threshold`.
15. `DocIdGenerator` генерирует `doc_id` по схеме `{doc_type_short}.{slug(title)}.v{N}`.
16. `RAGCardRegistry.save_version(card)` и `save_metadata(metadata)` — сохранение карточки.
17. `ArtifactStorage` сохраняет Markdown-файл по пути `rag/cards/{setup_job_id}/{doc_id}.md`.
18. `SourceLifecycleService.link_artifact()` обновляет lineage `parsed_section → rag_card` (`GENERATED_FROM`).
19. Система присваивает статус: `generated` → `ready_for_metadata_validation`; если confidence низкий → `review_required`.
20. Frontend получает progress events; после завершения job пользователь видит список карточек.
21. Пользователь открывает карточку и видит metadata, Markdown preview, source trace, статус, confidence.
22. SetupGraph переходит к SETUP-06 (если есть `review_required`) или SETUP-07.

**Ожидаемый результат:**
- по parsed sections созданы RAG-карточки с YAML front matter и Markdown body;
- карточки имеют `doc_id`, `doc_type`, `source_files`, `source_sections`;
- low-confidence карточки помечены `review_required`;
- `source_document_lineage` обновлён;
- пользователь видит список карточек и статусы.

### 7.2. Альтернативные сценарии

**A1. LLM недоступна (`FE_BOT_FORCE_FALLBACK=1` или timeout).**
Если `doc_type` поддерживает template generation → карточка создаётся rule-based через `RAGCardFallbackGenerator` с `confidence_level=low`, статус `review_required`. Иначе → `generation_failed`.

**A2. Metadata неполная.**
Карточка создана, но mandatory metadata отсутствует: `status = metadata_incomplete`. Карточка сохраняется как `draft`, не переходит к chunking.

**A3. Body пустой или слишком короткий.**
LLM вернула пустое body: `status = body_empty`, `error_code = CARD_BODY_EMPTY`. Система делает retry.

**A4. Низкая уверенность (`confidence < threshold`).**
`status = review_required`. Карточка сохраняется, передаётся в SETUP-06. Пользователь видит LowConfidenceCardsPanel.

**A5. Частичный успех job.**
Часть карточек создана, часть failed: `RAGCardGenerationJob.status = partial_success`. UI предлагает: продолжить с созданными карточками, повторить генерацию для failed sections или исключить failed sections.

**A6. Повторная генерация (regenerate).**
Карточка уже существует: `regenerate_card()` загружает существующую карточку, получает `source_document_id` и `primary_source_section_id`, создаёт мини-job для одной секции. Новая карточка получает `card_version = old_version + 1`. Старая версия не удаляется. Audit event `RAG_CARD_REGENERATE_TRIGGERED`.

**A7. Конфликт `doc_id`.**
`DocIdGenerator` инкрементирует суффикс версии: `.v1` → `.v2` → `.v3`. Конфликт не приводит к ошибке при наличии версий.

### 7.3. Негативные сценарии

**N1. Нет parsed sections.**
`error_code = NO_SECTIONS_READY_FOR_CARD_GENERATION`. UI: «Нет секций для генерации RAG-карточек. Сначала выполните парсинг документов».

**N2. Parsed section невалидна (нет текста).**
`status = generation_failed`, `error_code = EMPTY_SECTION`.

**N3. Ontology недоступна.**
`status = metadata_incomplete`, `error_code = ONTOLOGY_UNAVAILABLE`.

**N4. Prompt template отсутствует.**
`status = generation_failed`, `error_code = PROMPT_TEMPLATE_NOT_FOUND`.

**N5. LLM вернула невалидный JSON.**
`error_code = INVALID_LLM_OUTPUT`. Система делает repair-prompt retry (до 3 попыток). После исчерпания → `generation_failed`.

**N6. LLM сгенерировала неизвестный `doc_type`.**
`error_code = INVALID_DOC_TYPE`. Карточка не переходит в `ready_for_metadata_validation`.

**N7. Ошибка сохранения Markdown-файла.**
`RAGCardDTO` сохранён, artifact не сохранён → `status = generation_failed`, `error_code = CARD_ARTIFACT_SAVE_FAILED`. Запускается compensation: artifact помечается orphaned.

**N8. Пользователь не имеет прав.**
API возвращает `403 Insufficient Permissions`.

**N9. Повторный запрос при активном job.**
`error_code = RAG_CARD_GENERATION_ALREADY_RUNNING`, HTTP 409.

**N10. Попытка prompt injection из parsed section.**
`MarkdownBuilder` sanitizes body: удаляет HTML-комментарии, `<script>`, `system:`-like spans. Prompt template структурно изолирует user_content.

### 7.4. Постусловия

После успешного завершения:
- создан и завершён `RAGCardGenerationJob` (DTO-59);
- созданы `RAGCardDTO` (DTO-66) со статусами `ready_for_metadata_validation` или `review_required`;
- созданы Markdown artifacts (DTO-62) в Object Storage;
- созданы `RAGCardMetadataDTO` (DTO-61) с YAML front matter;
- созданы `RAGCardSourceLinkDTO` (DTO-63) с типом `GENERATED_FROM`;
- создан `CardGenerationReportDTO` (DTO-64);
- `source_document_lineage` обновлён;
- processing log содержит generation events;
- UI показывает список карточек с фильтрами;
- карточки `review_required` передаются в SETUP-06; `ready_for_metadata_validation` — в SETUP-07.

---

## 8. Sequence diagram: система и внешние участники

```mermaid
sequenceDiagram
    actor User as Пользователь-настройщик
    actor Expert as Предметный эксперт
    participant Browser as Browser / Frontend
    participant System as Система (API + Backend)
    participant LLM as Ollama / LLM

    User->>Browser: Открыть мастер настройки Knowledge Base
    Browser->>System: GET /api/setup/{setup_job_id} + parsed sections summary
    System-->>Browser: Setup job + sections summary

    User->>Browser: Нажать «Сгенерировать RAG-карточки»
    Browser->>System: POST /api/setup/{setup_job_id}/rag-cards/generate
    System-->>Browser: 202 Accepted — generation_job_id, status=created

    Browser->>System: POST /api/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}/run
    System->>System: Получить parsed sections; определить doc_type и metadata candidates
    System->>System: Нормализовать metadata через OntologyMapper

    alt LLM-режим
        System->>LLM: Prompt (front matter + body generation)
        LLM-->>System: Structured output (front_matter, body_markdown, confidence)
    else Template-режим (FE_BOT_FORCE_FALLBACK=1)
        System->>System: RAGCardFallbackGenerator.generate(section)
    end

    System->>System: Precheck, ConfidenceCalculator, DocIdGenerator
    System->>System: Сохранить RAGCardDTO + Markdown artifact + lineage
    System-->>Browser: Progress event (rag_card.generated / review_required / failed)

    alt Генерация завершена
        System-->>Browser: job.completed — cards_by_type summary
        Browser-->>User: Показать список карточек (generated, review_required, failed)
    else Частичный успех
        System-->>Browser: job.partial_success
        Browser-->>User: Показать LowConfidenceCardsPanel + retry-опции
    end

    Expert->>Browser: Открыть карточку для просмотра
    Browser->>System: GET /api/setup/{setup_job_id}/rag-cards/{doc_id}/preview
    System-->>Browser: RAGCardPreviewDTO (metadata + body + source trace + precheck)
    Browser-->>Expert: Preview Drawer (Overview, YAML, Markdown, Source Trace)
```

---

## 9. Sequence diagram: взаимодействие сервисов системы

```mermaid
sequenceDiagram
    participant UI as Frontend UI
    participant API as API Backend
    participant Auth as Auth Service
    participant Orch as Setup Orchestrator
    participant Gen as RAGCardGenerationOrchestrator
    participant PSR as ParsedSection Registry
    participant SR as Source Registry
    participant ME as MetadataExtractor
    participant OM as OntologyMapper
    participant PTR as PromptTemplateRegistry
    participant LLM as LLMGateway
    participant Pre as CardValidationPrecheck
    participant Reg as RAGCardRegistry
    participant Art as ArtifactStorage
    participant Bus as EventBus
    participant Aud as AuditService
    participant Ana as AnalyticsService

    UI->>API: POST /api/setup/{setup_job_id}/rag-cards/generate
    API->>Auth: authorize(kb.rag_card.generate, setup_job_id)
    Auth-->>API: allowed
    API->>Orch: startRAGCardGeneration(setup_job_id, request)
    Orch->>Gen: create_job(setup_job_id, requested_by, section_ids, config)
    Gen->>Reg: get_active_for_setup_job() → None (нет активного)
    Gen->>PSR: list sections ready for generation
    PSR-->>Gen: [ParsedSection, ...]
    Gen->>Reg: create RAGCardGenerationJob (status=CREATED)
    Gen->>Bus: emit RAGCardGenerationJobCreatedEvent
    Gen->>Aud: audit(RAG_CARD_GENERATION_TRIGGERED)
    API-->>UI: 202 Accepted {generation_job_id, status=created}

    UI->>API: POST /run
    API->>Gen: run(generation_job_id)
    Gen->>Reg: transition CREATED→QUEUED→RUNNING
    Gen->>Bus: emit RAGCardGenerationJobStartedEvent

    loop для каждой ParsedSection
        Gen->>PSR: get section
        Gen->>SR: get source trace
        Gen->>ME: extract_metadata_candidates(section)
        Gen->>OM: normalize_*(candidates)
        OM-->>Gen: normalized + warnings
        Gen->>PTR: render(doc_type, context)
        PTR-->>Gen: rendered prompt
        alt LLM-режим
            Gen->>LLM: generate_structured(prompt, RAGCardDraft)
            LLM-->>Gen: draft (front_matter, body_markdown, confidence)
        else Fallback
            Gen->>Gen: RAGCardFallbackGenerator.generate(section)
        end
        Gen->>Pre: check(draft) → CardValidationReportDTO
        Gen->>Gen: ConfidenceCalculator.calculate(...)
        Gen->>Gen: DocIdGenerator.generate_doc_id(...)
        Gen->>Gen: MarkdownBuilder.build_markdown(metadata, body)
        alt precheck passed
            Gen->>Reg: save_version(card) + save_metadata(metadata)
            Gen->>Art: upload(setup_job_id, doc_id, markdown_bytes)
            Gen->>SR: link_artifact(GENERATED_FROM)
            Gen->>Bus: emit RAGCardGeneratedEvent
            alt review_required
                Gen->>Bus: emit RAGCardReviewRequiredEvent
            end
            Gen->>Ana: metrics(doc_type, confidence_bucket, duration_ms)
        else precheck failed
            Gen->>Reg: save failure (status=generation_failed)
            Gen->>Bus: emit RAGCardGenerationFailedEvent
        end
        Gen->>Reg: update RAGCardGenerationJobSection (status, duration_ms)
    end

    Gen->>Gen: Подсчитать summary; transition RUNNING→COMPLETED/PARTIAL_SUCCESS/FAILED
    Gen->>Reg: save CardGenerationReportDTO
    Gen->>Bus: emit RAGCardGenerationJobCompletedEvent / PartialSuccessEvent
    Gen->>Aud: audit(RAG_CARD_GENERATED × N)
    API-->>UI: 200 OK final RAGCardGenerationJobResponse
```

---

## 10. Frontend Scope

### 10.1. UI компоненты

```
KnowledgeBaseSetupPage
  └── RAGCardGenerationStep          ← новый wizard step (после ParsingStep)
        ├── RAGCardGenerationProgress   ← прогресс-бар + counters
        ├── RAGCardGenerationSummary    ← cards_by_type chips после завершения
        ├── LowConfidenceCardsPanel     ← banner при наличии review_required карточек
        ├── RAGCardGenerationErrorsPanel ← список failed sections
        └── RAGCardList                 ← таблица карточек с фильтрами
              └── RAGCardPreviewDrawer  ← детальный просмотр карточки
                    ├── RAGCardMetadataPanel   ← YAML metadata
                    ├── RAGCardBodyPreview     ← rendered Markdown
                    ├── RAGCardSourceTracePanel ← source doc + section
                    └── RegenerateCardButton
```

**RAGCardGenerationStep** — управляет lifecycle генерации:
- кнопка «Создать generation job» → POST `/rag-cards/generate`;
- кнопка «Запустить генерацию» → POST `/run` (sync);
- polling 2s через `useQuery refetchInterval` до terminal status;
- прогресс-бар `processed_sections / total_sections`;
- counters: generated, failed, review_required;
- кнопка «Отменить» (только если CREATED/QUEUED/RUNNING);
- кнопка «Далее →» (disabled если status = FAILED).

**RAGCardList** — колонки: `doc_id`, `title`, `doc_type` (badge), `status` (color), `confidence_level` (color), `source_document`, `retrieval_tags` (top-3 chips), `created_at`, actions (Preview, Regenerate).

Фильтры: `doc_type` (multi-select), `status` (multi-select), `confidence_level` (segmented), `source_document_id` (autocomplete). Pagination: page/page_size (default 20). Sort: `created_at:desc` default.

**RAGCardPreviewDrawer** — вкладки: Overview, YAML Metadata, Markdown Body, Source Trace, Validation/Precheck, Version History.

**LowConfidenceCardsPanel** — banner с CTA «Перейти к ручному review (SETUP-06)»; показывает `doc_id`, `title`, `confidence_level`, `review_required_reason`.

### 10.2. Клиентская логика

**Валидации:**
- нельзя запустить генерацию, если нет parsed sections;
- нельзя открыть карточку без `doc_id`;
- нельзя перейти к chunking, если есть critical failed cards без review;
- нельзя regenerate карточку без permission `kb.rag_card.regenerate`;
- нельзя редактировать generated metadata в SETUP-05 (editing вынесен в SETUP-06).

**Управление состоянием:** `generationJob`, `generationProgress`, `ragCards`, `selectedRAGCard`, `cardPreview`, `cardMetadata`, `cardBody`, `cardErrors`, `lowConfidenceCards`, `filters`, `pagination`, `sort`, `permissions`, `loadingStates`, `errorStates`.

**Feature flags:** `enable_llm_card_generation`, `enable_template_card_generation`, `enable_card_preview`, `enable_card_regeneration`, `enable_low_confidence_review`.

**TypeScript типы (новые):**
- `RAGCardGenerationJobStatus`, `RAGCardGenerationErrorCode`;
- `RAGCardGenerationJob`, `RAGCardListItem`, `RAGCardDetails`, `RAGCardPreview`;
- `RAGCardConfidenceLevel = 'high' | 'medium' | 'low'`;
- `RAGCardStatus` (10 значений);
- `DocType = 'schema_card' | 'task_card' | 'analytics_card' | 'field_definition_card' | 'feature_pattern_card' | 'validation_rule_card' | 'question_template_card'`.

### 10.3. UX/UI требования

- длительная генерация не блокирует UI; прогресс обновляется через polling;
- карточки доступны для preview сразу после создания (streaming);
- `review_required` карточки визуально выделены (цвет badge, LowConfidenceCardsPanel);
- failed sections имеют понятное объяснение ошибки;
- `partial_success` состояние понятно пользователю: что создано, что нет, что делать дальше;
- metadata и Markdown body отображаются на отдельных вкладках Preview Drawer;
- source trace доступен из каждой карточки.

---

## 11. Backend Scope

### 11.1. Новые и изменяемые сервисы

**API Backend** — новые endpoints (см. §16.1).

**RAGCardGenerationOrchestrator** (`src/fe_bot/setup/rag_card_generation/orchestrator.py`):
- `create_job(setup_job_id, requested_by, *, section_ids, config)` — создаёт job, блокирует дубли;
- `run(generation_job_id)` — синхронный in-process run;
- `regenerate_card(setup_job_id, doc_id, *, requested_by, reason, override_doc_type)` — повторная генерация одной карточки.

**Новые детерминированные компоненты** (`src/fe_bot/setup/rag_card_generation/`):
- `DocTypeDetector` — rule-based маппинг `section_type → doc_type`;
- `MetadataExtractor` — deterministic extraction без LLM;
- `OntologyMapper` — нормализация по `ontology_v1.yaml`;
- `PromptTemplateRegistry` — загрузка и render шаблонов из `prompts/rag_card/`;
- `DocIdGenerator` — deterministic `doc_id` с conflict resolution;
- `MarkdownBuilder` — сборка YAML front matter + sanitized body;
- `ConfidenceCalculator` — правила high/medium/low;
- `CardValidationPrecheck` — blocking validation перед сохранением.

**Переиспользуемые компоненты:**
- `LLMGateway` — через `LLMCardAdapter` (`src/fe_bot/setup/rag_card_generation/llm_adapter.py`);
- `RAGCardFallbackGenerator` — fallback при `FE_BOT_FORCE_FALLBACK=1` или LLM timeout;
- `SourceLifecycleService` — `link_artifact()` и `append_processing_log()` (SETUP-03);
- `ArtifactStorage`, `EventBus`, `AuditService`, `MetricsService`.

**RAGCardRegistry (расширение)** — новые методы: `save_metadata`, `get_metadata`, `save_version`, `list_versions`, `attach_artifact`, `list_for_setup_job` с фильтрами.

### 11.2. Таблицы PostgreSQL (целевое состояние; MVP — in-memory)

```sql
-- Lifecycle generation job
rag_card_generation_jobs (
    generation_job_id     TEXT PRIMARY KEY,
    setup_job_id          TEXT NOT NULL REFERENCES setup_jobs(id),
    requested_by          TEXT,
    status                TEXT NOT NULL,           -- RAGCardGenerationJobStatus
    total_sections        INT DEFAULT 0,
    processed_sections    INT DEFAULT 0,
    generated_cards       INT DEFAULT 0,
    failed_sections       INT DEFAULT 0,
    review_required_cards INT DEFAULT 0,
    started_at            TIMESTAMPTZ,
    finished_at           TIMESTAMPTZ,
    created_at            TIMESTAMPTZ NOT NULL,
    updated_at            TIMESTAMPTZ NOT NULL,
    error_code            TEXT,
    error_message         TEXT,
    config_json           JSONB
);

-- Per-section tracking
rag_card_generation_job_sections (
    generation_job_section_id  TEXT PRIMARY KEY,
    generation_job_id          TEXT NOT NULL REFERENCES rag_card_generation_jobs,
    section_id                 TEXT NOT NULL,
    source_document_id         TEXT NOT NULL,
    status                     TEXT NOT NULL,
    target_doc_type            TEXT,
    generated_doc_id           TEXT,
    confidence_level           TEXT,
    started_at                 TIMESTAMPTZ,
    finished_at                TIMESTAMPTZ,
    duration_ms                INT,
    error_code                 TEXT,
    error_message              TEXT,
    warnings_json              JSONB,
    metadata_json              JSONB,
    UNIQUE (generation_job_id, section_id)
);

-- RAG card main entity
rag_cards (
    doc_id                    TEXT NOT NULL,
    card_version              TEXT NOT NULL,
    setup_job_id              TEXT,
    doc_type                  TEXT NOT NULL,
    title                     TEXT NOT NULL,
    status                    TEXT NOT NULL,       -- 10 статусов
    confidence_level          TEXT,
    markdown_artifact_id      TEXT,
    source_document_id        TEXT,
    primary_source_section_id TEXT,
    created_by_type           TEXT,
    created_by_id             TEXT,
    created_at                TIMESTAMPTZ NOT NULL,
    updated_at                TIMESTAMPTZ NOT NULL,
    review_required_reason    TEXT,
    error_code                TEXT,
    error_message             TEXT,
    metadata_json             JSONB,
    PRIMARY KEY (doc_id, card_version)
);

-- YAML front matter / typed metadata
rag_card_metadata (
    doc_id                  TEXT NOT NULL,
    card_version            TEXT NOT NULL,
    front_matter_json       JSONB NOT NULL,
    domain                  TEXT[],
    task_type               TEXT[],
    data_source             TEXT[],
    entity_type             TEXT[],
    phase                   TEXT[],
    agent_targets           TEXT[],
    retrieval_tags          TEXT[],
    required_input_fields   TEXT[],
    output_fields           TEXT[],
    feature_tables_json     JSONB,
    validation_rules_json   JSONB,
    compatible_models       TEXT[],
    owner                   TEXT,
    last_verified_at        TIMESTAMPTZ,
    metadata_schema_version TEXT DEFAULT 'rag_metadata_v1',
    PRIMARY KEY (doc_id, card_version)
);

-- Source lineage
rag_card_source_links (
    source_link_id     TEXT PRIMARY KEY,
    doc_id             TEXT NOT NULL,
    card_version       TEXT NOT NULL,
    source_document_id TEXT NOT NULL,
    source_section_id  TEXT NOT NULL,
    relation_type      TEXT DEFAULT 'generated_from',
    created_at         TIMESTAMPTZ NOT NULL,
    metadata_json      JSONB,
    UNIQUE (doc_id, card_version, source_section_id, relation_type)
);

-- Artifact links
rag_card_artifacts (
    artifact_link_id TEXT PRIMARY KEY,
    doc_id           TEXT NOT NULL,
    card_version     TEXT NOT NULL,
    artifact_id      TEXT NOT NULL,
    artifact_type    TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL
);
```

### 11.3. Интеграционные изменения

- `ParsedSectionDTO` — вход `RAGCardGenerationOrchestrator`; не изменяется.
- `SourceLifecycleService` — вызов `link_artifact(source_document_id, target_type=RAG_CARD, target_id=doc_id, relation_type=GENERATED_FROM)`.
- `LineageRelationType` расширен значением `GENERATED_FROM` (если не существует из SETUP-03).
- SETUP-07 принимает `RAGCardDTO` (DTO-66) со статусом `ready_for_metadata_validation`.
- SETUP-08 принимает только карточки, прошедшие policy validation/review.
- `SetupGraph` — новый step `rag_card_generation` между `parse` и `run`.

---

## 12. Бизнес-правила и ограничения

**Правила выбора секций:**
- BR-01. Генерировать карточки можно только по `ParsedSectionDTO` со статусом `classified` или `ready_for_rag_card_generation`.
- BR-02. Секции со статусом `invalid` или `ignored` не используются.

**Правила обязательных полей:**
- BR-03. Каждый `RAGCardDTO` должен иметь `source_document_id` и `source_section_id`.
- BR-04. `doc_id` должен быть уникален в пределах `(setup_job_id, card_version)`.
- BR-05. `doc_type` должен входить в допустимый enum из `ontology_v1.yaml`.
- BR-06. Карточки без body (`body_empty`) не допускаются к следующему этапу.
- BR-07. Карточки без required metadata получают `status = metadata_incomplete`.

**Правила доверия к LLM:**
- BR-08. LLM output не принимается без schema validation.
- BR-09. Ontology values имеют приоритет над LLM-предложениями.
- BR-10. Deterministic metadata extraction имеет приоритет над LLM metadata при более высоком confidence.

**Правила статусов:**
- BR-11. `draft`/`review_required` карточки не индексируются в Vector DB.
- BR-12. `RAGCardGenerator` не создаёт карточки напрямую в active Knowledge Base.
- BR-13. Карточки с `confidence < threshold` (дефолт 0.7) получают `status = review_required`.

**Правила повторной генерации:**
- BR-14. Повторная генерация карточки создаёт новую `card_version`; старая версия не удаляется.
- BR-15. `regenerate` должен иметь `reason`; не изменяет `source_trace`.
- BR-16. Повторная генерация по тому же `section_id` не создаёт дубликат без новой версии.

**Правила `doc_id`:**
- BR-17. `doc_id` генерируется детерминированно: `{doc_type_short}.{slug(title)}.v{N}`.
- BR-18. Конфликт `doc_id` разрешается инкрементом суффикса `N`.

**Правила prompt safety:**
- BR-19. Prompt template структурно изолирует source content: `<system>...</system>` отделён от `<user_content>`.
- BR-20. `MarkdownBuilder` sanitizes body: удаляет HTML-комментарии, `<script>`, `system:`-like spans.

---

## 13. Входные данные и источники

### 13.1. Входные поля запроса

| Поле | Тип | Обязательность | Источник | Правило валидации |
| --- | --- | --- | --- | --- |
| `setup_job_id` | string | Required | UI/API | Должен существовать |
| `generation_request_id` | string | Recommended | UI/API | Для идемпотентности |
| `section_ids` | list[string] | Optional | UI/API | Если пусто — все ready sections |
| `source_document_ids` | list[string] | Optional | UI/API | Фильтр по документам |
| `generation_mode` | string | Optional | UI/config | `llm`, `template`, `hybrid` |
| `ontology_version` | string | Optional | Config | Дефолт `ontology_v1` |
| `metadata_schema_version` | string | Optional | Config | Дефолт `rag_metadata_v1` |
| `prompt_template_version` | string | Optional | Config | Дефолт `rag_card_prompts_v1` |
| `llm_model` | string | Optional | Config | Дефолт `llama3.2:latest` |
| `confidence_threshold` | float | Optional | Config | Диапазон 0–1; дефолт 0.7 |
| `allow_multiple_cards_per_section` | bool | Optional | Config | Дефолт false (MVP) |

### 13.2. Источники данных

| Источник | Что предоставляет |
| --- | --- |
| Parsed Section Registry | `ParsedSectionDTO` с `normalized_text`, `structural_payload`, `section_type` |
| Source Registry | `source_document_id`, filename, lineage |
| Ontology Registry (`ontology_v1.yaml`) | canonical enum values для domain, task_type, data_source, entity_type, phase, agent_targets; синонимы |
| Prompt Template Registry (`prompts/rag_card/*.txt`) | шаблоны для 7 `doc_type` |
| LLM Gateway / Ollama | structured output (front_matter, body_markdown, confidence, warnings) |
| `RAGCardFallbackGenerator` | rule-based карточка при недоступности LLM |

### 13.3. Связь с ontology v1

Файл `rag/ontology/ontology_v1.yaml` определяет canonical enum values для полей metadata:

| Поле | Canonical values (примеры) |
| --- | --- |
| `domain` | `naval`, `air`, `ground`, `cyber`, `analytical`, `custom` |
| `task_type` | `classification`, `regression`, `clustering`, `anomaly_detection`, `ranking`, `trajectory_forecasting`, `object_detection` |
| `data_source` | `radar`, `sonar`, `AIS`, `ESM`, `EO_IR`, `satellite`, `tracks_fused`, `CSV`, `JSON`, `SQL`, `custom` |
| `entity_type` | `track`, `sensor`, `vessel`, `aircraft`, `vehicle`, `event`, `session`, `customer`, `product`, `device`, `zone`, `environment` |
| `phase` | `nlu`, `task_discovery`, `data_profiling`, `domain_context`, `feature_synthesis`, `validation`, `data_generation`, `model_selection`, `export`, `analytics` |
| `agent_targets` | 16 агентов из AGENTS.md: `TaskDiscoveryAgent`, `DataProfilingAgent`, `FeatureSynthesisAgent`, `FeatureCriticAgent`, ... |

Неизвестные значения порождают `WARNING_ONTOLOGY_UNKNOWN_TERM`, не errors. Карточка с `domain = custom` автоматически помечается `review_required`.

---

## 14. Выходные данные и результаты

### 14.1. Ответ на запуск job (202 Accepted)

```json
{
  "generation_job_id": "rag_gen_job_001",
  "setup_job_id": "setup_001",
  "status": "created",
  "total_sections": 24,
  "processed_sections": 0,
  "generated_cards": 0,
  "failed_sections": 0,
  "review_required_cards": 0,
  "message": "Генерация RAG-карточек запущена"
}
```

### 14.2. Ответ после завершения run (200 OK)

```json
{
  "generation_job_id": "rag_gen_job_001",
  "setup_job_id": "setup_001",
  "status": "completed",
  "total_sections": 24,
  "processed_sections": 24,
  "generated_cards": 22,
  "failed_sections": 2,
  "review_required_cards": 4,
  "started_at": "2026-06-19T13:00:00Z",
  "finished_at": "2026-06-19T13:08:30Z"
}
```

### 14.3. Побочные эффекты

Создаются/обновляются:
- `RAGCardGenerationJob` (DTO-59) — lifecycle job;
- `RAGCardGenerationJobSection` (DTO-60) — per-section результат;
- `RAGCard` (DTO-66) — основная карточка;
- `RAGCardMetadataDTO` (DTO-61) — YAML front matter;
- `RAGCardMarkdownDTO` (DTO-62) — Markdown файл в Object Storage;
- `RAGCardSourceLinkDTO` (DTO-63) — lineage link;
- `CardGenerationReportDTO` (DTO-64) — итоговый отчёт;
- `CardValidationReportDTO` (DTO-65) — precheck-результат per card;
- `source_document_lineage` — lineage `parsed_section → rag_card`;
- audit events, analytics events, processing logs.

### 14.4. Результирующее состояние

| Исход | Job status | Дальнейший путь |
| --- | --- | --- |
| Полный успех | `completed` | `review_required` → SETUP-06; `ready_for_metadata_validation` → SETUP-07 |
| Частичный успех | `partial_success` | UI предлагает retry для failed; продолжение доступно |
| Полная ошибка | `failed` | UI показывает retry; SetupGraph не переходит к chunking |

---

## 15. DTO и модели данных

### 15.1. Входные DTO

**DTO-59 (вход): GenerateRAGCardsRequest**

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
    "confidence_threshold": 0.7,
    "allow_multiple_cards_per_section": false,
    "mark_low_confidence_as_review_required": true,
    "save_llm_trace": false
  }
}
```

### 15.2. Выходные DTO

**DTO-59: RAGCardGenerationJobDTO**

```json
{
  "generation_job_id": "rag_gen_job_001",
  "setup_job_id": "setup_001",
  "requested_by": "user_001",
  "status": "completed",
  "total_sections": 24,
  "processed_sections": 24,
  "generated_cards": 22,
  "failed_sections": 2,
  "review_required_cards": 4,
  "started_at": "2026-06-19T13:00:00Z",
  "finished_at": "2026-06-19T13:08:30Z",
  "created_at": "2026-06-19T12:59:59Z",
  "updated_at": "2026-06-19T13:08:30Z",
  "error_code": null,
  "error_message": null,
  "config": {
    "generation_mode": "hybrid",
    "confidence_threshold": 0.7,
    "llm_model": "llama3.2:latest",
    "prompt_template_version": "rag_card_prompts_v1",
    "ontology_version": "ontology_v1"
  }
}
```

**DTO-66: RAGCardDTO** (расширение DTO-11)

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
  "created_by_id": "rag_card_generation_service",
  "created_at": "2026-06-19T13:01:00Z",
  "updated_at": "2026-06-19T13:01:00Z",
  "review_required_reason": "Некоторые metadata поля имеют medium confidence",
  "error_code": null,
  "error_message": null
}
```

**DTO-61: RAGCardMetadataDTO**

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
    "retrieval_tags": ["sensor", "analytics", "uptime", "detection_probability"]
  },
  "metadata_schema_version": "rag_metadata_v1"
}
```

**DTO-62: RAGCardMarkdownDTO**

```json
{
  "doc_id": "analytics.sensor_analytics_T.v1",
  "card_version": "1.0",
  "front_matter_yaml": "---\ndoc_id: analytics.sensor_analytics_T.v1\n...\n---",
  "body_markdown": "## Sensor Analytics Feature Table\n\nОписание аналитических признаков...",
  "markdown": "---\ndoc_id: analytics.sensor_analytics_T.v1\n...\n---\n\n## Sensor Analytics Feature Table\n\n..."
}
```

**DTO-63: RAGCardSourceLinkDTO**

```json
{
  "source_link_id": "link_001",
  "doc_id": "analytics.sensor_analytics_T.v1",
  "card_version": "1.0",
  "source_document_id": "src_001",
  "source_section_id": "sec_005",
  "relation_type": "generated_from",
  "created_at": "2026-06-19T13:01:00Z",
  "metadata": {}
}
```

**DTO-65: CardValidationReportDTO**

```json
{
  "validation_report_id": "vr_001",
  "doc_id": "analytics.sensor_analytics_T.v1",
  "card_version": "1.0",
  "passed": true,
  "errors": [],
  "warnings": [{"code": "RETRIEVAL_TAGS_EMPTY", "message": "..."}],
  "checked_at": "2026-06-19T13:01:00Z"
}
```

### 15.3. Доменные связи

```
RAGCardGenerationJob (DTO-59)
  1 → N  RAGCardGenerationJobSection (DTO-60)

ParsedSection
  1 → 1  RAGCard (DTO-66)   [MVP; архитектура поддерживает 1→N]

RAGCard (DTO-66)
  1 → 1  RAGCardMetadataDTO (DTO-61)    [по (doc_id, card_version)]
  1 → 1  RAGCardMarkdownDTO (DTO-62)    [через markdown_artifact_id]
  1 → N  RAGCardSourceLinkDTO (DTO-63)
  1 → N  CardValidationReportDTO (DTO-65)
```

### 15.4. Версионирование DTO

- `GenerateRAGCardsRequest` v1, `RAGCardGenerationJobDTO` v1, `RAGCardDTO` v1, `RAGCardMetadataDTO` v1 (schema version `rag_metadata_v1`).
- `doc_id` идентифицирует логическую карточку; `card_version` — конкретную версию.
- Regenerate создаёт новую `card_version`; старые версии не удаляются.
- `deprecated` версия не участвует в новых индексах.
- Добавление optional metadata fields — backward-compatible. Изменение обязательных полей требует новой `metadata_schema_version`.

---

## 16. API contracts / event contracts / integration contracts

### 16.1. REST API

| Метод | URL | Назначение | Auth | Ответ |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/setup/{setup_job_id}/rag-cards/generate` | Создать generation job | `kb.rag_card.generate` | 202 `RAGCardGenerationJobResponse` |
| POST | `/api/v1/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}/run` | Запустить sync run | `kb.rag_card.generate` | 200 финальный `RAGCardGenerationJobResponse` |
| GET | `/api/v1/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}` | Статус job | `kb.rag_card.read` | 200 `RAGCardGenerationJobResponse` |
| POST | `/api/v1/setup/{setup_job_id}/rag-card-generation-jobs/{job_id}/cancel` | Отменить job | `kb.rag_card.generate` | 200 / 409 |
| GET | `/api/v1/setup/{setup_job_id}/rag-cards` | Список карточек с фильтрами | `kb.rag_card.read` | 200 `RAGCardListResponse` |
| GET | `/api/v1/setup/{setup_job_id}/rag-cards/{doc_id}` | Детали карточки | `kb.rag_card.read` | 200 `RAGCardDetailsDTO` |
| GET | `/api/v1/setup/{setup_job_id}/rag-cards/{doc_id}/preview` | Preview карточки | `kb.rag_card.preview` | 200 `RAGCardPreviewDTO` |
| POST | `/api/v1/setup/{setup_job_id}/rag-cards/{doc_id}/regenerate` | Повторная генерация | `kb.rag_card.regenerate` | 200 `RegenerateRAGCardResponse` |

**Query params для GET /rag-cards:** `doc_type`, `status`, `confidence_level`, `source_document_id`, `page` (default 1), `page_size` (default 20), `sort` (`created_at:desc` default).

**Коды ошибок API:**

| HTTP | Код | Условие |
| --- | --- | --- |
| 400 | `NO_SECTIONS_READY_FOR_CARD_GENERATION` | Нет секций для генерации |
| 400 | `INVALID_GENERATION_MODE` | Недопустимый generation_mode |
| 400 | `ONTOLOGY_VERSION_NOT_FOUND` | Версия ontology не найдена |
| 400 | `PROMPT_TEMPLATE_NOT_FOUND` | Шаблон не найден |
| 403 | `INSUFFICIENT_PERMISSIONS` | Нет прав |
| 404 | `SETUP_JOB_NOT_FOUND` | Setup job не найден |
| 404 | `SECTION_NOT_FOUND` | Section не найдена |
| 409 | `RAG_CARD_GENERATION_ALREADY_RUNNING` | Уже запущен активный job |
| 409 | `SECTION_NOT_READY` | Section не в нужном статусе |

### 16.2. Event contracts

| Event | Topic | Payload | Семантика |
| --- | --- | --- | --- |
| `RAGCardGenerationJobCreatedEvent` | `rag_card_generation.job.created` | `{generation_job_id, setup_job_id, total_sections, requested_by, occurred_at}` | at-least-once |
| `RAGCardGenerationJobStartedEvent` | `rag_card_generation.job.started` | `{generation_job_id, setup_job_id, occurred_at}` | at-least-once |
| `RAGCardGeneratedEvent` | `rag_card.generated` | `{generation_job_id, doc_id, doc_type, source_section_id, confidence_level, occurred_at}` | at-least-once |
| `RAGCardReviewRequiredEvent` | `rag_card.review_required` | `{generation_job_id, doc_id, reasons[], occurred_at}` | at-least-once |
| `RAGCardGenerationFailedEvent` | `rag_card.generation_failed` | `{generation_job_id, section_id, error_code, reason, occurred_at}` | at-least-once |
| `RAGCardGenerationJobCompletedEvent` | `rag_card_generation.job.completed` | `{generation_job_id, generated_cards, failed_sections, review_required_cards, duration_ms, occurred_at}` | at-least-once |
| `RAGCardGenerationJobPartialSuccessEvent` | `rag_card_generation.job.partial_success` | `{generation_job_id, ...summary, occurred_at}` | at-least-once |
| `RAGCardGenerationJobFailedEvent` | `rag_card_generation.job.failed` | `{generation_job_id, error_code, reason, occurred_at}` | at-least-once |

**Все events:** `frozen=True`, `extra="forbid"`, payload встраивается в `SetupProgressEvent.metrics`.

### 16.3. Контрактные требования

**Идемпотентность:**
- `generation_request_id` дедуплицирует повторные POST `/generate`;
- `(generation_job_id, section_id)` уникальны в `job_sections`;
- `(doc_id, card_version)` уникальны в `rag_cards`;
- `source_link_repo.link()` идемпотентен по `(doc_id, card_version, source_section_id, relation_type)`;
- save markdown artifact идемпотентен по `(doc_id, card_version)`.

**Таймауты и retry:**
- API возвращает 202 Accepted немедленно; sync run блокирует до завершения;
- LLM timeout задаётся конфигурацией (дефолт 60s per-request);
- invalid JSON → repair-prompt retry (max 3 попытки);
- LLM timeout/unavailable → retry with backoff → fallback или `generation_failed`;
- artifact save failed → retry → compensation;
- event publish failed → outbox pattern.

---

## 17. Нефункциональные требования

### 17.1. Производительность

- запуск generation job возвращает `job_id` немедленно (202 Accepted);
- синхронный run блокирует HTTP-соединение (MVP); polling для прогресса;
- каждый LLM-вызов имеет configurable timeout (дефолт 60s);
- карточки сохраняются по мере готовности (не batch в конце);
- `max_sections_per_generation_job`, `max_llm_calls_per_job`, `max_prompt_tokens` — configurable лимиты.

### 17.2. Доступность

- UI восстанавливает generation job после refresh через polling;
- сбой Notification Service не ломает generation job;
- сбой LLM для одной секции не ломает весь job (partial_success);
- частичный успех сохраняет созданные карточки.

### 17.3. Безопасность

- проверка `setup_job_id` владельца — cross-job access blocked;
- prompt injection из parsed section не интерпретируется как инструкция: `MarkdownBuilder` sanitizes, prompt template структурно изолирует `<user_content>`;
- raw LLM response не сохраняется (security); только parsed/validated данные;
- карточки в restricted KB не уходят во внешние LLM.

### 17.4. Аудит

Фиксируется: кто запустил job; какие sections использовались; `prompt_template_version`, `llm_model`; какие карточки созданы; какие `review_required`; какие failed; кто запустил regenerate.

### 17.5. Наблюдаемость

**Метрики:**

| Метрика | Тип | Labels |
| --- | --- | --- |
| `rag_card_generation_jobs_total` | Counter | `outcome` (completed/partial/failed) |
| `rag_cards_generated_total` | Counter | `doc_type`, `confidence_bucket` |
| `rag_cards_failed_total` | Counter | `error_code` |
| `rag_cards_review_required_total` | Counter | `doc_type` |
| `rag_card_generation_duration_ms` | Histogram | `outcome` |
| `llm_card_generation_calls_total` | Counter | `doc_type`, `model` |
| `llm_invalid_output_total` | Counter | `doc_type` |
| `llm_timeout_total` | Counter | `model` |
| `metadata_incomplete_total` | Counter | `doc_type` |
| `doc_id_conflicts_total` | Counter | — |

**Structured log per card:** `{generation_job_id, section_id, doc_id, doc_type, prompt_template_version, ontology_version, llm_model, confidence_level, duration_ms, outcome}`.

**Trace context:** `setup_job_id`, `source_document_id`, `source_section_id`, `generation_job_id`, `doc_id`, `card_version`, `artifact_id`.

### 17.6. Масштабируемость

- worker pool для `RAGCardGenerationOrchestrator` (будущее);
- LLM calls ограничены rate limit;
- cards и generation logs имеют pagination.

---

## 18. Ошибки и обработка исключений

### 18.1. Формат ошибки

```json
{
  "error_code": "NO_SECTIONS_READY_FOR_CARD_GENERATION",
  "message": "Нет секций, готовых для генерации RAG-карточек",
  "details": {"setup_job_id": "setup_001"}
}
```

### 18.2. Коды ошибок валидации (4xx)

| Код | HTTP | Описание |
| --- | --- | --- |
| `SETUP_JOB_NOT_FOUND` | 404 | Setup job не существует |
| `NO_SECTIONS_READY_FOR_CARD_GENERATION` | 400 | Нет ready sections |
| `SECTION_NOT_FOUND` | 404 | Конкретная section не найдена |
| `SECTION_NOT_READY` | 409 | Section не в нужном статусе |
| `INVALID_GENERATION_MODE` | 400 | Недопустимый generation_mode |
| `ONTOLOGY_VERSION_NOT_FOUND` | 400 | Версия ontology не найдена |
| `METADATA_SCHEMA_NOT_FOUND` | 400 | Metadata schema не найдена |
| `PROMPT_TEMPLATE_NOT_FOUND` | 400 | Шаблон для doc_type не найден |
| `RAG_CARD_GENERATION_ALREADY_RUNNING` | 409 | Активный job уже существует |
| `INSUFFICIENT_PERMISSIONS` | 403 | Нет необходимых прав |

### 18.3. Системные ошибки (5xx / per-card)

| Код | Описание |
| --- | --- |
| `LLM_GATEWAY_UNAVAILABLE` | LLM Gateway недоступен |
| `LLM_TIMEOUT` | Timeout LLM-запроса |
| `INVALID_LLM_OUTPUT` | LLM вернула невалидный JSON или схему |
| `INVALID_DOC_TYPE` | Неизвестный `doc_type` в output |
| `DOC_ID_CONFLICT` | Не удалось разрешить конфликт `doc_id` |
| `CARD_BODY_EMPTY` | Body карточки пустое |
| `FRONT_MATTER_INVALID` | YAML front matter невалиден |
| `ONTOLOGY_MAPPER_UNAVAILABLE` | OntologyMapper недоступен |
| `CARD_REGISTRY_UNAVAILABLE` | RAGCardRegistry недоступен |
| `ARTIFACT_STORAGE_SAVE_FAILED` | Ошибка сохранения Markdown artifact |
| `SOURCE_LINEAGE_UPDATE_FAILED` | Ошибка обновления lineage |
| `DATABASE_UNAVAILABLE` | PostgreSQL недоступен |
| `EVENT_BUS_UNAVAILABLE` | Event Bus недоступен |

### 18.4. Поведение системы при ошибках

**Retry:** invalid LLM JSON → repair-prompt → retry (max 3); LLM timeout → retry with backoff; artifact save failed → retry; registry save failed → retry; event publish failed → outbox.

**Compensation:** если `RAGCardDTO` сохранён, но Markdown artifact не сохранён → карточка получает `generation_failed`; если artifact сохранён, но registry save failed → artifact помечается orphaned (cleanup в S7).

**Dead letter queue:** `rag_card.generated/generation_failed` events; lineage update events; artifact save events.

**Ручная обработка:** RAG admin открывает failed sections, запускает regenerate или отправляет на ручной review SETUP-06.

---

## 19. Acceptance Criteria

### AC-01..05. Запуск генерации

- **AC-01.** POST `/rag-cards/generate` с валидным `setup_job_id` и правами `kb.rag_card.generate` возвращает 202 Accepted с `generation_job_id` и `status=created`.
- **AC-02.** POST `/rag-cards/generate` без прав возвращает 403 с кодом `INSUFFICIENT_PERMISSIONS`.
- **AC-03.** POST `/rag-cards/generate` при активном job возвращает 409 с кодом `RAG_CARD_GENERATION_ALREADY_RUNNING`.
- **AC-04.** POST `/rag-cards/generate` для несуществующего `setup_job_id` возвращает 404.
- **AC-05.** Повторный POST с тем же `generation_request_id` возвращает существующий job без создания дубля.

### AC-06..09. Выбор секций

- **AC-06.** Если `section_ids` не указан, job включает все sections со статусом `classified` или `ready_for_rag_card_generation`.
- **AC-07.** Sections со статусом `invalid` или `ignored` исключаются из job.
- **AC-08.** POST `/rag-cards/generate` при отсутствии ready sections возвращает 400 с кодом `NO_SECTIONS_READY_FOR_CARD_GENERATION`.
- **AC-09.** Если `section_ids` указан, job обрабатывает только указанные sections.

### AC-10..17. Генерация карточек

- **AC-10.** Для каждой section определяется `target_doc_type` через `DocTypeDetector`; значение из допустимого enum `ontology_v1.yaml`.
- **AC-11.** `doc_id` генерируется детерминированно по схеме `{doc_type_short}.{slug(title)}.v{N}`.
- **AC-12.** Каждая карточка содержит YAML front matter с required fields: `doc_id`, `doc_type`, `title`, `version`, `status`, `source_files`, `source_sections`.
- **AC-13.** Каждая карточка содержит непустой Markdown body.
- **AC-14.** Каждая карточка имеет `source_document_id`, привязанный к исходному документу.
- **AC-15.** Каждая карточка имеет `primary_source_section_id`, привязанный к parsed section.
- **AC-16.** Карточки с пустым `body_markdown` (менее 20 символов) получают `status=body_empty` и не переходят к следующему этапу.
- **AC-17.** Карточки с `doc_type`, не входящим в допустимый enum, получают `error_code=INVALID_DOC_TYPE`.

### AC-18..22. Metadata и ontology

- **AC-18.** `retrieval_tags` непустые у ≥ 95% карточек; карточки с пустыми tags получают warning `RETRIEVAL_TAGS_EMPTY`.
- **AC-19.** `domain`, `phase`, `agent_targets` нормализованы по `ontology_v1.yaml`; неизвестные значения порождают warning.
- **AC-20.** Карточки с `domain=custom` автоматически получают `status=review_required`.
- **AC-21.** Карточки без required metadata полей получают `status=metadata_incomplete`.
- **AC-22.** `metadata_schema_version` установлена в `rag_metadata_v1` для всех карточек.

### AC-23..27. LLM output

- **AC-23.** LLM output проходит schema validation перед сохранением; невалидный JSON вызывает repair-retry.
- **AC-24.** При 3 неудачных попытках парсинга LLM output section получает `status=generation_failed`.
- **AC-25.** При `FE_BOT_FORCE_FALLBACK=1` или LLM timeout используется `RAGCardFallbackGenerator`; карточка получает `confidence_level=low`.
- **AC-26.** Raw LLM response не сохраняется в `RAGCardDTO` или artifacts.
- **AC-27.** Prompt injection в `normalized_text` parsed section не выполняется как инструкция LLM; `MarkdownBuilder` удаляет `system:`-like spans из body.

### AC-28..31. Статусы и review

- **AC-28.** Карточки с `confidence_score < confidence_threshold` (дефолт 0.7) получают `status=review_required`.
- **AC-29.** `confidence_level` принимает значение `high` (score ≥ 0.85), `medium` (0.6–0.85), `low` (< 0.6).
- **AC-30.** `review_required_reason` заполнен при `status=review_required`.
- **AC-31.** `draft` и `review_required` карточки не индексируются в Vector DB (не переходят в SETUP-09).

### AC-32..36. Сохранение и lineage

- **AC-32.** Каждая успешно сгенерированная карточка сохраняется в `RAGCardRegistry` с уникальным `(doc_id, card_version)`.
- **AC-33.** Markdown файл сохраняется в `ArtifactStorage` по пути `rag/cards/{setup_job_id}/{doc_id}.md`.
- **AC-34.** `source_document_lineage` обновляется через `SourceLifecycleService.link_artifact()` с `relation_type=GENERATED_FROM`.
- **AC-35.** `RAGCardSourceLinkDTO` идемпотентен по `(doc_id, card_version, source_section_id, relation_type)`.
- **AC-36.** Повторная генерация (regenerate) создаёт новую `card_version`; старая версия остаётся в registry.

### AC-37..42. UI и прогресс

- **AC-37.** После POST `/generate` UI показывает этап «Генерация RAG-карточек» с прогресс-баром.
- **AC-38.** Прогресс `processed_sections / total_sections` обновляется через polling (интервал ≤ 2s).
- **AC-39.** После завершения job UI показывает `RAGCardList` с колонками: `doc_id`, `title`, `doc_type`, `status`, `confidence_level`.
- **AC-40.** `RAGCardPreviewDrawer` показывает YAML metadata, Markdown body, Source Trace и Precheck report.
- **AC-41.** `LowConfidenceCardsPanel` появляется при наличии карточек `status=review_required`; содержит CTA к SETUP-06.
- **AC-42.** Кнопка «Далее →» disabled при `job.status=failed`.

### AC-43..46. Частичный успех и retry

- **AC-43.** При `job.status=partial_success` UI показывает количество успешных, failed и `review_required` карточек.
- **AC-44.** Пользователь может запустить regenerate для failed sections без перезапуска всего job.
- **AC-45.** Regenerate карточки требует permission `kb.rag_card.regenerate`; без прав возвращает 403.
- **AC-46.** Regenerate создаёт мини-job для одной секции; итоговый статус отражается в `RAGCardList`.

### AC-47..51. События и аудит

- **AC-47.** При создании job публикуется `RAGCardGenerationJobCreatedEvent`.
- **AC-48.** При завершении каждой карточки публикуется `RAGCardGeneratedEvent` или `RAGCardGenerationFailedEvent`.
- **AC-49.** При `status=review_required` публикуется `RAGCardReviewRequiredEvent`.
- **AC-50.** При завершении job публикуется `RAGCardGenerationJobCompletedEvent` или `PartialSuccessEvent`.
- **AC-51.** Audit Service фиксирует `RAG_CARD_GENERATION_TRIGGERED`, `RAG_CARD_GENERATED` (per card), `RAG_CARD_REGENERATE_TRIGGERED`, `RAG_CARD_REVIEW_REQUIRED` с `actor_id`, `target_type="rag_card"`, `target_id=doc_id`, `setup_job_id`.

---

## 20. Definition of Done

- [ ] API: 8 endpoints реализованы, задокументированы в OpenAPI, покрыты integration tests.
- [ ] Schemas: DTO-59..66 реализованы как Pydantic 2 модели (`ConfigDict(extra="forbid")`).
- [ ] Миграции: DDL для 6 таблиц PostgreSQL подготовлены (MVP: in-memory + snapshot/restore).
- [ ] Оркестратор: `RAGCardGenerationOrchestrator` с `create_job()`, `run()`, `regenerate_card()`.
- [ ] Детерминированные компоненты: `DocTypeDetector`, `MetadataExtractor`, `OntologyMapper`, `PromptTemplateRegistry`, `DocIdGenerator`, `MarkdownBuilder`, `ConfidenceCalculator`, `CardValidationPrecheck` — реализованы и покрыты unit tests.
- [ ] LLM adapter: `LLMCardAdapter` с retry, repair-prompt, fallback на `RAGCardFallbackGenerator`.
- [ ] Prompt templates: 7 шаблонов в `prompts/rag_card/` с prompt injection protection.
- [ ] Lineage: `GENERATED_FROM` в `LineageRelationType`; `link_artifact()` вызывается per card.
- [ ] Frontend: `RAGCardGenerationStep`, `RAGCardList`, `RAGCardPreviewDrawer`, `LowConfidenceCardsPanel` реализованы и покрыты unit tests.
- [ ] Events: 8 event-классов; все публикуются через `EventBus`.
- [ ] Audit: 4 `AuditAction` фиксируются.
- [ ] Metrics: 10 счётчиков/histograms.
- [ ] Structured logging: per-card и per-job log records.
- [ ] Tests: ~250 новых тестов (unit + component + integration + frontend); все зелёные.
- [ ] Mypy clean, ruff clean, frontend typecheck clean, build clean.
- [ ] Traceability: `docs/traceability/setup-05.md` обновлён; 51 AC → тесты.
- [ ] Security review: prompt injection protection задокументирована; raw LLM response не хранится.
- [ ] Документация: `docs/06-rag/card-lifecycle.md` обновлён; runbook создан.
- [ ] Регрессия: legacy `SetupPipeline._generate_cards` (SETUP-01..03 e2e) зелёный.

---

## 21. Тесты

### 21.1. Unit tests

| Компонент | Что проверяется | Целевой файл |
| --- | --- | --- |
| `RAGCardGenerationJob` | state machine transitions; counters; http_status_for | `tests/unit/test_rag_card_generation_job_schema.py` |
| `DocTypeDetector` | 7 прямых маппингов; fallback; INVALID | `tests/unit/test_doc_type_detector.py` |
| `MetadataExtractor` | каждый extractor; roundtrip для analytics section | `tests/unit/test_metadata_extractor.py` |
| `OntologyMapper` | normalize для каждого поля; неизвестное значение → warning; синонимы | `tests/unit/test_ontology_mapper.py` |
| `PromptTemplateRegistry` | render для каждого doc_type; missing template raises; injection protection | `tests/unit/test_prompt_template_registry.py` |
| `DocIdGenerator` | basic; кириллица; conflict → v2; long title | `tests/unit/test_doc_id_generator.py` |
| `MarkdownBuilder` | build; deterministic order; sanitize html; sanitize system prompt; extract roundtrip | `tests/unit/test_markdown_builder.py` |
| `ConfidenceCalculator` | high/medium/low; threshold edge; fallback always low | `tests/unit/test_confidence_calculator.py` |
| `CardValidationPrecheck` | каждый error; каждый warning; happy path | `tests/unit/test_card_validation_precheck.py` |
| `LLMCardAdapter` | happy; invalid_json_retry; repair; timeout; fallback mode | `tests/unit/test_llm_card_adapter.py` |
| `RAGCardMetadataDTO` | roundtrip yaml; missing required; unknown enum rejected | `tests/unit/test_rag_card_metadata_schema.py` |
| `RAGCardMarkdownDTO` | parse; build_from_parts; empty body rejected; missing front matter | `tests/unit/test_rag_card_markdown_schema.py` |
| `RAGCardSourceLinkDTO` | instantiation; idempotency key | `tests/unit/test_rag_card_source_link_schema.py` |
| `CardGenerationReportDTO` | frozen; summary totals | `tests/unit/test_rag_card_generation_report_schema.py` |
| Repositories (5) | create; get; update; list; duplicate raises; snapshot_restore | `tests/unit/test_rag_card_*_repository.py` |
| Events (8) | instantiation; payload; frozen | `tests/unit/test_rag_card_generation_events.py` |

### 21.2. Component tests

| Компонент | Сценарии |
| --- | --- |
| `RAGCardGenerationOrchestrator` | create_job happy; no_sections raises; already_running raises; run_single happy; run_multi happy; partial_success; full_failure; low_confidence → review_required; 8 events emitted; lifecycle.link_artifact called; fallback mode; artifact uploaded |

Целевой файл: `tests/component/test_rag_card_generation_orchestrator.py`.

### 21.3. Integration tests

| Группа | Сценарии |
| --- | --- |
| Generate endpoint | happy; 400 no_sections; 403; 404; 409 already_running |
| Run endpoint | completes; 409 terminal state |
| Status endpoint | returns full job; 404 unknown; cross-job isolation |
| List endpoint | list happy; filters; pagination total |
| Details / Preview | get happy; specific version; 404; preview 403 |
| Regenerate | happy; 404 unknown; 403 for user; version incremented; old preserved |
| Cancel | created → cancelled; terminal → 409 |
| Audit + Metrics | audit record per card; metrics counter per doc_type; duration histogram |
| Structured logs | per-card log; per-job log |
| Smoke E2E | create setup_job → upload → parse → POST /generate → POST /run → GET /rag-cards → ≥ 1 card |

### 21.4. Contract tests

- OpenAPI schema для 8 endpoints соответствует коду.
- `RAGCardDTO` (DTO-66) backward-compat: legacy карточки из SETUP-01..03 остаются валидными.
- `doc_type` enum backward-compat: добавление нового значения не ломает contract.
- Events schema: payload соответствует event-классам.

### 21.5. Prompt evaluation tests

- Каждый из 7 шаблонов возвращает валидный JSON, соответствующий `RAGCardDraft`.
- Prompt не выполняет инструкции из source content (проверяется структурным тестом).
- Output содержит `source_sections`; содержит `retrieval_tags`.
- Output не придумывает `source_files`, не существующие в `ParsedSection`.

### 21.6. Negative / resilience tests

- LLM Gateway unavailable → fallback или `generation_failed` per section.
- LLM timeout → retry with backoff → fallback.
- Invalid LLM output → repair-prompt retry (max 3) → `generation_failed`.
- Prompt template missing → `PROMPT_TEMPLATE_NOT_FOUND`.
- OntologyMapper unavailable → `metadata_incomplete`.
- ArtifactStorage unavailable → compensation → `generation_failed`.
- RAGCardRegistry unavailable → retry → `generation_failed`.
- `doc_id` conflict → `DocIdGenerator` инкрементирует версию.
- Repeated generation request → идемпотентность по `generation_request_id`.
- Prompt injection в parsed section не выполняется.
- Cross-job isolation: пользователь не видит карточки чужого setup job.

### 21.7. Frontend unit tests (vitest + MSW)

- 8 API функций покрыты mock-тестами.
- `RAGCardGenerationStep`: create button triggers POST; run button disabled until job created; progress updates on poll; cancel button visibility; summary renders cards_by_type; low_confidence banner shown; next button disabled on FAILED.
- `RAGCardList`: render with data; filter by doc_type; combine filters; pagination; sort toggle; empty state; action buttons; status badge color.
- `RAGCardPreviewDrawer`: tabs render; YAML displayed; Markdown body displayed; source trace links.
- `LowConfidenceCardsPanel`: shown when review_required > 0; CTA present.

---

## 22. Риски, допущения, открытые вопросы

### 22.1. Риски

| Риск | Вероятность | Митигация |
| --- | --- | --- |
| Большая доля карточек в `review_required` из-за необкатанных prompts | Medium | Тщательные prompt templates в Phase A (A3) + repair-retry + `FE_BOT_FORCE_FALLBACK` для отладки |
| Prompt injection из parsed section | Low | Структурная изоляция в prompt template + `MarkdownBuilder` sanitizer |
| Коллизии `doc_id` при одинаковых titles в разных setup jobs | Medium | `DocIdGenerator` с инкрементом версии + проверка через `JobSectionRepo` |
| Рассинхронизация Markdown artifact и DB (`save_card` успешен, `save_artifact` падает) | Medium | Compensation: `status=generation_failed` для карточки; orphan cleanup в S7 |
| Ollama timeout блокирует весь job | Medium | Per-request timeout 60s + fallback на template generation |
| Регрессия legacy pipeline (`SetupPipeline._generate_cards`) | Low | Новый orchestrator — отдельный path; регрессионные тесты |
| Раздутие snapshot при тысячах карточек | Low | Snapshot/restore по DTO (как SETUP-04); cleanup documented |

### 22.2. Допущения

- SETUP-04 создаёт `ParsedSectionDTO` с `normalized_text` и `section_type`.
- Source Registry содержит `source_document_id` и filename.
- `ontology_v1.yaml` доступен и загружен; prompt templates существуют в `prompts/rag_card/`.
- Локальная LLM/Ollama доступна или включён template fallback.
- RAG-карточки сохраняются как Markdown artifacts; полная validation metadata в SETUP-07.
- `LineageRelationType.GENERATED_FROM` и `LineageTargetType.RAG_CARD` существуют из SETUP-03 или добавляются в этой фиче.
- `RAGCardGenerator` и `RAGCardFallbackGenerator` переиспользуются как есть; не переписываются.

### 22.3. Принятые решения (закреплены 2026-06-19)

| Вопрос | Принятое решение |
| --- | --- |
| Поддерживаемые `doc_type` для MVP | 7 типов: `schema_card`, `task_card`, `analytics_card`, `field_definition_card`, `feature_pattern_card`, `validation_rule_card`, `question_template_card` |
| Несколько карточек из одной секции | Нет в MVP (один-к-одному); архитектура допускает 1→N |
| Сохранять ли raw LLM response | Нет (security); метаданные о вызове — да |
| `confidence_threshold` дефолт | 0.7 (переопределяется через options) |
| Режим выполнения | Синхронный in-process (как SETUP-04); async с очередями — следующий инкремент |
| Auto-repair по результатам SETUP-07 | Нет (отложено) |
| Сохранять ли Markdown artifact для `review_required` | Да, всегда |
| Запретить ли regenerate для approved карточек | Да, требуется отдельный permission |
| Включать ли `relationship_card` в MVP | Нет |
| При `partial_success`: продолжать или ждать | UI показывает обе опции; default — продолжать |

### 22.4. Открытые вопросы (требуют ответа до S3/S4)

| Вопрос | Ответственный | Срок |
| --- | --- | --- |
| Минимальная длина Markdown body для каждого `doc_type` | RAG Admin | до S3 |
| Формат YAML front matter для `feature_pattern_card` (formula/inputs vs free text) | ML Engineer | до S2 |
| Нужен ли `ontology_v1.yaml` в синонимах для agent_targets | RAG Architect | до A4 (закрыто в Phase A) |
| Как обрабатывать sections с `section_type=unknown` при отсутствии heading keywords | Backend Lead | до S2 |

---

## 23. Связанные документы и артефакты

### 23.1. Feature документы

| Документ | Связь |
| --- | --- |
| [SETUP-01-setup-wizard.md](SETUP-01-setup-wizard.md) | Мастер настройки; LLMGateway, EventBus, ArtifactStorage — переиспользуются |
| [SETUP-02-document-upload.md](SETUP-02-document-upload.md) | Source documents — вход для parsed sections |
| [SETUP-03-source-registry.md](SETUP-03-source-registry.md) | SourceLifecycleService, lineage model, GENERATED_FROM |
| [SETUP-04-document-parsing.md](SETUP-04-document-parsing.md) | ParsedSectionDTO — основной вход; структурный аналог для orchestrator |
| SETUP-06-rag-card-review.md | Следующий этап; получает `review_required` карточки |
| SETUP-07-metadata-validation.md | Получает `ready_for_metadata_validation` карточки |
| SETUP-08-chunking.md | Получает validated карточки |

### 23.2. Архитектурные документы

| Документ | Связь |
| --- | --- |
| [docs/03-architecture/services/data-transfer-objects.md](../../../docs/03-architecture/services/data-transfer-objects.md) | DTO-59..66 — каталог |
| [docs/03-architecture/services/README.md](../../../docs/03-architecture/services/README.md) | SVC catalog |
| [docs/03-architecture/services/external-actors-and-systems.md](../../../docs/03-architecture/services/external-actors-and-systems.md) | EXT actors |
| [docs/09-langgraph/setup-graph.md](../../../docs/09-langgraph/setup-graph.md) | Позиция step `rag_card_generation` в SetupGraph |

### 23.3. RAG документы

| Документ | Связь |
| --- | --- |
| [rag/ontology/ontology_v1.yaml](../../../rag/ontology/ontology_v1.yaml) | Canonical enum values для metadata нормализации |
| [docs/06-rag/rag-methodology.md](../../../docs/06-rag/rag-methodology.md) | Общие принципы RAG pipeline |
| [docs/06-rag/metadata-schema.md](../../../docs/06-rag/metadata-schema.md) | `rag_metadata_v1` — schema version |
| [docs/06-rag/card-lifecycle.md](../../../docs/06-rag/card-lifecycle.md) | 10 статусов + versioning policy (обновить после реализации) |
| [docs/06-rag/retrieval-policies.md](../../../docs/06-rag/retrieval-policies.md) | Retrieval filtering по `doc_type`, `phase`, `agent_targets` |

### 23.4. Implementation plan и тесты

| Документ | Связь |
| --- | --- |
| [docs/implementation-plan/SETUP-05.tasks.md](../../../docs/implementation-plan/SETUP-05.tasks.md) | 42 задачи в 8 слайсах; scope decisions 2026-06-19 |
| [docs/10-testing/SETUP-05-test-plan.md](../../../docs/10-testing/SETUP-05-test-plan.md) | Детальный тест-план (Phase A, A7) |
| [docs/traceability/setup-05.md](../../../docs/traceability/setup-05.md) | Матрица AC-01..51 → тесты (после реализации S7) |

### 23.5. Prompt templates

| Файл | `doc_type` |
| --- | --- |
| `prompts/rag_card/schema_card.txt` | `schema_card` |
| `prompts/rag_card/task_card.txt` | `task_card` |
| `prompts/rag_card/analytics_card.txt` | `analytics_card` |
| `prompts/rag_card/field_definition_card.txt` | `field_definition_card` |
| `prompts/rag_card/feature_pattern_card.txt` | `feature_pattern_card` |
| `prompts/rag_card/validation_rule_card.txt` | `validation_rule_card` |
| `prompts/rag_card/question_template_card.txt` | `question_template_card` |

### 23.6. Операционные артефакты

- `docs/11-operations/rag-card-generation-runbook.md` — диагностика `LLM_TIMEOUT`/`INVALID_LLM_OUTPUT`; использование `FE_BOT_FORCE_FALLBACK=1`; очистка state.
- Card Generation Monitoring Dashboard — метрики из §17.5.
- Prompt Injection Mitigation Guide — структура prompt template с изоляцией `<user_content>`.
- RAG Card Status Policy — 10 статусов; переходы; правила.
- RAG Card Versioning Policy — `card_version` monotonic; old не удаляется; `deprecated` не индексируется.
