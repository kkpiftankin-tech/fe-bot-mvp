# Бизнес-требования

Каталог бизнес-требований к FE-Bot и их привязка к системным фичам. Документ отвечает на вопрос «что бизнес потребовал от системы» и «в какой фиче это реализовано». Системная детализация — в [../02-system/](../02-system/).

## Источник

Требования выделены из исходного бизнес-документа [incoming-docs/raw/Бизнес Feature Engineering & Data Generation Bot.md](../../incoming-docs/raw/Бизнес%20Feature%20Engineering%20%26%20Data%20Generation%20Bot.md): функциональные требования — разделы 7–8, нефункциональные — раздел 9, бизнес-правила — раздел 12, метрики — раздел 14, допущения, риски и MVP — разделы 16–18.

Исходный документ описывает **Runtime** (диалог ML-задачи). Стадия **Setup** появилась позже; её требования определены в файлах [SETUP-01..SETUP-13](../02-system/features/feature-index.md), а цели — в [goals.md](goals.md#g-09-база-знаний-собирается-из-документов-за-один-сеанс-мастера).

## Нотация идентификаторов

В документации встречаются несколько семейств идентификаторов `BR-*`. Они определены в разных местах:

| Префикс | Что это | Где определено |
| --- | --- | --- |
| `BR-FR-NNN` | Функциональные требования Runtime | Этот документ, [каталог ниже](#функциональные-требования-runtime) |
| `BR-NFR-NNN` | Нефункциональные требования | Этот документ, [каталог ниже](#нефункциональные-требования); в 02 зеркалятся как `NFR-*` ([non-functional-requirements.md](../02-system/non-functional-requirements.md)) |
| `BR-Metrics-*` | Метрики успеха | [goals.md](goals.md#метрики-успеха-mvp); в 02 зеркалятся как `NFR-Qual-*` и в ANALYTICS-фичах |
| `BR-FR-<Area>-NNN` (`Gen`, `Data`, `Feature`, `Sys`, `Model`, `Export`) | Ссылки в файлах фич | Отдельного определения нет; по смыслу совпадают с `FR-<Area>-NNN` из [functional-requirements.md](../02-system/functional-requirements.md) |
| `BR-FR-Setup-NNN`, `BR-FR-Platform-NNN`, `BR-FR-Setup-Lifecycle-NNN` | Требования Setup и платформы | Только в разделах «Связанные требования» файлов соответствующих фич |

## Каталог требований

Колонка «Реализующие фичи» построена по ссылкам на `BR-*` в разделах «Связанные требования» файлов фич из 02.

### Функциональные требования (Runtime)

#### 7.1. Инициализация и управление сессией

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-001 | Создание новой сессии | [RUNTIME-01](../02-system/features/RUNTIME-01-session.md) |
| BR-FR-002 | Восстановление сессии | [RUNTIME-01](../02-system/features/RUNTIME-01-session.md) |
| BR-FR-003 | Сброс сессии | [RUNTIME-01](../02-system/features/RUNTIME-01-session.md) |

#### 7.2. NLU и понимание пользовательского ввода

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-010 | Классификация намерений | [RUNTIME-02](../02-system/features/RUNTIME-02-nlu.md) |
| BR-FR-011 | Извлечение сущностей | [RUNTIME-02](../02-system/features/RUNTIME-02-nlu.md) |
| BR-FR-012 | Оценка уверенности | [RUNTIME-02](../02-system/features/RUNTIME-02-nlu.md) |
| BR-FR-013 | Анализ ясности запроса | [RUNTIME-02](../02-system/features/RUNTIME-02-nlu.md) |

#### 7.3. RAG и база знаний

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-020 | Использование RAG на всех содержательных этапах | [PLATFORM-05](../02-system/features/PLATFORM-05-rag-retrieval.md) |
| BR-FR-021 | Структура RAG-индекса | [PLATFORM-05](../02-system/features/PLATFORM-05-rag-retrieval.md) |
| BR-FR-022 | Требования к RAG-документам | [PLATFORM-05](../02-system/features/PLATFORM-05-rag-retrieval.md) |
| BR-FR-023 | Evidence-based generation | [PLATFORM-05](../02-system/features/PLATFORM-05-rag-retrieval.md) |

#### 7.4. Оркестрация диалога

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-030 | Управление фазами | [PLATFORM-02](../02-system/features/PLATFORM-02-langgraph-orchestrator.md) |
| BR-FR-031 | Проверка завершённости фазы | [PLATFORM-02](../02-system/features/PLATFORM-02-langgraph-orchestrator.md) |
| BR-FR-032 | Возврат к предыдущей фазе | [PLATFORM-02](../02-system/features/PLATFORM-02-langgraph-orchestrator.md) |

#### 7.5. ContextMemory

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-040 | Хранение контекста | [RUNTIME-01](../02-system/features/RUNTIME-01-session.md) |
| BR-FR-041 | Валидация обновлений контекста | [RUNTIME-01](../02-system/features/RUNTIME-01-session.md) |

#### 8.1. Phase 1 — Task Discovery

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-050 | Определение типа задачи | [RUNTIME-03](../02-system/features/RUNTIME-03-task-discovery.md) |
| BR-FR-051 | Определение целевой переменной | [RUNTIME-03](../02-system/features/RUNTIME-03-task-discovery.md) |
| BR-FR-052 | Определение домена и источника данных | [RUNTIME-03](../02-system/features/RUNTIME-03-task-discovery.md) |

#### 8.2. Phase 2 — Data Profiling

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-060 | Сбор профиля данных | [RUNTIME-04](../02-system/features/RUNTIME-04-data-profiling.md) |
| BR-FR-061 | Нормализация полей | [RUNTIME-04](../02-system/features/RUNTIME-04-data-profiling.md) |
| BR-FR-062 | Обработка неизвестных полей | [RUNTIME-04](../02-system/features/RUNTIME-04-data-profiling.md) |

#### 8.3. Phase 3 — Domain Context

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-070 | Уточнение доменного контекста | [RUNTIME-05](../02-system/features/RUNTIME-05-domain-context.md) |
| BR-FR-071 | Выявление критичных факторов | [RUNTIME-05](../02-system/features/RUNTIME-05-domain-context.md) |
| BR-FR-072 | Требования к интерпретируемости | [RUNTIME-05](../02-system/features/RUNTIME-05-domain-context.md) |

#### 8.4. Phase 4 — Feature Synthesis

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-080 | Генерация базовых признаков | [RUNTIME-06](../02-system/features/RUNTIME-06-feature-synthesis.md) |
| BR-FR-081 | Генерация производных признаков | [RUNTIME-06](../02-system/features/RUNTIME-06-feature-synthesis.md) |
| BR-FR-082 | Генерация признаков взаимодействия | [RUNTIME-06](../02-system/features/RUNTIME-06-feature-synthesis.md) |
| BR-FR-083 | Объяснение признаков | [RUNTIME-06](../02-system/features/RUNTIME-06-feature-synthesis.md) |
| BR-FR-084 | Подтверждение пользователем | [RUNTIME-08](../02-system/features/RUNTIME-08-feature-review.md) |

#### 8.5. Phase 5 — Data Generation

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-090 | Генерация синтетической обучающей выборки | [RUNTIME-10](../02-system/features/RUNTIME-10-data-generation.md) |
| BR-FR-091 | Настройки генерации | [RUNTIME-09](../02-system/features/RUNTIME-09-generation-spec.md) |
| BR-FR-092 | Валидация сгенерированных данных | [RUNTIME-10](../02-system/features/RUNTIME-10-data-generation.md) |
| BR-FR-093 | Сохранение данных | [RUNTIME-10](../02-system/features/RUNTIME-10-data-generation.md) |

#### 8.6. Phase 6 — Model Selection

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-100 | Рекомендация моделей | [RUNTIME-11](../02-system/features/RUNTIME-11-model-selection.md) |
| BR-FR-101 | Минимальный набор моделей | [RUNTIME-11](../02-system/features/RUNTIME-11-model-selection.md) |
| BR-FR-102 | Обоснование выбора модели | [RUNTIME-11](../02-system/features/RUNTIME-11-model-selection.md) |
| BR-FR-103 | Генерация training config | [RUNTIME-11](../02-system/features/RUNTIME-11-model-selection.md) |

#### 8.7. Phase 7 — Export

| ID | Требование | Реализующие фичи |
| --- | --- | --- |
| BR-FR-110 | Экспорт артефактов | [RUNTIME-12](../02-system/features/RUNTIME-12-export.md) |
| BR-FR-111 | Требования к `features.json` | [RUNTIME-12](../02-system/features/RUNTIME-12-export.md) |
| BR-FR-112 | Требования к `config.yaml` | [RUNTIME-12](../02-system/features/RUNTIME-12-export.md) |
| BR-FR-113 | Требования к `pipeline.py` | [RUNTIME-12](../02-system/features/RUNTIME-12-export.md) |
| BR-FR-114 | Требования к `metadata.json` | [RUNTIME-12](../02-system/features/RUNTIME-12-export.md) |

### Нефункциональные требования

#### 9.1. Производительность

| ID | Требование | Зеркало в 02 |
| --- | --- | --- |
| BR-NFR-001 | Время ответа в диалоге | NFR-Perf-001 |
| BR-NFR-002 | Производительность RAG | NFR-Perf-002 |
| BR-NFR-003 | Производительность LLM | NFR-Perf-003 |
| BR-NFR-004 | Время генерации признаков | NFR-Perf-004 |
| BR-NFR-005 | Время генерации данных | NFR-Perf-005 |

#### 9.2. Масштабируемость

| ID | Требование | Зеркало в 02 |
| --- | --- | --- |
| BR-NFR-010 | Масштабирование базы знаний | NFR-Scale-001 |
| BR-NFR-011 | Масштабирование доменов | NFR-Scale-002 |
| BR-NFR-012 | Масштабирование признаков | NFR-Scale-003 |

#### 9.3. Надёжность

| ID | Требование | Зеркало в 02 |
| --- | --- | --- |
| BR-NFR-020 | Устойчивость к ошибкам LLM | NFR-Rel-001 |
| BR-NFR-021 | Устойчивость к отсутствию RAG-контекста | NFR-Rel-002 |
| BR-NFR-022 | Сохранение состояния | NFR-Rel-003 |

#### 9.4. Безопасность и доступ

| ID | Требование | Зеркало в 02 |
| --- | --- | --- |
| BR-NFR-030 | Контроль доступа | NFR-Sec-001 |
| BR-NFR-031 | Защита артефактов | NFR-Sec-002 |
| BR-NFR-032 | Аудит | NFR-Audit-001 |

#### 9.5. UX и язык

| ID | Требование | Зеркало в 02 |
| --- | --- | --- |
| BR-NFR-040 | Язык интерфейса | NFR-Use-001 |
| BR-NFR-041 | Прозрачность для пользователя | NFR-Use-002 |

### Требования Setup и платформы

Эти идентификаторы определены только в разделах «Связанные требования» файлов фич и указаны там диапазонами с кратким описанием. Поэтому каталог приводит диапазоны, а не отдельные требования.

| Диапазон | Суть | Фича |
| --- | --- | --- |
| BR-FR-Setup-021..024 | Поддерживаемые типы файлов, максимальный размер, дедупликация, загрузка только по явному действию (opt-in) | [SETUP-02](../02-system/features/SETUP-02-document-upload.md) |
| BR-FR-Setup-031..034 | Идентичность источника, статус, просматриваемость, удаляемость | [SETUP-03](../02-system/features/SETUP-03-source-registry.md) |
| BR-FR-Setup-041..044 | Парсеры по типам файлов, подсказка классификатора, идентичность секции | [SETUP-04](../02-system/features/SETUP-04-document-parsing.md) |
| BR-FR-Setup-051..054 | Генерация карточек по типам, полнота metadata, привязка к источнику, confidence scoring | [SETUP-05](../02-system/features/SETUP-05-rag-cards-generation.md) |
| BR-FR-Setup-091..094 | Идентификатор embedding-модели, размерность, раскладка коллекций, версионирование | [SETUP-09](../02-system/features/SETUP-09-embeddings-index.md) |
| BR-FR-Setup-101..104 | Набор контрольных запросов, порог recall@k, путь переопределения, форма отчёта | [SETUP-10](../02-system/features/SETUP-10-retrieval-tests.md) |
| BR-FR-Setup-111..114 | Указатель активной KB, неизменяемость, уведомление, разблокировка Runtime | [SETUP-11](../02-system/features/SETUP-11-publish-kb.md) |
| BR-FR-Setup-Lifecycle-001..004 | Учёт использования карточек, устаревание, переходы статусов | [ANALYTICS-04](../02-system/features/ANALYTICS-04-rag-content-lifecycle.md) |
| BR-FR-Platform-001..003 | Единая точка входа, валидация схем, контракт ошибок | [PLATFORM-01](../02-system/features/PLATFORM-01-api-backend.md) |
| BR-FR-Platform-031..034 | Изоляция по сессии, TTL ссылок, аудит скачиваний, checksum | [PLATFORM-04](../02-system/features/PLATFORM-04-artifact-storage.md) |

Фичи [SETUP-01](../02-system/features/SETUP-01-setup-wizard.md), [SETUP-06](../02-system/features/SETUP-06-rag-card-review.md), [SETUP-07](../02-system/features/SETUP-07-metadata-validation.md), [SETUP-08](../02-system/features/SETUP-08-chunking.md), [SETUP-12](../02-system/features/SETUP-12-llm-taxonomy-classification.md) и [SETUP-13](../02-system/features/SETUP-13-classifier-library.md) на `BR-FR-Setup-*` не ссылаются: их требования записаны в собственных разделах «Бизнес-правила» и «Acceptance Criteria».

## Бизнес-правила

Правила из раздела 12 исходного документа. Они действуют на все фазы Runtime.

**Общие.**
1. Система не переходит к следующей фазе, пока обязательные поля текущей не заполнены.
2. Критически важные интерпретации подтверждаются пользователем.
3. Все изменения контекста сохраняются.
4. По признакам и моделям даются объяснения.
5. RAG используется для доменных рекомендаций; evidence сохраняется для аудита.
6. Где возможно, применяются детерминированные валидаторы.
7. Пользовательские факты явно отделяются от предположений LLM.
8. Решения можно менять до экспорта.
9. Артефакты воспроизводимы.

**Генерация признаков.**
1. Базовые признаки соответствуют полям пользователя; производные используют существующие базовые.
2. Interaction-признаки ограничены по количеству; избегается чрезмерный рост размерности.
3. У каждого признака есть описание и формула.
4. При высоком требовании к интерпретируемости признаки имеют физический смысл.
5. Набор проходит проверку мультиколлинеарности.
6. Итоговый набор подтверждает пользователь.

**Выбор модели.**
1. Модель выбирается после подтверждения набора признаков.
2. Рекомендация учитывает тип задачи, тип данных и интерпретируемость; предлагается top-3 или top-5 моделей.
3. Для выбранной модели создаётся training config; метрики соответствуют типу задачи.

**Экспорт.**
1. Экспорт разрешён только после завершения Model Selection.
2. Все артефакты согласованы между собой; `pipeline.py` ссылается на конфигурацию обучения; `metadata.json` описывает все артефакты.
3. Архив включает все обязательные файлы; ссылка на скачивание сохраняется в БД.

## Пробелы трассировки

- **Коллекции `model_configs`, `feature_analysis`, `response_templates` из `BR-FR-021`** не имеют соответствующих типов документов в [document-types.md](../06-rag/document-types.md) и нигде в проекте не упоминаются. Решение — в разделе «Открытые вопросы» [PLATFORM-05](../02-system/features/PLATFORM-05-rag-retrieval.md).
- **Требования Setup и платформы** (`BR-FR-Setup-*`, `BR-FR-Platform-*`) существуют только как диапазоны в файлах фич; отдельных формулировок по каждому идентификатору нет (см. [таблицу выше](#требования-setup-и-платформы)).

## Связанные документы

- [vision.md](vision.md), [goals.md](goals.md), [mvp-scope.md](mvp-scope.md)
- [../02-system/functional-requirements.md](../02-system/functional-requirements.md), [../02-system/non-functional-requirements.md](../02-system/non-functional-requirements.md)
- [../02-system/features/feature-index.md](../02-system/features/feature-index.md)
