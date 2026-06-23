# Runbook — review RAG-карточек (SETUP-06)

Операционный гайд для разработчиков и on-call по SETUP-06. Описывает запуск
review-flow, диагностику и восстановление при типичных ошибках.

## Когда использовать

- После SETUP-05 много карточек попадает в `review_required` / `low_confidence`.
- Approve блокируется validation errors.
- Conflict при edit (version mismatch).
- Регенерация не запускается.
- Bulk approve проходит частично.

## 1. Запуск через UI

1. Открыть мастер `http://localhost:5173/`.
2. Шаг 6 "Проверить карточки" — выбрать setup_job с готовыми карточками.
3. В таблице фильтр по `status = review_required`.
4. Открыть карточку → drawer с 7 вкладками.
5. Вкладка **Overview**: можно сразу Approve, либо перейти к Validation.
6. Вкладка **Validation**: видны critical_errors и warnings; формы reject/regenerate
   с required reason.
7. Вкладка **Metadata/Body**: edit с inline editor → «Сохранить новую версию».
8. Подтверждённые карточки переходят в `approved` и появляются в SETUP-07
   ready list (как только все блокирующие будут обработаны).

## 2. Запуск через API

```bash
SID=setup_xxxxxxxx
H="-H X-User-Id:u1 -H X-Roles:user"
DOC=schema_card.test.v1

# 1) list карточек
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-cards-review?status=review_required" $H | jq

# 2) details
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC" $H | jq

# 3) approve
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC/review" \
  -H "Content-Type: application/json" $H \
  -d '{"decision":"approve","review_decision_id":"rd_001"}'

# 4) reject с reason
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC/review" \
  -H "Content-Type: application/json" $H \
  -d '{"decision":"reject","reason":"duplicate","comment":"see card X"}'

# 5) edit (создаёт новую версию)
curl -s -X PATCH "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC" \
  -H "Content-Type: application/json" $H \
  -d '{"expected_version":"1.0","metadata_patch":{"title":"Fixed"},"change_reason":"typo"}'

# 6) regenerate
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC/regenerate" \
  -H "Content-Type: application/json" $H \
  -d '{"reason":"low_quality","instruction":"add domain context"}'

# 7) bulk approve (admin only)
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/bulk-review" \
  -H "Content-Type: application/json" -H "X-User-Id:admin1" -H "X-Roles:admin" \
  -d '{"decision":"approve","items":[{"doc_id":"a","card_version":"1.0"},{"doc_id":"b","card_version":"1.0"}]}'

# 8) review log
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-cards-review/$DOC/review-log" $H | jq
```

## 3. Диагностика типичных ошибок

### `CARD_HAS_CRITICAL_VALIDATION_ERRORS` (422)

Симптомы: approve возвращает 422 с массивом `codes`.

Действия:
1. Открыть details карточки → вкладка Validation → видны critical_errors.
2. Если `SOURCE_TRACE_REQUIRED` — карточка не привязана к section/document.
   Запустить regenerate или edit с заполнением source.
3. Если `CARD_BODY_EMPTY` или `CARD_BODY_TOO_SHORT` — edit с непустым body
   ≥ 20 символов.
4. Если `CARD_BODY_DANGEROUS_HTML` — удалить script/iframe/javascript: из body.

### `CARD_VERSION_CONFLICT` (409)

Кто-то отредактировал карточку между вашим открытием и save. Действия:
1. Перезагрузить details (refresh).
2. Повторить edit с актуальной `expected_version`.

### `REJECT_REASON_REQUIRED` (400) / regenerate без reason

Approve не требует reason, но reject и regenerate требуют. Frontend должен
показать модал с обязательным выбором; если API вызов из curl — добавить
`"reason": "..."`.

### `SYSTEM_METADATA_READ_ONLY` (400)

Попытка изменить `doc_id`, `source_files`, `created_at` или другие system
поля через edit. Действия:
1. Удалить запрещённые поля из metadata_patch (см. `SYSTEM_METADATA_FIELDS`
   в `card_review/editor.py`).
2. Если действительно нужно сменить doc_id — выполнить regenerate
   (создаст новую карточку через SETUP-05 orchestrator).

### `EDIT_LOCK_ACTIVE` (409)

Карточка редактируется другим пользователем. Действия:
1. Подождать TTL lock (по умолчанию 10 мин).
2. Открыть карточку в read-only.
3. Admin может выполнить `release` через service API (admin_override=True).

### Regenerate не создаёт generation_job

Если `RAGCardGenerationOrchestrator` недоступен или у карточки нет
`primary_source_section_id` — `generation_job_id` будет пустым в response,
но статус карточки всё равно переходит в `REGENERATE_REQUESTED`.

Действия:
1. Проверить логи `rag_card_regenerate_orchestrator_unavailable`.
2. Если карточка legacy (без primary_source_section_id) — старая UI manual
   edit, не regenerate.

### Readiness не разблокировал SETUP-07

Действия:
1. Проверить `summary.by_status` в list-response.
2. Все блокирующие статусы должны быть resolved:
   `REVIEW_REQUIRED`, `VALIDATION_FAILED`, `METADATA_INCOMPLETE`,
   `LOW_CONFIDENCE`, `EDITING`, `GENERATED`.
3. Каждый блокер — либо approve, либо reject, либо regenerate.

## 4. Cleanup state

```bash
# Soft reset одного setup_job: только review state.
rm -f var/state/review_decisions.json var/state/review_logs.json \
       var/state/card_versions.json var/state/edit_locks.json

# Hard reset всего state.
rm -rf var/state/*.json
```

После reset перезапустить backend.

## 5. Наблюдаемость

### Audit log

| Action | Когда |
| --- | --- |
| `card.review_approved` | per approve |
| `card.review_rejected` | per reject |
| `card.review_edited` | per edit |
| `rag_card.regenerate_triggered` | per regenerate |

### Метрики (`/metrics`)

- `rag_card_reviews_total{decision}` — все решения.
- `rag_card_approved_total{doc_type}` — approved by type.
- `rag_card_rejected_total{doc_type,reason}` — rejected with reason.
- `rag_card_edited_total{doc_type}`.
- `rag_card_regenerate_requested_total{doc_type}`.
- `rag_card_validation_blocked_approve_total{error_code}` — approve заблокирован.
- `rag_card_version_conflicts_total` — edit conflicts.
- `rag_card_review_duration_ms{decision,doc_type}` — histogram.

### Structured logs

JSON-логи; ищите по `rag_card_review_decision_made`, `rag_card_edited`,
`rag_card_regenerate_requested`, `rag_card_bulk_review_completed`. Каждая запись
содержит `setup_job_id`, `doc_id`, `card_version`, `reviewer_id`, `outcome`.

## 6. Связанные документы

- [SETUP-06 feature](../02-system/features/SETUP-06-rag-card-review.md)
- [SETUP-06 traceability](../traceability/setup-06.md)
- [Card lifecycle](../06-rag/card-lifecycle.md)
- [Implementation plan](../implementation-plan/SETUP-06.tasks.md)
