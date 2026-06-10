# LangGraph: обзор

## Назначение

Описать форму runtime-графа FE-Bot: какие узлы есть, как они связаны, какие условные переходы существуют, какие repair-loops и interrupt-points работают.

## Гранулярность

- Один узел графа ≈ один агент.
- Узел читает и пишет `ContextMemory` (состояние графа).
- Все «бизнес-решения о маршруте» — в conditional edges, не в LLM.

## Высокоуровневый граф

```text
START
  │
  ▼
NLUAgent
  │
  ▼
RAGRetrievalAgent  (готовит EvidencePack под current_phase)
  │
  ▼
route_by_phase
  ├─► TaskDiscoveryAgent       (PHASE_1)
  ├─► DataProfilingAgent       (PHASE_2)
  ├─► DomainContextAgent       (PHASE_3)
  ├─► FeatureSynthesisAgent ──► FeatureCriticAgent
  │                          ──► MulticollinearityAgent
  │                          ──► (repair / human review) (PHASE_4)
  ├─► DataGenerationSpecAgent ──► DataGenerationWorker
  │                            ──► GeneratedDataValidator
  │                            ──► (repair) (PHASE_5)
  ├─► ModelSelectionAgent      (PHASE_6)
  └─► ExportAgent              (PHASE_7)
  │
  ▼
END
```

Каждый узел эмитит `AgentRunRecord` (audit-emitter) и при наличии — `ValidationReport`.

## Связанные документы

- [state-machine.md](state-machine.md)
- [nodes.md](nodes.md)
- [edges.md](edges.md)
- [repair-loops.md](repair-loops.md)
- [human-in-the-loop.md](human-in-the-loop.md)
- [../03-architecture/c4-component-agent-runtime.md](../03-architecture/c4-component-agent-runtime.md)
