# UC-FE-03. Мониторинг качества системы

## Фичи

- [ANALYTICS-01..ANALYTICS-09](../../features/feature-index.md) — дашборды и audit.
- Опорные: [PLATFORM-01](../../features/PLATFORM-01-api-backend.md), [PLATFORM-03](../../features/PLATFORM-03-structured-output-contracts.md).

## Основной актор

Product Owner / Architect / Tech Lead.

## Поддерживающие акторы

- RAG Knowledge Base Admin (на drill-down в RAG-качество).
- ML-инженер (на drill-down в признаки и модели).
- Аудитор / compliance reviewer (на audit trail).

## Предусловия

- Хотя бы одна KB опубликована (`UC-FE-01`).
- Хотя бы одна Runtime-сессия прогнана (`UC-FE-02`).
- Conversation DB и Event Log Store содержат собранные события.

## Триггер

Product Owner открывает экран **Analytics** в начале спринт-обзора качества.

## Основной поток

1. На главной Analytics-странице пользователь видит summary: число активных KB-версий, число сессий за период, медианное wall-clock до экспорта, share сессий, дошедших до `archive.zip`, ratio override-ов модели.
2. **Воронка сессий ([ANALYTICS-01](../../features/ANALYTICS-01-session-dashboard.md)).** Выбирает прошлый месяц; видит drop-off bar по фазам. Замечает повышенный drop-off на `feature_synthesis`.
3. **Производительность агентов ([ANALYTICS-03](../../features/ANALYTICS-03-agent-performance.md)).** Открывает панель `FeatureSynthesisAgent`: rate repair-loop = 18 % (выше нормы), топ-причина — «derived feature references unknown base».
4. **Аналитика признаков ([ANALYTICS-05](../../features/ANALYTICS-05-feature-analytics.md)).** Видит, что 22 % отвергнутых признаков были `interaction`-ами, нарушающими `MAX_INTERACTIONS`. Указание на промпт: нужно научить агента уважать лимит.
5. **Качество RAG ([ANALYTICS-02](../../features/ANALYTICS-02-rag-quality.md)).** Замечает рост no-context rate в `feature_synthesis`-вызовах. Drill-down на падающие запросы.
6. **Жизненный цикл RAG ([ANALYTICS-04](../../features/ANALYTICS-04-rag-content-lifecycle.md)).** Видит 12 `feature_pattern`-карточек без retrieval hits за 60 дней. Отправляет их в `needs_review` — они автоматически всплывут на следующем setup-проходе ([SETUP-06](../../features/SETUP-06-rag-card-review.md)).
7. **Качество датасетов ([ANALYTICS-06](../../features/ANALYTICS-06-dataset-quality.md)).** Точечная проверка: фактический anomaly rate в среднем 0.019 (целевой 0.02). Норма.
8. **Рекомендации моделей ([ANALYTICS-07](../../features/ANALYTICS-07-model-recommendation.md)).** Override-rate `BayesianNetwork` = 80 %; пользователи выбирают `XGBoost + SHAP`. Решение: обновить веса `deployment_context` в `model_recommendation`-карточках.
9. **Доменный feature store ([ANALYTICS-08](../../features/ANALYTICS-08-domain-feature-store.md)).** Открывает sensor-панель: `jammed_time_ratio` вырос за последнюю неделю. Сигнал доменной команде.
10. **Audit trail ([ANALYTICS-09](../../features/ANALYTICS-09-audit-trail.md)).** Аудитор берёт один экспортированный архив и кликает **Trace origin** — видит линейный timeline от PDF → секция → карточка → чанк → evidence pack → агент → признак → датасет → архив. Скачивает JSON для compliance-отчёта.

## Альтернативные потоки

### A1. Дашборд пуст

Если в выбранном диапазоне нет событий, панель показывает «нет данных», а не нули.

### A2. Drill-down упирается в недостающий event

Если retrieval-call не был залогирован (баг observability), audit panel показывает разрыв цепочки красным цветом и линкует на runbook.

### A3. Audit-цепочка содержит редакцию

Если в audit timeline есть события `redaction`, они показываются с автором и обоснованием. Сама цепочка остаётся append-only; редакция — это новое событие.

### A4. Доменный feature store недоступен

Если внешние источники аналитики недоступны, [ANALYTICS-08](../../features/ANALYTICS-08-domain-feature-store.md) показывает «данных нет», а не synthetic значения.

## Постусловия

- Пользователь имеет список конкретных тикетов на улучшение: фиксы промптов агентов, обновления карточек, ревью content lifecycle, обновления model_recommendation.
- Audit-цепочка экспортирована (если требуется).
- Изменения в RAG-карточках поставлены в очередь следующего setup-прохода.

## Связанные сервисы

Analytics Service, RAG Analytics Service, Domain Analytics Service, Audit Service, Traceability Service, Conversation DB, Event Log Store, RAG Card Registry, Knowledge Base Registry, Vector DB, ContextMemory Service.

## Связанные контракты

`SessionFunnelEvent`, `RetrievalAuditEntry`, `AgentRunRecord`, `RAGCardUsageStats`, `FeatureGenerationEvent`, `DatasetQualityReport`, `ModelRecommendationEvent`, `FeatureStoreReading`, `AuditChain`, `AuditNode`.
