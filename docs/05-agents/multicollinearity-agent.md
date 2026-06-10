# MulticollinearityAgent

## Purpose

Обнаружить пары / группы признаков с высокой коррелированностью (`|ρ| ≥ MULTICOLLINEARITY_THRESHOLD`) или высоким VIF и эмитить `MulticollinearityReport` с рекомендациями.

## Phase

`PHASE_4_FEATURE_SYNTHESIS`

## Input

- `FeatureCandidateSet` (после прохождения FeatureCriticAgent).
- `GenerationSpec.samples_preview` (мини-сэмпл synthetic data) — если уже есть; иначе — теоретические распределения.

## Output

`MulticollinearityReport { pairs: list[CorrelatedPair], vif: dict[name, value], recommendations: list[str] }`.

## Tools

- `numpy.corrcoef` для попарных коэффициентов.
- `statsmodels.outliers_influence.variance_inflation_factor` для VIF.

## RAG Policy

Не использует RAG.

## Hard Rules

- Не сам решает, что отбрасывать; эмитит `recommendations` для UI / FeatureCriticAgent.
- Пара с `|ρ| ≥ 0.95` обязана быть помечена `severity=high`.
- VIF ≥ 10 → `severity=high`; 5 ≤ VIF < 10 → `severity=medium`.

## Failure Modes

- Если synthetic preview ещё не доступен, использует теоретическую `corr matrix` из распределений; помечает результат `confidence_level=medium`.
- Численная неустойчивость (singular matrix) → возвращает `vif=null` для затронутых, продолжает с парных корреляций.
