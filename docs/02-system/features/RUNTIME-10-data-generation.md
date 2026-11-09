# RUNTIME-10. Генерация синтетических данных

## Назначение

Запустить Python `SyntheticDataGenerator` против одобренного `GenerationSpec` и произвести `X_train.csv`, `y_train.npy` и `metadata.json`, затем провалидировать результат. **LLM не участвует.**

## Бизнес-ценность

Воспроизводимый датасет, отражающий домен пользователя (без раскрытия реальных данных), разблокирует нижестоящее прототипирование и экспорт-пакет. Пользователь получает что-то запускаемое за минуты, а не за недели.

## Вход и выход

- **Вход.** Одобренный `GenerationSpec` и команда **Generate dataset**.
- **Выход.** `X_train.csv`, `y_train.npy`, `metadata.json` (с digests) и результат `generated_data_validator`; повторный запуск с тем же spec даёт байт-идентичный датасет.

## Пользовательский сценарий

1. После [RUNTIME-09](RUNTIME-09-generation-spec.md) пользователь жмёт **Generate dataset**.
2. Worker генерирует `y` по class prior, затем `X | y` по `class_conditional_distributions`, затем производные и interaction-признаки, затем подмешивает шум и аномалии.
3. UI показывает прогресс по стадиям; по завершению пользователь видит `X.shape`, `y.shape`, фактическое распределение классов vs. запрошенное, status валидации.

## Связанные требования

- BR-FR-090, BR-FR-092, BR-FR-093 (генерация синтетической выборки по признакам, типу задачи, балансу классов, шуму, аномалиям и seed; валидация; сохранение данных).
- BR-FR-Gen-002 (Python-only генерация).
- BR-FR-Gen-003 (валидация: нет NaN / нет Inf при `missing_data_strategy = none`, баланс классов в допуске, соответствие схеме).
- BR-FR-Gen-004 (байт-идентичные перезапуски для того же spec + seed).

## Связанные сервисы

- DataGenerationWorker, ValidationWorker, Artifact Storage, API Backend, Frontend Data Generation Progress UI, ContextMemory Service.

## Связанные контракты

- `GeneratedDataset` (`schemas/generated_dataset.py`): пути файлов, формы, фактическое распределение классов, summary маски аномалий.
- Валидатор: [`validators/generated_data_validator.py`](../../../validators/generated_data_validator.py).

## Критерии приёмки

- Для эталонного spec: `X.shape == (100000, 19)`, `y.shape == (100000,)`, `y ∈ {0, 1, 2, 3}`, class priors в пределах ±1 % от spec.
- Перезапуск с тем же spec ОБЯЗАН произвести байт-идентичный датасет (совпадение digest в `metadata.json`).
- Тесты: `tests/component/test_data_generation_worker.py`, `tests/integration/test_data_generation_flow.py`.

## Вне scope

- Генерация image / tensor / sequence в MVP (только tabular).
