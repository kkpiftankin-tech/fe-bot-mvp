# ExportAgent

## Purpose

Собрать `ExportManifest` со списком всех артефактов, инициировать сборку `archive.zip` через Export Service, выпустить time-bound download-ссылку.

## Phase

`PHASE_7_EXPORT`

## Input

- `ContextMemory` (полный, после Model Selection).
- Список `ArtifactRecord`-ов в Artifact Storage.

## Output

`ExportManifest` — см. `schemas/export_manifest.py`.

## Tools

- `export_service.bundle(conversation_id) -> archive_artifact_id`.
- `download_url.signed(artifact_id, ttl)`.

## RAG Policy

Не использует RAG.

## Hard Rules

- Не «изобретает» контент: сериализует подтверждённую `ContextMemory`.
- Каждый артефакт обязан иметь checksum; mismatch — фейл экспорта.
- `pipeline.py` обязан импортировать только разрешённые библиотеки (`pandas, numpy, scikit-learn, xgboost`, опц. `lightgbm`) — никаких FE-Bot-специфичных импортов.

## Failure Modes

- Один из артефактов отсутствует → структурированная ошибка `missing_artifact` с указанием отсутствующего kind.
- `export_manifest_validator` отверг → агент не публикует архив; помечает `status=failed`.
