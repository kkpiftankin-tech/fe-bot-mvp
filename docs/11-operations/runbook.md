# Runbook

Каталог самых частых симптомов и действий по их устранению. Шаблон записи — в [../00-methodology/artifact-templates.md](../00-methodology/artifact-templates.md#запись-в-runbook-docs11-operationsrunbookmd).

## Symptom: Feature Synthesis возвращает невалидные признаки

### Detection

- `fe_bot_validation_failures_total{validator_name="feature_validator"}` растёт.
- В Analytics: топ-причина отклонения — `FEAT_001_UNKNOWN_INPUT` или `FEAT_003_NO_EVIDENCE`.

### Checks

1. `ContextMemory.fields` для проблемной сессии.
2. `EvidencePack`, переданный в `FeatureSynthesisAgent`.
3. Версия промпта `feature_synthesis@vX.Y`.
4. Политика retrieval в [docs/06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md).
5. Логи RAG retrieval: вернулся ли `feature_pattern`-карточки для домена.

### Actions

- Перезапустить retrieval с уточнением `domain` / `data_source`.
- Запросить у пользователя недостающие поля.
- Если у домена нет `feature_pattern`-карточек — пинать RAG admin запустить [SETUP-05](../02-system/features/SETUP-05-rag-cards-generation.md) для нужного семейства.
- Если регрессия после bump промпта — откатить версию.

---

## Symptom: Setup-мастер падает на фазе Indexing

### Detection

- В UI `SetupProgressEvent` с phase=`indexing`, status=`failed`.
- `fe_bot_setup_phase_total{phase="indexing", outcome="failed"}` растёт.

### Checks

1. Qdrant: жив ли (`docker compose ps`, healthcheck).
2. Embedding model — отдаётся ли сервис; размерность 384.
3. Чанк-манифест: невалидный JSON / отсутствующие поля.

### Actions

- Перезапустить Qdrant; повторить фазу indexing из snapshot.
- При несовместимости embedding-модели → перегенерировать embeddings (фаза не публикуется, можно безопасно перезапустить).

---

## Symptom: Generated dataset не проходит class-balance check

### Detection

- `validation_report.json` с code `DATA_004_CLASS_BALANCE_OFF`.

### Checks

1. `GenerationSpec.target.classes[*].prior` — суммируются ли в 1.0.
2. `n_samples` — слишком мал для редкого класса?
3. `class_conditional_distributions` — корректно ли спроектированы?

### Actions

- Увеличить `n_samples` до достаточного, чтобы редкий класс не превращался в 0.
- Поправить spec через repair-loop (приложить отчёт валидатора).

---

## Symptom: Низкий RAG recall@k

### Detection

- `fe_bot_rag_no_context_total` растёт; пользователи получают «нужно больше контекста».

### Checks

1. Активная `kb_version`: какие коллекции есть, какие отсутствуют.
2. Падающие eval-запросы в [SETUP-10](../02-system/features/SETUP-10-retrieval-tests.md).
3. Distribution `last_used_at` карточек в [ANALYTICS-04](../02-system/features/ANALYTICS-04-rag-content-lifecycle.md).

### Actions

- Запустить новый Setup-проход с пополнением corpus.
- Подкрутить `similarity_threshold` в проблемной политике (после ADR).
- Пересмотреть `retrieval_tags` в самых востребованных карточках.

---

## Symptom: Невалидный JSON у конкретного агента (>10 %)

### Detection

- `fe_bot_llm_invalid_json_total{agent_name=...}` растёт.

### Checks

1. Сравнить с baseline по `prompt_template_version`.
2. Прогнать `tests/prompt_eval/<agent>_cases.yaml` на текущей версии.

### Actions

- Откатить версию промпта.
- Внести правки в промпт + bump версию + обновить prompt-eval-кейсы.
