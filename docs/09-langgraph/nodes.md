# Узлы графа

Каждый узел — обёртка над агентом или Python-worker-ом.

| Имя узла | Класс-исполнитель | Фаза | Что пишет в ContextMemory |
| --- | --- | --- | --- |
| `session_start` | `SessionAgent` | initialization | `conversation_id`, `kb_version`, `current_phase`, `started_at` |
| `nlu` | `NLUAgent` | all | `parsed_user_input` (transient) |
| `rag_retrieve` | `RAGRetrievalAgent` | all | `evidence_pack` (transient) |
| `task_discovery` | `TaskDiscoveryAgent` | task_discovery | `task_type`, `target_variable`, `classes`, `domain`, `data_source`, `required_latency`, `deployment_context` |
| `data_profiling` | `DataProfilingAgent` | data_profiling | `data_type`, `data_volume`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance` |
| `domain_context` | `DomainContextAgent` | domain_context | `critical_factors`, `interpretability_requirement`, `domain_constraints` |
| `feature_synthesis` | `FeatureSynthesisAgent` | feature_synthesis | `base_features`, `derived_features`, `interaction_features` |
| `feature_critic` | `FeatureCriticAgent` | feature_synthesis | `validation_reports[+]` |
| `multicollinearity` | `MulticollinearityAgent` | feature_synthesis | `validation_reports[+]` |
| `feature_review` | Human Review Controller | feature_synthesis | `final_features`, `user_feedback[+]` |
| `generation_spec` | `DataGenerationSpecAgent` | data_generation | `generation_spec` |
| `data_generation` | `DataGenerationWorker` | data_generation | `generated_dataset` |
| `data_validation` | `ValidationWorker` (generated_data_validator) | data_generation | `validation_reports[+]` |
| `model_selection` | `ModelSelectionAgent` | model_selection | `recommended_model`, `model_ranking`, `training_config` |
| `model_review` | Human action | model_selection | `selected_model`, `override_reason` |
| `export` | `ExportAgent` | export | `artifacts`, `export_manifest` |

Узлы `nlu` и `rag_retrieve` запускаются на каждый user-turn вне зависимости от фазы.

## Связанные документы

- [graph-overview.md](graph-overview.md)
- [edges.md](edges.md)
- [../05-agents/](../05-agents/)
