# ANALYTICS-09. Сквозной audit trail

## Назначение

Сделать каждое решение системы трассируемым: исходный документ → parsed-секция → RAG-карточка → чанк → evidence pack → агентный вывод → признак / модель → экспортированный артефакт. Один экран, один запрос.

## Бизнес-ценность

Audit-трассируемость — это то, что позволяет доменному SME объяснить, *почему* модель рекомендует `XGBoost` для этого контакта: цепочка обратно до оригинального PDF сохранена. Без неё система — чёрный ящик, как бы прозрачен ни был каждый отдельный агент.

## Вход и выход

- **Вход.** События и ссылки Setup и Runtime: документы, секции, карточки, чанки, evidence packs, выводы агентов, признаки, модели, артефакты.
- **Выход.** Append-only цепочка «исходный документ → … → экспортированный артефакт» на одном экране; экспорт в JSON для compliance-ревью.

## Пользовательский сценарий

Аудитор выбирает признак в экспортированном пакете и кликает **Trace origin**. Система рендерит линейный timeline: PDF пользователя (стр. 7) → parsed-секция → `feature_pattern.signal_quality.v1` (с `confidence_level`) → чанк `feature_pattern.signal_quality.v1.formula` → evidence pack, отданный `FeatureSynthesisAgent`-у на шаге 12 → эмитированный `FeatureCandidate` → валидатор прошёл → действие пользователя `confirm` → `final_features` → `features.json` → `archive.zip` скачан в 2026-05-18T14:33:00Z.

## Связанные требования

- BR-FR-Audit-001..004 (привязка source ↔ artifact, неизменяемый timeline, скачиваемая trace).
- NFR-Audit-001 (каждое изменение state логируется).

## Связанные сервисы

- Audit Service, Traceability Service, ContextMemory Service, RAG Card Registry, Conversation DB, Artifact Storage, Frontend Audit UI.

## Связанные контракты

- `AuditChain` (`schemas/audit.py`): упорядоченный список `AuditNode { kind, entity_id, parent_id, occurred_at, payload_digest }`.

## Критерии приёмки

- Для любого экспортированного артефакта trace ОБЯЗАН доходить как минимум до одного `source_document_id`.
- Audit-timeline ОБЯЗАН быть append-only; редактирование требует документированного override.
- Цепочка ОБЯЗАНА быть экспортируемой как JSON для compliance-ревью.
- Тест: `tests/e2e/test_audit_trail.py`.
