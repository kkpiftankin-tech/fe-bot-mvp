# DomainContextAgent

## Purpose

Установить `critical_factors`, `interpretability_requirement`, `domain_constraints` на основе RAG-карточек домена и подтверждения пользователя.

## Phase

`PHASE_3_DOMAIN_CONTEXT`

## Input

- `ContextMemory` (`domain`, `data_source`, `task_type`).
- `EvidencePack` с `domain_profile`-карточками и `analytics_card`-ами.

## Output

`DomainContext` — см. `schemas/agent_outputs.py`.

## Tools

- `domain_profile.critical_factors_extract(...)`.
- `interpretability.recommend(domain, deployment_context)`.

## RAG Policy

```yaml
phase: domain_context
doc_type:
  - domain_profile
  - analytics_card
  - validation_rule_card
domain: current.domain
data_source: current.data_source
top_k: 5
```

## Hard Rules

- Без подходящих `domain_profile`-карточек обязан вернуть `need_more_context=true`, а не выдумывать factors.
- `interpretability_requirement` ∈ `{high, medium, low}`.
- Пользователь может расширить / отредактировать factors; финальный набор фиксируется только после явного подтверждения.

## Failure Modes

- 0 domain-карточек → блок-вопрос «опишите домен в 1–2 предложениях» + предложить запуск Setup для добавления карточек.
