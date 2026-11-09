# Runbook — генерация RAG-карточек (SETUP-05)

Операционный гайд для разработчиков и on-call по SETUP-05. Описывает запуск,
диагностику и восстановление RAG card generation jobs.

## Когда использовать

- Пайплайн застрял на `rag_cards_generating` или прогресс не движется.
- Карточки массово помечены `review_required` или `generation_failed`.
- Регенерация одной карточки даёт неожиданный результат.
- Нужно пере-запустить генерацию после изменения промптов / ontology.

## 1. Запуск через UI

1. Открыть мастер `http://localhost:5173/`.
2. Шаги 1–3 (создать проект → загрузить документы → парсинг) должны быть в
   статусе `completed` или `partial_success`.
3. На шаге **4. Генерация RAG-карточек**:
   - нажать «1) Создать GenerationJob» → backend создаст `RAGCardGenerationJob`
     поверх eligible `ParsedSection`'ов;
   - нажать «2) Запустить генерацию» → синхронный run.
4. После terminal-статуса (`completed` / `partial_success` / `failed`):
   - таблица карточек обновляется автоматически;
   - low-confidence карточки попадают в отдельную панель сверху;
   - drawer (вкладки Metadata / Body / Source trace / Versions / Actions)
     открывается по клику «Просмотр».

## 2. Запуск через API

```bash
SID=setup_xxxxxxxx
H="-H X-User-Id:u1 -H X-Roles:user"

# 1) create
curl -s -X POST "http://localhost:8000/api/v1/setup/$SID/rag-cards/generate" \
     $H -H "Content-Type: application/json" \
     -d '{"generation_mode":"template"}'

# 2) run sync
GID=gen_xxxxxxxx
curl -s -X POST \
     "http://localhost:8000/api/v1/setup/$SID/rag-card-generation-jobs/$GID/run" $H

# 3) status / report
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-card-generation-jobs/$GID" $H | jq
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-card-generation-jobs/$GID/report" $H | jq

# 4) listing
curl -s "http://localhost:8000/api/v1/setup/$SID/rag-cards-catalog?confidence_level=low" $H | jq
```

## 3. Диагностика типичных ошибок

### `LLM_TIMEOUT`

Симптомы: section падает с `error_code=LLM_TIMEOUT`, в логах
`fe_bot.setup.rag_card_generation.orchestrator` запись `rag_card_generation_failed`
с этим кодом.

Действия:
1. Проверить, что Ollama жив: `curl http://localhost:11434/api/tags`.
2. Включить fallback-режим для всех вызовов:
   ```bash
   export FE_BOT_FORCE_FALLBACK=1
   uvicorn fe_bot.app:app --reload
   ```
   Это заставляет `LLMCardAdapter` всегда отдавать deterministic stub
   (карточка будет в `review_required`, но job не упадёт).
3. Перезапустить generation job (новый job на тех же секциях через
   `POST /rag-cards/generate` — старый failed job не блокирует).

### `INVALID_LLM_OUTPUT`

LLM вернул мусор или не соответствующий схеме JSON. Adapter уже делает один
repair-retry; если оба раза не получилось — section помечается failed.

Действия:
1. Проверить логи `llm_call` в `var/state/llm_traces/` (если включено
   `save_llm_trace`).
2. Если повторяется на конкретном `doc_type` — проблема в промпте
   ([prompts/rag_card/](../../prompts/rag_card/)) или в onтологии. Не править
   промпт в проде — открыть отдельный feature branch.
3. Можно временно переключить generation_mode на `template` (deterministic
   fallback): передать `{"generation_mode":"template"}` при create.

### `DOC_ID_CONFLICT`

`DocIdGenerator` нашёл существующий `doc_id` с той же базой; бамп версии не
сработал (или коллизия на новом slug). Обычно — следствие ручной правки
state-snapshot.

Действия:
1. Очистить state (см. ниже).
2. Проверить, что онтология / синонимы не дают одинаковый translit разным
   секциям.

### `CARD_BODY_EMPTY` / precheck failed

