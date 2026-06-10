# Матрица покрытия

Roll-up матрица: какие docs, контракты, промпты, валидаторы и тесты покрывают каждую фичу.

## Схема

| Feature | Use Cases | Agents | Contracts | Prompts | Validators | Tests | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Значения статусов

- `planned` — запись есть, но артефактов ещё нет.
- `in-progress` — часть артефактов на месте, есть пробелы.
- `covered` — каждый обязательный столбец заполнен и тесты проходят.
- `deprecated` — фича выведена; строка остаётся с датой для истории.

## TODO

- Заполняется по мере добавления фич в `docs/02-system/features/`.

## Связанные карты

- [feature-to-service-map.md](feature-to-service-map.md) — фича → SVC
- [dto-to-service-map.md](dto-to-service-map.md) — DTO → producer/consumer SVC
- [agent-to-contract-map.md](agent-to-contract-map.md) — агент → schema → tests
- [rag-coverage-matrix.md](rag-coverage-matrix.md) — фаза → retrieval policy → evaluation case
