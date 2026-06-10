# Security RAG

Документ описывает три темы: **контроль доступа** к RAG-артефактам, **изоляцию** баз знаний и **redaction** чувствительного содержимого перед индексацией.

## 1. Контроль доступа

Проверки выполняются Auth Service (SVC-03) на каждом действии. Соответствующий DTO — [DTO-03 PermissionDTO](../03-architecture/services/data-transfer-objects.md#dto-03-permissiondto).

### Что должно проверяться

```text
кто загрузил документ (uploaded_by);
кто может читать документ (resource_type = source_document);
кто может публиковать KB (action = publish, resource_type = knowledge_base);
кто может видеть chunks (resource_type = rag_chunk);
кто может скачивать reports (resource_type = artifact, action = download).
```

### Роли

| Роль | Чем владеет |
| --- | --- |
| `user` | Свои runtime-сессии и их артефакты |
| `rag_admin` | Загрузка, ревью карточек, публикация KB |
| `domain_expert` | Approve `analytics_card` / `task_card` |
| `ml_engineer` | Approve `feature_pattern_card` / `validation_rule_card` |
| `admin` | Полный доступ |

Полный реестр ролей и permissions — в [DTO-01 UserProfileDTO](../03-architecture/services/data-transfer-objects.md#dto-01-userprofiledto).

## 2. Изоляция Knowledge Base

Возможные режимы изоляции:

| Режим | Кто видит KB |
| --- | --- |
| `global` | Все пользователи системы |
| `organization` | Пользователи одной организации (`UserProfileDTO.organization_id`) |
| `project` | Только пользователи проекта (KB привязана к `setup_job_id`) |
| `user` | Только владелец |
| `classified` | По специальной ACL (per-document permission) |

### Реализация

- Изоляция — это поле `visibility` в `KnowledgeBaseVersionDTO.metadata`.
- При retrieval RAG Retrieval Service (SVC-21) фильтрует доступные `knowledge_base_version` по `user_id`/`organization_id`/`project_id`.
- Cross-tenant retrieval запрещён на уровне API.

### Cross-conversation read

В MVP применяется правило **per-conversation artifact scope**: артефакты (datasets, archives, generation_specs) видны только в рамках своей `conversation_id`. RAG-карточки и chunks — на уровне Knowledge Base в зависимости от `visibility`.

## 3. Redaction перед индексацией

Перед тем как карточка попадает в `chunked` (см. [rag-lifecycle.md](rag-lifecycle.md)), запускается redactor. Удаляются:

```text
- секреты (API keys, tokens по regex/entropy);
- ключи (RSA/EC blocks);
- пароли (heuristic patterns);
- персональные данные (PII: email, phone, passport) — если включена политика;
- нерелевантные sensitive fragments (CONFIDENTIAL banners);
- неразрешённые документы (classified ≠ visibility KB).
```

### Где это происходит

```text
ParsedSectionDTO
  → Redactor
  → RAGCardDraft
```

Redactor работает на уровне `ParsedSection.normalized_text` до генерации карточки. Метаданные о redaction сохраняются:

```yaml
redaction:
  applied_rules: [secret_keys, pii_email]
  redacted_count: 4
  redacted_at: 2026-05-19T10:23:00Z
```

### Что НЕ redact

- доменные термины — нормализуются через `glossary_term`, но не вырезаются;
- цифры и единицы измерения — нужны для формул;
- источники (`source_document_ids`) — нужны для audit.

## Audit и compliance

Каждое действие над RAG-артефактом эмитит `AuditEventDTO` (см. [DTO-48](../03-architecture/services/data-transfer-objects.md#dto-48-auditeventdto)). Аудит покрывает:

```text
upload документа (actor_type=user, event_type=upload)
approve карточки (event_type=approve, before_state/after_state)
publish KB (event_type=publish)
deprecate карточки (event_type=deprecate)
redaction (event_type=redact, metadata = applied_rules)
permission check failed (event_type=access_denied)
```

Хранилище аудита — PostgreSQL (критичные события) + ClickHouse (timeline). См. [storage-conventions.md](../03-architecture/services/storage-conventions.md).

## Запрещённые операции

- **Не индексировать** документы без явного `status = approved`.
- **Не передавать** агенту evidence из чужого `knowledge_base_version`.
- **Не делать** retrieval без проверки `visibility` KB.
- **Не показывать** raw text исходных документов во frontend без проверки permissions.
- **Не логировать** raw secrets — только after redaction.

## Связанные документы

- [rag-methodology.md](rag-methodology.md)
- [rag-lifecycle.md](rag-lifecycle.md)
- [rag-quality.md](rag-quality.md)
- [../03-architecture/services/data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md)
- [../03-architecture/services/storage-conventions.md](../03-architecture/services/storage-conventions.md)
- [../11-operations/runbook.md](../11-operations/runbook.md)
