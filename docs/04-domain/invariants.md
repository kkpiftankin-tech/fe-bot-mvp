# Инварианты

Утверждения, которые обязаны оставаться истинными в любой момент времени. Каждый инвариант форсится одним из:

- Pydantic-схемой,
- детерминированным валидатором,
- DB-constraint,
- логикой оркестратора (LangGraph / Setup).

## Идентичность и уникальность

- **INV-ID-001.** `source_document_id` уникален.
- **INV-ID-002.** `doc_id` уникален по всей `rag/cards/`.
- **INV-ID-003.** `chunk_id` уникален в рамках `kb_version`.
- **INV-ID-004.** `conversation_id` уникален.
- **INV-ID-005.** `feature.name` уникален в рамках `ContextMemory.final_features`.

## База знаний

- **INV-KB-001.** В каждый момент только одна `KnowledgeBaseVersion` имеет `status = active`.
- **INV-KB-002.** Опубликованная `KnowledgeBaseVersion` — иммутабельна: её `card_versions` и `index_version` нельзя править. Любое изменение — это новая версия.
- **INV-KB-003.** `Conversation.kb_version` фиксируется в момент `SessionStarted` и не меняется до завершения сессии.

## ContextMemory

- **INV-CM-001.** `current_phase` ∈ закрытому множеству `Phase`.
- **INV-CM-002.** Продвижение `current_phase` возможно только при выполнении completion-criteria текущей фазы (см. [../09-langgraph/state-machine.md](../09-langgraph/state-machine.md)).
- **INV-CM-003.** Откат фазы инвалидирует downstream-слоты: `final_features`, `generation_spec`, `generated_dataset`, `recommended_model`, `training_config`, `artifacts`, `export_manifest`.
- **INV-CM-004.** `kb_version` обязателен и неизменяем для сессии после `SessionStarted`.

## Признаки

- **INV-Feat-001.** Каждый `FeatureSpec.status = approved` обязан иметь непустой `evidence_doc_ids`.
- **INV-Feat-002.** Каждый `derived`-признак обязан перечислять `input_features`, все из которых существуют в `ContextMemory.fields` или среди ранее принятых признаков.
- **INV-Feat-003.** Каждый `interaction`-признак обязан ссылаться только на признаки, уже принятые в `final_features`.
- **INV-Feat-004.** Если `ContextMemory.temporal_importance = false`, ни один признак не может иметь `role = temporal`.
- **INV-Feat-005.** Если `role = temporal`, `ContextMemory.fields` обязан содержать `timestamp` и `entity_id`.
- **INV-Feat-006.** Количество признаков не превышает `MAX_FEATURES = 200`; количество `interaction`-признаков не превышает `MAX_INTERACTIONS = 50`.
- **INV-Feat-007.** Признаки с попарной корреляцией `|ρ| ≥ MULTICOLLINEARITY_THRESHOLD` не могут оба оказаться в `final_features` без override с обоснованием.

## Генерация данных

- **INV-Gen-001.** В `GenerationSpec` сумма `target.classes[*].prior` равна 1.0 ± 1e-6.
- **INV-Gen-002.** `GenerationSpec.feature_specs` содержит ровно `len(ContextMemory.final_features)` записей; имена и роли совпадают.
- **INV-Gen-003.** Для каждой `derived`-spec формула парсится безопасным evaluator-ом и ссылается только на ранее определённые признаки.
- **INV-Gen-004.** Перезапуск с тем же `(spec, random_state)` производит байт-идентичный `X_train.csv` и `y_train.npy` (digest match).
- **INV-Gen-005.** В сгенерированном датасете нет NaN/Inf, если `missing_data_strategy = none`.
- **INV-Gen-006.** Фактическое распределение классов отклоняется от `GenerationSpec.target.classes[*].prior` не более чем на 1 п. п.

## Выводы LLM и валидация

- **INV-LLM-001.** Ни один `LLM`-вывод не потребляется ниже по pipeline без успешного `model_validate`.
- **INV-LLM-002.** Repair-loop ограничен `max_retries`; после исчерпания фаза фейлится со структурированной ошибкой.
- **INV-LLM-003.** В output-схемах, требующих evidence, поле `evidence_doc_ids` обязательно непустое.

## Безопасность и audit

- **INV-Sec-001.** Артефакт доступен только для своего `conversation_id`.
- **INV-Sec-002.** Download URL валиден до своего TTL и только для своего `conversation_id`.
- **INV-Audit-001.** Каждое изменение `ContextMemory`, каждый `AgentRun`, каждое action ревью карточек, каждое экспортированное скачивание ОБЯЗАНО иметь соответствующее событие в `AuditChain`.
- **INV-Audit-002.** `AuditChain` append-only; редакция — это новое `AuditNode` со ссылкой на корректируемое.

## Где это форсится

| Инвариант | Механизм |
| --- | --- |
| INV-ID-001..005 | DB unique constraints + Pydantic |
| INV-KB-001..003 | Knowledge Base Registry + transactional update |
| INV-CM-001..004 | LangGraph state machine + ContextMemory Pydantic |
| INV-Feat-001..007 | `validators/feature_validator.py` + `MulticollinearityAgent` |
| INV-Gen-001..006 | `validators/generation_spec_validator.py` + `validators/generated_data_validator.py` |
| INV-LLM-001..003 | Structured-Output Caller + Repair Loop |
| INV-Sec-001..002 | API auth + signed-URL TTL |
| INV-Audit-001..002 | Audit Service writes + DB constraints |

## Связанные документы

- [entities.md](entities.md)
- [value-objects.md](value-objects.md)
- [domain-events.md](domain-events.md)
- [../07-contracts/](../07-contracts/)
- [../09-langgraph/repair-loops.md](../09-langgraph/repair-loops.md)
