# Unit-тесты

## Назначение

Доказать корректность чистых функций, схем и валидаторов в изоляции.

## Что покрывается

- Pydantic-схемы (`schemas/`): валидное / невалидное JSON-описание.
- Валидаторы (`validators/`): каждое правило кодов из [docs/07-contracts/validation-report.md](../07-contracts/validation-report.md).
- Утилиты разбора формул и safe-evaluator (см. `validators/feature_validator.py`).

## Структура

```text
tests/unit/
├── test_context_memory_schema.py
├── test_feature_spec_schema.py
├── test_generation_spec_schema.py
├── test_validation_report_schema.py
├── test_export_manifest_schema.py
├── test_rag_metadata_validator.py
├── test_feature_validator.py
├── test_generation_spec_validator.py
├── test_generated_data_validator.py
└── test_safe_formula_evaluator.py
```

## Принципы

- Без I/O. Никаких сетевых вызовов, никакого LLM, никакой БД.
- Один тест — одно утверждение.
- Параметризовать через `pytest.mark.parametrize`.

## Запуск

```bash
make test-unit
pytest tests/unit/test_feature_validator.py::test_temporal_feature_when_not_allowed -q
```
