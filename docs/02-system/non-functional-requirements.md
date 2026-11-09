# Нефункциональные требования

Атрибуты качества, которым обязана удовлетворять система. У каждого есть ID `NFR-<Quality>-<NN>` и измеримый сигнал приёмки. Зеркалит `BR-NFR-XXX` из бизнес-требований; cross-references в финальной таблице.

## Производительность

- **NFR-Perf-001.** Интерактивный round-trip диалога ОБЯЗАН укладываться в ≤ 1–2 с wall-clock p95 (FastAPI-запрос → загрузка из БД → RAG retrieval → intent classification → entity extraction → DialogueEngine → генерация ответа → сохранение в БД → HTTP-ответ). Зеркалит `BR-NFR-001`.
- **NFR-Perf-002.** RAG vector search ОБЯЗАН укладываться в ≤ 50 мс p95 на эталонной нагрузке (~10k чанков, 384-мерные embeddings). Top-K = 3–5, similarity threshold по умолчанию 0.7. Зеркалит `BR-NFR-002`.
- **NFR-Perf-003.** Per-agent вызов LLM ОБЯЗАН укладываться в 200–500 мс p95 на локальном Ollama c моделью класса 1B–3B (`llama3.2`, Phi-2, Mistral-7B quantized, TinyLlama). Бюджет контекста 4k–8k токенов. Зеркалит `BR-NFR-003`.
- **NFR-Perf-004.** Фаза Feature Synthesis ОБЯЗАНА укладываться в 2–3 с для эталонного radar-сценария (≤ 19 признаков по base / derived / interaction). Зеркалит `BR-NFR-004`.
- **NFR-Perf-005.** Synthetic Data Generation ОБЯЗАНА укладываться в ≤ 2 с для эталонного табличного случая 100k × 19 на одном хосте. Зеркалит `BR-NFR-005`.
- **NFR-Perf-006.** Сквозной happy path (описание задачи → `archive.zip`) ОБЯЗАН укладываться в ≤ 15 минут wall-clock для эталонного сценария.

## Масштабируемость

- **NFR-Scale-001.** База знаний ОБЯЗАНА масштабироваться до ≥ 12 500 документов (целевой референс) и оставаться поисковой в рамках latency-бюджета. Зеркалит `BR-NFR-010`.
- **NFR-Scale-002.** Система ОБЯЗАНА поддерживать добавление новых доменов (например, `naval`, `air`, `ground`, `cyber`, `analytical`) без переписывания workflow. Зеркалит `BR-NFR-011`.
- **NFR-Scale-003.** Лимиты по признакам: `MAX_FEATURES = 200`, `MAX_INTERACTIONS = 50`, `MIN_FEATURE_VARIANCE = 0.01`, `MULTICOLLINEARITY_THRESHOLD = 0.95` (VIF < 10). Зеркалит `BR-NFR-012`.

## Ресурсы

- **NFR-Res-001.** Дефолтный Compose-профиль ОБЯЗАН работать в 16 GB RAM на 4-ядерном consumer-ноутбуке.
- **NFR-Res-002.** Индекс Vector DB для эталонной нагрузки ОБЯЗАН оставаться под 1 GB на диске.

## Надёжность

- **NFR-Rel-001.** Агент, выдавший невалидный JSON, ОБЯЗАН запустить ограниченную repair-петлю (`max_retries`, по умолчанию 3), затем зафейлить фазу со структурированной ошибкой и fallback-шаблоном. Система НЕ ОБЯЗАНА падать. Зеркалит `BR-NFR-020`.
- **NFR-Rel-002.** Если RAG не вернул релевантный контекст, агент ОБЯЗАН переключиться в generic-режим, эмитнуть `need_more_context=true` и попросить пользователя уточнить — НЕ выдумывать доменные факты. Зеркалит `BR-NFR-021`.
- **NFR-Rel-003.** Context-снапшоты ОБЯЗАНЫ персиститься per-фазу; крах посреди диалога ОБЯЗАН позволять возобновление с последнего checkpoint-а. Зеркалит `BR-NFR-022`.
- **NFR-Rel-004.** Потеря Ollama или Qdrant ОБЯЗАНА обрабатываться retry-with-backoff (3 попытки, 200 мс / 1 с / 5 с) и структурированной ошибкой, видимой пользователю.

## Воспроизводимость

- **NFR-Repro-001.** При заданных `GenerationSpec` и `random_state` сгенерированный датасет ОБЯЗАН быть байт-идентичным между запусками.
- **NFR-Repro-002.** `metadata.json` ОБЯЗАН фиксировать digests `X_train.csv`, `y_train.npy`, версии схем, версии шаблонов промптов, id embedding-модели, id LLM-модели и активную версию индекса базы знаний.

## Наблюдаемость

