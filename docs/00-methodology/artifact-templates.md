# Шаблоны артефактов

Каркасы документов, которые мы производим. Копируйте, заполняйте, удаляйте комментарии. Шаблоны нормативны — если какой-то раздел кажется ненужным для вашего случая, объясните это **внутри** раздела, а не убирайте его.

---

## Feature (`docs/02-system/features/<ID>-<slug>.md`)

```markdown
# <ID>. <Title>

## Purpose
<Один абзац: какую проблему пользователя решает эта фича.>

## Business Value
<Почему это важно; связать с docs/01-business/goals.md.>

## Related Requirements
- BR-FR-<Area>-<NN>. <Формулировка функционального требования.>

## Related Agents / Services
- <AgentName> или <ServiceName>

## Related Contracts
- <SchemaName> (см. schemas/<file>.py)

## Related RAG Docs
- <doc_type>: <какого вида карточка>

## Acceptance Criteria
- <Наблюдаемый, тестируемый критерий.>

## Source Fragments
- <Опционально: указатели на фрагменты incoming-docs/, мотивировавшие эту фичу.>
```

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
