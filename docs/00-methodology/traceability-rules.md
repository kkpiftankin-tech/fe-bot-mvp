# Правила traceability

Traceability — это то, что позволяет ответить: *«если я меняю X, что ещё должно измениться?»*. В мультиагентной системе с RAG ответ редко очевиден. Правила ниже поддерживают честность графа артефактов.

## Что обязательно трассируется

1. **Source → Artifact.** Какой фрагмент `incoming-docs/` мотивировал это требование, фичу или RAG-карточку.
2. **Requirement → Tests.** У каждого функционального требования есть как минимум одна ссылка на тест.
3. **Agent → Contract.** Каждый агент из [AGENTS.md](../../AGENTS.md) сопоставлен со схемой в `schemas/`.
4. **RAG Coverage.** У каждой фазы агента есть документированная retrieval-политика в `docs/06-rag/retrieval-policies.md` и evaluation case в `tests/rag_eval/`.
5. **Feature → Validators.** Каждая фича перечисляет детерминированные валидаторы, на которых держатся её критерии приёмки.
6. **Feature → SVC.** Каждая фича в [docs/02-system/features/](../02-system/features/) реализуется одним или несколькими сервисами из [docs/03-architecture/services/](../03-architecture/services/).
7. **DTO → SVC.** Каждый DTO из [data-transfer-objects.md](../03-architecture/services/data-transfer-objects.md) имеет хотя бы одного producer-сервиса и одного consumer-сервиса в [dto-to-service-map.md](../traceability/dto-to-service-map.md).

## Матрицы, которые ведутся в `docs/traceability/`

| Файл | Назначение |
| --- | --- |
| `source-to-artifact-map.md` | `incoming-docs/raw/*` → произведённые docs/cards/schemas |
| `requirements-to-tests.md` | FR/NFR → файлы тестов |
| `agent-to-contract-map.md` | Агент → schema → prompt → validator → tests |
| `rag-coverage-matrix.md` | Фаза → типы retrieved-документов → RAG eval case |
| `coverage-matrix.md` | Roll-up: какие docs/code/tests покрывают какие фичи |
| `feature-to-service-map.md` | Фича → SVC (см. [feature-to-service-map.md](../traceability/feature-to-service-map.md)) |
| `dto-to-service-map.md` | DTO → producer/consumer SVC (см. [dto-to-service-map.md](../traceability/dto-to-service-map.md)) |

## Дисциплина обновлений

- При добавлении нового артефакта **добавить или обновить** соответствующую матрицу в **том же изменении**.
- При удалении артефакта пройтись по ссылкам в матрицах. Висячая ссылка — это баг.
- Матрицы ревьюятся в PR; не мержить изменения, ломающие traceability, без ADR, объясняющего почему.

## Автоматизация

`scripts/docs/validate_traceability.py` читает матрицы и валит CI, когда:

- Строка ссылается на несуществующий файл.
- Агент в `AGENTS.md` отсутствует в `agent-to-contract-map.md`.
- Фича указана в индексе фич, но не имеет записи в `coverage-matrix.md`.
- У RAG-карточки нет строки в `rag-coverage-matrix.md`.

Локальный запуск:

```bash
make docs-validate
```

## Анти-паттерны

- **«Обновлю матрицу позже».** «Позже» не наступает; матрица постепенно дрейфует и перестаёт быть надёжной.
- **Свободные ссылки в стиле «см. docs».** Всегда ссылаться по относительному пути.
- **Прятать traceability внутри промптов агентов.** Промпты — не база. База — это матрицы.
