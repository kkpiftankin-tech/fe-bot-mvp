# SETUP-04. Извлечение секций

## Назначение

Превратить каждый исходный документ в список типизированных, адресуемых **секций**, которые могут стать RAG-карточками. Секции сохраняют иерархию заголовков, code-блоки, таблицы и оригинальные смещения в документе, чтобы каждый последующий артефакт мог цитировать источник точно.

## Бизнес-ценность

RAG-карточки, сгенерированные из blob-ов целых документов, шумные и плохо отслеживаемые. Парсированные секции дают генератору карточек чистую единицу работы, а audit trail — точный якорь `section_id`.

## Вход и выход

- **Вход.** Исходные документы из реестра источников.
- **Выход.** Дерево секций на каждый документ (`ParsedSection`: заголовок, текст, смещения, `predicted_type`, результат классификации по дереву `classifier_result`), счётчики и ошибки парсинга по документам; вход для [SETUP-05](SETUP-05-rag-cards-generation.md).

Классификация секции по дереву классов ([SETUP-13](SETUP-13-classifier-library.md)) выполняется здесь, на шаге 3, **один раз**. Это единственное место, где определяется смысл фрагмента; последующие шаги берут классификацию из `classifier_result` и не переклассифицируют секцию ([ADR-HTC-10](../../03-architecture/adr/ADR-HTC-10-classification-hints-single-source.md)).

### Нормализация длины секций

Между boundary-детекцией стратегии (заголовки/нумерация) и классификацией выполняется `SectionLengthNormalizer` (`fe_bot/setup/parser/length_normalizer.py`): секции короче `min_chars` (по умолчанию 800) объединяются с соседними, если заголовок каждой из них сам похож на пункт нумерованного списка («1. …», «2 …») — именно та форма, которую PDF-эвристика заголовков (`_DECIMAL_HEADING_RE`) может ложно принять за настоящий заголовок, разбивая один смысловой кусок текста на обрывки по одному предложению. Объединение никогда не пересекает границу настоящего заголовка (разный `heading_path`/`parent_section_id`) и никогда не трогает секции с обычным заголовком — короткая, но самостоятельная секция (термин глоссария, короткое поле схемы) не теряет идентичность только из-за объёма текста. Секции длиннее `max_chars` (по умолчанию 4000) делятся по границам абзацев (`\n\s*\n`), не разрезая абзац посередине; если единственный абзац сам превышает порог — он остаётся одной длинной секцией как есть. Обе границы настраиваются при создании `DocumentParserOrchestrator` (`length_normalizer=SectionLengthNormalizer(min_chars=..., max_chars=...)`).

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
- `ParsedSection.classifier_result` (`FragmentClassificationResult`, `schemas/classifier/classification_result.py`): путь по дереву классов с confidence на каждом уровне; в целевом дизайне также `resolved_hints` — разрешённые по пути metadata-хинты ([SETUP-13 §8](SETUP-13-classifier-library.md#8-metadata-хинты-узлов)). Поле реализовано в `schemas/setup/parsed_section.py`.

## Критерии приёмки

- Для Markdown-документа с заголовками H1/H2/H3 дерево секций ОБЯЗАНО зеркалить эту иерархию.
- Для PDF номера страниц ОБЯЗАНЫ сохраняться per-секция (`structural_payload.page_start/page_end`).
- Для PDF секции ОБЯЗАНЫ отражать реальную структуру документа (нумерация
  `N`/`N.N`/`N.N.N`, `Chapter N`/`Глава N`/`Part N`/`Часть N`), а не границы
  страниц — постраничное деление используется только как fallback, когда во
  всём документе не найдено ни одного заголовка. Table of Contents и
  References/Bibliography распознаются отдельно и помечаются
  `structural_payload.zone = "toc" | "references"` с заниженным confidence
  (это не контентные секции для RAG-карточек). См.
  `src/fe_bot/setup/parser/strategies/pdf_parser.py` module docstring для
  деталей эвристики (font-size через pypdf visitor API оказался ненадёжным
  на реальных PDF — используется только нумерация + структурные паттерны).
- `predicted_type` ОБЯЗАН быть best-effort меткой для отображения и грубой фильтрации. SETUP-05 **не использует** её для определения `doc_type`, если есть `classifier_result`: при классификации по дереву SETUP-13 `ClassifierTreeSectionClassifier` не выводит legacy-тип и записывает `section_type = OTHER` (`UNKNOWN`, если ни один класс верхнего уровня не подошёл или нет активного дерева).
- Статус секции после классификации по дереву: `CLASSIFIED`, если `overall_confidence` пути не ниже порога (по умолчанию 0.5), иначе `LOW_CONFIDENCE`; пустой путь — всегда `LOW_CONFIDENCE`. В генерацию карточек попадают только секции, пригодные по [SETUP-05 BR-01](SETUP-05-rag-cards-generation.md#12-бизнес-правила-и-ограничения). Сбой LLM классификатора помечает документ `CLASSIFICATION_FAILED` (см. [SETUP-13 §6](SETUP-13-classifier-library.md#6-критерии-приёмки)).
- Тест: `tests/component/test_setup_parser.py`, `tests/unit/test_parser_strategies.py::TestPDF`.
