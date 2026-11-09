# SETUP-13 Traceability — Classifier Library

Документ фиксирует реализованные слайсы SETUP-13 и прослеживает связи
AC → код → тест. Заменяет SETUP-12 для классификации секций документа
(см. [ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)).

## Слайсы

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| S0 | `ClassifierNode`/`ClassifierTree` схемы + import parser + prompt renderer | done |
| S1 | `ClassifierTreeRepository`/`ClassifierTreeService` (CRUD) + permissions | done |
| S2 | REST API (`classifier_router.py`) + DI + snapshot-персистентность | done |
| S3 | Frontend: шаг мастера «Библиотека классификаторов» (дерево + панель редактирования) | done |
| S4 | Промпт: описание узла (`description`) + LLM-черновик описания | done |
| S5 | Промпт: убрана неиспользуемая секция фрагмента из редактируемого текста, few-shot примеры, порядок полей reason→confidence→id | done |
| S6 | `FragmentClassifier` + `ClassifierTreeSectionClassifier` — подключение к `DocumentParserOrchestrator` | done |
| S7 | Frontend: отображение `classifier_result` в «Парсинг документов» (badge + detail drawer) | done |
| S8 | Orchestrator resilience: `CLASSIFICATION_FAILED` вместо необработанного 500 | done |

## Планируемые слайсы: metadata-хинты узлов ([ADR-HTC-10](../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md))

| Слайс | Содержимое | Статус |
| --- | --- | --- |
| S9 | Схемы `ClassifierMetadataHints`, `ResolvedMetadataHints`; поле `ClassifierNode.metadata_hints`; поле `FragmentClassificationResult.resolved_hints` | planned |
| S10 | `ClassifierTreeService.resolve_hints(path)`; валидация хинтов по онтологии при сохранении узла; смена `ClassifierTree.version` при правках | planned |
| S11 | `FragmentClassifier` заполняет `resolved_hints`; API узла принимает/отдаёт хинты и источники | planned |
| S12 | Frontend: редактирование хинтов в `ClassifierNodePanel`, показ унаследованных значений; `resolved_hints` во вкладке «Классификация»; отчёт покрытия | planned |
| S13 | Потребление в SETUP-05 (`ClassificationMetadataResolver`), перевод промптов, `ConfidenceCalculator`, чанкинг — см. [setup-05.md](setup-05.md) и [TD-HTC-004](../tech-debt/TD-HTC-004-duplicate-classification-in-card-generation.md) | planned |

