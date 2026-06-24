# SETUP-08 Traceability — Chunking

Документ фиксирует реализованные слайсы SETUP-08 и прослеживает связи
AC → task → код → тест.

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| Phase A | Feature spec (16 секций, 14 AC) + plan | done |
| S0 | ChunkManifestDTO + ChunkingRunDTO + 6 unit | done |
| S1 | ChunkManifestRepository + 7 unit | done |
| S2 | Orchestrator + events + metrics + audit + DI + 9 component | done |
| S3 | 3 permissions + 4 API endpoints + 11 integration | done |
| S5 | Frontend ChunkPreviewPanel + 3 frontend | done |
| S6 | Audit + metrics + structured logs + 5 integration | done |
| S7 | Traceability + runbook + final commit | done |

## Контракты

| DTO | Файл |
| --- | --- |
| `ChunkManifestDTO` + `ChunkingRunDTO` | [schemas/setup/chunk_manifest.py](../../schemas/setup/chunk_manifest.py) |
| `Chunk` (используется) | [schemas/rag/chunk.py](../../schemas/rag/chunk.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| Repository | [src/fe_bot/setup/chunking/manifest_repository.py](../../src/fe_bot/setup/chunking/manifest_repository.py) |
| Events | [src/fe_bot/setup/chunking/events.py](../../src/fe_bot/setup/chunking/events.py) |
| Metrics | [src/fe_bot/setup/chunking/metrics.py](../../src/fe_bot/setup/chunking/metrics.py) |
| Orchestrator | [src/fe_bot/setup/chunking/orchestrator.py](../../src/fe_bot/setup/chunking/orchestrator.py) |
| Service (stateless engine, unchanged) | [src/fe_bot/setup/chunking/service.py](../../src/fe_bot/setup/chunking/service.py) |
| Audit actions | [src/fe_bot/audit/service.py](../../src/fe_bot/audit/service.py) (+2 CHUNKING_*) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) (+3 KB_CHUNKING_*) |
| API | [src/fe_bot/api/setup/chunking_dto.py](../../src/fe_bot/api/setup/chunking_dto.py), [.../chunking_router.py](../../src/fe_bot/api/setup/chunking_router.py) |
| DI + app | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/app.py](../../src/fe_bot/app.py), [src/fe_bot/persistence/snapshot.py](../../src/fe_bot/persistence/snapshot.py) |
| Frontend | [frontend/src/api/chunking.ts](../../frontend/src/api/chunking.ts), [frontend/src/components/Wizard/chunking/ChunkPreviewPanel.tsx](../../frontend/src/components/Wizard/chunking/ChunkPreviewPanel.tsx) |
| Lifecycle | [schemas/rag/rag_card.py](../../schemas/rag/rag_card.py) — METADATA_VALIDATED → CHUNKED |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_chunk_manifest_schema.py](../../tests/unit/test_chunk_manifest_schema.py) | 6 |
| unit | [tests/unit/test_chunk_manifest_repository.py](../../tests/unit/test_chunk_manifest_repository.py) | 7 |
| component | [tests/component/test_chunking_orchestrator.py](../../tests/component/test_chunking_orchestrator.py) | 9 |
| integration | [tests/integration/test_chunking_endpoints.py](../../tests/integration/test_chunking_endpoints.py) | 11 — 4 endpoints + RBAC + cross-job |
| integration | [tests/integration/test_chunking_audit_metrics.py](../../tests/integration/test_chunking_audit_metrics.py) | 5 |
| frontend | [frontend/src/components/Wizard/chunking/__tests__/ChunkPreviewPanel.test.tsx](../../frontend/src/components/Wizard/chunking/__tests__/ChunkPreviewPanel.test.tsx) | 3 |

## Permissions

| Permission | Roles | Endpoints |
| --- | --- | --- |
| `kb.chunking.read` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR, ADMIN | GET /manifest, GET /preview |
| `kb.chunking.run` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /run |
| `kb.chunking.refresh` | USER, DOMAIN_EXPERT, RAG_ADMIN, ADMIN | POST /refresh |

## Audit actions

| Action | Когда |
| --- | --- |
| `chunking.run_triggered` | POST /chunking/run |
| `chunking.manifest_created` | per saved manifest |

## Метрики

| Имя | Тип | Labels |
| --- | --- | --- |
| `chunking_runs_total` | counter | outcome |
| `chunks_created_total` | counter | chunk_type |
| `chunking_card_duration_ms` | histogram | — |
| `chunking_run_duration_ms` | histogram | — |

## Structured logs

- `chunking_run_completed` — setup_job_id, chunking_run_id, manifest_id,
  total_cards, chunks_created, by_type, duration_ms, outcome.

## Known limits MVP

- Refresh для одной карточки сохраняет manifest только с её chunks
  (полный merge — в SETUP-09).
- Только built-in типы chunks: summary, definition, metadata_summary
  (custom strategies — out of scope).
- Versioning manifest — append-only; latest = последний save.

## Связанные документы

- [SETUP-07 traceability](setup-07.md)
- [SETUP-08 feature spec](../02-system/features/SETUP-08-chunking.md)
- [Chunk schema](../06-rag/chunk-schema.md)
- [Runbook](../11-operations/chunking-runbook.md)
