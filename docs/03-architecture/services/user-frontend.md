# Пользовательский слой (SVC-01..SVC-03)

Сервисы, обращённые к пользователю.

---

## SVC-01. Frontend UI

### Назначение

Единый интерфейс пользователя для трёх режимов: настройки RAG-базы, runtime-диалога с мультиагентной системой и просмотра аналитики.

### Функции

Загрузка документов, отображение pipeline подготовки RAG, просмотр RAG-карточек, запуск чата, подтверждение признаков, настройка генерации, выбор модели, скачивание артефактов, Analytics-дашборды.

### DTO

`UserSessionDTO`, `ChatMessageDTO`, `SourceDocumentDTO`, `RAGCardDTO`, `ChunkDTO`, `ContextMemoryDTO`, `FeatureSpecDTO`, `GenerationSpecDTO`, `DatasetArtifactDTO`, `ModelRecommendationDTO`, `ExportManifestDTO`, `AnalyticsEventDTO`.

### Внешние участники

EXT-01 пользователь, EXT-02 RAG admin, EXT-03 SME, EXT-04 Data Scientist, EXT-05 DevOps, EXT-06 Identity Provider (косвенно).

### Соседние сервисы

SVC-02 API Gateway, SVC-03 Auth, SVC-05 Document Upload, SVC-04 Setup Orchestrator, SVC-15 KB Registry, SVC-18 LangGraph Orchestrator, SVC-34 Export, SVC-35 Analytics, SVC-37 Notification.

### Информационный обмен

С `SVC-02` обмен HTTP-запросами: загрузка файлов, старт сессии, отправка сообщений, статусы, подтверждения, скачивания.
С `SVC-03` — данные пользователя, роли, permissions.
С `SVC-37` — события прогресса (`setup_progress`, `rag_ready`, `generation_completed`, `export_ready`) через SSE/WebSocket.

### Входные данные

Файлы пользователя, текстовые сообщения, клики подтверждения, параметры генерации, фильтры дашборда, команды запуска.

### Выходные данные

HTTP-запросы к backend, пользовательские события, отображаемые экраны, visual status pipeline, UI-уведомления, download actions.

### Реализует фичи

[SETUP-01](../../02-system/features/SETUP-01-setup-wizard.md), [RUNTIME-01..12](../../02-system/features/feature-index.md) (UI-часть), [ANALYTICS-01..09](../../02-system/features/feature-index.md) (UI-часть).

---

## SVC-02. API Gateway / Backend API

### Назначение

Единая точка входа для frontend; маршрутизирует запросы в сервисы настройки, runtime, аналитики и экспорта.

### Функции

Принимает пользовательские запросы, валидирует сессию, вызывает нужный backend-сервис, агрегирует ответ, отдаёт статусы и обеспечивает единый API-контракт для UI.

### DTO

`UserSessionDTO`, `ChatMessageDTO`, `SourceDocumentDTO`, `ContextMemoryDTO`, `RAGCardDTO`, `ValidationReportDTO`, `ExportManifestDTO`, `AnalyticsEventDTO`.

### Внешние участники

EXT-01 пользователь (через SVC-01), EXT-06 Identity Provider.

### Соседние сервисы

SVC-01 Frontend, SVC-03 Auth, SVC-16 Session, SVC-04 Setup Orchestrator, SVC-18 LangGraph Orchestrator, SVC-05 Document Upload, SVC-15 KB Registry, SVC-38 Artifact Storage, SVC-35 Analytics, SVC-36 Audit.

### Информационный обмен

С `SVC-03` — токены, user profile, permissions.
С `SVC-04` — команды запуска RAG-настройки, статусы pipeline.
С `SVC-18` — сообщения пользователя и следующий ответ системы.
С `SVC-38` — download URL для артефактов.
С `SVC-35` — данные дашбордов.

### Входные данные

HTTP-запросы frontend, access token, файлы, JSON-команды, параметры фильтрации, message payload.

### Выходные данные

HTTP-ответы, ошибки, статусы workflow, DTO для frontend, download links, streaming/progress events.

### Реализует фичи

[PLATFORM-01](../../02-system/features/PLATFORM-01-api-backend.md).

---

## SVC-03. Auth Service

### Назначение

Аутентификация, авторизация и проверка прав доступа.

### Функции

Проверяет токены, определяет роль пользователя, ограничивает доступ к сессиям, KB, артефактам и административным операциям.

### DTO

`UserSessionDTO`, `AuthTokenDTO`, `UserProfileDTO`, `PermissionDTO`.

### Внешние участники

EXT-06 Identity Provider, EXT-01 пользователь.

### Соседние сервисы

SVC-02 API Gateway, SVC-01 Frontend, SVC-38 Artifact Storage, SVC-15 KB Registry, SVC-36 Audit.

### Информационный обмен

С `SVC-06` — token introspection, user claims, roles.
С `SVC-02` — результат проверки прав.
С `SVC-38` — подтверждение доступа к файлам.
С `SVC-36` — события входа и отказа.

### Входные данные

Access token, session cookie, requested resource, action type.

### Выходные данные

User identity, roles, permissions, access decision, auth errors.

### Замечание для MVP

В MVP — anonymous mode по умолчанию; единственная роль `developer`. Полноценная интеграция с Identity Provider — пост-MVP.

---

## Связанные документы

- [README.md](README.md)
- [external-actors-and-systems.md](external-actors-and-systems.md)
- [../c4-container.md](../c4-container.md)
- [../../02-system/features/PLATFORM-01-api-backend.md](../../02-system/features/PLATFORM-01-api-backend.md)
