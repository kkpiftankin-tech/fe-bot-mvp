# SETUP-07. Валидация metadata и онтологии

## Назначение

Детерминированно валидировать, что у каждой RAG-карточки есть обязательная metadata, её значения находятся внутри проектной онтологии и её ссылки разрешимы. Работает непрерывно, пока пользователь ревьюит ([SETUP-06](SETUP-06-rag-card-review.md)), и гейтит чанкование ([SETUP-08](SETUP-08-chunking.md)).

## Бизнес-ценность

Metadata-driven retrieval возможен только тогда, когда metadata корректна. Опечатка в `doc_type` или неизвестное значение `domain` делает карточку невидимой для retrieval-фильтров; SETUP-07 ловит это до того, как Runtime сделает первый запрос.

## Пользовательский сценарий

1. Мастер всегда показывает панель **Validation status**: `valid`, `invalid`, `review_required` по семействам карточек.
2. Клик по панели открывает validation report, сгруппированный по классу ошибок: отсутствует `doc_id`, неизвестный `doc_type`, `domain` не в онтологии, пустые `retrieval_tags`, `phase` не в допустимом сете, битый `source_document_id`.
3. Пользователь чинит ошибки inline; валидация перезапускается на save.

## Связанные требования

- BR-FR-Setup-071..074 (обязательные поля, проверки онтологии, целостность ссылок, машиночитаемый отчёт).
- Правила валидации: см. [../../06-rag/metadata-schema.md](../../06-rag/metadata-schema.md) и [../../../validators/rag_metadata_validator.py](../../../validators/rag_metadata_validator.py).

## Связанные сервисы

- Metadata Validation Service, Ontology Service, RAG Card Registry, Frontend Validation Report View.

## Связанные контракты

- `RAGMetadataValidationReport` (`schemas/validation_report.py`): список `{ card_id, severity, code, message }`.

## Связанные RAG-документы

- Валидатор также форсится оффлайн через [`make rag-validate`](../../../Makefile) на каждом CI-запуске.

## Критерии приёмки

- Карточка с любой строкой `severity = error` НЕ ОБЯЗАНА переходить в чанкование.
- Перевалидация после правки ОБЯЗАНА быть идемпотентной (тот же вход → тот же отчёт).
- Тесты: `tests/unit/test_rag_metadata_validator.py`, `tests/component/test_setup_validation_loop.py`.
