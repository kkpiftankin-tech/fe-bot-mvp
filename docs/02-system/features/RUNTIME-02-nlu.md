# RUNTIME-02. NLU (intent + entities)

## Назначение

Распарсить каждый шаг пользователя в типизированный `ParsedUserInput`: один из закрытого набора intents (`describe_task`, `describe_data`, `request_features`, `clarify_feature`, `confirm_features`, `generate_data`, `recommend_model`, `export_config`, `restart`), словарь entities, оценка confidence и список `missing_slots`.

## Бизнес-ценность

Без типизированных intents оркестратор не может маршрутизировать шаг. С ними вся машинерия фаз становится детерминированной.

## Пользовательский сценарий

Пользователь пишет: *«Нужен классификатор типа морской цели по данным РЛС»*. NLU возвращает:

```json
{
  "intent": "describe_task",
  "confidence": 0.98,
  "entities": {
    "task_type": "classification",
    "domain": "naval",
    "data_source": "radar",
    "target_variable": "target_type"
  },
  "missing_slots": ["classes", "fields"]
}
```

Оркестратор маршрутизирует в `TaskDiscoveryAgent` ([RUNTIME-03](RUNTIME-03-task-discovery.md)).

## Связанные требования

- BR-FR-010..013 (intent classification, entity extraction, confidence scoring, clarity analysis).
- NFR-Qual-001..002 (≥ 85 % intent accuracy, ≥ 80 % entity accuracy).
- NFR-Use-001 (терпимость к русским + английским терминам, например `РЛС/radar`).

## Связанные агенты

- `NLUAgent`, `RAGRetrievalAgent` (нормализация терминов через глоссарные карточки).

## Связанные контракты

- `ParsedUserInput` (`schemas/agent_outputs.py`).

## Связанные RAG-документы

- `glossary`-карточки (нормализация терминов), `question_template`-карточки (когда confidence низкий → какой уточняющий вопрос задать).

## Критерии приёмки

- Out-of-set intent ОБЯЗАН проявиться как `unknown` и триггерить уточняющий вопрос, а не галлюцинированный маршрут.
- `confidence < 0.7` ОБЯЗАН вести к структурированному clarifying prompt, а не к продвижению фазы.
- Тесты: `tests/component/test_nlu_agent.py`, `tests/prompt_eval/nlu_agent_cases.yaml`.
