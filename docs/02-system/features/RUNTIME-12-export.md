# RUNTIME-12. Экспорт ML-пакета

## Назначение

Собрать каждый артефакт, нужный пользователю для запуска ML-pipeline вне FE-Bot — `features.json`, `generation_spec.json`, `X_train.csv`, `y_train.npy`, `training_config.yaml`, `pipeline.py`, `data_generator.py`, `metadata.json`, `validation_report.json` — и упаковать в `archive.zip` с time-bound download-ссылкой.

## Бизнес-ценность

Этот пакет — единственное, что пользователь уносит с диалога. Именно он делает всю систему ценной: запускаемая, инспектируемая стартовая точка для ML-работы.

## Пользовательский сценарий

1. После [RUNTIME-11](RUNTIME-11-model-selection.md) пользователь жмёт **Export project**.
2. Export Service материализует артефакты из `ContextMemory`, запускает `ExportManifestValidator`, строит `archive.zip` и выкладывает download-ссылку в Download Manager ([PLATFORM-04](PLATFORM-04-artifact-storage.md)).
3. Пользователь скачивает архив и может локально запустить `python data_generator.py && python pipeline.py --config config.yaml` без дополнительных вводов.

## Связанные требования

- BR-FR-Export-001..003 / BR-FR-110..114 (обязательные артефакты, manifest, форма файлов, форма `pipeline.py`).
- `pipeline.py` ОБЯЗАН выставлять класс `MLPipeline` с методами `load_data`, `preprocess`, `train`, `evaluate`, `predict`, `save_model` + запускаемый блок `__main__`.
- `metadata.json` ОБЯЗАН записывать digests, версии шаблонов промптов, id модели, версию KB.

## Связанные агенты

- `ExportAgent` (только оркестрация — он не изобретает контент, он сериализует подтверждённое состояние).

## Связанные сервисы

- Export Service, Artifact Storage (MinIO), API Backend, Frontend Download Manager, ContextMemory Service, Audit Service.

## Связанные контракты

- `ExportManifest` (`schemas/export_manifest.py`).
- Валидатор: [`validators/export_manifest_validator.py`](../../../validators/export_manifest_validator.py).

## Критерии приёмки

- `archive.zip` ОБЯЗАН содержать все 9 артефактов.
- `pipeline.py` ОБЯЗАН `import`-ить только `pandas`, `numpy`, `scikit-learn`, `xgboost` (и опционально `lightgbm`) — никаких FE-Bot-специфичных импортов.
- Повторный запуск экспорта на неизменённой `ContextMemory` ОБЯЗАН производить идентичный `metadata.json` в части датасета.
- Тест: `tests/e2e/test_export_happy_path.py`.
