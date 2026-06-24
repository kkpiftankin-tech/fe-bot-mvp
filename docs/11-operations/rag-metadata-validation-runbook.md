# Runbook — metadata validation (SETUP-07)

Операционный гайд по SETUP-07. Описывает запуск валидации, диагностику и
восстановление при типичных ошибках.

## Когда использовать

- После SETUP-06 approve хочется убедиться что metadata корректна перед chunking.
- Появились карточки в `REVIEW_REQUIRED` после auto-validation.
- Нужно re-validate одну карточку после ручной правки.
- Aggregate report для UI.

## 1. Запуск через UI

1. После approve в SETUP-06 шаг 6 — auto-validate срабатывает сам.
2. ValidationSummaryCard показывает текущие счётчики.
3. Кнопка «Запустить валидацию» → batch run.
4. ValidationReportTable со списком reports + фильтры.

## 2. Запуск через API

```bash
SID=setup_xxxxxxxx
H="-H X-User-Id:u1 -H X-Roles:user"
DOC=schema_card.test.v1

# 1) batch run
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/validation/run" \
  -H "Content-Type: application/json" $H -d '{}' | jq

# 2) list reports + filter
curl -s "http://localhost:8000/api/v1/setup/$SID/validation/reports?status=failed" $H | jq

# 3) single report
curl -s "http://localhost:8000/api/v1/setup/$SID/validation/reports/$DOC" $H | jq

# 4) refresh one card
curl -s -X POST \
  "http://localhost:8000/api/v1/setup/$SID/validation/reports/$DOC/refresh" \
  -H "Content-Type: application/json" $H -d '{}' | jq

# 5) summary
curl -s "http://localhost:8000/api/v1/setup/$SID/validation/summary" $H | jq
```

## 3. Диагностика

### Validator вернул `FAILED`

Действия:
1. Открыть `/reports/{doc_id}` → видим `errors[]` с типизированными `code`.
2. Открыть карточку через SETUP-06 review drawer → исправить metadata.
3. После edit auto-validate (T-S07-017) автоматически.

### Validator throws (REPAIR_REQUIRED)

Service не падает: report пишется со status=REPAIR_REQUIRED, статус карточки
не меняется. Действия:
1. Проверить логи `validation_run_completed` со status=`completed_with_failures`.
2. Если validator action необходим — disabled через ALLOW_WARNINGS policy.

### Approved → REVIEW_REQUIRED после validation

Это автоматический rollback: T-S07-017 видит FAILED и возвращает карточку
к ручной проверке. Не баг.

### Reports не создаются

Действия:
1. Проверить `audit_log` — есть ли `VALIDATION_RUN_TRIGGERED`?
2. Проверить counter `validation_runs_total` — увеличился?
3. Если eligible карточек нет (всё уже METADATA_VALIDATED) — report не создаётся.

## 4. Cleanup state

```bash
# Только validation state
rm -f var/state/validation_reports.json var/state/validation_runs.json
```

## 5. Наблюдаемость

### Audit

| Action | Когда |
| --- | --- |
| `validation.run_triggered` | per batch run |
| `validation.report_created` | per report |

### Метрики (`/metrics`)

- `validation_runs_total{outcome}` — completed / completed_with_failures.
- `validation_reports_total{status}` — passed/warning/failed/repair_required.
- `validation_issues_total{code,severity}` — детальная разбивка ошибок.
- `validation_card_duration_ms` histogram.
- `validation_run_duration_ms` histogram.

### Structured logs

`validation_run_completed` — основное событие с full context.

## 6. Связанные документы

- [SETUP-07 feature](../02-system/features/SETUP-07-metadata-validation.md)
- [SETUP-07 traceability](../traceability/setup-07.md)
- [Implementation plan](../implementation-plan/SETUP-07.tasks.md)
- [Metadata schema](../06-rag/metadata-schema.md)
