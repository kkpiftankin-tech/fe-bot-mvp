# PLATFORM-04. Artifact Storage и Download Manager

## Назначение

Conversation-scoped объектное хранилище (MinIO в локальной разработке) для каждого файла, который производит система: `X_train.csv`, `y_train.npy`, `features.json`, `pipeline.py`, `metadata.json`, `archive.zip`, retrieval-отчёты, validation-отчёты, audit-trace-ы. Плюс UI Download Manager для скачивания.

## Бизнес-ценность

Без scoped-хранилища артефакты протекают между сессиями и становятся audit- и security-обязательством. Download Manager — это также видимое пользователю «вознаграждение» за весь диалог.

## Вход и выход

- **Вход.** Файлы, которые производит система: `X_train.csv`, `y_train.npy`, `features.json`, `pipeline.py`, `metadata.json`, `archive.zip`, отчёты.
- **Выход.** Conversation-scoped хранилище (MinIO) и Download Manager с time-bound ссылками; просроченная ссылка возвращает `410 Gone`.

## Пользовательский сценарий

После [RUNTIME-12](RUNTIME-12-export.md) пользователь жмёт **Downloads**. Видит per-conversation: каждый артефакт, его размер, его checksum и кнопку **Download**. Клик стримит файл через time-bound, conversation-scoped URL.

## Связанные требования

- BR-FR-Platform-031..034 (per-session scoping, TTL на ссылки, audit на скачивании, выставление checksum).
- NFR-Sec-001..002 (межсессионные чтения запрещены; ссылки истекают).

## Связанные сервисы

- Artifact Storage (MinIO), Export Service, Download Manager UI, API Backend, Audit Service.

## Связанные контракты

- `ArtifactRecord` (`schemas/artifacts.py`): `artifact_id`, `conversation_id`, `kind`, `bucket`, `key`, `size_bytes`, `checksum_sha256`, `created_at`.

## Критерии приёмки

- Download-URL ОБЯЗАН быть валиден только для своего `conversation_id` и только до своего TTL.
- Истёкший URL ОБЯЗАН отказывать с `410 Gone` и actionable-сообщением.
- Каждое скачивание ОБЯЗАНО эмитить audit event.
- Тест: `tests/integration/test_artifact_download.py`.
