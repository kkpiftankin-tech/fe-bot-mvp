# Типы документов

Каждое значение `doc_type` имеет фиксированное назначение и фиксированный набор слотов в чанках.

| doc_type | Назначение | Куда складывается |
| --- | --- | --- |
| `ontology_card` | Описание концепций онтологии (domains, task_types, feature_families, ...) | `rag/cards/ontology/` |
| `domain_profile` | Доменный профиль: ключевые факторы, окружение, ограничения | `rag/cards/domain_profiles/` |
| `schema_card` | Канонические поля данных + dtype + единицы | `rag/cards/schema_cards/` |
| `field_definition_card` | Подробное описание **одного** поля: canonical name, synonyms, allowed ranges, validation rules | `rag/cards/field_definitions/` |
| `task_card` | Описание ML-задачи (target, классы, метрики) | `rag/cards/task_cards/` |
| `feature_pattern_card` | Шаблон признака (формула, входы, evidence) | `rag/cards/feature_patterns/` |
| `analytics_card` | Готовый аналитический показатель из feature-store | `rag/cards/analytics_cards/` |
| `validation_rule_card` | Деталь правила валидации (формат, ограничения) | `rag/cards/validation_rules/` |
| `question_template_card` | Шаблон уточняющего вопроса per-missing-slot | `rag/cards/question_templates/` |
| `model_recommendation_card` | Рекомендация модели для класса задач (XGBoost / Bayesian / CNN / LSTM / ...) | `rag/cards/model_recommendations/` |
| `glossary_term` | Термин + синонимы + нормализованное имя | `rag/cards/glossary/` |
| `example_card` | Положительный пример (как делать правильно) | `rag/cards/examples/` |
| `bad_example_card` | Отрицательный пример (как НЕ делать) | `rag/cards/examples/bad/` |

## Кто читает какой тип

| doc_type | Главные потребители |
| --- | --- |
| `ontology_card` | `RAGRetrievalAgent`, `MetadataValidator`, `RAGCardGenerator` |
| `domain_profile` | `TaskDiscoveryAgent`, `DomainContextAgent` |
| `schema_card` | `DataProfilingAgent`, `FeatureSynthesisAgent`, `FeatureCriticAgent`, `DataGenerationSpecAgent` |
| `field_definition_card` | `DataProfilingAgent`, `FeatureSynthesisAgent`, `FeatureCriticAgent` |
| `task_card` | `TaskDiscoveryAgent`, `ModelSelectionAgent` |
| `feature_pattern_card` | `FeatureSynthesisAgent`, `DataGenerationSpecAgent` |
| `analytics_card` | `DomainContextAgent`, `FeatureSynthesisAgent`, `DataGenerationSpecAgent`, `ANALYTICS-08` dashboards |
| `validation_rule_card` | `FeatureCriticAgent`, `validators/` |
| `question_template_card` | `NLUAgent`, `DataProfilingAgent`, `DomainContextAgent` |
| `model_recommendation_card` | `ModelSelectionAgent` |
| `glossary_term` | `NLUAgent`, `DataProfilingAgent` |
| `example_card` / `bad_example_card` | `tests/prompt_eval/`, обучение людей |

## Минимальный объём для MVP

Из бизнес-требований ([docs/01-business/](../01-business/) + `Бизнес.md` §13.3):

- ≥ 3–5 `domain_profile`-карточек.
- ≥ 5–10 `schema_card`-ов на data_source.
- ≥ 20 `field_definition_card` (на критичные поля).
- ≥ 50–100 `feature_pattern_card`.
- ≥ 20–30 `analytics_card`.
- ≥ 10 `model_recommendation_card`.
- ≥ 50 `glossary_term`.
- ≥ 20 `question_template_card`.
- ≥ 10 `validation_rule_card`.

## Жизненный цикл

Все карточки проходят через закрытый набор статусов (`draft → generated → metadata_validated → review_required → approved → chunked → embedded → indexed → published → deprecated`). Полное описание переходов и правил deprecation — в [rag-lifecycle.md](rag-lifecycle.md). Кто подтверждает каждый тип карточки перед `approved` — там же в секции «Review policy».

## Связанные документы

- [ontology.md](ontology.md)
- [metadata-schema.md](metadata-schema.md)
- [chunk-schema.md](chunk-schema.md)
- [rag-lifecycle.md](rag-lifecycle.md)
