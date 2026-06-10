# C4 — Уровень 3: Component (Setup Orchestrator)

## Назначение

Декомпозировать контейнер Setup Orchestrator: компоненты, ответственные за 9 фаз мастера. В отличие от LangGraph (runtime), Setup использует более простой sequential pipeline с явными checkpoints.

## Диаграмма (Mermaid)

```mermaid
C4Component
  title Setup Orchestrator — Components

  Container_Boundary(setup, "Setup Orchestrator") {
    Component(wizard_controller, "Wizard Controller", "Python", "Главный entry-point; держит SetupSession; маршрутизирует UI-команды в фазы")
    Component(phase_runner, "Phase Runner", "Python", "Выполняет конкретную фазу: запускает соответствующий subcomponent, ждёт завершения, эмитит SetupProgressEvent")
    Component(upload_handler, "Upload Handler", "Python", "Валидация формата, проверка дубля, запись в Source Registry")
    Component(parser_dispatcher, "Parser Dispatcher", "Python", "Выбирает Markdown / PDF / DOCX / CSV / JSON парсер по MIME-type")
    Component(card_gen_runner, "Card Generation Runner", "Python", "Параллельно зовёт RAG Service.generate(parsed_section) для пачки секций")
    Component(review_controller, "Review Controller", "Python", "Гейт ревью: блокирует продвижение, пока есть нерассмотренные карточки")
    Component(metadata_validation_runner, "Metadata Validation Runner", "Python", "Прогоняет валидатор после каждого approve")
    Component(chunking_runner, "Chunking Runner", "Python", "Зовёт RAG Service.chunk(approved_cards)")
    Component(embedding_indexing_runner, "Embedding & Indexing Runner", "Python", "Зовёт RAG Service.embed_and_index(chunks)")
    Component(eval_runner_proxy, "Retrieval Eval Runner Proxy", "Python", "Зовёт RAG Service.evaluate(index_version)")
    Component(publication_controller, "Publication Controller", "Python", "Промоутит kb_version в active; иммутабильность; уведомление")
    Component(snapshot_manager, "Snapshot Manager", "Python", "Per-phase snapshots для resumable wizard")
  }

  Container_Ext(api_backend, "API Backend", "FastAPI")
  Container_Ext(rag_service, "RAG Service", "Python")
  ContainerDb_Ext(postgres, "PostgreSQL", "Postgres 16")
  ContainerDb_Ext(minio, "MinIO", "S3-совместимое")
  Container_Ext(notification, "Notification Service", "Python")

  Rel(api_backend, wizard_controller, "POST /setup/...")
  Rel(wizard_controller, phase_runner, "run(phase)")
  Rel(wizard_controller, snapshot_manager, "snapshot(phase)")
  Rel(snapshot_manager, postgres, "SetupSession state", "SQL")

  Rel(phase_runner, upload_handler, "phase=upload")
  Rel(phase_runner, parser_dispatcher, "phase=parsing")
  Rel(phase_runner, card_gen_runner, "phase=card_generation")
  Rel(phase_runner, review_controller, "phase=review")
  Rel(phase_runner, metadata_validation_runner, "phase=validation")
  Rel(phase_runner, chunking_runner, "phase=chunking")
  Rel(phase_runner, embedding_indexing_runner, "phase=indexing")
  Rel(phase_runner, eval_runner_proxy, "phase=eval")
  Rel(phase_runner, publication_controller, "phase=publication")

  Rel(upload_handler, minio, "save file", "S3 API")
  Rel(upload_handler, postgres, "source registry", "SQL")
  Rel(card_gen_runner, rag_service, "generate(section)")
  Rel(metadata_validation_runner, rag_service, "validate(card)")
  Rel(chunking_runner, rag_service, "chunk(cards)")
  Rel(embedding_indexing_runner, rag_service, "embed+index(chunks)")
  Rel(eval_runner_proxy, rag_service, "evaluate(kb_version)")
  Rel(publication_controller, rag_service, "publish(kb_version)")
  Rel(publication_controller, notification, "knowledge_base_ready")
```

## Компоненты

### Wizard Controller

Главный controller, виден API Backend. Держит `SetupSession`, эмитит `SetupProgressEvent` через SSE в UI.

### Phase Runner

Унифицированный исполнитель фазы. Принимает идентификатор фазы и состояние сессии, маршрутизирует к соответствующему subcomponent, ловит сбои фазы (без падения мастера).

### Upload / Parser / Card Gen / Review / Validation / Chunking / Embedding / Eval / Publication Runners

По одному per-фаза. Каждый — тонкий слой над RAG Service / DB / Storage.

### Snapshot Manager

Per-phase snapshots `SetupSession`. Позволяет восстановить мастер после crash или перезахода пользователя.

### Publication Controller

Атомарно промоутит новую `kb_version` в `active`. До успешного завершения retrieval-тестов кнопка публикации скрыта.

## Связанные документы

- [c4-container.md](c4-container.md)
- [c4-component-rag-service.md](c4-component-rag-service.md)
- [../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md](../02-system/use-cases/UC-FE-01-build-knowledge-base/use-case.md)
- [../02-system/features/SETUP-01-setup-wizard.md](../02-system/features/SETUP-01-setup-wizard.md)
