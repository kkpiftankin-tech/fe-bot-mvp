# Доменная модель: иерархическая таксономия классификации

См. также: [feature SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md).

> **Legacy.** Модель ниже (bitmap, `TaxonomyVersion`, `ClassificationState`) замещена деревом классификаторов SETUP-13 ([ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)): `ClassifierNode`, `ClassifierTree`, `FragmentClassificationResult` — см. [SETUP-13 §4](../02-system/features/SETUP-13-classifier-library.md#4-связанные-контракты). Целевые сущности `ClassifierMetadataHints` и `ResolvedMetadataHints` — [SETUP-13 §8](../02-system/features/SETUP-13-classifier-library.md#8-metadata-хинты-узлов), [ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md).

## Сущности

### TaxonomyVersion

Snapshot реестра на момент времени. Идентифицируется semver
(`v1.0.0`). Активная — одна в каждый момент.

Поля:
- `version_id : VARCHAR(32)` — semver.
- `created_at : timestamp`.
- `description : text`.
- `is_active : bool`.

Жизненный цикл:
- `draft` (загрузка seed-YAML, ещё не активирован) →
- `active` (текущий рабочий) →
- `frozen` (заменён следующей активной версией).

### TaxonomyBitRegistryEntry (Node)

Один слот в bit-registry — соответствует одному классу одного
уровня под одним `parent_path`. Identity:
`(version_id, level, parent_path, bit_index)`.

Уникален также `(version_id, level, parent_path, class_slug)`.

Поля:
- identity (см. выше)
- `class_slug : VARCHAR(64)` — stable kebab-case.
- `display_name_ru`, `display_name_en`, `description`.
- `status : enum(active, deprecated_merged)`.
- `merged_into_slug : VARCHAR(64) | NULL`.
- `auto_created : bool`.
- `created_at`, `created_by_section`.
- `usage_count : int`.
- `doc_type_hint : VARCHAR(32) | NULL`.
- `embedding : VECTOR(384)`.

### ClassificationState (Value Object)

Значение, прикрепляемое к ParsedSection (а через неё — к RAGCard).
Описывает результат классификации в bitmap-форме.

Поля:
- `classification_bitmap : uint32` (30 эффективных бит).
- `primary_l0_idx : int | None`.
- `primary_l1_idx : int | None`.
- `unknown_at_level : int | None`.
- `confidence_per_level : (float, float, float)`.
- `confidence_per_bit : dict[str, float]` (key = `"<level>:<bit>"`).
- `taxonomy_version_id : VARCHAR(32)`.
- `classification_method : VARCHAR(32)`.
- `auto_created_bits : list[AutoCreationRecord]`.
- `llm_trace_ids : list[str]`.

### AutoCreationRecord (Value Object)

Запись о бит-allocation'е через auto-allocator.

Поля:
- `level`, `parent_path`, `bit_index`, `class_slug`.
- `triggered_by_section_id`.
- `similarity_to_closest`, `closest_existing_slug`.
- `created_at`.

### Decision (ADT)

Результат LLM-вызова на одном уровне:
- `EXISTING(selected : list[ExistingSelection], overall_confidence, reason)`.
- `NEW(proposal : NewClassProposal, overall_confidence, reason)`.
- `UNKNOWN(reason, overall_confidence)`.

## Инварианты

1. **Bitmap range**: `classification_bitmap & ~BIT_MASK_ALL == 0`.
2. **Primary consistency**: если `primary_l0_idx is not None`, то
   соответствующий бит установлен. Аналогично для L1.
3. **Cascading unknown**: если `unknown_at_level = k`, то биты
   уровней ≥ k обнулены и primary'и этих уровней = None.
4. **Version constancy**: расшифровка bitmap'а валидна только в
   рамках своей `taxonomy_version_id` (биты могут переезжать между
   major-версиями).
5. **Slug uniqueness**: внутри `(version_id, level, parent_path)`
   все `class_slug` уникальны.
6. **Bit position uniqueness**: внутри `(version_id, level,
   parent_path)` все `bit_index` уникальны.
7. **Active version uniqueness**: ровно одна `TaxonomyVersion`
   имеет `is_active = true`.

## Aggregate roots

- **TaxonomyRegistry** — корень для всех записей реестра версии.
- **ParsedSection** — корень для `ClassificationState`
  (transient, материализуется в bridge `section_class_tags`).

## Identity & equality

- `TaxonomyBitRegistryEntry` равны, если совпадает идентификатор
  `(version_id, level, parent_path, bit_index)`.
- `ClassificationState` равны, если совпадает весь bitmap + всё
  meta (это transient value, equality для тестов).

## Связь с другими доменами

- `ParsedSection.classification_state` ⊆ taxonomy aggregate.
- `RAGCard.front_matter.taxonomy_path` ⊆ derive из
  ClassificationState.
- `RetrievalRequest.taxonomy_filter` ⊆ derive из ClassificationState.
