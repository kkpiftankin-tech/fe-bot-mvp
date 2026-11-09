# Шаблоны артефактов

Каркасы документов, которые мы производим. Копируйте, заполняйте, удаляйте комментарии. Шаблоны нормативны — если какой-то раздел кажется ненужным для вашего случая, объясните это **внутри** раздела, а не убирайте его.

---

## Feature (`docs/02-system/features/<ID>-<slug>.md`)

У фичи две допустимые формы. Короткая — для небольших и сквозных фич (так оформлены `RUNTIME-*`, `ANALYTICS-*`, `PLATFORM-*` и часть `SETUP-*`). Расширенная — для крупных пользовательских фич с UI, API и несколькими сервисами (эталон — [SETUP-01](../02-system/features/SETUP-01-setup-wizard.md)). В обеих формах **обязателен явный раздел про вход и выход фичи**: читателю без контекста должно быть понятно, что фича принимает и что отдаёт.

### Короткая форма

```markdown
# <ID>. <Название>

## Назначение
<Один абзац: какую проблему пользователя решает фича.>

## Бизнес-ценность
<Почему это важно; связать с docs/01-business/goals.md.>

## Вход и выход
- **Вход.** <Что фича принимает: данные от пользователя, артефакты предыдущей фичи, события.>
- **Выход.** <Что фича производит: артефакты, статусы, события. Для кого и где это используется дальше.>

## Пользовательский сценарий
1. <Шаги глазами пользователя.>

## Связанные требования
- BR-FR-<Area>-<NN>. <Формулировка функционального требования.>

## Связанные агенты / сервисы
- <AgentName> или <ServiceName>

## Связанные контракты
- <SchemaName> (см. schemas/<file>.py)

## Связанные RAG-документы
- <doc_type>: <какого вида карточка>

## Критерии приёмки
- <Наблюдаемый, тестируемый критерий.>
- Тест: `tests/<layer>/test_<name>.py`.

## Вне scope
- <Что сознательно не входит.>
```

После создания фичи добавьте строку в [feature-index.md](../02-system/features/feature-index.md), включая колонки «Вход» и «Выход».

### Расширенная форма (23 раздела)

Разделы нумеруются и идут в этом порядке (в конце — «Краткое резюме»):

1. Назначение фичи
2. Контекст и бизнес-цель
3. Термины и определения
4. Границы фичи (in scope / out of scope / ограничения)
5. Пользовательские роли и внешние участники
6. Сервисы и системы-участники
7. Пользовательские сценарии (основной, альтернативные, негативные, постусловия)
8. Диаграмма последовательности: пользователь и внешние участники
9. Диаграмма последовательности: взаимодействие сервисов
10. Frontend Scope
11. Backend Scope
12. Бизнес-правила и ограничения
13. **Входные данные и источники**
14. **Выходные данные и результаты**
15. DTO и модель данных
16. API contracts / event contracts / integration contracts
17. Нефункциональные требования
18. Ошибки и обработка исключений
19. Acceptance Criteria
20. Definition of Done
21. Тесты
22. Риски, допущения и открытые вопросы
23. Связанные документы и артефакты

Разделы 13 и 14 — вход и выход фичи: поля с типом, обязательностью, источником и правилами валидации; примеры ответов; побочные эффекты; результирующее состояние.

---

## Use Case (`docs/02-system/use-cases/UC-FE-XX-<slug>/use-case.md`)

```markdown
# UC-FE-XX. <Title>

## Feature
- <ID> <feature>

## Primary Actor
<Кто инициирует.>

## Supporting Actors
<Другие участники: люди или системы.>

## Preconditions
- <Состояние, в котором должна быть система.>

## Trigger
<Что пользователь напечатал или сделал.>

## Main Flow
1. <Шаг.>

## Alternative Flows
### A1. <название>
<Описание.>

## Postconditions
- <Состояние после успеха.>

## Related Agents
## Related Contracts
```

---

## Спецификация агента (`docs/05-agents/<agent>.md`)

```markdown
# <AgentName>

## Purpose
<Одно предложение.>

## Phase
<PHASE_X_NAME>

## Input
- <ContextMemory.field>
- <Слот EvidencePack>

## Output
<SchemaName> — см. schemas/<file>.py

## Tools
- <tool_name>

## RAG Policy
```yaml
phase: <phase>
doc_type:
  - <type>
domain: current.domain
data_source: current.data_source
```

## Hard Rules
- <Правило.>

## Failure Modes
- <Когда evidence недостаточно → вернуть need_more_context=true с конкретным запросом.>
```

---

## ADR (`docs/03-architecture/adr/ADR-XXX-<slug>.md`)

```markdown
# ADR-XXX. <Decision>

## Status
Proposed | Accepted | Deprecated | Superseded by ADR-YYY

## Context
<Силы, ограничения, альтернативы.>

## Decision
<Что выбрали.>

## Consequences
- Положительные: <…>
- Отрицательные: <…>
- Нейтральные: <…>
```

---

## RAG-карточка (`rag/cards/<family>/<card-id>.yaml`)

```yaml
doc_id: <stable-id>
doc_type: <ontology_card|schema_card|task_card|feature_pattern_card|analytics_card|validation_rule_card|question_template_card|example_card|bad_example_card>
title: <человекочитаемое название>
phase:
  - <phase>
domain:
  - <domain>
data_source:
  - <data_source>
task_type:
  - <task_type>
retrieval_tags:
  - <свободный тег>
confidence_level: high | medium | low
version: <semver>
owner: <команда или человек>

content: |
  <тело карточки в markdown>
```

---

## Задача реализации (`docs/implementation-plan/<plan>.tasks.md`)

```markdown
## T-<AREA>-<NNN>. <Title>

Target:
- <путь к файлу>
- <путь к файлу>

Acceptance:
- <Тестируемый критерий.>
- <Тестируемый критерий.>
```

---

## Запись в runbook (`docs/11-operations/runbook.md`)

```markdown
## Symptom: <Короткое описание>

### Detection
- <Метрика / строка лога / жалоба пользователя>

### Checks
1. <Где смотреть>

### Actions
- <Шаги по митигации>
- <Путь эскалации>
```
