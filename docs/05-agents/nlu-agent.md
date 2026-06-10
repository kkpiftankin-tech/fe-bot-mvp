# NLUAgent

## Purpose

Распарсить шаг пользователя в типизированный `ParsedUserInput`: intent + entities + confidence + missing_slots.

## Phase

`all` — вызывается каждым шагом пользователя.

## Input

- `UserMessage { text: str }`
- `ContextMemory.current_phase`
- `EvidencePack` со `glossary` и `question_template`-карточками текущей фазы.

## Output

`ParsedUserInput` — см. `schemas/agent_outputs.py`.

## Tools

- `glossary_lookup(term)` — нормализация двуязычных терминов (`РЛС → radar`).
- `regex_intent_match(text)` — быстрая до-LLM проверка по словарю патернов.

## RAG Policy

```yaml
phase: nlu
doc_type:
  - glossary_term
  - question_template_card
domain: current.domain  # если уже известен
data_source: current.data_source  # если уже известен
```

## Hard Rules

- Intent ∈ закрытому набору `{describe_task, describe_data, request_features, clarify_feature, confirm_features, generate_data, recommend_model, export_config, restart}`. Out-of-set → `unknown`.
- При `confidence < 0.7` обязан эмитить `need_more_context=true` с конкретным уточняющим вопросом.
- Не выходить за пределы предоставленного `EvidencePack` — не лезть в RAG напрямую.

## Failure Modes

- Пользовательский текст не парсится → `intent=unknown`, prompt-клик «опишите задачу одним предложением».
- Низкий confidence на отдельной entity → пометить её в `missing_slots`, продолжить с остальными.
