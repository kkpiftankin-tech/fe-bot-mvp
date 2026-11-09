# ANALYTICS-02. Дашборд качества RAG

## Назначение

Обнажить сигналы качества retrieval: recall@k, precision@k, no-context rate, топ-используемые / неиспользуемые документы, топ-падающие запросы, распределение latency retrieval и per-`doc_type` объём retrieval.

## Бизнес-ценность

Runtime хорош ровно настолько, насколько хорошо его retrieval. Тихая регрессия — плохой embedding, сломанный metadata-фильтр, дрейф онтологии — должна быть видна в момент возникновения, а не когда пользователь пожалуется.

## Вход и выход

- **Вход.** Логи retrieval и результаты eval-прогонов.
- **Выход.** Recall@k, precision@k, no-context rate, топ-используемые и неиспользуемые документы, топ-падающие запросы, распределение latency retrieval, объём retrieval по `doc_type`.

## Пользовательский сценарий

RAG admin открывает дашборд и видит: агрегированный recall@5 за последние 24 ч, список запросов с `retrieved_doc_count = 0`, 10 наиболее цитируемых карточек (cross-reference на доверие), 10 карточек с нулевыми попаданиями за период (кандидаты на ревью или удаление).

## Связанные требования

- BR-Metrics-RAG-001..003 (отслеживание recall@k, precision@k, no-context rate).
- NFR-Obs-003 (каждый вызов retrieval логируется с `rag_query_id`, `retrieved_doc_ids`, набором фильтров).

## Связанные сервисы

- RAG Analytics Service, RAG Retrieval Service, Vector DB, Frontend RAG Quality Dashboard, RAG Evaluation Service, Event Log Store.

## Связанные контракты

- `RetrievalAuditEntry` (`schemas/analytics.py`): `rag_query_id`, `phase`, `agent_name`, `filters`, `retrieved_doc_ids`, `retrieved_chunk_ids`, `scores`, `latency_ms`.

## Критерии приёмки

- Drill-down на падающий запрос ОБЯЗАН показать активный набор фильтров, retrieved docs и ожидаемые docs (если запрос — часть eval-сьюта).
- Тест: `tests/component/test_rag_quality_dashboard.py`.
