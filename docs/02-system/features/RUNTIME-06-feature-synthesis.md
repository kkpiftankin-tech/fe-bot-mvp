# RUNTIME-06. Feature Synthesis

## Назначение

Сгенерировать кандидатный набор признаков, разбитый на `base_features`, `derived_features` и `interaction_features`, у каждого — name, role, dtype, description, formula (где применимо), `input_features` и `evidence_doc_ids`.

## Бизнес-ценность

Это заголовочная фича платформы: превратить data-профиль + доменный контекст в защитимый, объяснимый каталог признаков, который пользователь может «отгрузить».

## Пользовательский сценарий

Для эталонного radar-сценария агент эмитит 19 признаков:

- **6 базовых**: `range, azimuth, elevation, rcs, snr, doppler`.
- **8 производных**: `signal_quality`, `rcs_normalized`, `distance_class`, `elevation_category`, `maneuver_index`, `threat_range` и ещё два.
- **5 interaction**: `range_x_snr`, `rcs_x_snr`, `doppler_x_elevation`, `range_x_azimuth`, `rcs_x_range`.

У каждого — `evidence_doc_ids`, `input_features` и однострочное `description`. Пользователь ревьюит их в [RUNTIME-08](RUNTIME-08-feature-review.md).

## Связанные требования

- BR-FR-080..083 (base, derived, interaction; документирование признака).
- Каждый `approved`-признак ОБЯЗАН цитировать непустые `evidence_doc_ids`.
- Временные признаки (например, `range_rate`) НЕ ОБЯЗАНЫ предлагаться, когда `temporal_importance = false`.
- Производные признаки ОБЯЗАНЫ ссылаться только на `input_features`, существующие в `ContextMemory.fields` или среди ранее принятых.

## Связанные агенты

- `FeatureSynthesisAgent`, `RAGRetrievalAgent`.

## Связанные контракты

- `FeatureCandidate`, `FeatureCandidateSet` (`schemas/agent_outputs.py`).
- `FeatureSpec` (`schemas/feature_spec.py`) — см. [../../07-contracts/feature-spec.md](../../07-contracts/feature-spec.md).

## Связанные RAG-документы

- Карточки `feature_pattern`, `analytics_card`, `schema_card`, `glossary`, отфильтрованные по текущим `domain` × `data_source` × `task_type`.

## Критерии приёмки

- Счётчики признаков: целевое 6 базовых / 8 производных / 5 interaction для radar-референса; настраивается через `MAX_FEATURES` и `MAX_INTERACTIONS`.
- Признак, чья формула не парсится `validators/feature_validator.py`, ОБЯЗАН быть отвергнут до попадания пользователю.
- Тесты: `tests/component/test_feature_synthesis_agent.py`, `tests/prompt_eval/feature_synthesis_agent_cases.yaml`.