Карточка не прошла `CardValidationPrecheck`. Это блокирующая ошибка —
карточка не сохраняется как usable.

Действия:
1. Посмотреть детали в `report.errors` — там код precheck-ошибки
   (`missing_doc_id`, `body_too_short`, …).
2. Если систематически — поправить промпт или MetadataExtractor, перезапустить
   job.

### `DOC_TYPE_HINT_MISSING` *(целевое поведение, [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md); в коде пока нет)*

Секция классифицирована по дереву, но по пути нет `doc_type_hint` (или у секции нет `classifier_result`). LLM не вызывалась, карточка не создана.

Действия:
1. В `error_message` секции — путь классификации (например, `Требования → Функциональные требования`).
2. Если секций много и они из одной ветки — открыть шаг «Библиотека классификаторов» ([SETUP-13](../02-system/features/SETUP-13-classifier-library.md)) и задать `doc_type_hint` на подходящем узле (листья наследуют). Если подходящего из 7 поддерживаемых типов нет — секции корректно остаются без карточек.
3. Повторить генерацию failed-секций без перезапуска всего job. Повторный парсинг и классификация не нужны.
4. Если `classifier_result` отсутствует у всех секций — проверить `FE_BOT_TAXONOMY_MODE=llm` и наличие активного дерева, затем перепарсить документы.

Сейчас (до реализации хинтов) в `llm`-режиме секции, классифицированные по дереву SETUP-13, завершаются `INVALID_DOC_TYPE` с причиной `No doc_type for section_type=other` — см. [TD-HTC-004](../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md).

### Job застрял в `running`

В MVP runner синхронный, так что «застрял» обычно означает зависший
Ollama-вызов. См. `LLM_TIMEOUT`.

Если job нужно принудительно отменить:
```bash
curl -s -X POST \
   "http://localhost:8000/api/v1/setup/$SID/rag-card-generation-jobs/$GID/cancel" $H
```

## 4. Полная очистка state

Сейчас все репозитории — in-memory с JSON snapshot в `var/state/`. Чтобы
снести данные одного setup_job или весь стейт:

```bash
# soft reset frontend wizard:
# В localStorage browser: ключ fe-bot.wizard.v1 → удалить.

# hard reset backend (потеряет все jobs!):
rm -rf var/state/*.json
# или только rag-card snapshots:
rm -f var/state/rag_card_generation_*.json var/state/rag_card_source_links.json
```

После reset перезапустить backend.

## 5. Наблюдаемость

### Audit log

Все важные события пишутся в `InMemoryAuditLog` через `AuditAction.RAG_CARD_*`:

| Action | Когда |
| --- | --- |
| `rag_card.generation_triggered` | create_job |
| `rag_card.generated` | per card success |
| `rag_card.regenerate_triggered` | POST regenerate |
| `rag_card.review_required` | per card low/medium confidence |
| `rag_card.generation_cancelled` | cancel endpoint |

### Метрики

В endpoint `/metrics` (Prometheus):

- `rag_card_generation_jobs_total{outcome=...}` — terminal-исходы.
- `rag_cards_generated_total{doc_type,confidence_bucket}` — сгенерированные карточки.
- `rag_cards_failed_total{error_code}` — failed sections by code.
- `rag_card_generation_duration_ms{doc_type}` — гистограмма длительности.

### Структурированные логи

JSON-логи: ищите `rag_card_generation_job_started`, `rag_card_generation_job_finished`,
`rag_card_generated`, `rag_card_generation_failed`. У каждой записи есть
`generation_job_id` и `setup_job_id` — этого достаточно для трассировки.

## 6. Связанные документы

- [SETUP-05 feature](../02-system/features/SETUP-05-rag-cards-generation.md)
- [SETUP-05 traceability](../traceability/setup-05.md)
- [Card lifecycle](../06-rag/card-lifecycle.md)
- [Metadata schema](../06-rag/metadata-schema.md)
- [Implementation plan](../implementation-plan/SETUP-05.tasks.md)
