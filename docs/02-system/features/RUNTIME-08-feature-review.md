# RUNTIME-08. Human review признаков

## Назначение

HITL-гейт перед генерацией данных. Пользователь видит финальный кандидатный набор (после [RUNTIME-07](RUNTIME-07-feature-validation.md)) и явно подтверждает, редактирует или откатывает к data profiling.

## Бизнес-ценность

Даже при детерминированной валидации последняя инстанция, решающая, какие признаки уйдут «в работу», — пользователь. Без этого гейта система молча генерировала бы датасеты и pipeline-ы на признаках, которых пользователь не видел — это убивает доверие и воспроизводимость.

## Вход и выход

- **Вход.** Валидированный набор признаков и решение пользователя: **Confirm**, правка или откат к Data Profiling.
- **Выход.** `FeatureReviewDecision` (`decision`, `added`, `removed`, `notes`, `decided_by`, `decided_at`) и зафиксированные `final_features`; без **Confirm** переход к генерации данных невозможен.

## Пользовательский сценарий

1. Пользователь открывает Feature Approval-панель.
2. Видит полный набор признаков с разделением по роли (base / derived / interaction), с формулой, исходными полями, evidence-ссылками и status валидатора.
3. Действует: **Confirm**, **Remove feature**, **Add feature** (свободный текст → перезапуск synthesis + validation), **Explain feature**, **Back to Data Profiling** (очистка downstream-признаков).
4. На **Confirm** `ContextMemory.final_features` блокируется до явной инвалидации.

## Связанные требования

- BR-FR-084 (подтверждение пользователем перед data generation).
- BR-FR-032, FR-Conv-006 (пользователь может вернуться к ранней фазе; downstream-слоты инвалидируются).
- NFR-Audit-001 (событие подтверждения логируется с `decided_by`, `decided_at`).

## Связанные сервисы

- Human Review Controller, Frontend Feature Approval UI, ContextMemory Service, LangGraph Orchestrator, Audit Service.

## Связанные контракты

- `FeatureReviewDecision` (`schemas/agent_outputs.py`): `decision` (`confirm | edit | rollback`), `added`, `removed`, `notes`, `decided_by`, `decided_at`.

## Критерии приёмки

- Без явного `confirm` оркестратор ОБЯЗАН отказать в переходе к `data_generation`.
- Действие `edit` ОБЯЗАНО заново прогонять [RUNTIME-07](RUNTIME-07-feature-validation.md) перед повторным показом набора.
- Откат к Data Profiling ОБЯЗАН инвалидировать downstream-слоты: features, generation spec, dataset, model recommendation, export.
- Тест: `tests/component/test_feature_review.py`.