Критерии приёмки AC-H1..H7 — [SETUP-13 §6](../02-system/features/SETUP-13-classifier-library.md#6-критерии-приёмки); тесты — [SETUP-13 §8.7](../02-system/features/SETUP-13-classifier-library.md#87-тесты-планируются). Слайсы S0–S8 ниже реализованы.

## Контракты

| DTO | Файл |
| --- | --- |
| `ClassifierNode` | [schemas/classifier/node.py](../../schemas/classifier/node.py) |
| `ClassifierTree` | [schemas/classifier/tree.py](../../schemas/classifier/tree.py) |
| `ClassifierPathStep` / `FragmentClassificationResult` | [schemas/classifier/classification_result.py](../../schemas/classifier/classification_result.py) |
| `ParsedSection.classifier_result` (+ legacy `classification_state`) | [schemas/setup/parsed_section.py](../../schemas/setup/parsed_section.py) |
| `ParseErrorCode.CLASSIFICATION_FAILED` | [schemas/setup/parse_job.py](../../schemas/setup/parse_job.py) |

## Реализация

| Компонент | Файл |
| --- | --- |
| Slug (транслитерация → ASCII node_id, т.к. id возвращается LLM в JSON) | [src/fe_bot/classifier/slug.py](../../src/fe_bot/classifier/slug.py) |
| Import parser (ASCII-дерево → `ClassifierTree`) | [src/fe_bot/classifier/import_tree.py](../../src/fe_bot/classifier/import_tree.py) |
| Repository / Service (CRUD) | [src/fe_bot/classifier/tree_repository.py](../../src/fe_bot/classifier/tree_repository.py), [tree_service.py](../../src/fe_bot/classifier/tree_service.py) |
| Prompt renderer | [src/fe_bot/classifier/prompt_renderer.py](../../src/fe_bot/classifier/prompt_renderer.py), [prompts/classification/classify_node.txt](../../prompts/classification/classify_node.txt) |
| Описание узла через LLM | [src/fe_bot/classifier/description_generator.py](../../src/fe_bot/classifier/description_generator.py) |
| Многоуровневая классификация фрагмента | [src/fe_bot/classifier/fragment_classifier.py](../../src/fe_bot/classifier/fragment_classifier.py) |
| Адаптер под `DocumentParserOrchestrator` | [src/fe_bot/classifier/section_classifier_adapter.py](../../src/fe_bot/classifier/section_classifier_adapter.py) |
| Orchestrator wiring + resilience | [src/fe_bot/setup/parser/orchestrator.py](../../src/fe_bot/setup/parser/orchestrator.py) |
| API | [src/fe_bot/api/setup/classifier_dto.py](../../src/fe_bot/api/setup/classifier_dto.py), [classifier_router.py](../../src/fe_bot/api/setup/classifier_router.py) |
| DI + factory (`FE_BOT_TAXONOMY_MODE=llm`) + persistence | [src/fe_bot/api/dependencies.py](../../src/fe_bot/api/dependencies.py), [src/fe_bot/persistence/snapshot.py](../../src/fe_bot/persistence/snapshot.py) |
| Permissions | [src/fe_bot/auth/permissions.py](../../src/fe_bot/auth/permissions.py) — `KB_CLASSIFIER_READ`/`KB_CLASSIFIER_WRITE` |
| Frontend API client | [frontend/src/api/classifier.ts](../../frontend/src/api/classifier.ts) |
| Frontend — редактор дерева | [frontend/src/components/Wizard/steps/ClassifierLibraryStep.tsx](../../frontend/src/components/Wizard/steps/ClassifierLibraryStep.tsx), [ClassifierTree.tsx](../../frontend/src/components/Wizard/classifier/ClassifierTree.tsx), [ClassifierNodePanel.tsx](../../frontend/src/components/Wizard/classifier/ClassifierNodePanel.tsx) |
| Frontend — результат в парсинге | [frontend/src/components/Classifier/ClassifierResultBadge.tsx](../../frontend/src/components/Classifier/ClassifierResultBadge.tsx), [frontend/src/components/Wizard/sections/SectionDetailDrawer.tsx](../../frontend/src/components/Wizard/sections/SectionDetailDrawer.tsx) |
| `Makefile` (`FE_BOT_TAXONOMY_MODE ?= llm` по умолчанию для `run-api`) | [Makefile](../../Makefile) |

## Тесты

| Уровень | Файл | Покрытие |
| --- | --- | --- |
| unit | [tests/unit/test_classifier_schemas.py](../../tests/unit/test_classifier_schemas.py) | 11 |
| unit | [tests/unit/test_classifier_slug.py](../../tests/unit/test_classifier_slug.py) | 6 |
| unit | [tests/unit/test_classifier_tree_import.py](../../tests/unit/test_classifier_tree_import.py) | 7 (вкл. реальный seed: 906 узлов, 12→64→336→345→122→27) |
| unit | [tests/unit/test_classifier_prompt_renderer.py](../../tests/unit/test_classifier_prompt_renderer.py) | 12 |
| unit | [tests/unit/test_classifier_classification_result.py](../../tests/unit/test_classifier_classification_result.py) | 4 |
| unit | [tests/unit/test_classifier_description_generator.py](../../tests/unit/test_classifier_description_generator.py) | 3 |
| unit | [tests/unit/test_fragment_classifier.py](../../tests/unit/test_fragment_classifier.py) | 8 |
| component | [tests/component/classifier/test_classifier_tree_service.py](../../tests/component/classifier/test_classifier_tree_service.py) | 16 |
| component | [tests/component/classifier/test_section_classifier_adapter.py](../../tests/component/classifier/test_section_classifier_adapter.py) | 5 |
| integration | [tests/integration/test_classifier_endpoints.py](../../tests/integration/test_classifier_endpoints.py) | 9 — CRUD + RBAC + generate-description |
| integration | [tests/integration/test_taxonomy_wiring.py](../../tests/integration/test_taxonomy_wiring.py) | `TestWiring1ClassifierFactory` — `FE_BOT_TAXONOMY_MODE=llm` строит `ClassifierTreeSectionClassifier` |
| frontend | [frontend/src/components/Wizard/__tests__/ClassifierLibraryStep.test.tsx](../../frontend/src/components/Wizard/__tests__/ClassifierLibraryStep.test.tsx) | 6 |
| frontend | [frontend/src/components/Classifier/__tests__/ClassifierResultBadge.test.tsx](../../frontend/src/components/Classifier/__tests__/ClassifierResultBadge.test.tsx) | 4 |

## Permissions

| Permission | Roles | Endpoints |
| --- | --- | --- |
| `KB_CLASSIFIER_READ` | USER, DOMAIN_EXPERT, RAG_ADMIN, AUDITOR | GET /tree, GET /tree/nodes/{id} |
| `KB_CLASSIFIER_WRITE` | USER, DOMAIN_EXPERT, RAG_ADMIN | POST/PATCH/DELETE /tree/nodes/..., POST .../generate-description |

## Живая проверка (не покрыто автотестами)

- Импорт реального `seed/classifier/asu_v1.txt` → 907 узлов (906 + синтетический корень), корневые id — ASCII (`analitika`, `dannye`, ...).
- CRUD lifecycle (создать/изменить/удалить узел) — против реального дерева через curl.
- Полный цикл: создать setup_job → загрузить документ → распарсить (`FE_BOT_TAXONOMY_MODE=llm`, модель `qwen2.5:7b`) → `ParsedSection.classifier_result` содержит содержательно верный многоуровневый путь (напр. текст про время отклика системы → «Требования → Функциональные требования → Входные операции»).
- Сравнение качества `llama3.2` vs `qwen2.5:7b` на контрастных фрагментах (см. §7 [feature doc](../02-system/features/SETUP-13-classifier-library.md)) — обоснование выбора модели по умолчанию.

## Known limits MVP

- Path-based retrieval-фильтр по новому дереву (аналог `TaxonomyFilter` SETUP-12) не спроектирован — `classifier_result` пока не участвует в retrieval.
- `classifier_result` не читает ни один шаг после парсинга (в том числе генерация карточек): `doc_type` и онтологические поля определяются повторно (`DocTypeDetector`, LLM). Целевое решение — хинты узлов, ADR-HTC-10; расхождение — TD-HTC-004.
- `ClassifierTree.version` не меняется при правках дерева.
- `qwen2.5:7b` заметно медленнее `llama3.2` (~2–3× latency на уровень дерева) — классификация большого документа в `llm`-режиме ощутимо дольше `rule_based`.
- SETUP-12 инфраструктура не удалена (снапшоты со старыми `classification_state` по-прежнему читаются как legacy), но новым кодом не производится.

## Связанные документы

- [SETUP-13 feature spec](../02-system/features/SETUP-13-classifier-library.md)
- [ADR-HTC-09](../03-architecture/adr/ADR-HTC-09-generic-tree-classifier-library.md)
- [SETUP-04 traceability](setup-04.md) (parsing pipeline, куда встроена классификация)
