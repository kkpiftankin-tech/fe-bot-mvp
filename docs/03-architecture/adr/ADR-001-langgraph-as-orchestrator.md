# ADR-001. LangGraph как Runtime-оркестратор

## Status

Accepted

## Context

Runtime-стадия проходит 8 фаз и обязана поддерживать: условные переходы, repair-loops при сбое валидации, human-in-the-loop, persistence промежуточного состояния и явное тестирование переходов в изоляции.

Альтернативы:

1. **Простой Python state machine на switch/if-цепочках.** Дёшево на старте, но плохо тестируется, плохо описывается визуально, repair-loops и HITL приходится изобретать заново.
2. **Workflow-движок общего назначения (Temporal, Prefect).** Мощно, но overkill: тяжёлая инфраструктура, не интегрировано с LLM-стеком, ускоренный TTL знаний в команде маленький.
3. **Голая цепочка вызовов LLM (одного «большого» промпта на всю задачу).** Невозможно для маленькой модели (`llama3.2`): теряет контекст, путается между фазами.
4. **LangGraph.** Заточен под мультиагентные потоки с typed state, поддерживает checkpointing, repair-loops, conditional routing, interrupts для HITL.

## Decision

Использовать LangGraph `StateGraph` как основной runtime-оркестратор, с `ContextMemory` как типизированным состоянием.

## Consequences

- Положительные:
  - Все агенты работают через единый `ContextMemory`-контракт.
  - Переходы между фазами явно описаны и тестируются изолированно (`tests/integration/test_langgraph_state_machine.py`).
  - Repair-loops с `max_retries` встроены в граф, а не разбросаны по коду.
  - HITL реализуется через interrupt-points, видимые в графе.
  - Persistence checkpoints — встроенная фича.
- Отрицательные:
  - Зависимость от стороннего пакета и его roadmap.
  - Для setup-стадии LangGraph не используется (там простой sequential — см. [c4-component-setup-orchestrator.md](../c4-component-setup-orchestrator.md)) — это создаёт две разных state-machine-парадигмы в одном репозитории.
- Нейтральные:
  - Гранулярность узла = один агент, что совпадает с реестром в [AGENTS.md](../../../AGENTS.md).

## Related

- [../c4-container.md](../c4-container.md)
- [../c4-component-agent-runtime.md](../c4-component-agent-runtime.md)
- [../../09-langgraph/state-machine.md](../../09-langgraph/state-machine.md)
