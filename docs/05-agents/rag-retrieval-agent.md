# RAGRetrievalAgent

## Purpose

По текущей фазе и `ContextMemory` собрать `RetrievalPlan`, выполнить его в Vector DB и вернуть компактный `EvidencePack` для последующих агентов.

## Phase

`all` — вызывается перед содержательными агентами на каждой фазе.

## Input

- `ContextMemory` (текущая фаза, `domain`, `data_source`, `task_type` и т. п.).
- `RetrievalContext { agent_name, slot_hints }`.

## Output

`EvidencePack` — см. `schemas/agent_outputs.py`.

## Tools

- `retrieval_planner.build(plan)`
- `vector_db.search(filters, query, top_k)`
- `evidence_assembler.compact(hits)`

## RAG Policy

Зависит от вызывающего агента и фазы. Базовый шаблон:

```yaml
phase: current.phase
doc_type:
  - <выбирается по запрашивающему агенту>
domain: current.domain
data_source: current.data_source
task_type: current.task_type
top_k: 5
similarity_threshold: 0.7
```

Конкретные политики — в [../06-rag/retrieval-policies.md](../06-rag/retrieval-policies.md).

## Hard Rules

- Сам ничего не «думает» — не вызывает LLM для дополнения ответов.
- Не возвращать сырые карточки целиком; компактовать в `EvidencePack`.
- Если 0 hits — выставить `need_more_context=true` и пометить `policy_drift_candidates` для analytics.

## Failure Modes

- Vector DB недоступна → retry с backoff; затем структурированная ошибка `vector_db_unavailable`.
- Эталонный similarity_threshold не дал hits → ослабить фильтры по `data_source`/`task_type` (по политике агента), но не по `domain`.
