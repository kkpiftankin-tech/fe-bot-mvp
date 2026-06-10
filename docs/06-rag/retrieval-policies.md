# Retrieval-политики

Для каждой пары `(агент, фаза)` зафиксирован шаблон retrieval-запроса. Шаблон — это набор metadata-фильтров + semantic-запрос + параметры top-K / threshold.

## Pipeline retrieval

```text
Agent запрашивает контекст
  → identify phase
  → identify agent
  → read ContextMemory slice
  → load retrieval policy
  → build metadata filters (deterministic)
  → generate semantic query
  → vector search (Qdrant)
  → rerank
  → graph expansion
  → build EvidencePack
  → return to agent
```

**Metadata-first.** Первый шаг retrieval — НЕ embedding search, а metadata filtering. Только после применения фильтров делается semantic search по `D_filtered`.

Формально:

$$
D_{\text{filtered}} = \{ d \in D \mid \text{metadata}(d) \models \text{filters} \}
$$

$$
R = \text{TopK}(\text{sim}(\text{emb}(q), \text{emb}(d))), \quad d \in D_{\text{filtered}}
$$

$$
\text{EvidencePack} = \text{compose}(\text{rerank}(R), \text{graph\_expand}(R), \text{ContextMemory})
$$

## Базовый формат

```yaml
phase: <Phase>
agent: <AgentName>
doc_type:
  - <doc_type_1>
  - <doc_type_2>
domain: current.domain
data_source: current.data_source
task_type: current.task_type
feature_family: current.feature_family   # опц.
top_k: 5
similarity_threshold: 0.7
rerank_signals:
  - confidence_level
  - priority
  - last_used_at
```

## Политики

### NLUAgent / all

```yaml
phase: nlu
doc_type:
  - glossary_term
  - question_template_card
top_k: 3
similarity_threshold: 0.6
```

### TaskDiscoveryAgent / task_discovery

```yaml
phase: task_discovery
doc_type:
  - domain_profile
  - question_template_card
domain: current.domain
top_k: 3
similarity_threshold: 0.7
```

### DataProfilingAgent / data_profiling

```yaml
phase: data_profiling
doc_type:
  - schema_card
  - question_template_card
  - glossary_term
domain: current.domain
data_source: current.data_source
top_k: 5
similarity_threshold: 0.7
```

### DomainContextAgent / domain_context

```yaml
phase: domain_context
doc_type:
  - domain_profile
  - analytics_card
  - validation_rule_card
domain: current.domain
data_source: current.data_source
top_k: 5
similarity_threshold: 0.7
```

### FeatureSynthesisAgent / feature_synthesis

```yaml
phase: feature_synthesis
doc_type:
  - feature_pattern_card
  - analytics_card
  - schema_card
  - glossary_term
domain: current.domain
data_source: current.data_source
task_type: current.task_type
top_k: 10
similarity_threshold: 0.7
```

### FeatureCriticAgent / feature_synthesis

```yaml
phase: feature_synthesis
doc_type:
  - validation_rule_card
task_type: current.task_type
domain: current.domain
top_k: 5
similarity_threshold: 0.65
```

### DataGenerationSpecAgent / data_generation

```yaml
phase: data_generation
doc_type:
  - feature_pattern_card
  - analytics_card
  - validation_rule_card
domain: current.domain
data_source: current.data_source
top_k: 8
similarity_threshold: 0.7
```

### ModelSelectionAgent / model_selection

```yaml
phase: model_selection
doc_type:
  - model_recommendation_card
task_type: current.task_type
data_type: current.data_type
top_k: 5
similarity_threshold: 0.7
```

## Fallback-стратегия

При 0 hits в политике:

1. Ослабить `data_source` (если фильтр был).
2. Ослабить `task_type` (если фильтр был).
3. Ослабить `feature_family`.
4. Не ослаблять `domain` и `doc_type`.
5. Снизить `similarity_threshold` на один шаг (0.7 → 0.6 → 0.5).
6. Если всё равно 0 — `RAGRetrievalAgent` выставляет `need_more_context=true`, дальнейшее поведение — в [rag-failure-modes.md §6](rag-failure-modes.md#6-runtime-retrieval-ничего-не-нашёл).

## Graph expansion

Semantic search возвращает релевантные карточки, но агенту часто нужны **связанные** карточки (schemas, validation rules, compatible models). Graph expansion добавляет их по типизированным связям.

Связи хранятся в `rag/relationships/graph_relationships.yaml`.

### Типы связей

| Связь | Смысл |
| --- | --- |
| `requires_schema` | Для задачи нужна определённая schema_card |
| `uses_field` | Признак использует конкретное поле (field_definition_card) |
| `produces_feature` | Карточка генерирует признак |
| `requires_validation` | Карточка требует определённого validation_rule_card |
| `compatible_model` | Подходящая model_recommendation_card |
| `depends_on_context` | Зависит от domain_profile |
| `forbidden_if` | Запрещена при выполнении условия |
| `source_document` | Связь с исходным документом |

### Пример expansion

```text
task.surface_threat_evaluation.v1
  → schema.tracks_fused.v1            (requires_schema)
  → schema.tactical_object.v1         (requires_schema)
  → analytics.object_analytics_T.v1   (produces_feature)
  → analytics.environment_analytics_T.v1
  → validation.requires_track_kinematics.v1  (requires_validation)
```

### Параметры

```yaml
graph_expansion:
  max_depth: 2
  follow_edges:
    - requires_schema
    - uses_field
    - requires_validation
  stop_at_doc_types:
    - example_card
    - bad_example_card
  budget_extra_chunks: 4
```

Эти параметры можно переопределять per-agent в `retrieval_policies.yaml`.

## Rerank

После top-K из Qdrant выполняется rerank по композитному score:

```text
score = similarity * 0.6
      + (confidence_high ? 0.2 : confidence_medium ? 0.1 : 0)
      + (priority / 100) * 0.1
      + freshness_factor(last_used_at) * 0.1
```

## Связанные документы

- [rag-overview.md](rag-overview.md)
- [rag-methodology.md](rag-methodology.md)
- [chunk-schema.md](chunk-schema.md)
- [evidence-pack.md](evidence-pack.md)
- [rag-failure-modes.md](rag-failure-modes.md)
- [rag-quality.md](rag-quality.md)
- [../02-system/features/RUNTIME-02-nlu.md](../02-system/features/RUNTIME-02-nlu.md)
- [../03-architecture/c4-component-rag-service.md](../03-architecture/c4-component-rag-service.md)
