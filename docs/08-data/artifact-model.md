# Модель артефактов

## Назначение

Перечислить, как именованы и где лежат все файлы, которые производит система.

## Виды артефактов (`ArtifactKind`)

| kind | Когда производится | Где лежит | Кому виден |
| --- | --- | --- | --- |
| `source_document` | SETUP-02 | `incoming-docs/raw/` + MinIO `kb/<kb_version>/source/<id>` | RAG admin |
| `rag_chunk_manifest` | SETUP-08 | MinIO `kb/<kb_version>/chunks/chunk_manifest.jsonl` | внутр. |
| `x_train_csv` | RUNTIME-10 | MinIO `conv/<conv_id>/X_train.csv` | пользователь |
| `y_train_npy` | RUNTIME-10 | MinIO `conv/<conv_id>/y_train.npy` | пользователь |
| `features_json` | RUNTIME-12 | MinIO `conv/<conv_id>/features.json` | пользователь |
| `generation_spec_json` | RUNTIME-12 | MinIO `conv/<conv_id>/generation_spec.json` | пользователь |
| `training_config_yaml` | RUNTIME-12 | MinIO `conv/<conv_id>/training_config.yaml` | пользователь |
| `pipeline_py` | RUNTIME-12 | MinIO `conv/<conv_id>/pipeline.py` | пользователь |
| `data_generator_py` | RUNTIME-12 | MinIO `conv/<conv_id>/data_generator.py` | пользователь |
| `metadata_json` | RUNTIME-10 + 12 | MinIO `conv/<conv_id>/metadata.json` | пользователь |
| `validation_report_json` | RUNTIME-07 + 10 | MinIO `conv/<conv_id>/validation_report.json` | пользователь |
| `archive_zip` | RUNTIME-12 | MinIO `conv/<conv_id>/archive.zip` | пользователь |
| `retrieval_report` | SETUP-10 | MinIO `kb/<kb_version>/retrieval_report.json` | RAG admin |
| `setup_session_snapshot` | SETUP-XX (per phase) | MinIO `kb/<kb_version>/snapshots/<phase>.json` | внутр. |

## Идентификация и метаданные

Каждый артефакт — `ArtifactRecord` (см. [entities.md](../04-domain/entities.md)) с `artifact_id`, `kind`, `bucket`, `key`, `checksum_sha256`, `size_bytes`, `created_at`.

## Доступ

- Download через time-bound URL (TTL по умолчанию 24 ч). Сами URL не сохраняются — генерируются по запросу.
- Per-conversation scoping форсится в API Backend (INV-Sec-001..002).

## Pipeline.py — обязательные импорты

Из RUNTIME-12:

```python
import pandas as pd
import numpy as np
from sklearn import ...
import xgboost as xgb       # или lightgbm
```

Импорты из `fe_bot.*` запрещены — пакет должен быть автономен.

## Связанные документы

- [generated-data-model.md](generated-data-model.md)
- [../02-system/features/RUNTIME-12-export.md](../02-system/features/RUNTIME-12-export.md)
- [../02-system/features/PLATFORM-04-artifact-storage.md](../02-system/features/PLATFORM-04-artifact-storage.md)
