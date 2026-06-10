# Переходы (edges)

## Безусловные

```text
START → session_start → nlu (на каждом turn-е)
nlu → rag_retrieve → route_by_phase
session_start → (one-shot init) → task_discovery
```

## Условные

```text
route_by_phase
  ├─ current_phase=task_discovery   → task_discovery
  ├─ current_phase=data_profiling   → data_profiling
  ├─ current_phase=domain_context   → domain_context
  ├─ current_phase=feature_synthesis → feature_synthesis
  ├─ current_phase=data_generation  → generation_spec
  ├─ current_phase=model_selection  → model_selection
  └─ current_phase=export           → export

task_discovery → (completion=true) → data_profiling
data_profiling → (completion=true) → domain_context
domain_context → (completion=true) → feature_synthesis

feature_synthesis → feature_critic → multicollinearity → feature_review
feature_critic → (decision=failed AND retries<max) → feature_synthesis (repair)
feature_critic → (decision=failed AND retries=max) → END_PHASE_FAILED
feature_review → (decision=confirm) → generation_spec
feature_review → (decision=rollback) → data_profiling (откат)

generation_spec → data_generation → data_validation
data_validation → (passed=false AND retries<max) → generation_spec (repair)
data_validation → (passed=true) → model_selection

model_selection → model_review → (decision=accept|override) → export

export → (success) → DONE
export → (failed) → END_PHASE_FAILED
```

## Глобальные интенты

- `intent=restart` → `session_start.restart`: создаёт новый `conversation_id`, прежний остаётся в audit.
- `intent=clarify_feature` в фазе `feature_synthesis` → mini-loop в `feature_synthesis` без отката фазы.

## Связанные документы

- [state-machine.md](state-machine.md)
- [repair-loops.md](repair-loops.md)
- [human-in-the-loop.md](human-in-the-loop.md)
