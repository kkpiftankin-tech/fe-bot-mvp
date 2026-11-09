# SETUP-09. Embeddings и векторный индекс

## Назначение

Посчитать embeddings для каждого чанка, произведённого [SETUP-08](SETUP-08-chunking.md), и загрузить их вместе с metadata в Vector DB (Qdrant) под версионированный набор коллекций.

## Бизнес-ценность

Здесь база знаний становится *retrievable*. Работающий индекс — единственный артефакт, на который полагается Runtime; всё остальное выше по pipeline — подготовка к нему.

## Вход и выход

- **Вход.** Чанки из [SETUP-08](SETUP-08-chunking.md).
- **Выход.** Embeddings (`EmbeddingJob`) и версионированная коллекция в Qdrant (`IndexCollection`: `collection_name`, `index_version`, `chunk_count`, `dim`); пока KB не опубликована, `index_version` неактивна.

## Пользовательский сценарий

1. Мастер переходит в фазу **Indexing**.
2. UI показывает прогресс per-коллекция (`domain_profiles`, `schema_cards`, `feature_patterns`, `analytics_cards`, `validation_rules`, `question_templates`, `glossary`, `examples`).
3. Счётчики обновляются live: embedded чанков, проиндексировано чанков, ошибок. Резервируется новая `knowledge_base_version` (например, `kb_2026_05_18_v1`).
4. По успеху пользователь видит per-collection статистику и новую `index_version`.

## Связанные требования

- BR-FR-Setup-091..094 (id embedding-модели, размерность, layout коллекций, версионирование).
- NFR-Perf-002 (vector search ≤ 50 мс p95).
- Дефолтная embedding-модель: 384-мерный sentence-transformer; настраивается. Зеркалит `BR-NFR-002`.
- **Расхождение с кодом (открытое решение).** Текущий дефолт в `schemas/common/defaults.py` — `nomic-embed-text` (768-мерная, через Ollama); выбор помечен `TODO[ADR-007]`. Пока ADR-007 не принят, целевым считается значение из этого документа (384), а размерность индекса определяется выбранной моделью.

## Связанные сервисы

- Embedding Service, Vector DB Indexer, Vector DB (Qdrant), API Backend, Frontend Indexing Monitor, Artifact Storage, Observability Service.

## Связанные контракты

- `EmbeddingJob` (`schemas/setup.py`): `chunk_id`, `model_id`, `dim`, `status`, `embedded_at`.
- `IndexCollection`: `collection_name`, `index_version`, `chunk_count`, `dim`, `created_at`.

## Критерии приёмки

- Сбой на одном чанке ОБЯЗАН быть изолирован; мастер ОБЯЗАН отчитаться о failed-чанках, но продолжить с остальными.
- Новая `index_version` НЕ ОБЯЗАНА активироваться в SETUP-09; активация — в [SETUP-11](SETUP-11-publish-kb.md) после прохождения smoke-тестов.
- Повторный запуск индексации ОБЯЗАН быть идемпотентным для неизменённого манифеста чанков.
- Тест: `tests/component/test_setup_embedding_indexing.py`.

## Вне scope

- GPU-ускоренный embedding (CPU-пути достаточно для эталонной нагрузки).
