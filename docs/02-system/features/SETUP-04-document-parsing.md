# SETUP-04. Извлечение секций

## Назначение

Превратить каждый исходный документ в список типизированных, адресуемых **секций**, которые могут стать RAG-карточками. Секции сохраняют иерархию заголовков, code-блоки, таблицы и оригинальные смещения в документе, чтобы каждый последующий артефакт мог цитировать источник точно.

## Бизнес-ценность

RAG-карточки, сгенерированные из blob-ов целых документов, шумные и плохо отслеживаемые. Парсированные секции дают генератору карточек чистую единицу работы, а audit trail — точный якорь `section_id`.

## Пользовательский сценарий

1. Мастер переходит в фазу **Parsing**.
2. Показывается per-document прогресс: обработано байт, найдено секций, ошибок.
3. После парсинга пользователь видит для каждого документа дерево секций (например, для Markdown с tactical-objects: верхнеуровневые блоки *Sensor*, *Weapon*, *Communication*, *Object*, *Group*, *External conditions*, *Global situation* видны как отдельные секции).

## Связанные требования

- BR-FR-Setup-041..044 (поддержка per-type парсеров, подсказка классификатора, идентичность секции).
- Парсеры: Markdown (по заголовкам), PDF (layout + текст), DOCX (по стилям), CSV/XLSX (sheet → таблица), JSON (объект → секция).

## Связанные сервисы

- Document Parser, Markdown Parser, PDF Extractor, DOCX Extractor, Section Classifier, API Backend.

## Связанные контракты

- `ParsedSection` (`schemas/setup.py`): `section_id`, `source_document_id`, `parent_section_id`, `heading`, `raw_text`, `normalized_text`, `offsets`, `predicted_type` (`schema | task | analytics | feature_pattern | validation_rule | question_template | glossary | example`).

## Критерии приёмки

- Для Markdown-документа с заголовками H1/H2/H3 дерево секций ОБЯЗАНО зеркалить эту иерархию.
- Для PDF номера страниц ОБЯЗАНЫ сохраняться per-секция.
- `predicted_type` ОБЯЗАН быть best-effort меткой; SETUP-05 может её переопределить.
- Тест: `tests/component/test_setup_parser.py`.
