# RAG-методология: иерархическая таксономия классификации

> **Legacy (SETUP-12).** Этот документ описывает 3-уровневую bitmap-таксономию, замещённую деревом классификаторов [SETUP-13](../02-system/features/SETUP-13-classifier-library.md) ([ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)). Раздел «Генерация карточек (SETUP-05)» ниже (`DocTypeDetector` читает `doc_type_hint` реестра, иерархические шаблоны промптов по `taxonomy_path`) в текущем пайплайне не действует. Как результат классификации по дереву превращается в metadata карточки и чанков — в [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md), [SETUP-13 §8](../02-system/features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов) и [metadata-schema.md §6.5](metadata-schema.md). Идея `doc_type_hint` на узле перенесена в SETUP-13 и расширена до всех онтологических полей.

См. также:
- [feature SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md)
- [метадата-схема карточек](metadata-schema.md)
- [retrieval-политики](rag-methodology.md)
- [card-lifecycle](card-lifecycle.md)

## Mental model

В отличие от плоского enum'а `SectionType` (SETUP-04), RAG-карточки
дальше живут в **иерархической** classification-системе с тремя
уровнями (L0, L1, L2). Каждый уровень — codebook ≤10 классов:

- L0 — корневая категория (task, schema, analytics, …). Общая.
- L1 — подкласс под конкретным L0 (task → pvo, navigation, …).
- L2 — sub-subclass под (L0, L1) (task.pvo → tracking, threat_assessment, …).

## Влияние на RAG-pipeline

### Парсинг (SETUP-04)

Section получает `ClassificationState` вместо плоского `section_type`.
Старый enum доступен derived-property для backward-compat.

### Генерация карточек (SETUP-05)

`DocTypeDetector`:
- Читает `classification_state.primary_l0_idx` → lookup
  `doc_type_hint` в registry. Это primary-источник `doc_type` карточки.
- Если на primary L0 `doc_type_hint = NULL`, fallback вверх по path
  не нужен (L0 — корень). Если null на конкретной registry-entry —
  карточка не генерируется (INVALID_DOC_TYPE).

`PromptTemplateRegistry`:
- Ищет template по `taxonomy_path`:
  - `task.pvo.tracking` → `prompts/rag_card/task/pvo/tracking.txt`
  - fallback: `task/pvo.txt` → `task.txt` → `default.txt`.
- Промпт получает path в `PromptContext.section.taxonomy_path`.

Карточка несёт в `front_matter`:
- `taxonomy_node_id` — slug primary L0 (для совместимости).
- `taxonomy_path` — list[str] от L0 до depth_reached.
- `taxonomy_version_id` — для корректной расшифровки.
- `classification_bitmap` — для дешёвых retrieval-фильтров без
  обращения в registry.

### Chunking (SETUP-08)

Chunks наследуют `taxonomy_path` родительской карточки. При chunking-
стратегии «split by section», границы chunks могут учитывать L1/L2
hierarchy для лучшей семантической когеренции.

### Indexing (SETUP-09)

Qdrant payload получает:
- `bitmap_l0 : int`, `bitmap_l1 : int`, `bitmap_l2 : int`
- `primary_l0 : str`, `primary_l1 : str`
- `taxonomy_version : str`
- `taxonomy_path : list[str]`

### Retrieval (SETUP-10 + Runtime)

См. [ADR-HTC-07](../03-architecture/adr/ADR-HTC-07-bitwise-retrieval-filters.md).

Поддерживаемые фильтры:

```
# task на L0 (включая multi-tag)
filter: bitmap_l0 & 1 != 0

# task.pvo
filter: primary_l0 == "task" AND bitmap_l1 & 1 != 0

# task.pvo.tracking
filter: primary_l0 == "task" AND primary_l1 == "pvo" AND bitmap_l2 & 1 != 0

# глобально ПВО (на L1, любого parent_path)
filter: section_class_tags WHERE level=1 AND class_slug='pvo'

# OR-сочетания
filter: bitmap_l0 & (1 | 4) != 0   # task OR analytics
```

### Runtime-агенты

Каждый агент может объявить `taxonomy_focus` — список путей, на
которых он специализируется. Retrieval-фильтр сужается:

```python
class FeatureSynthesisAgent:
    taxonomy_focus = ["task.*", "schema.*"]
    # → запрос только в области задач и схем
```

Это даёт первое осмысленное доменное сужение в Runtime, до
полного evidence-pack'а.

## Governance

- Auto-allocation: см. [ADR-HTC-04](../03-architecture/adr/ADR-HTC-04-automatic-allocation.md).
- Cascading-unknown: см. [ADR-HTC-06](../03-architecture/adr/ADR-HTC-06-cascading-unknown.md).
- Без human review в MVP ([TD-HTC-002](../tech-debt/TD-HTC-002-taxonomy-admin-ui.md)).

## Failure modes (расширение [rag-failure-modes](rag-failure-modes.md))

| Mode | Симптом | Поведение |
|---|---|---|
| L0 UNKNOWN | bitmap = 0, unknown_at_level = 0 | Карточка не генерируется |
| L1 UNKNOWN | bitmap содержит только L0, unknown_at_level = 1 | Карточка с `taxonomy_path = [L0]` |
| Class overflow | новый класс склеен force-merge | Карточка получает приклеенный slug; alert в метриках |
| Inconsistent version_id | Section/RAGCard ссылаются на отсутствующую version | Read-error в retrieval; нужно либо мигрировать секцию, либо вернуть version из archive |
