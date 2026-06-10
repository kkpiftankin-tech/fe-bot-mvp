# RUNTIME-05. Domain Context

## Назначение

Заякорить диалог на правильный срез базы знаний: извлечь карточки `domain_profile`, `analytics`, `feature_pattern`, релевантные `domain` × `data_source` × `task_type`, и выудить у пользователя `critical_factors`, `interpretability_requirement` и любые доменные ограничения.

## Бизнес-ценность

Синтез признаков, опирающийся на доменный evidence, остаётся физически осмысленным. Без этой фазы у LLM на руках только имена полей, и она быстро дрейфует в безосновательную математику.

## Пользовательский сценарий

Для radar-примера агент поднимает naval-radar domain profile и предлагает:

```yaml
critical_factors: [range, rcs, snr, doppler, radar_performance_factor, jamming_level]
interpretability_requirement: high
domain_constraints:
  - "features should be physically interpretable"
  - "avoid black-box transformations without explanation"
```

Пользователь может принять, отредактировать или расширить любой блок.

## Связанные требования

- BR-FR-070..072 (выявление доменного контекста, извлечение critical-факторов, уровень интерпретируемости).
- При `interpretability_requirement = high` система ОБЯЗАНА предпочитать семейства признаков с физическим смыслом и модели с поддержкой feature-importance / explainability.

## Связанные агенты

- `DomainContextAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `DomainContext` (`schemas/agent_outputs.py`).
- Слоты `ContextMemory`: `critical_factors`, `interpretability_requirement`, `domain_constraints`, `temporal_importance`.

## Связанные RAG-документы

- Карточки `domain_profile`, `analytics_card`, `validation_rule` для активного `domain` + `data_source`.

## Критерии приёмки

- При отсутствии релевантного `domain_profile` система ОБЯЗАНА выставить `need_more_context=true` и попросить пользователя уточнить, не изобретая факторы.
- `interpretability_requirement` ОБЯЗАН быть одним из `high | medium | low`.
- Тест: `tests/component/test_domain_context_agent.py`.
