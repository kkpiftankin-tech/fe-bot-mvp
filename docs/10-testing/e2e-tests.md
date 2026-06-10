# E2E-тесты

## Назначение

Прогнать полный пользовательский поток в окружении, максимально близком к production: Docker Compose, реальные Postgres / Qdrant / MinIO / Ollama.

## Эталонные сценарии

- `test_setup_wizard_happy_path` — `UC-FE-01`: загрузка набора radar-документов → publish KB.
- `test_runtime_happy_path` — `UC-FE-02`: задача → признаки → синтетический датасет → модель → archive.zip.
- `test_audit_trail` — `UC-FE-03`: после happy path построить audit-цепочку до source.
- `test_export_happy_path` — гарантия идемпотентности экспорта для одного и того же ContextMemory.
- `test_setup_publish` — корректность контракта SETUP-11.

## Окружение

`make up-all` — поднимает Compose со всеми сервисами. Тесты ходят по HTTP против `http://localhost:8000`.

## Принципы

- E2E прогоняется на CI с расписанием, а не на каждый PR (дорого по времени).
- Smoke-вариант (`make smoke`) ужимает сценарий до 1–2 минут и должен проходить на каждый PR.

## Запуск

```bash
make up-all
make test-e2e
make smoke
```
