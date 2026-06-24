# Runbook — chunking (SETUP-08)

## Когда использовать

- После SETUP-07 одобрены METADATA_VALIDATED карточки — пора нарезать chunks.
- Нужно preview chunks без persistence (UI debug).
- Re-chunk одной карточки после edit (SETUP-06).

## 1. UI

1. Шаг Chunking — кнопка «Сгенерировать chunks».
2. Manifest визуализирует by_type counters.

## 2. API

```bash
SID=setup_xxxxxxxx
H="-H X-User-Id:u1 -H X-Roles:user"
DOC=schema_card.test.v1

# Batch run
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/chunking/run" \
  -H "Content-Type: application/json" $H -d '{}' | jq

# Manifest
curl -s "http://localhost:8000/api/v1/setup/$SID/chunking/manifest" $H | jq

# Preview
curl -s "http://localhost:8000/api/v1/setup/$SID/chunking/preview/$DOC" $H | jq

# Refresh single
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/chunking/refresh/$DOC" $H | jq
```

## 3. Диагностика

### Manifest не создан

`/manifest` → 404. Действия:
1. Запустить `POST /chunking/run` — проверить что есть METADATA_VALIDATED карточки.
2. Если total_cards = 0 — сначала пройти SETUP-07 validation.

### Карточки не переходят в CHUNKED

Лог `chunking_status_update_failed` — невалидный transition.
Действия: проверить status карточек — допускаются только METADATA_VALIDATED → CHUNKED.

### Embedding text слишком длинный

CHUNK_CHAR_BUDGET = 4000. Если в preview видно превышение — поправить
`_normalize_for_embedding` в `chunking/service.py`.

## 4. Cleanup state

```bash
rm -f var/state/chunk_manifests.json
```

## 5. Observability

### Audit
- `chunking.run_triggered` per batch
- `chunking.manifest_created` per saved manifest

### Метрики
- `chunking_runs_total{outcome}`
- `chunks_created_total{chunk_type}`
- `chunking_card_duration_ms` histogram
- `chunking_run_duration_ms` histogram

### Structured logs
- `chunking_run_completed` — основное событие
