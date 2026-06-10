# PLATFORM-03. Контракты структурированных выводов

## Назначение

Каждый произведённый LLM артефакт пересекает Pydantic-границу до потребления ниже по pipeline: `ParsedUserInput`, `TaskDiscoveryResult`, `DataProfile`, `DomainContext`, `FeatureCandidateSet`, `ValidationReport`, `GenerationSpec`, `ModelRecommendation`, `ExportManifest`. Сбои триггерят repair-промпты, которые повторно включают схему и ошибку валидатора.

## Бизнес-ценность

Весь тезис проекта «маленькая LLM работает» держится на этой фиче. Без типизированных контрактов система была бы цепочкой обменов свободным текстом, в которой каждая ошибка усиливает предыдущую.

## Пользовательский сценарий

`FeatureSynthesisAgent` возвращает JSON. Слой контрактов парсит его через `FeatureCandidateSet.model_validate`. На успехе оркестратор продвигается. На сбое слой собирает `RepairRequest` со схемой, нарушающим JSON, путём ошибки и переспрашивает агента. После `max_retries` фаза падает чисто с пользовательской ошибкой.

## Связанные требования

- BR-FR-Sys-001 (каждый агентный вывод валидируется против схемы).
- NFR-Rel-001 (repair loop ограничен `max_retries`).
- Схемы лежат в [../../../schemas/](../../../schemas/); docs — в [../../07-contracts/](../../07-contracts/).

## Связанные сервисы

- Schema Registry, Pydantic Validators, LLM Gateway, Agent Runtime, Validation Service.

## Связанные контракты

- Все Pydantic-модели из `schemas/`.

## Критерии приёмки

- Ни один code-path в `src/fe_bot/` не имеет права потреблять LLM-строку без `model_validate`.
- Несоответствие версии схемы ОБЯЗАНО быть жёсткой ошибкой, а не тихим reformat.
- Тест: `tests/unit/test_structured_output_contracts.py`.
