# Agent → Contract (карта)

Для каждого агента из [AGENTS.md](../../AGENTS.md) эта таблица отслеживает цепочку артефактов, которые должны существовать, чтобы агент считался реализованным.

## Схема

| Agent | Spec | Schema | Prompt | Validator | Component Test | Status |
| --- | --- | --- | --- | --- | --- | --- |
| SessionAgent | docs/05-agents/session-agent.md | schemas/agent_outputs.py | prompts/session_agent.md | — | tests/component/test_session_agent.py | planned |
| NLUAgent | docs/05-agents/nlu-agent.md | schemas/agent_outputs.py | prompts/nlu_agent.md | — | tests/component/test_nlu_agent.py | planned |
| RAGRetrievalAgent | docs/05-agents/rag-retrieval-agent.md | schemas/agent_outputs.py | prompts/rag_retrieval_agent.md | validators/rag_metadata_validator.py | tests/component/test_rag_retrieval_agent.py | planned |
| DialogueOrchestratorAgent | docs/05-agents/dialogue-orchestrator-agent.md | schemas/agent_outputs.py | prompts/dialogue_orchestrator_agent.md | — | tests/component/test_dialogue_orchestrator_agent.py | planned |
| ContextMemoryAgent | docs/05-agents/context-memory-agent.md | schemas/context_memory.py | — | validators/context_validator.py | tests/component/test_context_memory_agent.py | planned |
| TaskDiscoveryAgent | docs/05-agents/task-discovery-agent.md | schemas/agent_outputs.py | prompts/task_discovery_agent.md | — | tests/component/test_task_discovery_agent.py | planned |
| DataProfilingAgent | docs/05-agents/data-profiling-agent.md | schemas/agent_outputs.py | prompts/data_profiling_agent.md | validators/context_validator.py | tests/component/test_data_profiling_agent.py | planned |
| DomainContextAgent | docs/05-agents/domain-context-agent.md | schemas/agent_outputs.py | prompts/domain_context_agent.md | — | tests/component/test_domain_context_agent.py | planned |
| FeatureSynthesisAgent | docs/05-agents/feature-synthesis-agent.md | schemas/feature_spec.py | prompts/feature_synthesis_agent.md | validators/feature_validator.py | tests/component/test_feature_synthesis_agent.py | planned |
| FeatureCriticAgent | docs/05-agents/feature-critic-agent.md | schemas/validation_report.py | prompts/feature_critic_agent.md | validators/feature_validator.py | tests/component/test_feature_critic_agent.py | planned |
| MulticollinearityAgent | docs/05-agents/multicollinearity-agent.md | schemas/validation_report.py | — | validators/feature_validator.py | tests/component/test_multicollinearity_agent.py | planned |
| DataGenerationSpecAgent | docs/05-agents/data-generation-spec-agent.md | schemas/generation_spec.py | prompts/generation_spec_agent.md | validators/generation_spec_validator.py | tests/component/test_data_generation_spec_agent.py | planned |
| ModelSelectionAgent | docs/05-agents/model-selection-agent.md | schemas/agent_outputs.py | prompts/model_selection_agent.md | — | tests/component/test_model_selection_agent.py | planned |
| ExportAgent | docs/05-agents/export-agent.md | schemas/export_manifest.py | — | validators/export_manifest_validator.py | tests/component/test_export_agent.py | planned |
| FeedbackAgent | docs/05-agents/feedback-agent.md | schemas/agent_outputs.py | prompts/feedback_agent.md | — | tests/component/test_feedback_agent.py | planned |
| AuditAgent | docs/05-agents/audit-agent.md | schemas/audit.py | — | — | tests/component/test_audit_agent.py | planned |

## Значения статусов

- `planned` — строка есть, файлов нет.
- `spec-only` — spec агента написан, schema или код не созданы.
- `wired` — spec + schema + prompt + (validator если применимо).
- `tested` — component-тест проходит.
- `production` — также покрыт integration + e2e тестами.

## Правила

- Новая запись в [AGENTS.md](../../AGENTS.md) требует строку здесь.
- Удаление агента требует удаления строки здесь в том же изменении.
- `Status` — источник истины для «готов ли этот агент к разводке в LangGraph».
