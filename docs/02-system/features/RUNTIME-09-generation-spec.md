# RUNTIME-09. Эмиссия GenerationSpec

## Назначение

Произвести типизированный `GenerationSpec` — Python-консумируемый JSON, описывающий, как генерировать синтетический датасет (распределения, target-логика, шум, аномалии, ожидания валидации). LLM эмитит спецификацию; **она никогда не эмитит строки**.

## Бизнес-ценность

Это межсетевой экран между «LLM предлагает» и «Python генерирует». Гарантирует воспроизводимость, валидацию и трассируемость каждой произведённой строки обратно до spec, который пользователь может прочитать.

## Пользовательский сценарий

Агент собирает spec из `final_features`, `class_distribution`, пользовательских `n_samples`, `noise_level`, `anomaly_rate` и radar-evidence-pack. Пользователь видит preview: target-классы + priors, per-feature распределения (`range ~ uniform(0, 200)`, `rcs ~ exponential(scale=10)`, `snr ~ normal(20, 10)`, …), модель шума, модель аномалий, ожидаемые проверки. Пользователь подтверждает или меняет до запуска генерации.

## Связанные требования

- BR-FR-Gen-001 (эмиссия типизированного spec).
- BR-FR-Gen-002 (LLM эмитит spec, не строки).
- Дефолтные эталонные значения: `n_samples = 100000`, `random_state = 42`, `noise_level = 0.01`, `anomaly_rate = 0.02`.

## Связанные агенты

- `DataGenerationSpecAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `GenerationSpec` (`schemas/generation_spec.py`) — см. [../../07-contracts/generation-spec.md](../../07-contracts/generation-spec.md).
- Валидатор: [`validators/generation_spec_validator.py`](../../../validators/generation_spec_validator.py).

## Связанные RAG-документы

- Карточки `feature_pattern`, `analytics_card`, `validation_rule`, отфильтрованные по `domain` × `data_source` × `task_type`.

## Критерии приёмки

- Эмитированный spec ОБЯЗАН проходить валидацию `GenerationSpec`: class priors суммируются к 1.0 ± 1e-6, производные признаки ссылаются на существующие base-признаки, нет временных при `temporal_importance = false`.
- Падающая валидация ОБЯЗАНА запускать ограниченный repair loop (`max_retries = 3`) с отчётом валидатора, приложенным к промпту.
- Тесты: `tests/unit/test_generation_spec_schema.py`, `tests/component/test_generation_spec_agent.py`.

## Вне scope

- Прямая генерация строк LLM (явно запрещена).
