# Failure handling RAG

Документ описывает поведение системы при сбоях в RAG-пайплайне на всех этапах: парсинг, генерация карточек, индексация, retrieval. Цель — чтобы любой сбой превращался в детерминированное действие (восстановление, HITL-запрос, отказ), а не в молчаливую галлюцинацию агента.

## 1. Документ не парсится

Source Registry получил файл, но Document Parser (SVC-07) не смог извлечь секции.

```text
- показать ошибку пользователю (Frontend);
- сохранить SourceDocumentDTO.status = failed;
- сохранить SourceDocumentDTO.error_message;
- предложить ручную загрузку extracted text (.md / .txt);
- НЕ допускать документ к Card Generation;
- залогировать AnalyticsEventDTO (event_type=setup_step, status=failed).
```

## 2. Карточка не прошла валидацию

`validators/rag_metadata_validator.py` вернул errors.

```text
- показать metadata errors пользователю (Card Review UI);
- предложить edit / regenerate;
- перевести карточку в status = review_required;
- НЕ допускать карточку к chunking;
- залогировать AnalyticsEventDTO (event_type=validation).
```

См. правила валидации в [rag-quality.md §1.1](rag-quality.md#11-валидация-rag-карточек).

## 3. Chunking даёт пустые embedding_text

```text
- chunk помечается status = failed;
- doc_id карточки откатывается на status = approved (chunk-цикл переподнимается);
- залогировать причину (длина < min_tokens, otherwise reason);
- если повторяется — карточка переходит в review_required.
```

## 4. Embedding model недоступна

LLM Gateway / Ollama не отвечают.

```text
- worker делает retry с экспоненциальной паузой (3 попытки);
- если не восстановилось — KnowledgeBaseVersion остаётся в status = building;
- индексация ставится на паузу;
- frontend показывает "embedding service degraded";
- alert в Notification Service (DTO-50).
```

## 5. Retrieval smoke tests provалились

`recall@5 < threshold` или `no_context_rate > threshold`.

```text
- KnowledgeBaseVersion НЕ публикуется (остаётся в status = testing);
- показать failed queries пользователю;
- предложить RAG admin:
    a) добавить ретrieval_tags;
    b) исправить metadata;
    c) добавить недостающие RAG-карточки;
    d) выпустить новую версию карточки с другим текстом;
- после исправлений возможен reindex без удаления KB.
```

Пороги — в [rag-quality.md §3.1](rag-quality.md#31-перед-публикацией-knowledge-base).

## 6. Runtime retrieval ничего не нашёл

Vector search вернул пустой набор после метаданных-фильтра и fallback-стратегии.

```text
- агент возвращает need_more_context = true;
- LangGraph Orchestrator переключается в clarification:
    a) задать уточняющий вопрос пользователю (question_template_card);
    b) либо пометить фазу blocked;
- логируется no_context event (DTO-49);
- предложить RAG admin добавить карточку в "what's missing" дашборд (см. ANALYTICS-04).
```

Fallback-цепочка — в [retrieval-policies.md](retrieval-policies.md).

## 7. Агент использовал deprecated карточку

Если в EvidencePack попал `doc_id` с `status = deprecated`:

```text
- Evidence Pack Builder фильтрует deprecated docs ДО передачи агенту;
- если карточка стала deprecated после построения пакета (race condition) — repair loop;
- логируется deprecated_docs_used (метрика из rag-quality.md);
- agent output помечается validation_status = repair_required.
```

## 8. Repair loop по invalid agent output

Если AgentResponseDTO `validation_status = invalid`:

```text
- 1-я попытка: повторный вызов агента с тем же EvidencePack;
- 2-я попытка: расширение EvidencePack (rerank + graph expansion);
- 3-я попытка: HITL-запрос (HumanReviewRequestDTO);
- max_retries = 3 (см. ADR-001).
```

## 9. KB version conflict

Активная `KnowledgeBaseVersion` иммутабельна. Если RAG admin пытается изменить её:

```text
- операция отклоняется на уровне Knowledge Base Registry;
- предлагается создать новую версию (vN+1);
- старая версия остаётся active до явного промоушена новой;
- audit event (DTO-48) с before_state / after_state.
```

## 10. Ontology drift

Если онтология изменилась, но карточки ссылаются на устаревшие значения:

```text
- metadata validator валит ВСЕ карточки с устаревшими значениями;
- предлагается миграция: list карточек к правке;
- KnowledgeBaseVersion НЕ может быть published пока есть нарушения;
- допустимо параллельно держать старую active KB на старой онтологии до миграции.
```

## 11. У ветки дерева классификатора нет `doc_type_hint`

Секция классифицирована по дереву SETUP-13, но ни на одном узле пути не задан `doc_type_hint` (или у секции нет `classifier_result`). Целевое поведение по [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md):

```text
- НЕ угадывать doc_type (ни по section_type, ни LLM-ом);
- НЕ вызывать LLM для секции, карточку не создавать;
- job-секция: status = failed, error_code = DOC_TYPE_HINT_MISSING,
  причина «taxonomy node has no doc_type_hint» + путь классификации;
- показать секцию в UI как «требует настройки дерева» со ссылкой на узел;
- после правки хинта в SETUP-13 повторить генерацию секции (без перепарсинга);
- вывести в отчёт job долю таких секций (покрытие дерева хинтами).
```

Если `doc_type` определён, но нет `domain_hint` или `phase_hint`, карточка создаётся со статусом `metadata_incomplete` и причиной, перечисляющей недостающие поля.

## Матрица failure → действие

| Failure | Кто реагирует | Действие |
| --- | --- | --- |
| parse error | Document Parser | failed + manual upload |
| invalid metadata | Card Review | review_required + edit |
| empty embedding_text | Chunking | retry, иначе review_required |
| LLM down | LLM Gateway | retry, иначе degraded |
| failed smoke tests | RAG Evaluation | block publish + dashboard |
| runtime no context | Agent | `need_more_context: true` + clarification |
| deprecated card used | Evidence Builder | filter + log |
| invalid agent output | LangGraph Orchestrator | repair loop (max 3) |
| KB version conflict | KB Registry | reject + new version |
| ontology drift | Metadata Validator | block + migration |
| у ветки дерева нет `doc_type_hint` | RAG Card Generator | `DOC_TYPE_HINT_MISSING`, без LLM; хинт на узле (SETUP-13) + повтор |

## Связанные документы

- [rag-methodology.md](rag-methodology.md)
- [rag-lifecycle.md](rag-lifecycle.md)
- [rag-quality.md](rag-quality.md)
- [retrieval-policies.md](retrieval-policies.md)
- [../09-langgraph/repair-loops.md](../09-langgraph/repair-loops.md)
- [../03-architecture/adr/ADR-001-langgraph-as-orchestrator.md](../03-architecture/adr/ADR-001-langgraph-as-orchestrator.md)