- **NFR-Obs-001.** Каждая строка лога ОБЯЗАНА быть структурированным JSON с `conversation_id`, `agent_name`, `phase`, `node_name`, `trace_id` (где применимо).
- **NFR-Obs-002.** Система ОБЯЗАНА выставлять метрики из [../11-operations/metrics.md](../11-operations/metrics.md).
- **NFR-Obs-003.** Audit-лог retrieval ОБЯЗАН включать `rag_query_id`, `retrieved_doc_ids`, `retrieved_chunk_ids` и активный фильтр-сет per-вызов (`doc_type`, `domain`, `task_type`, `data_source`, `phase`).

## Качество (NLU / RAG)

- **NFR-Qual-001.** Точность intent ОБЯЗАНА быть ≥ 85 % на curated MVP-test-set. Зеркалит `BR-Metrics-NLU-intent`.
- **NFR-Qual-002.** Точность entity extraction ОБЯЗАНА быть ≥ 80 % на curated MVP-test-set. Зеркалит `BR-Metrics-NLU-entity`.
- **NFR-Qual-003.** Валидаторы ОБЯЗАНЫ проходить для ≥ 80 % сгенерированных признаков и 100 % экспортированных артефактов. Зеркалит `BR-Metrics-feature-validation` / `BR-Metrics-artifact-validation`.

## Безопасность и Governance

- **NFR-Sec-001.** Сессии ОБЯЗАНЫ быть изолированы по `conversation_id`; межсессионные чтения запрещены в MVP. Зеркалит `BR-NFR-030`.
- **NFR-Sec-002.** Артефакты ОБЯЗАНЫ храниться с conversation-scoped доступом; download-ссылки ОБЯЗАНЫ быть time-bound (TTL). Межсессионный доступ требует явного sharing. Зеркалит `BR-NFR-031`.
- **NFR-Sec-003.** API ОБЯЗАН валидировать каждое request-тело против Pydantic-схем до dispatch-а.
- **NFR-Sec-004.** Сырые загрузки пользователя в [incoming-docs/raw/](../../incoming-docs/raw/) ОБЯЗАНЫ быть opt-in для ingestion — никогда не автопубликоваться.
- **NFR-Sec-005.** Никаких секретов в коде или docs. Все credentials через переменные окружения.
- **NFR-Audit-001.** Каждое изменение state, агентный вывод, RAG evidence id, результат валидации и экспортированный артефакт ОБЯЗАНЫ персиститься в audit trail. Зеркалит `BR-NFR-032`.

## Портативность

- **NFR-Port-001.** Полный стек ОБЯЗАН работать на macOS, Linux и WSL2 с установленным Docker.
- **NFR-Port-002.** Никакой жёсткой зависимости от проприетарных frontier LLM в дефолтном пути.

## Поддерживаемость

- **NFR-Maint-001.** Каждый агент ОБЯЗАН быть заменяем альтернативной реализацией, если она возвращает ту же Pydantic-схему.
- **NFR-Maint-002.** Изменения схемы, ломающие контракт, ОБЯЗАНЫ сопровождаться bump-ом версии и migration note в соответствующем ADR.
- **NFR-Maint-003.** Ни один файл в `src/` не создаётся без соответствующих doc + schema + test (см. [../00-methodology/development-process.md](../00-methodology/development-process.md)).

## Usability и язык

- **NFR-Use-001.** Основной язык UI — русский; система ОБЯЗАНА принимать русские и английские термины в NLU (например, `РЛС/radar`, `классификация/classification`, `табличные/tabular`). Зеркалит `BR-NFR-040`.
- **NFR-Use-002.** Пользователь ОБЯЗАН всегда видеть: текущую фазу, 7-фазный прогресс-бар (Setup использует свой — мастер из 11 шагов), собранные слоты, недостающие слоты, объяснение, почему предложен признак или модель, и список артефактов, которые вот-вот будут произведены. Зеркалит `BR-NFR-041`.
- **NFR-Use-003.** Уточняющие вопросы ОБЯЗАНЫ ссылаться на недостающее поле по имени; сообщения об ошибках ОБЯЗАНЫ называть фазу-источник.

## Compliance / Методология

- **NFR-Gov-001.** Каждое изменение агентов, контрактов, RAG-карточек или фич ОБЯЗАНО отражаться в [../traceability/](../traceability/).
- **NFR-Gov-002.** Каждый ADR в [../03-architecture/adr/](../03-architecture/adr/) ОБЯЗАН иметь один из статусов: Proposed, Accepted, Deprecated, Superseded.

## Соответствие `BR-NFR-XXX`

| Этот doc | Бизнес-doc |
| --- | --- |
| NFR-Perf-001..005 | BR-NFR-001..005 |
| NFR-Scale-001..003 | BR-NFR-010..012 |
| NFR-Rel-001..003 | BR-NFR-020..022 |
| NFR-Sec-001, 002 / NFR-Audit-001 | BR-NFR-030..032 |
| NFR-Use-001, 002 | BR-NFR-040..041 |

## Связанные документы

- [functional-requirements.md](functional-requirements.md)
- [../11-operations/metrics.md](../11-operations/metrics.md)
- [../11-operations/runbook.md](../11-operations/runbook.md)
- [../01-business/constraints.md](../01-business/constraints.md)
