# ANALYTICS-04. Жизненный цикл RAG-контента

## Назначение

Обнажить устаревшие, неиспользуемые, low-confidence или невалидные RAG-карточки. Управлять curation: отправлять карточки на ревью, помечать reindex или выводить из KB.

## Бизнес-ценность

Базы знаний гниют. Без lifecycle-телеметрии накапливаются низкокачественные карточки, retrieval дрейфует, доверие испаряется.

## Вход и выход

- **Вход.** Реестр RAG-карточек и логи их использования.
- **Выход.** Список устаревших, неиспользуемых, low-confidence и невалидных карточек; действия curation — отправить на ревью, пометить reindex, вывести из KB.

## Пользовательский сценарий

RAG admin фильтрует по `doc_type = feature_pattern`, сортирует по возрастанию `last_used_at` и находит 12 карточек с нулевыми попаданиями retrieval за 60 дней. Ревьюит каждую и принимает решение: оставить (редкое-но-важное), обновить, удалить.

## Связанные требования

- BR-FR-Setup-Lifecycle-001..004 (per-card usage tracking, staleness, переходы статусов).
- NFR-Audit-001 (изменения lifecycle логируются).

## Связанные сервисы

- RAG Card Registry, Knowledge Base Registry, Analytics Service, Frontend RAG Content Dashboard, Validation Service.

## Связанные контракты

- `RAGCardUsageStats` (`schemas/analytics.py`): `doc_id`, `retrieval_count`, `last_used_at`, `last_validated_at`, `confidence_level`, `status`.

## Критерии приёмки

- Пользователь ОБЯЗАН иметь возможность фильтровать по `doc_type`, `domain`, `status`, `last_used_at`, `confidence_level`.
- Отправка карточки в «needs review» ОБЯЗАНА повышать её видимость в [SETUP-06](SETUP-06-rag-card-review.md) при следующем setup-проходе.
- Тест: `tests/component/test_rag_content_lifecycle.py`.
