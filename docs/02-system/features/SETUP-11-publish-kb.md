# SETUP-11. Публикация базы знаний

## Назначение

Промоутить новую `index_version` в активную базу знаний, заморозить дальнейшие мутации в её отношении, эмитнуть уведомление **«Knowledge Base ready»** и разблокировать точку входа Runtime.

## Бизнес-ценность

Публикация — это контрактная граница между «KB в процессе» и «что Runtime разрешено читать». Без явного шага promotion Runtime пришлось бы догадываться, какой индекс актуален, и устаревшие или частичные индексы могли бы тихо просачиваться в production-диалоги.

## Вход и выход

- **Вход.** Зелёный retrieval-отчёт и явное подтверждение пользователя.
- **Выход.** Активная `KnowledgeBaseVersion` (`kb_version`, `index_version`, `published_at`, `published_by`), защищённые от правок карточки, чанки и индекс, audit event и сообщение **«Knowledge Base ready»**.

## Пользовательский сценарий

1. После прохождения [SETUP-10](SETUP-10-retrieval-tests.md) мастер выводит действие **Publish Knowledge Base** с однооконным summary: счётчики карточек по семействам, количество чанков, версия индекса, результат retrieval-тестов.
2. Пользователь подтверждает. Система пишет указатель активной KB, замораживает соответствующие карточки/чанки/индекс от in-place правок и эмитит audit event.
3. Мастер показывает сообщение **«Knowledge Base ready»** и deep link на точку входа Runtime.

## Связанные требования

- BR-FR-Setup-111..114 (active-pointer, неизменяемость, уведомление, разблокировка Runtime).
- NFR-Audit-001 (публикация — auditable event).

## Связанные сервисы

- Knowledge Base Registry, Vector DB, RAG Retrieval Service, API Backend, Frontend Setup UI, Notification Service, Audit Service.

## Связанные контракты

- `KnowledgeBaseVersion` (`schemas/knowledge_base.py`): `kb_version`, `index_version`, `card_versions`, `published_at`, `published_by`, `previous_kb_version`.

## Критерии приёмки

- Только одна `kb_version` может быть `active` в данный момент времени.
- Опубликованная KB ОБЯЗАНА быть запрашиваемой `RAG Retrieval Service`-ом немедленно после публикации.
- Точка входа Runtime ОБЯЗАНА отказывать в старте, когда активной KB нет.
- Тест: `tests/e2e/test_setup_publish.py`.

## Вне scope

- Blue/green переключение KB (MVP свапает на месте).
- Per-user pin KB (все видят активную KB).
