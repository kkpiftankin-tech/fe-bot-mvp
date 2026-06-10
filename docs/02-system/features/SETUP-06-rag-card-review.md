# SETUP-06. Ревью RAG-карточек (HITL)

## Назначение

Human-in-the-loop UI для пользователя (обычно — доменный SME или RAG admin), позволяющий инспектировать, редактировать, одобрять, отклонять или отправлять на регенерацию каждую черновую RAG-карточку, произведённую [SETUP-05](SETUP-05-rag-card-generation.md).

## Бизнес-ценность

LLM-черновики дрейфуют. Без шага ревью low-confidence или галлюцинированные карточки попадают в индекс и молча портят retrieval Runtime. SETUP-06 — это чокпойнт, удерживающий KB надёжной.

## Пользовательский сценарий

1. Мастер переходит в фазу **Review**.
2. Пользователь открывает список карточек с фильтром по семейству (`schema`, `task`, `analytics`, `feature_pattern`, `validation_rule`, `question_template` и др.).
3. Для каждой карточки видны: metadata, отрендеренное тело, выписка исходной секции, ошибки валидации из [SETUP-07](SETUP-07-metadata-validation.md), уровень confidence.
4. Действия: **Approve** (карточка → `approved`), **Reject** (карточка → `rejected`, с причиной), **Edit** (inline-правки, затем approve), **Regenerate** (повторный вызов генератора с опциональным steering-текстом).

## Связанные требования

- BR-FR-Setup-061..064 (переходы статусов, редактирование, регенерация, версионирование).
- NFR-Audit-001 (каждое решение ревью логируется с `decided_by`, `decided_at`, `reason`).

## Связанные сервисы

- RAG Review UI, RAG Card Registry, Card Editor, Versioning Service, API Backend.

## Связанные контракты

- `RAGCardReviewAction` (`schemas/rag_cards.py`): `card_id`, `action` (`approve | reject | regenerate | edit`), `reason`, `notes`, `decided_by`, `decided_at`.

## Критерии приёмки

- Карточка не может перейти в [SETUP-08](SETUP-08-chunking.md), пока `status = approved`.
- Редактирование карточки ОБЯЗАНО создавать новую версию; предыдущая остаётся в истории.
- Каждое действие ревью ОБЯЗАНО появиться в audit trail.
- Тест: `tests/component/test_setup_card_review.py`.

## Вне scope

- Multi-reviewer консенсус (одного approver достаточно в MVP).
