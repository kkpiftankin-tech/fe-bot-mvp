[TOC]


# Бизнес-требования к мультиагентной системе Feature Engineering & Data Generation Bot

Документ ниже оформлен как бизнес-требования к системе, которая на основе диалога с пользователем диагностирует ML-задачу, собирает профиль данных, учитывает доменный контекст, формирует признаки, генерирует обучающую выборку, рекомендует ML-модель и экспортирует готовые артефакты. Это основано на двух приложенных документах: в одном система описана как интерактивный чат-бот для диагностики задачи, выяснения источников данных, генерации физически осмысленных признаков, синтеза обучающей выборки и рекомендации модели ; во втором детализирован happy path с LLM 1B–3B, RAG, FastAPI backend, фронтендом, FSM-оркестрацией, ContextMemory, Feature Engine, Data Generator, Model Selector и Export Engine .

---

# 1. Назначение системы

## 1.1. Бизнес-цель

Создать интерактивную мультиагентную систему, которая помогает аналитику, оператору или ML-инженеру быстро перейти от неформального описания задачи к готовому набору артефактов для построения ML-модели:

$$
\text{Описание задачи}
\rightarrow
\text{Профиль данных}
\rightarrow
\text{Доменный контекст}
\rightarrow
\text{Набор признаков}
\rightarrow
\text{Синтетическая выборка}
\rightarrow
\text{Рекомендованная модель}
\rightarrow
\text{Экспортируемый ML pipeline}
$$

Система должна быть особенно полезна в ситуациях, где пользователь понимает предметную область, но не всегда может формально описать ML-задачу, признаки, целевую переменную, схему данных, модель и pipeline.

## 1.2. Ключевая бизнес-ценность

Система должна:

1. Сократить время первичного проектирования ML-эксперимента.
2. Снизить зависимость от ручной работы ML-инженера на ранних этапах.
3. Стандартизировать сбор требований к данным и признакам.
4. Повысить объяснимость выбора признаков и моделей.
5. Создать повторяемый процесс генерации артефактов: `features.json`, `config.yaml`, `data_generator.py`, `pipeline.py`, `metadata.json`.
6. Обеспечить работу с небольшой локальной LLM через RAG, структурированные промпты, разбиение задачи на агентов и жёсткую валидацию.

В приложенном плане явно указано, что система должна диагностировать задачу, выяснять данные и источники, рекомендовать признаки на основе домена, генерировать физически осмысленный feature set, предлагать функции синтеза обучающей выборки и рекомендовать оптимальную ML-модель .

---

# 2. Заинтересованные стороны

## 2.1. Основные пользователи

| Роль                            | Цели                                                                               | Ожидаемая ценность                                             |
| ------------------------------- | ---------------------------------------------------------------------------------- | -------------------------------------------------------------- |
| Аналитик предметной области     | Описать задачу, источник данных, классы, физические факторы                        | Получить понятный набор признаков и объяснение                 |
| Оператор / пользователь системы | Быстро сформировать ML-конфигурацию через диалог                                   | Минимизировать техническую сложность                           |
| ML-инженер                      | Получить структурированный feature set, data generator, training config и pipeline | Ускорить прототипирование                                      |
| Data scientist                  | Проверить гипотезы о признаках и моделях                                           | Использовать сгенерированные артефакты как основу эксперимента |
| Администратор базы знаний       | Поддерживать RAG-документы, справочники, feature library, model recommendations    | Управлять качеством рекомендаций                               |
| Архитектор / владелец продукта  | Контролировать функциональный объём, качество, SLA и roadmap                       | Обеспечить развитие системы                                    |

## 2.2. Вторичные пользователи

| Роль                                    | Интерес                                                 |
| --------------------------------------- | ------------------------------------------------------- |
| DevOps / MLOps-инженер                  | Развёртывание, хранение артефактов, мониторинг          |
| Руководитель аналитического направления | Контроль качества, воспроизводимость, стандартизация    |
| Эксперт по данным                       | Проверка корректности признаков, источников и допущений |

---

# 3. Область применения

## 3.1. Входит в scope

Система должна поддерживать полный цикл:

1. Инициализация диалога.
2. Определение задачи: классификация, регрессия, кластеризация, обнаружение аномалий, ранжирование.
3. Сбор информации о целевой переменной.
4. Сбор профиля данных: источник, тип, объём, поля, пропуски, баланс классов, временная динамика.
5. Получение доменного контекста: область применения, критичные факторы, интерпретируемость.
6. Генерация признаков:

   * базовые признаки;
   * производные признаки;
   * признаки взаимодействия;
   * при необходимости временные и статистические признаки.
7. Проверка набора признаков:

   * физический смысл;
   * соответствие домену;
   * мультиколлинеарность;
   * ограничения по количеству признаков.
8. Генерация синтетических данных.
9. Рекомендация ML-модели и гиперпараметров.
10. Экспорт артефактов.
11. Сохранение контекста, истории диалога и ссылок на артефакты.

В документе happy path перечислены 7 фаз: Discovery, Data Profiling, Domain Context, Feature Synthesis, Data Generation, Model Selection и Export . В плане разработки аналогичный граф состояний ведёт пользователя от `PHASE_1_TASK_DISCOVERY` до `PHASE_7_EXPORT`, включая уточнение задачи, описание данных, доменный контекст, синтез признаков, генерацию выборки, выбор модели и экспорт feature set / generator / config / pipeline .

## 3.2. Не входит в scope первой версии

1. Автоматическое обучение production-модели без участия пользователя.
2. Автоматический деплой модели в боевую среду.
3. Замена эксперта предметной области.
4. Гарантия качества модели на реальных данных без последующей валидации.
5. Полностью автономное принятие решений на основе ML-вывода.
6. Работа с закрытыми источниками данных без предварительной интеграции и разрешений.
7. Генерация operational/tactical рекомендаций; система должна ограничиваться подготовкой ML-признаков, данных, конфигов и pipeline.

---

# 4. Целевая концепция решения

## 4.1. Общая концепция

Система должна быть реализована как мультиагентный диалоговый помощник, где каждый агент отвечает за ограниченный участок процесса. Это снижает нагрузку на маленькую LLM и повышает управляемость.

Целевая архитектура:

```text
Пользователь
  ↓
Chat Interface
  ↓
Dialogue Orchestrator / LangGraph
  ↓
NLU Agent
  ↓
RAG Retrieval Agent
  ↓
Context Memory Agent
  ↓
Task Discovery Agent
  ↓
Data Profiling Agent
  ↓
Domain Context Agent
  ↓
Feature Synthesis Agents
  ↓
Validation / Critic Agents
  ↓
Data Generation Agent
  ↓
Model Selection Agent
  ↓
Export Agent
  ↓
Artifact Storage / Download
```

В приложенной архитектуре уже заложены фронтенд, backend, DialogueEngine, ContextMemory, NLU module, specialist components, VectorDB, LLM API, Database и File Storage . Мультиагентная версия должна сохранить эти компоненты, но разложить ответственность между специализированными агентами.

## 4.2. Почему требуется мультиагентность

Поскольку целевая LLM малая, система не должна полагаться на один длинный prompt. Вместо этого каждый агент должен выполнять узкую бизнес-функцию:

$$
\text{Quality}
\approx
\text{Decomposition}
+
\text{RAG}
+
\text{Validation}
+
\text{State Management}
$$

Мультиагентность требуется для:

1. Разделения сложного процесса на управляемые этапы.
2. Снижения риска галлюцинаций.
3. Возможности независимой валидации результатов.
4. Повторного использования агентов в разных доменах.
5. Чёткого аудита: какой агент принял какое решение.
6. Управления контекстом через state, а не через длинную историю чата.

---
## 4.3 Дополнения


Идея раздела 4.1 в том, что система строится не как один большой чат с LLM, а как **управляемый бизнес-процесс**, разбитый на специализированные роли. В приложенном happy path это уже заложено через frontend, FastAPI backend, DialogueEngine, ContextMemory, NLU module, Feature Engine, Data Generator, Model Selector, Export Engine, VectorDB, LLM API, Database и File Storage . Во втором документе та же логика описана как чат-интерфейс, NLU, dialogue state machine, context memory, domain knowledge base, feature repository, feature engine, model selector и output generator .

Главная мысль:

$$
\text{маленькая LLM}
+
\text{RAG}
+
\text{LangGraph}
+
\text{агенты}
+
\text{валидаторы}
\text{управляемая система генерации ML-признаков}
$$

---

### 4.3.1. Почему не один агент

Если дать маленькой модели `llama3.2:latest` одну большую задачу:

> «Пойми задачу, спроси данные, выбери признаки, сгенерируй выборку, выбери модель, создай pipeline»

она будет часто:

* терять контекст;
* перескакивать фазы;
* придумывать признаки;
* забывать ограничения;
* смешивать бизнес-вопросы и технические детали;
* генерировать невалидный JSON/код;
* плохо контролировать качество.

Поэтому система делится на маленькие роли:

$$
A = {A_1, A_2, \dots, A_n}
$$

где каждый агент $A_i$ решает узкую задачу:

$$
A_i: (S_t, C_i, R_i) \rightarrow O_i
$$

где:

* $S_t$ — текущее состояние диалога;
* $C_i$ — локальный контекст агента;
* $R_i$ — RAG-документы, нужные только этому агенту;
* $O_i$ — структурированный результат.

---

### 4.3.2. Что означает вся цепочка

Исходная цепочка:

```text
Пользователь
  ↓
Chat Interface
  ↓
Dialogue Orchestrator / LangGraph
  ↓
NLU Agent
  ↓
RAG Retrieval Agent
  ↓
Context Memory Agent
  ↓
Task Discovery Agent
  ↓
Data Profiling Agent
  ↓
Domain Context Agent
  ↓
Feature Synthesis Agents
  ↓
Validation / Critic Agents
  ↓
Data Generation Agent
  ↓
Model Selection Agent
  ↓
Export Agent
  ↓
Artifact Storage / Download
```

Это не значит, что все агенты всегда вызываются строго линейно. Это **логическая архитектура**. Реально LangGraph может вызывать агентов условно, циклически или параллельно.

Например:

```text
Feature Synthesis Agent
  ↓
Validation Agent
  ↓
ошибка?
  ├─ да → обратно в Feature Synthesis Agent
  └─ нет → Model Selection Agent
```

---

### 4.3.3. Роль каждого компонента

#### 4.3.3.1. Пользователь

Пользователь даёт неформальное описание:

```text
Нужен классификатор для определения типа морских целей по РЛС.
Есть дальность, азимут, угол места, RCS, SNR, доплер.
```

Пользователь не обязан сразу знать:

* правильный тип ML-задачи;
* точную схему признаков;
* модель;
* формат pipeline;
* правила генерации данных.

Система должна постепенно привести его к формальной постановке.

---

#### 4.3.3.2. Chat Interface

Это внешний интерфейс:

* web chat;
* CLI;
* Telegram/Slack bot;
* внутренний корпоративный портал.

Его задача — не «думать», а удобно принимать и показывать:

* сообщения;
* текущую фазу;
* быстрые кнопки;
* список собранных параметров;
* список признаков;
* ссылки на артефакты.

В приложенном happy path frontend включает chat interface, progress bar на 7 фаз и download manager .

Пример состояния UI:

```text
Фаза 2 из 7: Data Profiling

Уже известно:
- task_type = classification
- domain = naval
- data_source = radar
- target = target_type

Не хватает:
- data_volume
- fields
- class_distribution
```

---

#### 4.3.3.3. Dialogue Orchestrator / LangGraph

Это главный управляющий слой.

Он отвечает за вопрос:

> «Что делать следующим шагом?»

Не LLM должна решать, куда идти дальше, а граф состояний.

Например:

```text
если не заполнен task_type → вызвать TaskDiscoveryAgent
если не заполнены fields → вызвать DataProfilingAgent
если признаки не подтверждены → вызвать FeatureSynthesisAgent
если признаки невалидны → вызвать ValidationAgent
если всё готово → вызвать ExportAgent
```

В документах это описано как DialogueEngine/FSM с 7 фазами и проверками завершённости каждой фазы .

Математически состояние можно представить так:

$$
S_t =
(
p_t,
M_t,
H_t,
E_t,
A_t
)
$$

где:

* $p_t$ — текущая фаза;
* $M_t$ — ContextMemory;
* $H_t$ — история диалога;
* $E_t$ — найденные RAG-доказательства;
* $A_t$ — созданные артефакты.

Переход:

$$
S_{t+1} = F(S_t, u_t, o_t)
$$

где:

* $u_t$ — сообщение пользователя;
* $o_t$ — output вызванного агента.

---

#### 4.3.3.4. NLU Agent

NLU Agent превращает текст пользователя в структуру.

Пример входа:

```text
Нужен классификатор для определения типа морских целей по РЛС.
```

Пример выхода:

```json
{
  "intent": "describe_task",
  "confidence": 0.98,
  "entities": {
    "task_type": {
      "value": "classification",
      "confidence": 0.99
    },
    "domain": {
      "value": "naval",
      "confidence": 0.98
    },
    "data_source": {
      "value": "radar",
      "confidence": 0.97
    },
    "target_variable": {
      "value": "target_type",
      "confidence": 0.95
    }
  },
  "missing_slots": []
}
```

В приложенном happy path NLU состоит из RAG Retrieval, Intent Classification, Entity Extraction и Sentiment/Clarity Analysis .

То есть NLU Agent не создаёт признаки. Он только отвечает:

> «Что пользователь сказал в формальных терминах?»

---

#### 4.3.3.5. RAG Retrieval Agent

RAG Retrieval Agent ищет нужный контекст.

Например, если пользователь говорит «РЛС», агент должен найти:

* что `РЛС = radar`;
* какие типовые поля бывают у radar data;
* какие признаки применимы к naval radar;
* какие модели хорошо работают на tabular classification;
* какие есть шаблоны вопросов.

В happy path RAG index содержит коллекции `domain_profiles`, `feature_library`, `model_recommendations`, `question_templates`, `glossary` .

RAG нужен, чтобы маленькая LLM не держала всё знание внутри себя.

Схема:

```text
user text
  ↓
embedding
  ↓
VectorDB
  ↓
top-k relevant docs
  ↓
evidence_pack
  ↓
agent prompt
```

---

#### 4.3.3.6. Context Memory Agent

Context Memory — это «рабочая память» системы.

Она хранит не длинный чат, а структурированные слоты:

```json
{
  "task_type": "classification",
  "target_variable": "target_type",
  "domain": "naval",
  "data_source": "radar",
  "data_volume": 50000,
  "data_type": "tabular",
  "fields": ["range", "azimuth", "elevation", "rcs", "snr", "doppler"],
  "class_distribution": [0.4, 0.3, 0.2, 0.1],
  "interpretability_requirement": "high",
  "final_features": [],
  "recommended_model": null
}
```

Во втором документе `ContextMemory` хранит Discovery, Data Profiling, Domain Context, Features, Data Generation, Model Selection и служебную информацию .

Это важно: маленькая LLM не должна помнить всё сама. Она получает только нужный кусок памяти.

---

#### 4.3.3.7. Task Discovery Agent

Этот агент отвечает за фазу:

> «Какую ML-задачу решаем?»

Он уточняет:

* классификация или регрессия;
* что является target;
* сколько классов;
* где будет применяться модель;
* есть ли требования по latency;
* нужен ли real-time.

Пример:

```text
Пользователь: Нужно определять тип цели.
Агент: Это похоже на задачу классификации. Какие классы цели нужно различать?
```

Результат:

```json
{
  "task_type": "classification",
  "target_variable": "target_type",
  "classes": ["civilian_ship", "military_ship", "submarine", "aircraft"]
}
```

---

#### 4.3.3.8. Data Profiling Agent

Этот агент выясняет:

* какие данные есть;
* источник данных;
* тип данных;
* объём;
* поля;
* пропуски;
* баланс классов;
* временная динамика.

Пример:

```text
Вопрос: Какие параметры РЛС доступны?
Ответ пользователя: дальность, азимут, угол места, RCS, SNR, доплер.
```

Выход:

```json
{
  "data_type": "tabular",
  "fields": [
    "range",
    "azimuth",
    "elevation",
    "rcs",
    "snr",
    "doppler"
  ],
  "missing_data_strategy": "none"
}
```

В happy path Data Profiling собирает именно такие поля: `data_volume`, `data_type`, `fields`, `missing_data_strategy`, `class_distribution`, `temporal_importance` .

---

#### 4.3.3.9. Domain Context Agent

Этот агент отвечает за предметный смысл.

Он должен понять:

* какие факторы важны в домене;
* какие признаки физически осмыслены;
* какие ограничения есть;
* насколько важна интерпретируемость.

Например, для морского РЛС-домена:

```text
- дальность влияет на надёжность обнаружения;
- RCS связан с типом цели;
- SNR отражает качество сигнала;
- доплер связан со скоростью/движением;
- угол места помогает отличить авиацию от морских объектов.
```

Результат:

```json
{
  "critical_factors": [
    "range",
    "rcs",
    "snr",
    "doppler",
    "elevation"
  ],
  "interpretability_requirement": "high",
  "domain_constraints": [
    "features should have physical meaning",
    "avoid unexplained black-box transformations"
  ]
}
```

---

#### 4.3.3.10. Feature Synthesis Agents

Здесь лучше не один агент, а несколько.

Например:

```text
BaseFeatureAgent
DerivedFeatureAgent
InteractionFeatureAgent
TemporalFeatureAgent
StatisticalFeatureAgent
FeatureExplanationAgent
```

Почему? Потому что генерация признаков — самая рискованная часть.

##### BaseFeatureAgent

Берёт исходные поля:

```text
range, azimuth, elevation, rcs, snr, doppler
```

и оформляет их как признаки.

##### DerivedFeatureAgent

Создаёт производные признаки:

```text
signal_quality = snr / reference_snr
rcs_normalized = log1p(rcs)
distance_class = bucket(range)
maneuver_index = function(doppler)
```

##### InteractionFeatureAgent

Создаёт взаимодействия:

```text
range_x_snr = range * snr
rcs_x_snr = rcs * snr
doppler_x_elevation = doppler * elevation
```

В happy path Feature Engine генерирует 19 признаков: 6 базовых, 8 производных, 5 взаимодействий .

---

#### 4.3.3.11. Validation / Critic Agents

Это очень важный слой.

Он отвечает не за генерацию, а за критику.

Проверяет:

* все ли признаки используют существующие поля;
* есть ли физический смысл;
* нет ли дублирования;
* нет ли слишком сильной корреляции;
* не слишком ли много interaction features;
* валидны ли формулы;
* соответствуют ли признаки задаче;
* можно ли посчитать признаки в pipeline.

Пример проверки:

```text
Признак range_acceleration требует временного ряда.
Но пользователь сказал, что каждая отметка независима.
Значит признак должен быть отклонён или помечен как unavailable.
```

Выход:

```json
{
  "status": "failed",
  "rejected_features": [
    {
      "name": "range_acceleration",
      "reason": "requires temporal sequence but temporal_importance=false"
    }
  ],
  "approved_features": [
    "range",
    "azimuth",
    "rcs",
    "snr",
    "doppler"
  ]
}
```

Это особенно важно для маленькой LLM: генератор может ошибаться, критик должен ловить ошибки.

---

#### 4.3.3.12. Data Generation Agent

Этот агент создаёт синтетическую выборку.

Он использует:

* `final_features`;
* число примеров;
* баланс классов;
* шум;
* аномалии;
* распределения признаков.

В happy path Data Generator создаёт synthetic data `100k × 19`, realistic distributions & dependencies, noise & anomalies simulation .

Результат:

```json
{
  "X_shape": [100000, 19],
  "y_shape": [100000],
  "class_distribution": {
    "civilian_ship": 0.4,
    "military_ship": 0.3,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "files": {
    "X_train": "X_train.csv",
    "y_train": "y_train.npy",
    "metadata": "metadata.json"
  }
}
```

---

#### 4.3.3.13. Model Selection Agent

Этот агент выбирает модель.

Он учитывает:

* тип задачи;
* размер данных;
* тип данных;
* число признаков;
* интерпретируемость;
* скорость обучения;
* требования к deployment.

Например:

```text
classification + tabular + 19 features + high interpretability
→ XGBoost, LightGBM, Random Forest
```

В happy path Model Selector использует RAG-based recommendations, hyperparameter templates и expected performance metrics .

Выход:

```json
{
  "recommended_models": [
    {
      "rank": 1,
      "model": "XGBoost",
      "reason": "good accuracy on tabular data and supports feature importance"
    },
    {
      "rank": 2,
      "model": "LightGBM",
      "reason": "faster training"
    },
    {
      "rank": 3,
      "model": "Random Forest",
      "reason": "high interpretability and robust baseline"
    }
  ],
  "selected_model": "XGBoost"
}
```

---

#### 4.3.3.14. Export Agent

Export Agent превращает всё накопленное состояние в файлы.

Минимальный набор:

```text
features.json
config.yaml
pipeline.py
data_generator.py
metadata.json
archive.zip
```

В обоих документах экспорт описан как генерация feature set, data generator script, model configuration, training pipeline и metadata  .

Export Agent не должен заново придумывать признаки или модель. Он только берёт утверждённый state и сериализует его.

---

#### 4.3.3.15. Artifact Storage / Download

Последний слой отвечает за хранение и выдачу результата.

Он хранит:

* CSV/NPY данные;
* JSON/YAML конфиги;
* Python-скрипты;
* zip-архивы;
* metadata;
* download links.

В happy path для этого предусмотрены Database и File Storage: база хранит conversations, context snapshots, artifact metadata, download links, а File Storage хранит CSV/NPY, generated code и zip archives .

---

### 4.3.4 Как это работает на одном примере

Пользователь пишет:

```text
Нужен классификатор для определения типа морских целей по РЛС.
```

Система делает:

```text
1. Chat Interface принимает сообщение.
2. LangGraph передаёт сообщение в NLU Agent.
3. NLU Agent извлекает:
   task_type = classification
   domain = naval
   data_source = radar
   target_variable = target_type
4. RAG Agent находит документы про naval radar classification.
5. Context Memory сохраняет найденные слоты.
6. LangGraph видит, что Phase 1 завершена.
7. Переход в Data Profiling.
8. Data Profiling Agent спрашивает:
   Какие поля доступны?
   Какой объём данных?
   Есть ли пропуски?
```

После нескольких шагов:

```text
fields = [range, azimuth, elevation, rcs, snr, doppler]
data_volume = 50000
class_distribution = [0.4, 0.3, 0.2, 0.1]
interpretability_requirement = high
```

Далее:

```text
Feature Synthesis Agents предлагают признаки.
Validation Agents проверяют признаки.
User подтверждает.
Data Generation Agent создаёт X/y.
Model Selection Agent предлагает XGBoost.
Export Agent создаёт файлы.
Artifact Storage отдаёт zip.
```

---

### 4.3.5. Почему это снижает нагрузку на маленькую LLM

Маленькая LLM не получает задачу:

```text
Сделай всё.
```

Она получает маленькие задачи:

```text
Извлеки только task_type.
```

или:

```text
Нормализуй только список полей.
```

или:

```text
Объясни только один признак.
```

или:

```text
Предложи 5 interaction features на основе уже подтверждённых base features.
```

То есть вместо одной сложной функции:

$$
f_{\text{LLM}}:
\text{raw dialogue}
\rightarrow
\text{full ML project}
$$

используется композиция простых функций:

$$
f =
f_{\text{export}}
\circ
f_{\text{model}}
\circ
f_{\text{data}}
\circ
f_{\text{validate}}
\circ
f_{\text{features}}
\circ
f_{\text{profile}}
\circ
f_{\text{discover}}
$$

Каждая функция проще, проверяемее и стабильнее.

---

### 4.3.6. Где здесь LangGraph

LangGraph нужен, чтобы описать не просто цепочку, а граф:

```text
START
  ↓
Task Discovery
  ↓
Data Profiling
  ↓
Domain Context
  ↓
Feature Synthesis
  ↓
Validation
  ├─ failed → Feature Synthesis
  └─ passed → Data Generation
  ↓
Model Selection
  ↓
Export
  ↓
END
```

Ключевая польза LangGraph:

* явные состояния;
* переходы между фазами;
* циклы исправления;
* условная маршрутизация;
* возможность human-in-the-loop;
* сохранение состояния;
* наблюдаемость;
* тестируемость отдельных узлов.

---

### 4.3.7. Главное отличие от обычного чат-бота

Обычный чат-бот:

```text
User message → LLM → answer
```

Ваша система:

```text
User message
  → parse
  → retrieve evidence
  → update state
  → check phase
  → call specialist agent
  → validate
  → save
  → generate response
```

То есть это не просто генерация текста. Это **workflow-система**.

---

### 4.3.8. Как это лучше переписать в требованиях

Раздел 4.1 можно усилить так:

```text
Система должна быть реализована как stateful multi-agent workflow, 
где LangGraph управляет переходами между фазами, ContextMemory хранит 
структурированное состояние, RAG Retrieval предоставляет проверяемый 
контекст, а специализированные агенты выполняют ограниченные функции: 
понимание запроса, диагностику задачи, профилирование данных, уточнение 
домена, синтез признаков, проверку признаков, генерацию данных, выбор 
модели и экспорт артефактов.

LLM не является единственным источником истины. Все критичные результаты 
должны быть основаны на RAG evidence, сохранены в ContextMemory и проверены 
валидаторами. Диалог должен двигаться по фазам только после выполнения 
completion criteria текущей фазы.
```

Коротко: **LangGraph управляет процессом, RAG даёт знания, ContextMemory хранит состояние, агенты выполняют узкие задачи, валидаторы защищают качество, Export превращает результат в файлы.**




# 5. Бизнес-процесс верхнего уровня

## 5.1. Основной happy path

| Этап | Название          | Бизнес-результат                                                               |
| ---- | ----------------- | ------------------------------------------------------------------------------ |
| 0    | Инициализация     | Создана сессия, пользователь получил приветствие                               |
| 1    | Discovery         | Определены тип задачи, домен, источник данных, целевая переменная              |
| 2    | Data Profiling    | Собран профиль данных: объём, тип, поля, пропуски, баланс классов              |
| 3    | Domain Context    | Уточнены физический/предметный контекст, критичные факторы, интерпретируемость |
| 4    | Feature Synthesis | Сформирован и подтверждён набор признаков                                      |
| 5    | Data Generation   | Сгенерирована обучающая выборка и метаданные                                   |
| 6    | Model Selection   | Рекомендованы top-N моделей и training config                                  |
| 7    | Export            | Сформированы артефакты и архив для скачивания                                  |

В документе happy path пример показывает, что после discovery и profiling контекст может содержать `task_type`, `domain`, `data_source`, `target_variable`, `data_volume`, `data_type`, `fields`, `missing_data_strategy`, `class_distribution` и `temporal_importance` .


Ниже — расширенная версия раздела **5.1. Основной happy path**.

Основной happy path — это идеальный сценарий, в котором пользователь последовательно проходит все фазы без ошибок, противоречий и возвратов назад. В результате система превращает неформальное описание задачи в полный набор ML-артефактов: признаки, синтетическую выборку, конфигурацию модели, pipeline и архив для скачивания.

В приложенном документе happy path этот сценарий описан как 7-фазный процесс: Discovery, Data Profiling, Domain Context, Feature Synthesis, Data Generation, Model Selection и Export; также предусмотрены frontend, backend, DialogueEngine, ContextMemory, NLU, RAG, Feature Engine, Data Generator, Model Selector и Export Engine . Во втором документе тот же процесс представлен как state machine от `PHASE_1_TASK_DISCOVERY` до `PHASE_7_EXPORT` .

---

### Общая логика happy path

Пользователь приходит с неформальным запросом:

```text
Нужен классификатор для определения типа морских целей по РЛС.
```

Система должна постепенно довести этот запрос до формальной структуры:

```json
{
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar",
  "target_variable": "target_type",
  "data_type": "tabular",
  "fields": ["range", "azimuth", "elevation", "rcs", "snr", "doppler"],
  "class_distribution": [0.4, 0.3, 0.2, 0.1],
  "interpretability_requirement": "high",
  "final_features": "...",
  "recommended_model": "XGBoost",
  "artifacts": ["features.json", "config.yaml", "pipeline.py"]
}
```

То есть happy path можно представить как цепочку:

$$
\text{User Intent}
\rightarrow
\text{Structured Context}
\rightarrow
\text{Feature Set}
\rightarrow
\text{Synthetic Dataset}
\rightarrow
\text{Model Config}
\rightarrow
\text{Export Package}
$$

---

### Этап 0. Инициализация

#### Назначение этапа

На этом этапе система создаёт рабочую сессию пользователя и подготавливает инфраструктуру диалога.

#### Что делает пользователь

Пользователь открывает веб-интерфейс и нажимает кнопку запуска, например:

```text
Start
```

#### Что делает система

Система должна:

1. Создать уникальный `conversation_id`.
2. Инициализировать пустую `ContextMemory`.
3. Установить текущую фазу:

```text
PHASE_1_TASK_DISCOVERY
```

4. Сохранить сессию в базе данных.
5. Показать приветствие.
6. Объяснить пользователю, что система поможет спроектировать ML-задачу.
7. Задать первый вопрос.

#### Пример ответа системы

```text
Здравствуйте! Я помогу вам сформировать признаки, подготовить обучающую выборку и подобрать ML-модель.

Начнём с постановки задачи. Что вы хотите предсказывать или классифицировать?
```

#### Состояние после этапа

```json
{
  "conversation_id": "conv_...",
  "current_phase": "PHASE_1_TASK_DISCOVERY",
  "context": {
    "task_type": null,
    "domain": null,
    "data_source": null,
    "target_variable": null
  }
}
```

#### Бизнес-результат

Создана управляемая сессия. Пользователь вошёл в процесс. Система готова собирать требования.

---

### Этап 1. Discovery

#### Назначение этапа

Discovery нужен, чтобы понять, **какую ML-зачу пользователь хочет решить**.

Система должна определить:

* тип задачи;
* предметный домен;
* источник данных;
* целевую переменную;
* классы или прогнозируемый показатель.

#### Пример пользовательского ввода

```text
Нужен классификатор для определения типа морских целей по РЛС.
```

#### Что делает NLU Agent

NLU Agent извлекает intent и entities:

```json
{
  "intent": "describe_task",
  "entities": {
    "task_type": "classification",
    "domain": "naval",
    "data_source": "radar",
    "target_variable": "target_type"
  },
  "confidence": 0.98
}
```

В happy path NLU использует RAG retrieval, intent classification, entity extraction и clarity analysis .

#### Что делает RAG Retrieval Agent

Он ищет документы:

```text
морской домен
РЛС
классификация целей
типовые классы морских объектов
```

Например, RAG может вернуть:

```json
{
  "domain": "naval",
  "task_type": "classification",
  "data_source": "radar",
  "typical_classes": [
    "civilian_ship",
    "military_ship",
    "submarine",
    "aircraft"
  ]
}
```

#### Что делает Context Memory

Сохраняет извлечённые значения:

```json
{
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar",
  "target_variable": "target_type"
}
```

#### Условие завершения этапа

Этап считается завершённым, если заполнены:

```text
task_type
domain
target_variable
```

`data_source` желательно заполнить сразу, но при необходимости можно уточнить позже.

#### Пример ответа системы

```text
Понял. Это задача классификации: нужно определить тип морской цели по данным РЛС.

Я зафиксировал:
- тип задачи: classification
- домен: naval
- источник данных: radar
- целевая переменная: target_type

Теперь нужно описать сами данные.
```

#### Бизнес-результат

Система понимает, что именно нужно построить:

$$
\text{classification}:
X \rightarrow y,
$$

где (X) — параметры РЛС, а (y) — тип цели.


#### Дополнение RAG


Да, именно так. Это одна из ключевых идей всей архитектуры.

RAG в такой системе — это не просто:

```text
vector similarity search
```

а:

$$
\text{semantic search}
+
\text{metadata filtering}
+
\text{ontology}
+
\text{workflow-aware retrieval}
$$

Именно поэтому для вашей задачи чрезвычайно важна **структура документов** и их **метаинформация**.

---

##### 1. Что реально хранится в RAG

Наивный RAG:

```text
длинный текст
→ embedding
→ vector DB
```

Для вашей системы этого недостаточно.

Вам нужен:

```text
document
+
structured metadata
+
ontology tags
+
workflow bindings
+
relationships
```

То есть документ выглядит примерно так:

```yaml
doc_id: domain_naval_radar_classification_001

doc_type: domain_profile

domain: naval
task_type: classification
data_source: radar

target_types:
  - civilian_ship
  - military_ship
  - submarine
  - aircraft

sensor_types:
  - radar

feature_families:
  - kinematic
  - rcs
  - signal_quality

critical_factors:
  - sea_state
  - thermocline
  - visibility

interpretability: high

retrieval_tags:
  - naval
  - radar
  - classification
  - maritime
  - target classification
  - rcs

language: ru

version: 1.0
confidence: high
```

и отдельно:

```markdown
# Морская классификация целей по РЛС

Классификация морских целей по РЛС обычно использует:
- дальность
- азимут
- ЭПР
- SNR
- доплер

Типичные классы:
- civilian_ship
- military_ship
- submarine
- aircraft
```

---

#####  2. Как реально работает retrieval

Когда пользователь пишет:

```text
Нужен классификатор морских целей по РЛС
```

система делает НЕ один поиск.

Она строит **retrieval plan**.

---

#####  3. Retrieval planner

После NLU:

```json
{
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar"
}
```

LangGraph вызывает:

```text
RAG Retrieval Planner
```

который строит несколько запросов.

Например:

---

###### Query 1 — domain profile

```yaml
doc_type = domain_profile
domain = naval
task_type = classification
```

---

######  Query 2 — feature patterns

```yaml
doc_type = feature_pattern
domain = naval
data_source = radar
```

---

######  Query 3 — model recommendations

```yaml
doc_type = model_recommendation
task_type = classification
data_type = tabular
```

---

######  Query 4 — glossary

```yaml
doc_type = glossary
tags contains:
  - radar
  - rcs
  - doppler
```

---

#####  4. Почему metadata критически важна

Потому что embedding similarity сама по себе недостаточна.

Например:

```text
морская классификация
```

может случайно найти:

```text
classification of marine mammals
```

или:

```text
ocean temperature prediction
```

Семантически они похожи.

Но metadata-фильтры:

```yaml
domain = naval
task_type = classification
data_source = radar
```

резко сужают пространство поиска.

---

#####  5. Важнейшая идея: retrieval идет НЕ только по embedding

В вашей системе retrieval должен быть:

$$
\text{Retrieval}=
\text{Metadata Filter}
+
\text{Semantic Search}
+
\text{Re-ranking}
$$

---

#####  6. Что реально делает retrieval

Например.

---

######  Пользователь

```text
Нужен классификатор морских целей по РЛС
```

---

######  NLU output

```json
{
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar"
}
```

---

######  Retrieval filters

```python
filters = {
    "domain": "naval",
    "task_type": "classification",
    "data_source": "radar"
}
```

---

######  Vector search

```python
semantic_query = """
naval radar target classification
"""
```

---

######  Result

```json
[
  {
    "doc_id": "domain_naval_001",
    "similarity": 0.94
  },
  {
    "doc_id": "feature_radar_rcs_001",
    "similarity": 0.91
  },
  {
    "doc_id": "model_xgboost_naval_001",
    "similarity": 0.89
  }
]
```

---

#####  7. Retrieval идет по типам документов

Это очень важно.

Потому что у вас НЕ одна база знаний.

У вас:

```text
domain_profiles
feature_library
feature_patterns
model_recommendations
glossary
validation_rules
question_templates
interaction_patterns
```

---

#####  8. Поэтому retrieval должен быть многоступенчатым

Не:

```text
user text
→ nearest chunks
```

а:

```text
user text
→ NLU
→ workflow state
→ retrieval planner
→ metadata filters
→ semantic search
→ rerank
→ evidence pack
```

---

#####  9. Evidence pack

В итоге агент получает НЕ сырые документы.

А:

```json
{
  "domain_profile": {...},
  "feature_patterns": [...],
  "model_recommendations": [...],
  "validation_rules": [...],
  "glossary": [...]
}
```

Это называется:

$$
\text{Evidence Pack}
$$

Именно его получает LLM.

---

#####  10. Это уже не просто RAG

Это ближе к:

$$
\text{Knowledge Operating System}
$$

или:

$$
\text{Ontology-Aware Agentic RAG}
$$

---

#####  11. Очень важная архитектурная идея

Metadata — это фактически:

$$
\text{ontology of the system}
$$

То есть:

```yaml
domain
task_type
data_source
feature_family
sensor_type
interpretability
risk_level
temporal_support
requires_sequence
```

создают граф понятий системы.

---

#####  12. На практике retrieval выглядит так

---

######  Feature synthesis agent хочет создать признаки

Он делает retrieval:

```yaml
doc_type = feature_pattern
domain = naval
data_source = radar
interpretability <= high
```

---

######  Validation agent

Ищет:

```yaml
doc_type = validation_rule
task_type = classification
data_type = tabular
```

---

######  Question generator

Ищет:

```yaml
doc_type = question_template
phase = PHASE_2
slot = class_distribution
```

---

######  Model selector

Ищет:

```yaml
doc_type = model_recommendation
task_type = classification
n_features < 50
interpretability = high
```

---

#####  13. Это уже похоже на query planner в БД

Фактически система делает:

$$
\text{user intent}
\rightarrow
\text{retrieval query plan}
$$

как SQL planner.

---

#####  14. Поэтому документы должны быть маленькими

НЕ:

```text
100-страничный PDF
```

а:

```text
маленькие retrieval cards
```

Потому что retrieval идет по:

* semantic meaning;
* metadata;
* tags;
* ontology;
* workflow phase.

---

#####  15. Очень важная идея: metadata позволяет делать deterministic retrieval

Это критично для маленькой LLM.

Например:

---

######  Без metadata

```text
semantic similarity only
```

Результат нестабилен.

---

######  С metadata

```yaml
domain = naval
task_type = classification
data_source = radar
```

результат становится почти deterministic.

---

##### 16. На практике структура retrieval card должна быть примерно такой

```yaml
doc_id: feature_range_rate_001

doc_type: feature_pattern

domain: naval
task_type: classification
data_source: radar

feature_family: kinematic
feature_type: derived

requires_temporal_sequence: true

input_features:
  - range
  - timestamp

output_feature:
  - range_rate

interpretability: high
risk_level: low

retrieval_tags:
  - velocity
  - kinematics
  - derivative
  - radar
  - motion

language: ru
version: 1.0
```

и отдельно:

```markdown
# range_rate

Скорость изменения дальности.

Формула:

range_rate = d(range)/dt

Используется для:
- оценки сближения
- оценки траектории
- оценки маневренности

Требует временной последовательности.
```

---

#####  17. Почему это особенно важно для LangGraph

Потому что каждый агент использует РАЗНЫЕ retrieval filters.

---

######  Example

######  Feature synthesis agent

```yaml
doc_type = feature_pattern
```

---

######  Model selector

```yaml
doc_type = model_recommendation
```

---

######  Validation agent

```yaml
doc_type = validation_rule
```

---

######  Question generator

```yaml
doc_type = question_template
```

---

#####  18. Это приводит к ключевой архитектуре

$$
\text{Agent}
+
\text{Workflow State}
+
\text{Metadata-Aware Retrieval}=
\text{Controlled Reasoning}
$$

---

#####  19. Очень важное следствие

В вашей системе качество будет определяться НЕ столько LLM.

А:

$$
\text{Quality}
\approx
\text{Ontology}
+
\text{Metadata}
+
\text{Retrieval Design}
+
\text{Validation}
$$

---

##### 20. Поэтому вам фактически нужен "knowledge schema"

То есть нужно проектировать:

```text
ontology
metadata schema
document types
retrieval policies
relationships
```

почти как проектируют:

* базы данных;
* knowledge graphs;
* enterprise ontologies.

---

#####  21. Фактически RAG превращается в semi-structured KB

То есть:

```text
RAG ≠ просто vector DB
```

а:

```text
RAG = semantic knowledge platform
```

---

#####  22. Для вашей системы я бы рекомендовал такую модель

---

######  Уровень 1 — Ontology

```text
domain
task_type
data_source
feature_family
model_family
validation_rule
phase
```

---

######  Уровень 2 — Metadata

```yaml
domain: naval
task_type: classification
feature_family: kinematic
```

---

######  Уровень 3 — Embeddings

Semantic similarity.

---

######  Уровень 4 — Graph relationships

Например:

```text
feature_pattern
  → compatible_models
  → required_fields
  → validation_rules
```

---

##### 23. Самая важная мысль

В вашей архитектуре retrieval — это уже часть reasoning.

Не:

```text
retrieve → think
```

а:

$$
\text{retrieve}
\subset
\text{reasoning}
$$

Потому что retrieval определяет:

* что агент знает;
* какие ограничения видит;
* какие признаки может предложить;
* какие модели допустимы;
* какие правила проверки применяются.








### Этап 2. Data Profiling

#### Назначение этапа

На этом этапе система собирает профиль данных. Это нужно, чтобы признаки и модель соответствовали реальной структуре данных.

#### Что система должна выяснить

Минимально:

```text
data_volume
data_type
fields
missing_data_strategy
class_distribution
temporal_importance
```

#### Пример диалога

Система:

```text
Какой примерный объём данных у вас есть?
```

Пользователь:

```text
50000 отметок.
```

Система:

```text
Какие параметры доступны?
```

Пользователь:

```text
Дальность, азимут, угол места, RCS, SNR, доплер.
```

Система:

```text
Есть ли пропуски?
```

Пользователь:

```text
Нет пропусков.
```

Система:

```text
Как распределены классы?
```

Пользователь:

```text
40% мирные суда, 30% военные корабли, 20% подлодки, 10% авиация.
```

Система:

```text
Нужна ли временная динамика?
```

Пользователь:

```text
Нет, каждая отметка независима.
```

#### Итоговый ContextMemory после Data Profiling

```json
{
  "data_volume": 50000,
  "data_type": "tabular",
  "fields": [
    "range",
    "azimuth",
    "elevation",
    "rcs",
    "snr",
    "doppler"
  ],
  "missing_data_strategy": "none",
  "class_distribution": {
    "civilian_ship": 0.4,
    "military_ship": 0.3,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "temporal_importance": false
}
```

В приложенном happy path после Discovery и Profiling контекст действительно содержит `task_type`, `domain`, `data_source`, `target_variable`, `data_volume`, `data_type`, `fields`, `missing_data_strategy`, `class_distribution` и `temporal_importance` .

#### Условие завершения этапа

Этап завершён, если заполнены:

```text
data_volume
data_type
fields
missing_data_strategy
```

Для классификации дополнительно желательно:

```text
class_distribution
```

#### Бизнес-результат

Система получает формальное описание данных:

$$
D =
{x_i, y_i}_{i=1}^{N},
\quad
N = 50000,
\quad
x_i \in \mathbb{R}^{6}.
$$

То есть пользовательская задача уже превращается в ML-форму.

---

### Этап 3. Domain Context

#### Назначение этапа

Этот этап нужен, чтобы признаки были не просто математическими, а **предметно осмысленными**.

Для ML это критично: можно сгенерировать сотни формальных признаков, но большая часть из них может быть бесполезной или физически бессмысленной.

#### Что система уточняет

```text
physical/domain factors
critical factors
environmental constraints
interpretability requirement
operational context
```

#### Пример вопроса

```text
Требуется ли высокая интерпретируемость модели?
Например, чтобы аналитик понимал, почему модель отнесла цель к военному кораблю или подлодке.
```

Пользователь:

```text
Да, интерпретируемость важна.
```

#### Что делает Domain Context Agent

Он обращается к RAG и извлекает доменный профиль:

```json
{
  "domain": "naval",
  "key_factors": [
    "range",
    "rcs",
    "snr",
    "doppler",
    "elevation"
  ],
  "interpretability_importance": "high",
  "typical_sensors": ["radar", "sonar", "camera"],
  "typical_threats": [
    "submarine",
    "military_ship",
    "aircraft"
  ]
}
```

#### Итоговый контекст

```json
{
  "interpretability_requirement": "high",
  "critical_factors": [
    "range",
    "rcs",
    "snr",
    "doppler",
    "elevation"
  ],
  "domain_constraints": [
    "features should be physically interpretable",
    "avoid black-box transformations without explanation"
  ]
}
```

#### Условие завершения этапа

Этап завершён, если заполнены:

```text
domain
interpretability_requirement
critical_factors
```

#### Бизнес-результат

Система понимает, что будущие признаки должны быть:

* объяснимыми;
* связанными с физикой РЛС;
* понятными аналитику;
* пригодными для обсуждения с предметным экспертом.

---

### Этап 4. Feature Synthesis

#### Назначение этапа

На этом этапе система формирует набор признаков.

Признаки делятся на три группы:

```text
base features
derived features
interaction features
```

В happy path Feature Engine генерирует 19 признаков: 6 базовых, 8 производных и 5 interaction-признаков .

#### Базовые признаки

Берутся из исходных полей:

| Признак     | Смысл                         |
| ----------- | ----------------------------- |
| `range`     | дальность до цели             |
| `azimuth`   | азимут                        |
| `elevation` | угол места                    |
| `rcs`       | эффективная площадь рассеяния |
| `snr`       | отношение сигнал/шум          |
| `doppler`   | доплеровский сдвиг            |

#### Производные признаки

Примеры:

| Признак              | Формула / смысл                       |
| -------------------- | ------------------------------------- |
| `signal_quality`     | нормированное качество сигнала        |
| `rcs_normalized`     | $ \log(1 + rcs) $                     |
| `distance_class`     | категория дальности                   |
| `elevation_category` | категория угла места                  |
| `maneuver_index`     | показатель манёвренности              |
| `threat_range`       | приближённая оценка опасной дальности |

#### Interaction-признаки

Примеры:

| Признак               | Формула                     | Смысл                               |
| --------------------- | --------------------------- | ----------------------------------- |
| `range_x_snr`         | $ range \cdot snr $         | дальность с учётом качества сигнала |
| `rcs_x_snr`           | $ rcs \cdot snr $           | видимость цели                      |
| `doppler_x_elevation` | $ doppler \cdot elevation $ | движение с учётом угла места        |

#### Что делает Validation / Critic Agent

Проверяет:

```text
- все ли признаки используют доступные поля;
- нет ли временных признаков, если temporal_importance=false;
- есть ли физический смысл;
- не слишком ли много взаимодействий;
- нет ли дублирования;
- нет ли слишком высокой корреляции;
- можно ли признаки посчитать в коде.
```

Например:

```text
range_acceleration нельзя использовать, если нет временной последовательности.
```

#### Пример результата

```json
{
  "base_features": 6,
  "derived_features": 8,
  "interaction_features": 5,
  "total_features": 19,
  "validation_status": "passed",
  "feature_synthesis_confirmed": true
}
```

#### Условие завершения этапа

Этап завершён, если:

```text
final_features не пустой
feature validation passed
user confirmed feature set
```

#### Бизнес-результат

Появляется подтверждённый feature set:

$$
\phi(x)=
(
\phi_1(x),
\phi_2(x),
\dots,
\phi_m(x)
),
\quad
m = 19.
$$

То есть исходные данные превращаются в пространство признаков для ML-модели.

---

### Этап 5. Data Generation

#### Назначение этапа

Система генерирует синтетическую обучающую выборку на основе утверждённых признаков.

Это нужно, чтобы пользователь получил воспроизводимый прототип ML pipeline даже до подключения реальных данных.

#### Вход этапа

```json
{
  "final_features": "...",
  "n_samples": 100000,
  "class_distribution": [0.4, 0.3, 0.2, 0.1],
  "noise_level": 0.01,
  "anomaly_rate": 0.02
}
```

В happy path Data Generator создаёт выборку `100k × 19`, реалистичные распределения, зависимости, шум и аномалии .

#### Что генерируется

```text
X_train.csv
y_train.npy
metadata.json
```

#### Пример результата

```json
{
  "X_shape": [100000, 19],
  "y_shape": [100000],
  "class_distribution": {
    "civilian_ship": 0.4,
    "military_ship": 0.3,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "files": {
    "X_train": "X_train.csv",
    "y_train": "y_train.npy",
    "metadata": "metadata.json"
  }
}
```

#### Проверки

Система должна проверить:

```text
X_shape_correct
y_shape_correct
no_nan
no_inf
valid_y_values
class_distribution_balanced
```

#### Условие завершения этапа

Этап завершён, если:

```text
data_X_path заполнен
data_y_path заполнен
metadata создана
validation passed
```

#### Бизнес-результат

Система создаёт обучающую выборку:

$$
X \in \mathbb{R}^{100000 \times 19},
\quad
y \in {0,1,2,3}^{100000}.
$$

---

### Этап 6. Model Selection

#### Назначение этапа

Система рекомендует подходящую ML-модель и создаёт training config.

#### Вход этапа

```json
{
  "task_type": "classification",
  "data_type": "tabular",
  "n_features": 19,
  "n_classes": 4,
  "interpretability_requirement": "high",
  "data_volume": 100000
}
```

#### Что делает Model Selection Agent

Он выбирает top-N моделей.

Например:

| Rank | Модель        | Причина                                                  |
| ---- | ------------- | -------------------------------------------------------- |
| 1    | XGBoost       | высокая точность на табличных данных, feature importance |
| 2    | LightGBM      | быстрее XGBoost                                          |
| 3    | Random Forest | хорошая интерпретируемость и baseline                    |

В happy path Model Selector использует RAG-рекомендации, hyperparameter templates и expected performance metrics .

#### Training config

Пример:

```yaml
model: XGBoost
task_type: classification
n_classes: 4
n_features: 19

hyperparameters:
  objective: multi:softprob
  num_class: 4
  n_estimators: 200
  max_depth: 7
  learning_rate: 0.05
  subsample: 0.8
  colsample_bytree: 0.8
  seed: 42

preprocessing:
  scaler: StandardScaler
  missing_values: none
  outliers: clip

validation:
  strategy: stratified_k_fold
  n_splits: 5
  test_size: 0.2

metrics:
  - accuracy
  - precision
  - recall
  - f1
  - auc_roc
```

#### Условие завершения этапа

Этап завершён, если:

```text
recommended_models сформированы
selected_model выбран
training_config создан
```

#### Бизнес-результат

Пользователь получает обоснованную ML-рекомендацию:

$$
\hat{f}=
\arg\max_{f \in \mathcal{M}}
\text{Score}(f \mid D, \phi, C),
$$

где:

* $\mathcal{M}$ — множество моделей;
* $D$ — данные;
* $\phi$ — признаки;
* $C$ — бизнес-ограничения.

---

### Этап 7. Export

#### Назначение этапа

Финальный этап превращает накопленный контекст в готовые файлы.

#### Что экспортируется

Минимальный набор:

```text
features.json
config.yaml
pipeline.py
data_generator.py
metadata.json
archive.zip
```

В happy path Export Engine создаёт multi-format artifacts, code templates, documentation, archive и download delivery .

#### Содержание артефактов

##### `features.json`

Описание всех признаков:

```json
{
  "version": "1.0",
  "total_features": 19,
  "features": [
    {
      "name": "range",
      "type": "float",
      "description": "Дальность до цели",
      "unit": "km",
      "role": "base"
    }
  ]
}
```

##### `config.yaml`

Конфигурация модели и обучения.

##### `pipeline.py`

Готовый код:

```text
load_data
preprocess
train
evaluate
predict
save_model
```

##### `data_generator.py`

Код для воспроизводимой генерации synthetic data.

##### `metadata.json`

Сводка:

```json
{
  "task": "classification",
  "domain": "naval",
  "data_source": "radar",
  "n_features": 19,
  "model": "XGBoost",
  "artifacts": [...]
}
```

#### Условие завершения этапа

Этап завершён, если:

```text
features_json_path exists
config_yaml_path exists
pipeline_py_path exists
data_generator_py_path exists
metadata_json_path exists
export_archive_path exists
download_link generated
```

#### Бизнес-результат

Пользователь получает готовый архив, который можно скачать и использовать как стартовый ML-проект.

---

#### Итоговое состояние после happy path

После прохождения всех этапов `ContextMemory` содержит:

```json
{
  "task_type": "classification",
  "target_variable": "target_type",
  "domain": "naval",
  "data_source": "radar",

  "data_volume": 50000,
  "data_type": "tabular",
  "fields": ["range", "azimuth", "elevation", "rcs", "snr", "doppler"],
  "missing_data_strategy": "none",
  "class_distribution": [0.4, 0.3, 0.2, 0.1],
  "temporal_importance": false,

  "interpretability_requirement": "high",
  "critical_factors": ["range", "rcs", "snr", "doppler", "elevation"],

  "base_features": 6,
  "derived_features": 8,
  "interaction_features": 5,
  "final_features": 19,

  "n_samples": 100000,
  "recommended_model": "XGBoost",
  "training_config": "config.yaml",

  "artifacts": [
    "features.json",
    "config.yaml",
    "pipeline.py",
    "data_generator.py",
    "metadata.json",
    "archive.zip"
  ]
}
```

---

### Сводная таблица happy path в расширенном виде

| Этап                 | Вход                   | Действие системы                        | Выход                           | Критерий завершения                        |
| -------------------- | ---------------------- | --------------------------------------- | ------------------------------- | ------------------------------------------ |
| 0. Инициализация     | Открытие интерфейса    | Создать сессию и пустой context         | `conversation_id`               | Сессия сохранена                           |
| 1. Discovery         | Описание задачи        | Извлечь task/domain/source/target       | Формальная постановка ML-задачи | Обязательные слоты заполнены               |
| 2. Data Profiling    | Ответы о данных        | Собрать профиль данных                  | `data_profile`                  | Есть объём, тип, поля, пропуски            |
| 3. Domain Context    | Ответы о домене        | Уточнить физический смысл и ограничения | `domain_context`                | Есть интерпретируемость и critical factors |
| 4. Feature Synthesis | Профиль данных и домен | Сгенерировать и проверить признаки      | `final_features`                | Признаки подтверждены                      |
| 5. Data Generation   | `final_features`       | Создать synthetic dataset               | `X_train`, `y_train`, metadata  | Данные валидны                             |
| 6. Model Selection   | Данные + признаки      | Подобрать модель и config               | `training_config`               | Модель выбрана                             |
| 7. Export            | Полный context         | Создать файлы и архив                   | `archive.zip`                   | Ссылка на скачивание готова                |

Главная идея happy path: **каждая фаза добавляет в ContextMemory новый слой формализации**, пока исходный неформальный запрос пользователя не превращается в готовый ML-проект.



## 5.2. Альтернативные сценарии

Система должна поддерживать:

1. Неполное описание задачи — бот задаёт уточняющие вопросы.
2. Низкая уверенность NLU — бот предлагает варианты интерпретации.
3. Неизвестный домен — бот использует общий режим и просит описание.
4. Неизвестные поля данных — бот уточняет смысл полей и сохраняет их как custom fields.
5. Пользователь хочет изменить признаки — система возвращается в Feature Synthesis.
6. Пользователь хочет добавить временные признаки — система пересчитывает feature set.
7. Пользователь хочет другую модель — система возвращается в Model Selection.
8. Пользователь хочет начать заново — система сбрасывает контекст и создаёт новую сессию.
9. Ошибка генерации артефакта — система сообщает о причине и повторяет генерацию.
10. Недостаточно RAG-контекста — система не должна выдумывать факты, а должна запросить уточнение или перейти в fallback.

---

# 6. Мультиагентная модель

## 6.1. Перечень агентов

| Агент                       | Бизнес-назначение                                 | Основной вход                              | Основной выход                         |
| --------------------------- | ------------------------------------------------- | ------------------------------------------ | -------------------------------------- |
| `SessionAgent`              | Создание и восстановление пользовательской сессии | Запрос `/start`, `conversation_id`         | Активная сессия                        |
| `NLUAgent`                  | Понимание пользовательского ввода                 | Текст пользователя                         | Intent, entities, confidence           |
| `RAGRetrievalAgent`         | Поиск релевантного контекста                      | Запрос, текущая фаза, metadata filters     | Evidence pack                          |
| `DialogueOrchestratorAgent` | Управление переходами между фазами                | ParsedInput, ContextMemory                 | Следующая фаза, вопрос, действие       |
| `ContextMemoryAgent`        | Ведение состояния диалога                         | Извлечённые сущности, ответы пользователя  | Обновлённый context                    |
| `TaskDiscoveryAgent`        | Определение ML-задачи                             | Intent, entities                           | task_type, target_variable, domain     |
| `DataProfilingAgent`        | Сбор профиля данных                               | Ответы пользователя, RAG-словарь           | data_profile                           |
| `DomainContextAgent`        | Уточнение предметного контекста                   | domain, task_type, data_source             | critical_factors, interpretability     |
| `FeatureSynthesisAgent`     | Генерация базовых и производных признаков         | fields, domain, data_source                | candidate feature set                  |
| `FeatureCriticAgent`        | Проверка признаков                                | feature set                                | validation comments, rejected features |
| `MulticollinearityAgent`    | Проверка корреляций/VIF                           | feature set, данные или RAG-профиль        | multicollinearity report               |
| `DataGenerationAgent`       | Генерация синтетической выборки                   | feature set, n_samples, class_distribution | X/y files, metadata                    |
| `ModelSelectionAgent`       | Рекомендация модели                               | task_type, features, constraints           | top-N models, training config          |
| `ExportAgent`               | Подготовка артефактов                             | context, features, config, data paths      | zip archive, links                     |
| `FeedbackAgent`             | Обработка подтверждений и изменений               | user feedback                              | route back / confirm                   |
| `AuditAgent`                | Запись событий и решений                          | state changes, agent outputs               | audit log                              |

## 6.2. Бизнес-правила работы агентов

1. Каждый агент должен иметь ограниченную ответственность.
2. Каждый агент должен возвращать структурированный результат.
3. Агент не должен изменять состояние напрямую, кроме `ContextMemoryAgent` или оркестратора.
4. Любой результат LLM должен проходить поствалидацию.
5. Агент не должен придумывать доменные факты, если они отсутствуют в RAG.
6. Агент должен передавать `confidence`.
7. При `confidence < threshold` система должна задавать уточняющий вопрос.
8. Все решения, влияющие на итоговый feature set, должны быть сохранены в истории.
9. Результаты генерации признаков должны быть объяснимы пользователю.
10. Генерация артефактов должна быть воспроизводимой.

---

# 7. Функциональные требования

Ниже требования оформлены в формате `BR-FR-XXX`.

---

## 7.1. Инициализация и управление сессией

### BR-FR-001. Создание новой сессии

Система должна создавать новую сессию при старте диалога.

**Бизнес-правила:**

1. Каждая сессия должна иметь уникальный `conversation_id`.
2. Для каждой сессии должен быть создан пустой или базовый `ContextMemory`.
3. Начальная фаза должна быть `PHASE_1_TASK_DISCOVERY`.
4. Пользователь должен получить приветственное сообщение.
5. Сессия должна быть сохранена в БД.

В happy path описано, что при `/api/start` генерируется `conversation_id`, инициализируются `ContextMemory` и `DialogueEngine`, затем запись сохраняется в БД и возвращается приветственное сообщение .

### BR-FR-002. Восстановление сессии

Система должна восстанавливать состояние диалога по `conversation_id`.

**Критерии:**

1. Пользователь продолжает с той же фазы.
2. Контекст не теряется.
3. История сообщений доступна для аудита.
4. Артефакты, если были созданы, остаются привязанными к сессии.

### BR-FR-003. Сброс сессии

Система должна поддерживать команду restart.

В приложенном плане intent `restart` описан как реакция на фразы «Заново», «Начнем с начала» и должен приводить к сбросу контекста .

---

## 7.2. NLU и понимание пользовательского ввода

### BR-FR-010. Классификация намерений

Система должна классифицировать пользовательские намерения.

Минимальный набор intents:

| Intent             | Назначение                                   |
| ------------------ | -------------------------------------------- |
| `describe_task`    | Пользователь описывает ML-задачу             |
| `describe_data`    | Пользователь описывает данные                |
| `request_features` | Пользователь просит предложить признаки      |
| `clarify_feature`  | Пользователь просит объяснить признак        |
| `confirm_features` | Пользователь подтверждает feature set        |
| `generate_data`    | Пользователь просит сгенерировать выборку    |
| `recommend_model`  | Пользователь просит подобрать модель         |
| `export_config`    | Пользователь просит экспортировать результат |
| `restart`          | Пользователь хочет начать заново             |

Этот набор intents приведён в плане разработки как основа NLU-модуля .

### BR-FR-011. Извлечение сущностей

Система должна извлекать из текста пользователя следующие сущности:

1. `task_type`
2. `target_variable`
3. `domain`
4. `data_source`
5. `data_type`
6. `data_volume`
7. `fields`
8. `missing_data_strategy`
9. `class_distribution`
10. `temporal_importance`
11. `interpretability_requirement`
12. `n_samples`
13. `model_preference`
14. `export_format`

В приложенном плане указаны регулярные паттерны для сущностей `task_type`, `data_type`, `data_source`, `target_variable`, а также двуязычные варианты на русском и английском .

### BR-FR-012. Оценка уверенности

Система должна вычислять confidence для intent и каждой извлечённой сущности.

**Бизнес-правила:**

1. Если confidence высокий — система продолжает процесс.
2. Если confidence средний — система подтверждает интерпретацию.
3. Если confidence низкий — система задаёт уточняющий вопрос.
4. Confidence должен сохраняться в state.

В happy path NLU возвращает `intent`, `confidence`, `entities`, `clarity`, `missing_slots` и `rag_context`; пример показывает confidence 0.98 для intent и отдельные confidence для `task_type`, `domain`, `data_source`, `target_variable` .

### BR-FR-013. Анализ ясности запроса

Система должна рассчитывать показатель ясности запроса.

**Формула:**

$$
\text{clarity_score}=
\frac{\text{slots_provided}}{\text{total_slots}}
\times
\text{user_confidence_score}
$$

Если `clarity_score` ниже порога, система должна не переходить к следующей фазе, а уточнять недостающую информацию.

---

## 7.3. RAG и база знаний

### BR-FR-020. Использование RAG на всех содержательных этапах

Система должна использовать RAG для:

1. Нормализации терминов.
2. Подбора доменного контекста.
3. Подбора feature patterns.
4. Проверки физических смыслов признаков.
5. Рекомендации моделей.
6. Формирования шаблонов вопросов.
7. Генерации объяснений.

В happy path NLU включает RAG retrieval, intent classification, entity extraction with RAG-based normalization и clarity analysis .

### BR-FR-021. Структура RAG-индекса

RAG-индекс должен включать следующие коллекции:

| Коллекция               | Назначение                                  |
| ----------------------- | ------------------------------------------- |
| `domain_profiles`       | Описания предметных областей                |
| `feature_library`       | Базовые, производные и interaction-признаки |
| `model_recommendations` | Рекомендации моделей и гиперпараметров      |
| `question_templates`    | Шаблоны вопросов для фаз                    |
| `glossary`              | Термины, синонимы, нормализация             |
| `model_configs`         | Шаблоны training config                     |
| `feature_analysis`      | Корреляции, VIF, мультиколлинеарность       |
| `response_templates`    | Шаблоны подтверждений и объяснений          |

В документе описан RAG-индекс с 12 500 документами, embedding dimension 384 и коллекциями `domain_profiles`, `feature_library`, `model_recommendations`, `question_templates`, `glossary` .

### BR-FR-022. Требования к RAG-документам

Каждый RAG-документ должен иметь:

```yaml
doc_id: string
doc_type: string
domain: string
task_type: string | null
data_source: string | null
feature_type: string | null
feature_name: string | null
tags: list[string]
version: string
owner: string
last_updated_at: datetime
confidence_level: high | medium | low
source_type: domain_profile | feature_library | model_recommendation | glossary | question_template
```

### BR-FR-023. Evidence-based generation

Каждая рекомендация признака, модели или вопроса должна быть основана на RAG evidence.

**Критерии:**

1. Внутри agent output должен быть список `evidence_doc_ids`.
2. Если evidence отсутствует, агент должен вернуть `need_more_context = true`.
3. Пользовательский интерфейс должен иметь возможность показать, почему был выбран признак или модель.

---

## 7.4. Оркестрация диалога

### BR-FR-030. Управление фазами

Система должна управлять диалогом как фазовым процессом:

```text
START
→ PHASE_1_TASK_DISCOVERY
→ PHASE_2_DATA_PROFILING
→ PHASE_3_DOMAIN_CONTEXT
→ PHASE_4_FEATURE_SYNTHESIS
→ PHASE_5_DATA_GENERATION
→ PHASE_6_MODEL_SELECTION
→ PHASE_7_EXPORT
→ COMPLETE
```

Граф фаз приведён в плане разработки: от уточнения задачи и профилирования данных до feature synthesis, data generation, model selection и export .

### BR-FR-031. Проверка завершённости фазы

Система должна переходить на следующую фазу только после выполнения completion criteria.

Пример обязательных условий:

| Фаза              | Условие завершения                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------- |
| Discovery         | Заполнены `task_type`, `target_variable`, желательно `domain` и `data_source`                           |
| Data Profiling    | Заполнены `data_source`, `data_type`, `fields`, `data_volume`; для классификации — `class_distribution` |
| Domain Context    | Заполнены `domain`, `interpretability_requirement`, критичные факторы                                   |
| Feature Synthesis | Сформирован и подтверждён `final_features`                                                              |
| Data Generation   | Сгенерированы X/y, metadata и пути к файлам                                                             |
| Model Selection   | Выбрана модель и создан `training_config`                                                               |
| Export            | Созданы основные артефакты и архив                                                                      |

В плане описана проверка завершённости фазы через `ContextMemory.is_phase_complete`, где для разных фаз требуются разные ключи, например `task_type`, `target_variable`, `data_source`, `data_type`, `fields`, `domain`, `interpretability_requirement`, `final_features`, `n_samples`, `recommended_model` .

### BR-FR-032. Возврат к предыдущей фазе

Система должна позволять пользователю вернуться к предыдущей фазе, если он хочет изменить:

1. Целевую переменную.
2. Источник данных.
3. Поля.
4. Домен.
5. Требования к интерпретируемости.
6. Количество признаков.
7. Размер синтетической выборки.
8. Модель.
9. Формат экспорта.

---

## 7.5. ContextMemory

### BR-FR-040. Хранение контекста

Система должна хранить структурированный контекст по всем фазам.

Минимальный состав `ContextMemory`:

```yaml
# Единая память состояния диалога и ML-проекта.
ContextMemory:

  # Тип ML-задачи.
  task_type: classification

  # Целевая переменная, которую предсказывает модель.
  target_variable: target_class

  # Требуемая задержка инференса или режима работы.
  required_latency: "batch/offline"

  # Контекст внедрения модели: прототип, сервер, edge, offline.
  deployment_context: "prototype"

  # Источник данных для признаков.
  data_source: radar

  # Тип данных: tabular, time_series, image, tensor, graph.
  data_type: tabular

  # Количество доступных наблюдений.
  data_volume: 50000

  # Частота обновления данных; null означает, что пока неизвестно.
  update_frequency: null

  # Список исходных полей данных.
  fields:

    # Дальность до цели.
    - range

    # Азимут цели.
    - azimuth

    # Угол места.
    - elevation

    # Эффективная поверхность рассеяния.
    - rcs

    # Отношение сигнал/шум.
    - snr

    # Доплеровская скорость.
    - doppler

  # Стратегия обработки пропусков.
  missing_data_strategy: none

  # Распределение классов целевой переменной.
  class_distribution:

    # Доля класса гражданских судов.
    civilian_ship: 0.4

    # Доля класса военных кораблей.
    military_ship: 0.3

    # Доля класса подводных лодок.
    submarine: 0.2

    # Доля класса воздушных целей.
    aircraft: 0.1

  # Предметная область задачи.
  domain: naval

  # Список критичных факторов предметной области.
  critical_factors:

    # RCS важен для различения типов целей.
    - rcs

    # SNR важен для оценки качества обнаружения.
    - snr

    # Doppler важен для оценки движения цели.
    - doppler

    # Фактор качества работы радара.
    - radar_performance_factor

    # Уровень помех.
    - jamming_level

  # Требование к объяснимости модели.
  interpretability_requirement: high

  # Нужно ли учитывать временную динамику.
  temporal_importance: false

  # Базовые признаки, напрямую взятые из данных.
  base_features:

    # Базовый признак дальности.
    - range

    # Базовый признак азимута.
    - azimuth

    # Базовый признак угла места.
    - elevation

    # Базовый признак радиолокационной заметности.
    - rcs

    # Базовый признак качества сигнала.
    - snr

    # Базовый признак радиальной скорости.
    - doppler

  # Производные признаки, рассчитанные из базовых.
  derived_features:

    # Производное качество сигнала.
    - signal_quality

    # Нормализованный RCS.
    - rcs_normalized

    # Категория угла места.
    - elevation_category

    # Категория дальности.
    - distance_class

  # Признаки взаимодействия между базовыми признаками.
  interaction_features:

    # Взаимодействие дальности и SNR.
    - range_x_snr

    # Взаимодействие RCS и SNR.
    - rcs_x_snr

    # Взаимодействие Doppler и elevation.
    - doppler_x_elevation

  # Финальный утверждённый набор признаков.
  final_features:

    # Итоговый признак дальности.
    - range

    # Итоговый признак азимута.
    - azimuth

    # Итоговый признак угла места.
    - elevation

    # Итоговый признак RCS.
    - rcs

    # Итоговый признак SNR.
    - snr

    # Итоговый признак Doppler.
    - doppler

    # Итоговое качество сигнала.
    - signal_quality

    # Итоговый нормализованный RCS.
    - rcs_normalized

    # Итоговая категория elevation.
    - elevation_category

    # Итоговая категория дальности.
    - distance_class

    # Итоговое взаимодействие range и SNR.
    - range_x_snr

    # Итоговое взаимодействие RCS и SNR.
    - rcs_x_snr

    # Итоговое взаимодействие Doppler и elevation.
    - doppler_x_elevation

  # Количество синтетических обучающих примеров.
  n_samples: 100000

  # Отношение доли самого частого класса к самому редкому.
  class_imbalance_ratio: 4.0

  # Уровень добавляемого шума в synthetic data.
  noise_level: 0.01

  # Доля аномальных наблюдений.
  anomaly_rate: 0.02

  # Рекомендованная модель.
  recommended_model: XGBoostClassifier

  # Ранжированный список моделей-кандидатов.
  model_ranking:

    # Первый кандидат в списке моделей.
    - model: XGBoostClassifier

      # Причина выбора первого кандидата.
      reason: "good for tabular multiclass classification"

    # Второй кандидат в списке моделей.
    - model: RandomForestClassifier

      # Причина выбора второго кандидата.
      reason: "robust baseline and interpretable feature importance"

    # Третий кандидат в списке моделей.
    - model: BayesianNetwork

      # Причина выбора третьего кандидата.
      reason: "high interpretability for operator-facing decision support"

  # Конфигурация обучения модели.
  training_config:

    # Разбиение выборки на train, validation и test.
    split:

      # Доля обучающей выборки.
      train: 0.7

      # Доля validation-выборки.
      validation: 0.15

      # Доля test-выборки.
      test: 0.15

    # Метрики качества модели.
    metrics:

      # Macro F1 для многоклассовой классификации.
      - f1_macro

      # Balanced accuracy для дисбаланса классов.
      - balanced_accuracy

      # Матрица ошибок для анализа классов.
      - confusion_matrix

    # Использование балансировки весов классов.
    class_weight: balanced

    # Seed для воспроизводимости.
    random_state: 42

  # Идентификатор диалоговой сессии.
  conversation_id: conv_001

  # Список обратной связи и решений пользователя.
  user_feedback:

    # Первая запись пользовательской обратной связи.
    - phase: data_profiling

      # Текст, сказанный пользователем.
      message: "No missing values"

      # Действие, выполненное системой.
      action: "missing_data_strategy set to none"

    # Вторая запись пользовательской обратной связи.
    - phase: feature_synthesis

      # Текст, сказанный пользователем.
      message: "Each radar mark is independent"

      # Действие, выполненное системой.
      action: "temporal features removed"
```

В приложенном плане `ContextMemory` содержит блоки Discovery, Data Profiling, Domain Context, Features, Data Generation, Model Selection и служебную информацию, включая `conversation_id` и `user_feedback` .

### BR-FR-041. Валидация обновлений контекста

Каждое обновление контекста должно проходить валидацию.

Примеры бизнес-правил:

1. `task_type` должен принадлежать допустимому списку.
2. `domain` должен принадлежать допустимому списку или быть помечен как custom.
3. `data_type` должен принадлежать допустимому списку.
4. `n_samples` должен быть целым числом в допустимых границах.
5. `fields` не должны быть пустыми после завершения Data Profiling.
6. При изменении upstream-слота downstream-артефакты должны инвалидироваться.

В плане приведены validation rules для `task_type`, `domain`, `data_type`, `n_samples`, включая ограничение `n_samples` от 1000 до 1 000 000 .

---

# 8. Требования по фазам

## 8.1. Phase 1 — Task Discovery

### BR-FR-050. Определение типа задачи

Система должна определить тип ML-задачи.

Поддерживаемые значения:

1. `classification`
2. `regression`
3. `clustering`
4. `anomaly_detection`
5. `ranking`

### BR-FR-051. Определение целевой переменной

Для supervised-задач система должна запросить целевую переменную.

Примеры:

```text
класс цели
тип объекта
уровень угрозы
вероятность события
числовой показатель
```

### BR-FR-052. Определение домена и источника данных

Система должна определить или запросить:

1. Домен: `naval`, `air`, `ground`, `cyber`, `analytical`, custom.
2. Источник данных: `radar`, `sonar`, `camera`, `SIGINT`, `OSINT`, `satellite`, `SQL`, `CSV`, custom.

---

## 8.2. Phase 2 — Data Profiling

### BR-FR-060. Сбор профиля данных

Система должна собрать:

1. Источник данных.
2. Тип данных.
3. Объём данных.
4. Частоту обновления.
5. Список полей.
6. Наличие пропусков.
7. Стратегию обработки пропусков.
8. Баланс классов для классификации.
9. Признак временной динамики.

В happy path пример Data Profiling собирает `data_volume = 50000`, `data_type = tabular`, `fields = [range, azimuth, elevation, rcs, snr, doppler]`, `missing_data_strategy = none`, `class_distribution = [0.4, 0.3, 0.2, 0.1]`, `temporal_importance = False` .

### BR-FR-061. Нормализация полей

Система должна нормализовать пользовательские названия полей.

Пример:

| Ввод пользователя | Нормализованное имя |
| ----------------- | ------------------- |
| дальность         | `range`             |
| азимут            | `azimuth`           |
| угол места        | `elevation`         |
| RCS / ЭПР         | `rcs`               |
| SNR               | `snr`               |
| доплер            | `doppler`           |

### BR-FR-062. Обработка неизвестных полей

Если поле не найдено в glossary:

1. Система должна попытаться найти ближайшее совпадение.
2. Если совпадение не найдено, система должна запросить пояснение.
3. После пояснения поле может быть добавлено как custom field.
4. Custom field должен быть помечен как требующий проверки экспертом.

---

## 8.3. Phase 3 — Domain Context

### BR-FR-070. Уточнение доменного контекста

Система должна определить:

1. Физический/предметный домен.
2. Операционный контекст.
3. Критичные факторы.
4. Требования к интерпретируемости.
5. Требования к точности.
6. Требования к latency, если пользователь их указал.
7. Важность временной динамики.

### BR-FR-071. Выявление критичных факторов

Для каждого домена система должна извлекать из RAG key factors.

Пример для морского домена:

1. Волнение моря.
2. Термоклин.
3. Видимость.
4. Вариация RCS.
5. Типичные угрозы.
6. Типичные сенсоры.

В happy path для `domain_naval_001` указаны key factors вроде `sea_state`, `thermocline`, `visibility`, `rcs_variation`, а также типичные угрозы и операционный контекст .

### BR-FR-072. Требования к интерпретируемости

Система должна поддерживать три уровня:

| Уровень | Бизнес-смысл                                       |
| ------- | -------------------------------------------------- |
| high    | Решения должны быть понятны аналитикам и экспертам |
| medium  | Баланс точности и объяснимости                     |
| low     | Приоритет максимальной предсказательной силы       |

Если интерпретируемость `high`, система должна предпочитать признаки с физическим смыслом и модели с feature importance / explainability.

---

## 8.4. Phase 4 — Feature Synthesis

### BR-FR-080. Генерация базовых признаков

Система должна выбрать базовые признаки на основе:

1. Домена.
2. Источника данных.
3. Полей, указанных пользователем.
4. RAG feature library.

Для примера `naval_radar` базовые признаки включают `range`, `azimuth`, `elevation`, `rcs`, `snr`, `doppler` .

### BR-FR-081. Генерация производных признаков

Система должна генерировать производные признаки на основе:

1. Физического смысла.
2. Типа ML-задачи.
3. Требований к интерпретируемости.
4. Наличия временной динамики.
5. RAG examples.

Примеры:

```text
range_rate
signal_quality
threat_range
bearing_rate
maneuver_index
rcs_normalized
elevation_category
distance_class
```

### BR-FR-082. Генерация признаков взаимодействия

Система должна предлагать interaction features.

Примеры:

```text
range_x_snr
rcs_x_snr
doppler_x_elevation
range_x_azimuth
rcs_x_range
```

В happy path Feature Engine генерирует 19 признаков как 6 базовых, 8 производных и 5 взаимодействий, используя RAG-sourced domain patterns и проверку мультиколлинеарности .

### BR-FR-083. Объяснение признаков

Каждый признак должен содержать:

```yaml
name: string
role: base | derived | interaction | temporal | statistical
type: float | int | categorical | datetime | bool
description: string
formula: string | null
unit: string | null
source_fields: list[string]
domain_interpretation: string
business_value: string
risk_level: low | medium | high
evidence_doc_ids: list[string]
```

### BR-FR-084. Подтверждение пользователем

Перед переходом к генерации данных пользователь должен подтвердить набор признаков.

**Система должна поддерживать команды:**

1. «Согласен».
2. «Добавь признак».
3. «Убери признак».
4. «Объясни признак».
5. «Добавь временные признаки».
6. «Сделай меньше признаков».
7. «Сделай более интерпретируемо».

---

## 8.5. Phase 5 — Data Generation

### BR-FR-090. Генерация синтетической обучающей выборки

Система должна генерировать синтетические данные на основе:

1. Набора признаков.
2. Типа задачи.
3. Количества классов.
4. Баланса классов.
5. Количества примеров.
6. Уровня шума.
7. Доли аномалий.
8. Seed для воспроизводимости.

В happy path Data Generator описан как компонент для synthetic data creation `100k × 19`, realistic distributions & dependencies, noise & anomalies simulation .

### BR-FR-091. Настройки генерации

Минимальные параметры:

```yaml
n_samples: int
class_distribution: dict | null
random_state: int
noise_level: float
anomaly_rate: float
n_features: int
n_classes: int | null
```

В приложенном happy path пример использует `n_samples = 100000`, `class_distribution = [0.4, 0.3, 0.2, 0.1]`, `random_state = 42`, `noise_level = 0.01`, `anomaly_rate = 0.02` .

### BR-FR-092. Валидация сгенерированных данных

Система должна проверять:

1. Shape X.
2. Shape y.
3. Отсутствие NaN.
4. Отсутствие inf.
5. Допустимые значения target.
6. Соответствие балансу классов.
7. Наличие metadata.

В happy path валидация проверяет `X_shape_correct`, `y_shape_correct`, `no_nan`, `no_inf`, `valid_y_values`, `class_distribution_balanced` .

### BR-FR-093. Сохранение данных

Система должна сохранять:

1. `X_train.csv`
2. `y_train.npy`
3. `metadata.json`

Документ happy path описывает сохранение X в CSV, y в NPY и метаданных с количеством примеров, количеством признаков, классами, распределением классов и размерами файлов .

---

## 8.6. Phase 6 — Model Selection

### BR-FR-100. Рекомендация моделей

Система должна рекомендовать top-N моделей на основе:

1. Типа задачи.
2. Домена.
3. Типа данных.
4. Количества признаков.
5. Количества классов.
6. Требований к интерпретируемости.
7. Ограничений по скорости и точности.
8. RAG model recommendations.

В happy path Model Selector использует RAG-based recommendations, hyperparameter templates и expected performance metrics .

### BR-FR-101. Минимальный набор моделей

Система должна поддерживать рекомендации для:

| Тип задачи        | Модели                                                  |
| ----------------- | ------------------------------------------------------- |
| Classification    | XGBoost, LightGBM, Random Forest, SVM, Neural Network   |
| Regression        | XGBoost, LightGBM, Random Forest, Linear/Elastic models |
| Clustering        | KMeans, DBSCAN, Gaussian Mixture                        |
| Anomaly Detection | Isolation Forest, One-Class SVM, Autoencoder            |
| Ranking           | Learning-to-rank модели, gradient boosting ranking      |

### BR-FR-102. Обоснование выбора модели

Для каждой модели система должна объяснить:

1. Почему подходит.
2. Преимущества.
3. Ограничения.
4. Ожидаемую точность или диапазон качества, если доступно в RAG.
5. Время обучения, если доступно.
6. Требования к preprocessing.
7. Интерпретируемость.

Пример в приложенном сценарии рекомендует XGBoost, LightGBM и Random Forest, указывает преимущества, недостатки, гиперпараметры, ожидаемую точность и использование feature importance для интерпретации .

### BR-FR-103. Генерация training config

Система должна формировать `training_config`.

Минимальная структура:

```yaml
model: string
task_type: string
domain: string
n_classes: int | null
n_features: int
hyperparameters: dict
preprocessing:
  scaler: string
  missing_values: string
  outliers: string
validation:
  strategy: string
  n_splits: int
  random_state: int
  test_size: float
metrics: list[string]
early_stopping:
  enabled: bool
  rounds: int
  metric: string
```

В happy path `generate_training_config` формирует конфиг для XGBoost с objective, num_class, n_estimators, max_depth, learning_rate, subsample, colsample_bytree, seed, preprocessing, validation, metrics и early stopping .

---

## 8.7. Phase 7 — Export

### BR-FR-110. Экспорт артефактов

Система должна экспортировать минимум пять артефактов:

1. `features.json`
2. `config.yaml`
3. `pipeline.py`
4. `data_generator.py`
5. `metadata.json`

Также система должна создать `.zip` архив.

В happy path ExportPhase генерирует `features.json`, `config.yaml`, `pipeline.py`, `data_generator.py`, `metadata.json` и архив . В плане разработки экспорт также включает feature set, data generator, training config, metadata и pipeline .

### BR-FR-111. Требования к `features.json`

`features.json` должен содержать:

```json
{
  "version": "1.0",
  "timestamp": "...",
  "total_features": 19,
  "features": [
    {
      "index": 0,
      "name": "range",
      "type": "float",
      "description": "Дальность до цели",
      "unit": "km",
      "formula": null,
      "role": "base"
    }
  ]
}
```

### BR-FR-112. Требования к `config.yaml`

`config.yaml` должен содержать:

1. Тип задачи.
2. Домен.
3. Модель.
4. Гиперпараметры.
5. Preprocessing.
6. Validation strategy.
7. Metrics.
8. Early stopping.

### BR-FR-113. Требования к `pipeline.py`

`pipeline.py` должен быть готовым к запуску и включать:

1. Загрузку данных.
2. Preprocessing.
3. Обучение.
4. Оценку.
5. Predict.
6. Сохранение модели.
7. Логирование.
8. Комментарии и docstrings.

В happy path prompt для генерации `pipeline.py` требует класс `MLPipeline` с методами `load_data`, `preprocess`, `train`, `evaluate`, `predict`, `save_model`, main-блок, использование sklearn/xgboost/pandas/numpy, комментарии, обработку ошибок и docstrings .

### BR-FR-114. Требования к `metadata.json`

`metadata.json` должен содержать:

1. `conversation_id`
2. timestamp
3. версию чатбота
4. описание задачи
5. описание данных
6. описание признаков
7. выбранную модель
8. список артефактов
9. инструкции по использованию

Happy path metadata включает task, data, features, model, artifacts и usage instructions вроде `python data_generator.py`, `python pipeline.py --config config.yaml`, `Evaluate metrics and deploy` .

---

# 9. Нефункциональные требования

## 9.1. Производительность

### BR-NFR-001. Время ответа в диалоге

Система должна стремиться к времени ответа в интерактивном диалоге не более 1–2 секунд для стандартного шага.

В happy path приведён пример полного round-trip примерно 1.1 секунды для `/api/chat`, включая загрузку из БД, RAG retrieval, intent classification, entity extraction, Dialogue Engine, response generation, сохранение в БД и HTTP response .

### BR-NFR-002. Производительность RAG

RAG-поиск должен выполняться быстро и не становиться bottleneck.

Целевые параметры:

| Метрика                          | Цель                                   |
| -------------------------------- | -------------------------------------- |
| Embedding dimension              | 384                                    |
| Vector search latency            | `< 50 ms`                              |
| Top-K retrieval                  | 3–5 документов                         |
| Минимальный similarity threshold | настраиваемый, по умолчанию 0.7        |
| Размер базы знаний MVP           | от нескольких сотен до 10k+ документов |

В happy path указано, что VectorDB использует 384D embeddings, быстрый similarity search `< 50ms` и 10k+ documents для domains, features, models .

### BR-NFR-003. Производительность LLM

Система должна быть рассчитана на малую LLM 1B–3B.

Целевые параметры из документа:

| Параметр        | Значение                               |
| --------------- | -------------------------------------- |
| LLM class       | 1B–3B                                  |
| Примеры моделей | Phi-2, Mistral-7B quantized, TinyLlama |
| Latency         | 200–500 ms per inference               |
| Context limit   | 4k–8k tokens                           |

Эти параметры указаны в описании внешнего LLM API .

### BR-NFR-004. Время генерации признаков

Фаза Feature Synthesis должна завершаться за приемлемое интерактивное время.

Целевой показатель: 2–3 секунды для стандартного набора признаков.

Happy path описывает генерацию 19 признаков за 2–3 секунды через несколько LLM вызовов и RAG .

### BR-NFR-005. Время генерации данных

Фаза Data Generation должна завершаться за приемлемое время для стандартного объёма.

Целевой показатель: 1–2 секунды для генерации стандартной синтетической выборки в happy path .

---

## 9.2. Масштабируемость

### BR-NFR-010. Масштабирование базы знаний

Система должна поддерживать рост RAG-корпуса:

1. Новые домены.
2. Новые источники данных.
3. Новые feature patterns.
4. Новые model recommendations.
5. Новые templates вопросов.
6. Новые glossary terms.

### BR-NFR-011. Масштабирование доменов

Система должна поддерживать добавление новых доменов без переписывания основного workflow.

Минимальные домены первой версии:

1. `naval`
2. `air`
3. `ground`
4. `cyber`
5. `analytical`

### BR-NFR-012. Масштабирование признаков

Система должна поддерживать генерацию расширенного набора признаков, но с бизнес-ограничениями.

Из конфигурации в плане:

| Параметр                      | Значение        |
| ----------------------------- | --------------- |
| `MAX_FEATURES`                | 200             |
| `MAX_INTERACTIONS`            | 50              |
| `MIN_FEATURE_VARIANCE`        | 0.01            |
| `MULTICOLLINEARITY_THRESHOLD` | 0.95 / VIF < 10 |

Эти параметры приведены в `ChatbotConfig` .

---

## 9.3. Надёжность

### BR-NFR-020. Устойчивость к ошибкам LLM

Система должна:

1. Валидировать JSON-ответы LLM.
2. Использовать fallback templates.
3. Не падать при невалидном LLM-output.
4. Повторять запрос ограниченное количество раз.
5. При невозможности восстановления задавать пользователю уточняющий вопрос.

### BR-NFR-021. Устойчивость к отсутствию RAG-контекста

Если RAG не нашёл релевантный контекст:

1. Система должна перейти в generic mode.
2. Система должна явно сообщить о нехватке контекста.
3. Система должна запросить дополнительные сведения.
4. Система не должна выдавать доменно-специфичные утверждения без evidence.

### BR-NFR-022. Сохранение состояния

Система должна сохранять context snapshots по фазам.

В архитектуре happy path Database хранит conversations table, context snapshots per phase, artifact metadata и download links .

---

## 9.4. Безопасность и доступ

### BR-NFR-030. Контроль доступа

Система должна поддерживать:

1. Авторизацию пользователя.
2. Изоляцию сессий.
3. Доступ к артефактам только владельцу сессии или разрешённым ролям.
4. Возможность anonymous mode для прототипа, если это разрешено владельцем продукта.

### BR-NFR-031. Защита артефактов

Система должна:

1. Хранить артефакты в защищённом хранилище.
2. Генерировать временные ссылки на скачивание.
3. Удалять временные файлы по TTL.
4. Не раскрывать чужие `conversation_id`.
5. Логировать скачивание.

### BR-NFR-032. Аудит

Система должна сохранять:

1. Ввод пользователя.
2. Извлечённые entities.
3. Confidence.
4. RAG evidence ids.
5. Сгенерированные признаки.
6. Подтверждения пользователя.
7. Выбранную модель.
8. Экспортированные артефакты.
9. Ошибки и fallback-сценарии.

---

## 9.5. UX и язык

### BR-NFR-040. Язык интерфейса

Основной язык интерфейса — русский.

Система должна поддерживать русские и английские термины в NLU, например `РЛС/radar`, `классификация/classification`, `табличные/tabular`.

### BR-NFR-041. Прозрачность для пользователя

Пользователь должен видеть:

1. Текущую фазу.
2. Прогресс по 7 фазам.
3. Какие данные уже собраны.
4. Какие данные отсутствуют.
5. Почему предложены конкретные признаки.
6. Почему предложена конкретная модель.
7. Какие артефакты будут созданы.

В архитектуре фронтенд содержит chat interface, progress bar для 7 фаз и download manager для delivery артефактов .

---

# 10. Требования к UI

## 10.1. Основные элементы интерфейса

UI должен содержать:

1. Чат.
2. Поле ввода.
3. Историю сообщений.
4. Индикатор печати/обработки.
5. Progress bar по 7 фазам.
6. Quick reply buttons.
7. Панель текущего состояния.
8. Панель подтверждения признаков.
9. Download manager.
10. Отображение ошибок.

## 10.2. Quick replies

Система должна предлагать быстрые ответы:

1. Выбор типа задачи.
2. Выбор домена.
3. Выбор типа данных.
4. Выбор интерпретируемости.
5. Подтверждение feature set.
6. Выбор модели.
7. Экспорт.

## 10.3. Просмотр feature set

Пользователь должен иметь возможность:

1. Посмотреть список признаков.
2. Разделить признаки по типам: base / derived / interaction.
3. Посмотреть формулу.
4. Посмотреть физический смысл.
5. Посмотреть единицы измерения.
6. Удалить признак.
7. Добавить новый признак.
8. Запросить объяснение.

---

# 11. Требования к данным и артефактам

## 11.1. Данные, вводимые пользователем

Система должна принимать:

1. Свободный текст.
2. Числовые значения.
3. Проценты.
4. Списки полей через запятую.
5. Подтверждения.
6. Команды изменения.
7. Команды экспорта.

## 11.2. Синтетические данные

Система должна уметь генерировать:

1. Табличные данные.
2. Временные признаки, если требуется.
3. Классификационные target labels.
4. Регрессионные target values.
5. Шум.
6. Аномалии.
7. Метаданные.

## 11.3. Артефакты

Обязательные артефакты:

| Артефакт            | Назначение                     |
| ------------------- | ------------------------------ |
| `features.json`     | Описание признаков             |
| `config.yaml`       | Конфигурация обучения          |
| `pipeline.py`       | ML pipeline                    |
| `data_generator.py` | Генератор синтетических данных |
| `metadata.json`     | Сводка задачи и артефактов     |
| `.zip`              | Архив для скачивания           |

Пример пользовательского сценария в приложенном плане заканчивается созданием `features.json`, `data_generator.py`, `config.yaml`, `pipeline.py`, `metadata.json` и инструкциями по запуску `python data_generator.py`, `python pipeline.py` .

---

# 12. Бизнес-правила

## 12.1. Общие правила

1. Система не должна переходить к следующей фазе, если обязательные поля текущей фазы не заполнены.
2. Система должна подтверждать критически важные интерпретации.
3. Система должна сохранять все изменения контекста.
4. Система должна давать объяснения по признакам и моделям.
5. Система должна использовать RAG для доменных рекомендаций.
6. Система должна сохранять evidence для аудита.
7. Система должна использовать deterministic validators там, где возможно.
8. Система должна явно отделять пользовательские факты от предположений LLM.
9. Система должна поддерживать изменение решений до экспорта.
10. Система должна формировать воспроизводимые артефакты.

## 12.2. Правила генерации признаков

1. Базовые признаки должны соответствовать полям пользователя.
2. Производные признаки должны использовать существующие базовые признаки.
3. Interaction features должны быть ограничены по количеству.
4. Признаки должны иметь описание и формулу.
5. Если требуется высокая интерпретируемость, признаки должны иметь физический смысл.
6. Набор признаков должен проходить проверку мультиколлинеарности.
7. Система должна избегать чрезмерного увеличения размерности.
8. Пользователь должен подтвердить итоговый feature set.

## 12.3. Правила выбора модели

1. Модель выбирается после подтверждения feature set.
2. Рекомендация должна учитывать task type.
3. Рекомендация должна учитывать тип данных.
4. Рекомендация должна учитывать интерпретируемость.
5. Система должна предложить top-3 или top-5 моделей.
6. Для выбранной модели должен быть создан training config.
7. Метрики должны соответствовать типу задачи.

## 12.4. Правила экспорта

1. Экспорт разрешён только после завершения Model Selection.
2. Все артефакты должны быть согласованы между собой.
3. `pipeline.py` должен ссылаться на `config.yaml`.
4. `metadata.json` должен описывать все артефакты.
5. Архив должен включать все обязательные файлы.
6. Ссылка на скачивание должна быть сохранена в БД.

---

# 13. Требования к качеству RAG-документов

## 13.1. Типы документов

Для качественной работы маленькой LLM нужны короткие, хорошо структурированные документы.

Обязательные типы:

1. `domain_profile`
2. `feature_definition`
3. `feature_pattern`
4. `model_recommendation`
5. `model_config`
6. `question_template`
7. `glossary_term`
8. `validation_rule`
9. `example_dialogue`
10. `bad_example`

## 13.2. Формат RAG-документа

Рекомендуемый формат:

```markdown
---
doc_id: feature.naval.radar.range.v1
doc_type: feature_definition
domain: naval
data_source: radar
feature_name: range
feature_type: base
unit: km
tags: [naval, radar, base_feature, classification]
version: 1.0
owner: ml_knowledge_team
last_updated_at: 2026-01-28
---

# Назначение

Дальность до цели.

# Использование

Используется как базовый навигационный признак.

# Формула

Raw sensor value.

# Ограничения

Требует проверки единиц измерения.

# Примеры

range = 15.2 km
```

## 13.3. Требования к полноте базы знаний

Для MVP база знаний должна покрывать:

1. Минимум 3–5 доменов.
2. Минимум 5–10 источников данных.
3. Минимум 50–100 feature definitions.
4. Минимум 20–30 feature patterns.
5. Минимум 10 model recommendation cards.
6. Минимум 50 glossary terms.
7. Минимум 20 question templates.
8. Минимум 10 validation rules.

---

# 14. Метрики успеха

## 14.1. Бизнес-метрики

| Метрика                                                                       | Целевое значение MVP    |
| ----------------------------------------------------------------------------- | ----------------------- |
| Время до готового feature set                                                 | ≤ 15 минут в happy path |
| Доля завершённых диалогов                                                     | ≥ 70%                   |
| Доля корректно заполненных mandatory slots                                    | ≥ 90%                   |
| Доля feature sets, подтверждённых пользователем без ручной полной переработки | ≥ 60%                   |
| Доля успешных экспортов                                                       | ≥ 95%                   |
| Средняя оценка полезности пользователем                                       | ≥ 4 из 5                |

В happy path приветствие позиционирует систему как помощника, который помогает создать ML-проект примерно за 10–15 минут .

## 14.2. ML/Feature Engineering метрики

| Метрика                                     | Цель             |
| ------------------------------------------- | ---------------- |
| Валидность JSON/YAML артефактов             | 100%             |
| Доля признаков с описанием                  | 100%             |
| Доля признаков с формулой, если применимо   | ≥ 95%            |
| Доля признаков с evidence_doc_ids           | ≥ 90%            |
| Доля признаков, прошедших validation        | ≥ 80%            |
| Количество критических ошибок в pipeline.py | 0 для happy path |

## 14.3. NLU/RAG метрики

| Метрика                             | Цель                          |
| ----------------------------------- | ----------------------------- |
| Intent accuracy на тестовом наборе  | ≥ 85% для MVP                 |
| Entity extraction accuracy          | ≥ 80% для MVP                 |
| Среднее время RAG retrieval         | ≤ 50 ms                       |
| Среднее время LLM inference         | 200–500 ms                    |
| Доля fallback-сценариев             | контролируемая, отслеживается |
| Доля запросов с `need_more_context` | отслеживается                 |

---

# 15. Acceptance criteria

## 15.1. End-to-end acceptance scenario

Сценарий считается успешным, если пользователь:

1. Запускает систему.
2. Описывает задачу, например: «Нужен классификатор для определения типа морских целей по РЛС».
3. Система извлекает:

   * `task_type = classification`
   * `domain = naval`
   * `data_source = radar`
   * `target_variable = target_type`
4. Система собирает профиль данных.
5. Система предлагает набор признаков.
6. Пользователь подтверждает или корректирует признаки.
7. Система генерирует синтетические данные.
8. Система рекомендует top-3 моделей.
9. Пользователь выбирает модель.
10. Система экспортирует все файлы.
11. Пользователь скачивает архив.
12. `pipeline.py` запускается с `config.yaml`.

## 15.2. Acceptance criteria по фазам

| Фаза              | Критерий приёмки                                       |
| ----------------- | ------------------------------------------------------ |
| Discovery         | Все обязательные слоты заполнены или запрошены         |
| Data Profiling    | Есть список полей, тип данных, объём, missing strategy |
| Domain Context    | Есть интерпретируемость и critical factors             |
| Feature Synthesis | Есть feature set с base/derived/interaction            |
| Validation        | Нет критических ошибок в feature set                   |
| Data Generation   | X/y созданы, shape корректен, metadata есть            |
| Model Selection   | Есть top-N моделей и выбранная training config         |
| Export            | Созданы обязательные файлы и архив                     |

---

# 16. Ограничения и допущения

## 16.1. Ограничения

1. Модель LLM малая, поэтому сложные рассуждения должны быть декомпозированы.
2. RAG-корпус критически влияет на качество системы.
3. Генерируемые данные являются синтетическими и не заменяют реальные данные.
4. Рекомендованная модель не гарантирует production-качество без обучения и валидации.
5. Формулы признаков должны проверяться валидаторами.
6. Пользователь должен подтверждать ключевые решения.

## 16.2. Допущения

1. Пользователь способен описать задачу хотя бы на базовом уровне.
2. RAG-база содержит релевантные доменные документы.
3. У системы есть доступ к локальному или серверному LLM API.
4. Система может хранить state и артефакты.
5. Для MVP допускается synthetic data generation без подключения к реальным данным.

---

# 17. Риски

| Риск                                               |         Влияние | Митигирующая мера                                            |
| -------------------------------------------------- | --------------: | ------------------------------------------------------------ |
| Маленькая LLM ошибается в intent/entity extraction |         Высокое | Confidence, clarification, regex fallback, RAG normalization |
| RAG-корпус неполный                                |         Высокое | `need_more_context`, curator workflow, versioning            |
| Галлюцинации признаков                             |         Высокое | Evidence required, validators, user confirmation             |
| Некорректные формулы                               |         Высокое | Formula parser, unit checks, validation agent                |
| Невалидный pipeline.py                             | Среднее/высокое | Code templates, static checks, tests                         |
| Слишком много признаков                            |         Среднее | MAX_FEATURES, MAX_INTERACTIONS, multicollinearity check      |
| Неверная рекомендация модели                       |         Среднее | Top-N recommendation, explanation, human selection           |
| Потеря контекста                                   |         Высокое | Persistent ContextMemory, snapshots per phase                |
| Низкая скорость ответа                             |         Среднее | Caching, short prompts, RAG top-K, agent decomposition       |
| Пользователь не понимает термины ML                |         Среднее | Простые объяснения, glossary, quick replies                  |

---

# 18. MVP

## 18.1. MVP-функциональность

Для первой версии достаточно реализовать:

1. Web chat interface.
2. 7-фазный dialogue workflow.
3. NLU для базовых intents.
4. Entity extraction для ключевых слотов.
5. ContextMemory.
6. RAG по коллекциям:

   * glossary;
   * domain profiles;
   * feature library;
   * model recommendations;
   * question templates.
7. Feature synthesis для одного основного сценария: tabular classification.
8. Генерация synthetic tabular data.
9. Рекомендация top-3 моделей.
10. Экспорт:

    * `features.json`
    * `config.yaml`
    * `data_generator.py`
    * `pipeline.py`
    * `metadata.json`
    * zip archive.

## 18.2. MVP-ограничения

1. Один основной домен для тестирования, например `naval_radar`.
2. Ограниченный набор моделей: XGBoost, LightGBM, Random Forest.
3. Ограниченный набор feature patterns.
4. Без автоматического подключения к реальным БД.
5. Без production deployment модели.
6. С human confirmation перед экспортом.

## 18.3. Критерий готовности MVP

MVP считается готовым, если на тестовом happy path система:

1. Завершает все 7 фаз.
2. Корректно сохраняет контекст.
3. Генерирует минимум 19 признаков для сценария `naval_radar`.
4. Генерирует синтетическую выборку.
5. Рекомендует top-3 модели.
6. Создаёт все обязательные артефакты.
7. Возвращает архив.
8. Логирует основные решения.
9. Не требует ручного вмешательства разработчика.

---

# 19. Рекомендуемая структура backlog

## Epic 1 — Dialogue & Session Management

* Создание сессии.
* Восстановление сессии.
* Сброс сессии.
* Progress bar.
* История сообщений.

## Epic 2 — NLU Agent

* Intent classification.
* Entity extraction.
* Confidence scoring.
* Clarification handling.
* Regex fallback.

## Epic 3 — RAG Platform

* VectorDB.
* Embeddings.
* Collections.
* Metadata filters.
* Evidence pack.
* RAG document admin.

## Epic 4 — Context & Orchestration

* ContextMemory.
* Phase transition.
* Completion criteria.
* State snapshots.
* Agent routing.

## Epic 5 — Feature Engineering

* Base feature selection.
* Derived feature generation.
* Interaction generation.
* Feature explanation.
* Feature validation.
* Multicollinearity check.

## Epic 6 — Synthetic Data Generation

* Generator config.
* Data generation.
* Noise/anomaly simulation.
* Data validation.
* Data export.

## Epic 7 — Model Selection

* Model recommendation.
* Hyperparameter templates.
* Training config.
* Metrics mapping.
* User model selection.

## Epic 8 — Export

* `features.json`.
* `config.yaml`.
* `pipeline.py`.
* `data_generator.py`.
* `metadata.json`.
* Zip archive.
* Download links.

## Epic 9 — Observability & Governance

* Logs.
* Audit trail.
* Metrics dashboard.
* Error handling.
* RAG quality monitoring.

---

# 20. Итоговая формулировка бизнес-требования

Система должна предоставлять пользователю управляемый диалоговый процесс проектирования ML-признаков и обучающей конфигурации. Процесс должен проходить через 7 фаз, сохранять состояние, использовать RAG для доменной поддержки, применять малую LLM только в узких агентных задачах, валидировать критичные результаты и экспортировать готовый набор артефактов для дальнейшего ML-прототипирования.

Ключевое требование: система должна быть не «чатом, который даёт советы», а **мультиагентным бизнес-процессом**, где каждый результат проверяем, сохранён, объясним и может быть экспортирован.



# 21. Дополнения по генерации данных

## Ключевой принцип

Маленькая LLM **не должна сама генерировать 100 000 строк данных токенами**. Это было бы медленно, дорого по контексту и почти наверняка невалидно.

Правильная архитектура такая:

$$
\text{LLM}
\rightarrow
\text{Data Generation Spec}
\rightarrow
\text{Python Generator}
\rightarrow
\text{Validation}
\rightarrow
\text{X_train.csv, y_train.npy, metadata.json}
$$

То есть маленькая модель генерирует **не данные**, а **спецификацию генерации данных**: какие признаки, какие распределения, какие зависимости, как формировать target, какой шум и какие аномалии добавить. А сами массивы (X) и (y) создаёт обычный Python-код.

В вашем happy path это уже заложено: `Data Generator` отвечает за synthetic data creation `100k × 19`, реалистичные распределения и зависимости, а также noise/anomalies simulation. 

---

## 1. Что именно делает маленькая LLM

Модель `llama3.2` или другая малая LLM должна выполнять только узкие функции:

```text
1. Прочитать утверждённый feature set.
2. Найти RAG-карточки по домену и признакам.
3. Сформировать JSON-спецификацию генерации.
4. Сформировать или выбрать шаблон Python-генератора.
5. Объяснить пользователю, что будет сгенерировано.
6. При ошибках валидатора исправить только spec, а не весь код.
```

Она **не должна**:

```text
- генерировать 100000 строк CSV;
- вручную писать каждое значение признака;
- сама проверять shape, NaN, inf;
- сама считать class balance;
- сама доверять своим формулам без валидатора.
```

---

## 2. Правильное разделение ответственности

### LLM делает

```json
{
  "feature_generation_plan": "...",
  "distributions": "...",
  "dependency_rules": "...",
  "target_generation_logic": "...",
  "noise_model": "...",
  "anomaly_model": "...",
  "validation_expectations": "..."
}
```

### Python делает

```text
np.random
pandas
numpy
scipy
sklearn
validation checks
file saving
```

### Validators делают

```text
shape check
NaN / inf check
class balance check
feature range check
formula consistency check
metadata consistency check
```

Такой подход особенно важен для маленькой модели: она остаётся планировщиком и генератором спецификаций, а не исполнителем массивных вычислений.

---

## 3. Входы этапа Data Generation

Минимальный вход:

```json
{
  "final_features": [
    {
      "name": "range",
      "role": "base",
      "type": "float",
      "unit": "km"
    },
    {
      "name": "rcs_normalized",
      "role": "derived",
      "formula": "log1p(rcs)"
    },
    {
      "name": "range_x_snr",
      "role": "interaction",
      "formula": "range * snr / 100"
    }
  ],
  "n_samples": 100000,
  "class_distribution": {
    "civilian_ship": 0.4,
    "military_ship": 0.3,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "noise_level": 0.01,
  "anomaly_rate": 0.02,
  "random_state": 42
}
```

В happy path генератор получает `task_type`, `n_samples`, `n_features`, `n_classes`, `class_distribution`, `random_state`, `noise_level`, `anomaly_rate`, после чего параллельно генерирует base features, derived features, interactions и target variable. 

---

## 4. Что должно быть в `final_features`

Для генерации данных одного имени признака недостаточно.

Плохой вариант:

```json
{
  "name": "range"
}
```

Хороший вариант:

```json
{
  "name": "range",
  "role": "base",
  "dtype": "float",
  "unit": "km",
  "distribution": {
    "type": "uniform",
    "min": 0,
    "max": 200
  },
  "semantic_group": "kinematic",
  "source": "radar",
  "required_for_target_logic": true
}
```

Для производного признака:

```json
{
  "name": "rcs_normalized",
  "role": "derived",
  "dtype": "float",
  "formula": "log1p(rcs)",
  "input_features": ["rcs"],
  "range_policy": "computed",
  "validation_rules": ["requires_rcs", "non_negative_input"]
}
```

Для interaction-признака:

```json
{
  "name": "range_x_snr",
  "role": "interaction",
  "dtype": "float",
  "formula": "range * snr / 100",
  "input_features": ["range", "snr"],
  "validation_rules": ["requires_range", "requires_snr"]
}
```

---

## 5. Что LLM должна получить из RAG

Для Data Generation RAG должен вернуть не общую справку, а **generation evidence pack**.

Пример:

```json
{
  "domain": "naval",
  "data_source": "radar",
  "task_type": "classification",
  "base_feature_distributions": {
    "range": {
      "distribution": "uniform",
      "min": 0,
      "max": 200,
      "unit": "km"
    },
    "azimuth": {
      "distribution": "uniform",
      "min": 0,
      "max": 360,
      "unit": "degree"
    },
    "rcs": {
      "distribution": "exponential",
      "scale": 10,
      "unit": "m2"
    },
    "snr": {
      "distribution": "normal",
      "mean": 20,
      "std": 10,
      "unit": "dB"
    },
    "doppler": {
      "distribution": "normal",
      "mean": 0,
      "std": 50,
      "unit": "mps"
    }
  },
  "target_classes": [
    "civilian_ship",
    "military_ship",
    "submarine",
    "aircraft"
  ],
  "noise_model": {
    "type": "gaussian",
    "std_fraction": 0.01
  },
  "anomaly_model": {
    "rate": 0.02,
    "multiplicative_factor_range": [2, 5]
  }
}
```

Такой evidence pack может быть собран из:

* task cards;
* feature cards;
* schema cards;
* analytics cards;
* distribution cards;
* validation rules.

В ваших документах `Situation.md` задаёт структуру тактической обстановки: внешние условия, tactical objects, sensors, weapons, navigation и `tracks_fused`; эти блоки могут быть источником схем и ограничений для генерации.  Документ `Состав данных аналитики.md` задаёт feature-store показатели для сенсоров: `uptime_ratio_T`, `detection_probability_T`, `false_alarm_rate_T`, `avg_position_error`, `track_drop_rate`, `revisit_time_stats`, `jammed_time_ratio` и другие агрегаты, которые могут использоваться как признаки или как ограничения генерации. 

---

## 6. Внутренний pipeline Data Generation

Реально этап должен работать так:

```text
START
  ↓
DataGenerationPlannerAgent
  ↓
RAG Retrieval: distributions + formulas + constraints
  ↓
GenerationSpecAgent
  ↓
Spec Validator
  ↓
Python SyntheticDataGenerator
  ↓
Data Validator
  ↓
Save X_train.csv, y_train.npy, metadata.json
  ↓
Update ContextMemory
END
```

---

## 7. DataGenerationPlannerAgent

Этот агент решает:

```text
какой тип данных генерировать
```

Например:

```json
{
  "generation_mode": "tabular_classification",
  "n_samples": 100000,
  "n_features": 19,
  "n_classes": 4,
  "target_type": "multiclass",
  "requires_temporal_sequence": false
}
```

Если задача другая, режим будет другим:

| Задача                  | Режим генерации                 |
| ----------------------- | ------------------------------- |
| tabular classification  | `tabular_classification`        |
| trajectory prediction   | `sequence_forecasting`          |
| range-Doppler detection | `radar_tensor_detection`        |
| sonar classification    | `spectrogram_classification`    |
| false-track detection   | `track_sequence_classification` |

В документе с перечнем задач есть примеры разных форматов обучающих данных: для radar detection предлагается генерировать synthetic range-Doppler maps с помехами и целями, а для real/decoy detection — синтетические трассы с ((X,Y,Z,Vx,Vy,Vz,RCS)) и контекстом.  

---

## 8. GenerationSpecAgent

Этот агент формирует строгую спецификацию.

Пример для вашего базового happy path:

```json
{
  "spec_version": "1.0",
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar",
  "n_samples": 100000,
  "random_state": 42,

  "target": {
    "name": "target_type",
    "type": "multiclass",
    "classes": [
      {
        "id": 0,
        "name": "civilian_ship",
        "prior": 0.4
      },
      {
        "id": 1,
        "name": "military_ship",
        "prior": 0.3
      },
      {
        "id": 2,
        "name": "submarine",
        "prior": 0.2
      },
      {
        "id": 3,
        "name": "aircraft",
        "prior": 0.1
      }
    ]
  },

  "base_features": [
    {
      "name": "range",
      "dtype": "float32",
      "unit": "km",
      "distribution": {
        "type": "uniform",
        "min": 0,
        "max": 200
      }
    },
    {
      "name": "azimuth",
      "dtype": "float32",
      "unit": "degree",
      "distribution": {
        "type": "uniform",
        "min": 0,
        "max": 360
      }
    },
    {
      "name": "elevation",
      "dtype": "float32",
      "unit": "degree",
      "distribution": {
        "type": "uniform",
        "min": -10,
        "max": 80
      }
    },
    {
      "name": "rcs",
      "dtype": "float32",
      "unit": "m2",
      "distribution": {
        "type": "exponential",
        "scale": 10
      }
    },
    {
      "name": "snr",
      "dtype": "float32",
      "unit": "dB",
      "distribution": {
        "type": "normal",
        "mean": 20,
        "std": 10
      }
    },
    {
      "name": "doppler",
      "dtype": "float32",
      "unit": "mps",
      "distribution": {
        "type": "normal",
        "mean": 0,
        "std": 50
      }
    }
  ],

  "derived_features": [
    {
      "name": "signal_quality",
      "formula": "snr / 20.0"
    },
    {
      "name": "rcs_normalized",
      "formula": "log1p(rcs)"
    },
    {
      "name": "elevation_category",
      "formula": "digitize(elevation, bins=[0, 20, 40, 60])"
    },
    {
      "name": "distance_class",
      "formula": "digitize(range, bins=[50, 100, 150])"
    }
  ],

  "interaction_features": [
    {
      "name": "range_x_snr",
      "formula": "range * snr / 100.0"
    },
    {
      "name": "rcs_x_snr",
      "formula": "rcs * snr"
    },
    {
      "name": "doppler_x_elevation",
      "formula": "doppler * elevation"
    }
  ],

  "noise": {
    "type": "gaussian",
    "std": 0.01
  },

  "anomalies": {
    "rate": 0.02,
    "type": "multiplicative_sensor_glitch",
    "factor_min": 2,
    "factor_max": 5
  }
}
```

LLM должна вернуть именно такой JSON. После этого Python проверяет, что:

```text
- все признаки имеют name;
- все base features имеют distribution;
- все derived features используют существующие input features;
- class priors суммируются к 1;
- n_samples допустим;
- anomaly_rate допустим;
- нет неизвестных формул.
```

---

## 9. Почему target лучше генерировать не случайно

Плохой вариант:

```python
y = np.random.randint(0, 4, n_samples)
```

Такой target почти не связан с признаками. Модель обучится плохо или случайно.

Хороший вариант:

```text
target зависит от признаков
```

Например:

```text
близко + большой RCS → military_ship
низкий elevation + малый RCS → submarine
высокий elevation → aircraft
остальное → civilian_ship
```

Именно такая идея есть в happy path: генератор целевой переменной использует физически обоснованную логику, где близкая цель с большим RCS относится к военному кораблю, низкий elevation и малый RCS — к подлодке, высокий elevation — к авиации, а остальные случаи — к мирным судам. 

---

## 10. Более правильный способ: conditional generation по классам

Для контролируемого class balance лучше сначала сгенерировать (y), а потом генерировать (X \mid y).

То есть:

$$
P(X, y) = P(y)P(X \mid y)
$$

Вход:

```json
"class_distribution": {
  "civilian_ship": 0.4,
  "military_ship": 0.3,
  "submarine": 0.2,
  "aircraft": 0.1
}
```

Система сначала создаёт:

```text
40000 civilian_ship
30000 military_ship
20000 submarine
10000 aircraft
```

А затем для каждого класса генерирует свои распределения признаков.

Пример:

```json
{
  "class_conditional_distributions": {
    "civilian_ship": {
      "range": {"type": "uniform", "min": 20, "max": 180},
      "rcs": {"type": "lognormal", "mean": 8, "sigma": 0.5},
      "elevation": {"type": "normal", "mean": 0, "std": 3},
      "doppler": {"type": "normal", "mean": 5, "std": 15}
    },
    "military_ship": {
      "range": {"type": "uniform", "min": 5, "max": 120},
      "rcs": {"type": "lognormal", "mean": 20, "sigma": 0.6},
      "elevation": {"type": "normal", "mean": 0, "std": 4},
      "doppler": {"type": "normal", "mean": 10, "std": 25}
    },
    "submarine": {
      "range": {"type": "uniform", "min": 5, "max": 80},
      "rcs": {"type": "lognormal", "mean": 2, "sigma": 0.4},
      "elevation": {"type": "normal", "mean": -2, "std": 2},
      "doppler": {"type": "normal", "mean": 1, "std": 8}
    },
    "aircraft": {
      "range": {"type": "uniform", "min": 10, "max": 200},
      "rcs": {"type": "lognormal", "mean": 5, "sigma": 0.8},
      "elevation": {"type": "normal", "mean": 35, "std": 15},
      "doppler": {"type": "normal", "mean": 80, "std": 40}
    }
  }
}
```

Такой генератор даёт более реалистичную ML-задачу, потому что признаки действительно различают классы.

---

## 11. Как строится (X)

Для happy path:

$$
X =
[X_{\text{base}}, X_{\text{derived}}, X_{\text{interaction}}]
$$

То есть:

```python
X = np.hstack([
    X_base,
    X_derived,
    X_interactions
])
```

В happy path прямо описано, что генератор создаёт `X_base`, `X_derived`, `X_interactions`, затем объединяет их через `np.hstack`, после чего добавляет шум и аномалии. 

---

## 12. Генерация base features

Base features — это первичные физические или сенсорные параметры.

Пример:

```python
range = np.random.uniform(0, 200, n_samples)
azimuth = np.random.uniform(0, 360, n_samples)
elevation = np.random.uniform(-10, 80, n_samples)
rcs = np.random.exponential(scale=10, size=n_samples)
snr = np.random.normal(20, 10, n_samples)
doppler = np.random.normal(0, 50, n_samples)
```

В happy path базовые признаки генерируются именно так: `range` равномерно в диапазоне 0–200 км, `azimuth` 0–360 градусов, `elevation` от -10 до 80 градусов, `rcs` через экспоненциальное распределение, `snr` нормальным распределением с центром 20 дБ, а `doppler` нормальным распределением с центром 0 м/с. 

---

## 13. Генерация derived features

Derived features считаются из base features.

Например:

$$
signal_quality = \frac{snr}{20}
$$

$$
rcs_normalized = \log(1 + rcs)
$$

$$
distance_class = bucket(range)
$$

Пример кода:

```python
signal_quality = snr / 20.0
rcs_normalized = np.log1p(rcs)
elevation_category = np.digitize(elevation, bins=[0, 20, 40, 60])
distance_class = np.digitize(range, bins=[50, 100, 150])
```

Важно: LLM не должна сама вычислять эти массивы. Она должна только указать формулы, а безопасный expression evaluator или заранее разрешённый набор функций выполняет расчёт.

---

## 14. Генерация interaction features

Interaction features считаются как комбинации признаков:

$$
\mathrm{range\_snr} = \frac{\mathrm{range} \cdot \mathrm{snr}}{100}
$$

$$
rcs_x_snr = rcs \cdot snr
$$

$$
doppler_x_elevation = doppler \cdot elevation
$$

В happy path interaction-признаки включают `range_x_snr`, `rcs_x_snr`, `doppler_x_elevation`, `range_x_azimuth`, `rcs_x_range`. 

---

## 15. Добавление шума

Шум нужен, чтобы данные не были идеально детерминированными.

Пример:

$$
X' = X + \epsilon,
\quad
\epsilon \sim \mathcal{N}(0, \sigma^2)
$$

Если:

```json
"noise_level": 0.01
```

то:

```python
noise = np.random.normal(0, 0.01, X.shape)
X = X + noise
```

В happy path шум добавляется как гауссовский noise для имитации ошибок измерения. 

---

## 16. Добавление аномалий

Аномалии нужны, чтобы dataset был похож на реальные измерения, где бывают:

```text
- сбои сенсоров;
- выбросы;
- сильные помехи;
- неверные измерения;
- редкие экстремальные значения.
```

Пример:

```python
n_anomalies = int(n_samples * anomaly_rate)
anomaly_indices = np.random.choice(n_samples, n_anomalies, replace=False)

X[anomaly_indices] *= np.random.uniform(
    2,
    5,
    size=(n_anomalies, X.shape[1])
)
```

В happy path аномалии моделируются как 2% выборки, где значения признаков умножаются на случайный коэффициент от 2 до 5, что интерпретируется как сбои датчиков. 

---

## 17. Обязательная проблема в текущем happy path

В текущем псевдокоде есть важный риск: `generate_derived_features()` и `generate_interactions()` внутри себя снова вызывают `generate_base_features()`.

Это может привести к рассогласованию:

```text
base range в X_base
≠
base range, из которого посчитан range_x_snr
```

Правильнее генерировать base features один раз:

```python
X_base, base = generate_base_features()
X_derived = generate_derived_features(base)
X_interactions = generate_interactions(base)
y = generate_target_variable(base, X_derived)
X = np.hstack([X_base, X_derived, X_interactions])
```

Иначе производные признаки будут не производными от тех же исходных признаков, которые попали в итоговый `X`.

---

## 18. Правильная архитектура генератора

```python
class SyntheticDataGenerator:
    def generate(self, spec):
        rng = np.random.default_rng(spec.random_state)

        y = self.generate_target_by_distribution(spec, rng)

        base = self.generate_base_features_conditioned_on_y(spec, y, rng)

        derived = self.compute_derived_features(spec, base)

        interactions = self.compute_interactions(spec, base, derived)

        X = self.assemble_matrix(spec, base, derived, interactions)

        X = self.add_noise(spec, X, rng)

        X, anomaly_mask = self.add_anomalies(spec, X, rng)

        report = self.validate(spec, X, y, anomaly_mask)

        return X, y, report
```

---

## 19. Как маленькая LLM участвует в генерации кода

Маленькая LLM может сгенерировать не произвольный код, а **параметры для шаблона**.

Плохой подход:

```text
LLM, напиши весь data_generator.py с нуля.
```

Лучший подход:

```text
LLM, верни JSON GenerationSpec.
```

А затем backend использует шаблон:

```python
generator = TabularClassificationGenerator(spec)
X, y, metadata = generator.generate()
```

Для маленькой модели это намного надёжнее.

---

## 20. Prompt для маленькой LLM

```text
SYSTEM:
You are DataGenerationSpecAgent.
Your task is to create a JSON specification for synthetic data generation.
Do not generate rows.
Do not generate CSV.
Do not write Python code unless explicitly asked.
Use only provided features and evidence.
Return valid JSON only.

INPUT:
- task_type
- domain
- data_source
- final_features
- class_distribution
- generation constraints
- RAG evidence

RULES:
1. Every generated feature must exist in final_features.
2. Derived features must reference existing base features.
3. Interaction features must reference existing numeric features.
4. Class priors must sum to 1.0.
5. Do not invent unavailable fields.
6. If distribution is unknown, set distribution.type = "default_by_dtype" and confidence = "low".
7. Include validation expectations.
```

---

## 21. Output schema для LLM

```json
{
  "type": "object",
  "required": [
    "generation_mode",
    "n_samples",
    "target",
    "feature_specs",
    "noise",
    "anomalies",
    "validation"
  ],
  "properties": {
    "generation_mode": {
      "type": "string"
    },
    "n_samples": {
      "type": "integer",
      "minimum": 100,
      "maximum": 1000000
    },
    "target": {
      "type": "object"
    },
    "feature_specs": {
      "type": "array"
    },
    "noise": {
      "type": "object"
    },
    "anomalies": {
      "type": "object"
    },
    "validation": {
      "type": "object"
    }
  }
}
```

---

## 22. Как должен выглядеть `metadata.json`

После генерации нужно сохранить не только данные, но и объяснение, как они были получены.

```json
{
  "dataset_id": "conv_abc123_dataset_v1",
  "created_at": "2026-05-18T00:00:00Z",
  "task_type": "classification",
  "domain": "naval",
  "data_source": "radar",
  "n_samples": 100000,
  "n_features": 19,
  "n_classes": 4,
  "class_names": [
    "civilian_ship",
    "military_ship",
    "submarine",
    "aircraft"
  ],
  "class_distribution_requested": {
    "civilian_ship": 0.4,
    "military_ship": 0.3,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "class_distribution_actual": {
    "civilian_ship": 0.3998,
    "military_ship": 0.3002,
    "submarine": 0.2,
    "aircraft": 0.1
  },
  "noise_level": 0.01,
  "anomaly_rate": 0.02,
  "random_state": 42,
  "files": {
    "X_train": "X_train.csv",
    "y_train": "y_train.npy"
  },
  "validation": {
    "X_shape_correct": true,
    "y_shape_correct": true,
    "no_nan": true,
    "no_inf": true,
    "valid_y_values": true,
    "class_distribution_balanced": true
  }
}
```

В happy path после валидации данные сохраняются как CSV для `X`, NPY для `y`, а также создаются метаданные. 

---

## 23. Проверки валидатора

Validator должен проверять минимум:

```python
checks = {
    "X_shape_correct": X.shape == (n_samples, len(feature_set)),
    "y_shape_correct": y.shape == (n_samples,),
    "no_nan": not np.isnan(X).any(),
    "no_inf": not np.isinf(X).any(),
    "valid_y_values": set(y).issubset(set(range(n_classes))),
    "class_distribution_balanced": distribution_close_enough(y, expected_priors),
    "feature_names_match": list(X_df.columns) == expected_feature_names,
    "derived_features_consistent": formulas_recompute_correctly(X_df),
    "anomaly_rate_actual": actual_anomaly_rate_close_to_requested
}
```

В happy path уже указаны проверки `X_shape_correct`, `y_shape_correct`, `no_nan`, `no_inf`, `valid_y_values`, `class_distribution_balanced`. 

---

## 24. Что делать, если проверка не прошла

Например, LLM вернула spec:

```json
{
  "formula": "range_rate = d(range)/dt"
}
```

Но в профиле данных:

```json
{
  "temporal_importance": false,
  "fields": ["range", "azimuth", "rcs", "snr", "doppler"]
}
```

Validator должен вернуть:

```json
{
  "status": "failed",
  "error": "range_rate requires timestamp or temporal sequence",
  "repair_instruction": "Remove temporal features or ask user to provide timestamp/track_id."
}
```

После этого LangGraph возвращает управление не пользователю сразу, а в `GenerationSpecAgent` или `FeatureSynthesisAgent`.

---

## 25. Data Generation для разных типов задач

### 25.1. Табличная классификация

Ваш текущий happy path:

$$
X \in \mathbb{R}^{100000 \times 19},
\quad
y \in {0,1,2,3}^{100000}
$$

Используется для:

```text
classification of naval radar targets
```

### 25.2. Radar detection

Для задачи обнаружения целей на фоне помех датасет будет не таблицей, а тензорами:

$$
X \in \mathbb{R}^{N \times H \times W \times C}
$$

Например:

```json
{
  "X_shape": [2000, 64, 64, 1],
  "y_shape": [2000, 64, 64, 1],
  "task": "cell_level_target_detection"
}
```

В документе `Перечень задач v1.md` приведён учебный пример, где генерируются synthetic range-Doppler maps с целями и помехами, формируется обучающая выборка и обучается CNN-модель «цель/фон» по ячейкам. 

### 25.3. Track classification

Для real/decoy или false target detection:

$$
X_{\text{seq}} \in \mathbb{R}^{N \times T \times F}
$$

Например:

```json
{
  "X_seq_shape": [5000, 20, 7],
  "X_ctx_shape": [5000, 4],
  "y_shape": [5000]
}
```

В документе `Перечень задач v1.md` описан пример генерации синтетических трасс с признаками ((X,Y,Z,Vx,Vy,Vz,RCS)), контекстом и метками real/false для обучения LSTM + MLP классификатора. 

---

## 26. Роль RAG в генерации данных

RAG должен отвечать на вопросы:

```text
- какие признаки доступны?
- какие распределения реалистичны?
- какие классы target допустимы?
- какие зависимости физически допустимы?
- какие признаки требуют временной последовательности?
- какие внешние условия влияют на сенсоры?
- какие validation rules нужны?
```

Например, `Situation.md` содержит поля внешней среды вроде `radar_performance_factor`, `electro_optical_effectiveness`, `communication_reliability`, `gnss_availability`, а также подробные описания сенсоров, статусов, ограничений и degradation factors; это можно использовать для генерации контекстных признаков или для условной генерации качества сенсора. 

Документ `Состав данных аналитики.md` описывает, как считать sensor analytics: `detection_probability_T`, `false_alarm_rate_T`, `avg_detection_range_by_class`, `avg_position_error`, `track_drop_rate`, `revisit_time_stats`, `performance_drop_by_weather`, `jammed_time_ratio`; эти показатели могут стать либо признаками в synthetic dataset, либо правилами для генерации зависимостей между сенсором, средой и результатом. 

---

## 27. Пример: как LLM генерирует spec, а не данные

### Вход в LLM

```json
{
  "context": {
    "task_type": "classification",
    "domain": "naval",
    "data_source": "radar",
    "n_samples": 100000,
    "class_distribution": {
      "civilian_ship": 0.4,
      "military_ship": 0.3,
      "submarine": 0.2,
      "aircraft": 0.1
    }
  },
  "final_features": [
    "range",
    "azimuth",
    "elevation",
    "rcs",
    "snr",
    "doppler",
    "signal_quality",
    "rcs_normalized",
    "distance_class",
    "range_x_snr"
  ],
  "evidence": [
    "radar fields include range, azimuth, elevation, rcs, snr, doppler",
    "sensor quality can be affected by rain, sea clutter, jamming",
    "synthetic data should include noise and anomalies"
  ]
}
```

### Выход LLM

```json
{
  "generation_mode": "tabular_classification",
  "n_samples": 100000,
  "target": {
    "name": "target_type",
    "classes": [
      {"id": 0, "name": "civilian_ship", "prior": 0.4},
      {"id": 1, "name": "military_ship", "prior": 0.3},
      {"id": 2, "name": "submarine", "prior": 0.2},
      {"id": 3, "name": "aircraft", "prior": 0.1}
    ]
  },
  "feature_specs": [
    {
      "name": "range",
      "role": "base",
      "distribution": {"type": "uniform", "min": 0, "max": 200}
    },
    {
      "name": "rcs_normalized",
      "role": "derived",
      "formula": "log1p(rcs)"
    }
  ],
  "noise": {"type": "gaussian", "std": 0.01},
  "anomalies": {"rate": 0.02, "type": "multiplicative_sensor_glitch"},
  "validation": {
    "expected_X_shape": [100000, 19],
    "expected_y_shape": [100000],
    "required_checks": [
      "no_nan",
      "no_inf",
      "class_distribution_balanced"
    ]
  }
}
```

---

## 28. Затем Python создаёт данные

Сильно упрощённо:

```python
def generate_from_spec(spec):
    rng = np.random.default_rng(spec["random_state"])

    y = generate_labels(
        n_samples=spec["n_samples"],
        classes=spec["target"]["classes"],
        rng=rng
    )

    base = generate_base_features_conditioned_on_y(spec, y, rng)

    df = pd.DataFrame(base)

    for feature in spec["feature_specs"]:
        if feature["role"] == "derived":
            df[feature["name"]] = compute_formula(feature["formula"], df)

    X = df[expected_feature_names].to_numpy(dtype=np.float32)

    X = add_noise(X, spec["noise"], rng)
    X, anomaly_mask = add_anomalies(X, spec["anomalies"], rng)

    validation = validate_generated_data(X, y, spec)

    return X, y, validation
```

---

## 29. Важная доработка: не делать target слишком простым

Если target создаётся жёсткими правилами:

```text
if elevation > 50 → aircraft
```

модель может получить слишком лёгкую задачу.

Лучше добавить вероятностность:

[
P(y=c \mid x) = softmax(g_c(x))
]

Например:

```python
score_aircraft = 0.05 * elevation + 0.02 * abs(doppler)
score_submarine = -0.1 * elevation - 0.05 * rcs
score_military = 0.04 * rcs + 0.03 * snr - 0.02 * range
score_civilian = 0.01 * range - 0.01 * abs(doppler)
```

Затем:

```python
probs = softmax(scores)
y = sample_from(probs)
```

Так данные будут реалистичнее: классы не идеально разделимы, есть шум и пограничные случаи.

---

## 30. Как обеспечить заданный class balance

Есть два подхода.

### Подход A — сначала $y$, потом $X \mid y$

Самый удобный:

```python
y = sample_labels_by_prior(class_distribution)
X = sample_features_given_class(y)
```

Плюс: class balance почти точно контролируется.

### Подход B — сначала $X$, потом $y = f(X)$

Плюс: target естественно зависит от признаков.

Минус: class balance может получиться не тот.

### Лучший вариант

Комбинация:

```text
1. Сгенерировать y по prior.
2. Сгенерировать X | y.
3. Добавить overlapping distributions.
4. Добавить label noise.
5. Проверить balance.
```

---

## 31. Как добавить label noise

В реальных данных target labels не всегда идеальны.

Пример:

```json
{
  "label_noise_rate": 0.01
}
```

Код:

```python
n_flip = int(n_samples * label_noise_rate)
idx = rng.choice(n_samples, n_flip, replace=False)

for i in idx:
    y[i] = rng.choice([c for c in classes if c != y[i]])
```

Это помогает сделать прототип менее игрушечным.

---

## 32. Как добавить missing values

Если на Data Profiling пользователь сказал:

```text
есть пропуски 5%
```

тогда генератор должен добавить:

```python
mask = rng.random(X.shape) < 0.05
X[mask] = np.nan
```

Но если:

```json
"missing_data_strategy": "none"
```

то NaN добавлять нельзя.

---

## 33. Как связать Data Generation с RAG-карточками

Для каждого признака в `metadata.json` желательно хранить evidence:

```json
{
  "feature_name": "jammed_time_ratio",
  "source_doc_id": "analytics.sensor_analytics_T.v1",
  "generation_rule": "sample from beta distribution conditioned on jamming_level",
  "validation_rule": "0 <= jammed_time_ratio <= 1"
}
```

Это позволит потом понять:

```text
почему этот признак есть
как он был сгенерирован
на каком документе он основан
какие проверки применялись
```

---

## 34. Пример для признаков из ваших документов

Если задача не “морские цели по РЛС”, а, например, “оценка качества сенсора”, synthetic generator может использовать признаки из `sensor_analytics_T`.

Пример GenerationSpec:

```json
{
  "generation_mode": "sensor_analytics_classification",
  "entity": "sensor",
  "target": {
    "name": "sensor_health_class",
    "classes": [
      {"id": 0, "name": "healthy", "prior": 0.6},
      {"id": 1, "name": "degraded", "prior": 0.3},
      {"id": 2, "name": "fault_prone", "prior": 0.1}
    ]
  },
  "base_features": [
    {
      "name": "uptime_ratio_T",
      "distribution_by_class": {
        "healthy": {"type": "beta", "alpha": 30, "beta": 2},
        "degraded": {"type": "beta", "alpha": 10, "beta": 5},
        "fault_prone": {"type": "beta", "alpha": 3, "beta": 8}
      }
    },
    {
      "name": "false_alarm_rate_T",
      "distribution_by_class": {
        "healthy": {"type": "poisson", "lambda": 1},
        "degraded": {"type": "poisson", "lambda": 5},
        "fault_prone": {"type": "poisson", "lambda": 12}
      }
    },
    {
      "name": "jammed_time_ratio",
      "distribution_by_class": {
        "healthy": {"type": "beta", "alpha": 2, "beta": 20},
        "degraded": {"type": "beta", "alpha": 4, "beta": 10},
        "fault_prone": {"type": "beta", "alpha": 8, "beta": 8}
      }
    }
  ]
}
```

Здесь LLM не придумывает признаки: они взяты из analytics-документа, где описаны доступность сенсора, эффективность обнаружения, качество информации и влияние внешней среды. 

---

## 35. LangGraph-узлы для этапа Data Generation

Я бы сделал такие узлы:

```text
DataGenerationInputValidator
  ↓
RAGGenerationContextRetriever
  ↓
GenerationSpecAgent
  ↓
GenerationSpecValidator
  ↓
SyntheticDataGeneratorTool
  ↓
GeneratedDataValidator
  ↓
MetadataBuilder
  ↓
ArtifactSaver
```

### `GenerationSpecAgent`

LLM-узел.

Вход:

```text
ContextMemory + final_features + RAG evidence
```

Выход:

```json
GenerationSpec
```

### `SyntheticDataGeneratorTool`

Не LLM. Обычный Python tool.

Вход:

```json
GenerationSpec
```

Выход:

```text
X, y, metadata
```

### `GeneratedDataValidator`

Не LLM. Обычный validator.

Вход:

```text
X, y, spec
```

Выход:

```json
ValidationReport
```

---

## 36. Почему маленькая модель справится

Потому что она решает не одну большую задачу:

```text
создай датасет 100000 × 19
```

а маленькую:

```text
верни JSON-спецификацию распределений и формул
```

Математически:

$
\text{LLM}: C \rightarrow S
$

где $C$ — контекст, $S$ — спецификация.

А затем:

$
\text{Python}: S \rightarrow (X, y)
$

Это намного проще и надёжнее.

---

## 37. Главный вывод

Маленькая LLM модель **не генерирует обучающую выборку напрямую**.

Она генерирует:

```text
1. GenerationSpec
2. объяснение
3. возможно, безопасный шаблон кода
4. repair-патчи к spec после ошибок валидатора
```

А обучающую выборку создаёт deterministic Python generator:

```text
GenerationSpec
→ NumPy/Pandas
→ X_train.csv
→ y_train.npy
→ metadata.json
→ validation report
```

Именно такой подход соответствует вашей архитектуре: в happy path Data Generator создаёт `100k × 19`, добавляет шум и аномалии, валидирует shape/NaN/inf/classes и сохраняет CSV/NPY/metadata, а LLM остаётся в роли планировщика и помощника по спецификации.   



# 22. Дополнение по context memory
Ниже `ContextMemory` — это не просто “память диалога”, а **единый typed state**, который передаётся между агентами LangGraph. Он фиксирует, что уже выяснено, какие решения приняты, какие признаки утверждены, какие данные нужно сгенерировать и какую модель рекомендовать.

Опорная идея: в ваших исходных документах задачи ML описаны через входы, выходы, алгоритмы и ограничения; например, для surface threat evaluation нужны `range`, `bearing`, `course`, `speed`, `CPA`, `TCPA`, environmental factors и historical threat patterns.  А данные тактической обстановки включают внешние условия, tactical objects, sensors, weapons, navigation и `tracks_fused`, то есть именно те блоки, из которых затем выводятся признаки. 

---

## 1. Блок постановки ML-задачи

```yaml
task_type: string
```

Тип ML-задачи.

Примеры:

```yaml
task_type: classification
task_type: regression
task_type: ranking
task_type: anomaly_detection
task_type: trajectory_forecasting
task_type: object_detection
task_type: reinforcement_learning
```

Зачем нужно: по этому полю система выбирает ветку пайплайна. Например, для `classification` нужны классы и `class_distribution`, для `regression` — числовая целевая переменная, для `trajectory_forecasting` — временные ряды и горизонт прогноза.

Пример:

```yaml
task_type: classification
```

Означает: система должна сформировать признаки $X$, метки $y$, классы, распределение классов, рекомендовать классификационные модели.

---

```yaml
target_variable: string
```

Целевая переменная, которую должна предсказывать ML-модель.

Примеры:

```yaml
target_variable: target_class
target_variable: threat_level
target_variable: collision_risk
target_variable: sensor_health_class
target_variable: future_position
```

Для задачи оценки угрозы это может быть:

```yaml
target_variable: threat_level
```

Тогда модель учит отображение:

$$
X \rightarrow y,
\quad
y \in {\text{low}, \text{medium}, \text{high}}.
$$

---

```yaml
required_latency: string | null
```

Требуемая задержка инференса или реакции системы.

Примеры:

```yaml
required_latency: "<100 ms"
required_latency: "1-5 sec"
required_latency: "batch/offline"
required_latency: null
```

Зачем нужно: это влияет на выбор модели. Если нужна задержка `<100 ms`, система не должна рекомендовать тяжёлый Transformer без edge-оптимизации. Для real-time radar/track задач latency критична; в документах встречаются задачи dynamic updates по radar scans, где обновления идут каждые 10–12 секунд. 

---

```yaml
deployment_context: string | null
```

Где будет работать модель.

Примеры:

```yaml
deployment_context: edge_device
deployment_context: shipboard_server
deployment_context: cloud
deployment_context: offline_research
deployment_context: operator_decision_support
```

Зачем нужно: один и тот же feature set может вести к разным моделям. На борту лучше выбирать компактные модели, в offline-аналитике можно использовать более тяжёлые ансамбли.

---

## 2. Блок профиля данных

```yaml
data_source: string
```

Источник данных.

Примеры:

```yaml
data_source: radar
data_source: AIS
data_source: sonar
data_source: ESM
data_source: tracks_fused
data_source: external_conditions
data_source: tactical_objects
```

В ваших материалах источники данных включают радары, AIS, sonar, EO/IR, ESM, fused tracks, weather, bathymetry, external conditions. 

---

```yaml
data_type: string
```

Формат данных.

Примеры:

```yaml
data_type: tabular
data_type: time_series
data_type: image
data_type: tensor
data_type: graph
data_type: event_log
```

Пример:

```yaml
data_type: tabular
```

Означает, что система будет строить таблицу признаков:

[
X \in \mathbb{R}^{N \times d}.
]

Если:

```yaml
data_type: time_series
```

то формат уже другой:

[
X \in \mathbb{R}^{N \times T \times d}.
]

---

```yaml
data_volume: int | string
```

Объём данных.

Примеры:

```yaml
data_volume: 50000
data_volume: "100k radar marks"
data_volume: "few thousand sonar echoes"
```

Зачем нужно: объём влияет на выбор модели и стратегию генерации. При малом объёме система может рекомендовать Random Forest, XGBoost, Bayesian model, transfer learning или synthetic augmentation.

---

```yaml
update_frequency: string | null
```

Частота обновления данных.

Примеры:

```yaml
update_frequency: "every 5 sec"
update_frequency: "per radar scan"
update_frequency: "hourly"
update_frequency: "daily batch"
update_frequency: null
```

Зачем нужно: отличает потоковую ML-задачу от offline-задачи. Например, `sensor_analytics_T` может считаться батчево за окно (T), а radar detection требует online updates.

---

```yaml
fields: list
```

Список доступных исходных полей.

Пример:

```yaml
fields:
  - range
  - bearing
  - course
  - speed
  - CPA
  - TCPA
  - rcs
  - snr
```

Это ключевое поле для Feature Synthesis Agent. Агент не должен предлагать признаки, которые невозможно посчитать из доступных полей.

---

```yaml
missing_data_strategy: string | null
```

Стратегия обработки пропусков.

Примеры:

```yaml
missing_data_strategy: none
missing_data_strategy: drop_rows
missing_data_strategy: mean_imputation
missing_data_strategy: forward_fill
missing_data_strategy: model_based_imputation
missing_data_strategy: add_missing_indicators
```

Если временной ряд, часто используется `forward_fill`. Если табличная классификация, часто полезно `median_imputation + missing_indicator`.

---

```yaml
class_distribution: dict | null
```

Распределение классов для классификации.

Пример:

```yaml
class_distribution:
  civilian_ship: 0.4
  military_ship: 0.3
  submarine: 0.2
  aircraft: 0.1
```

Зачем нужно: влияет на synthetic data generation, class weights, SMOTE, focal loss и метрики. Если поле отсутствует, система должна спросить пользователя или поставить `unknown`.

---

# 3. Блок предметной области

```yaml
domain: string
```

Предметная область.

Примеры:

```yaml
domain: maritime
domain: naval
domain: finance
domain: medicine
domain: industrial_iot
```

В вашем случае чаще всего:

```yaml
domain: naval
```

Это поле используется как metadata filter для RAG. Например, сначала ищутся документы с `domain: naval`, затем уже `task_type`, `data_source`, `feature_family`.

---

```yaml
critical_factors: list
```

Критичные факторы предметной области.

Пример для морской РЛС:

```yaml
critical_factors:
  - sea_state
  - jamming_level
  - visibility
  - radar_performance_factor
  - track_quality
  - class_imbalance
```

В исходных материалах внешние условия включают weather, sea state, electromagnetic environment, GNSS interference, tactical impact summary и другие факторы, влияющие на сенсоры и операции. 

---

```yaml
interpretability_requirement: high | medium | low
```

Требование к интерпретируемости.

Примеры:

```yaml
interpretability_requirement: high
```

Для тактических и safety-critical задач обычно `high`, потому что оператор должен понимать, почему цель получила высокий threat level.

Влияние:

```text
high   → Bayesian Network, Logistic Regression, Decision Tree, Explainable Boosting, SHAP
medium → Random Forest, XGBoost + SHAP
low    → Deep Neural Network, Transformer, CNN
```

---

```yaml
temporal_importance: bool | string
```

Нужна ли временная динамика.

Примеры:

```yaml
temporal_importance: false
temporal_importance: true
temporal_importance: "per-track sequence required"
```

Если `false`, можно строить признаки по одной отметке. Если `true`, нужны `timestamp`, `track_id`, история состояний, лаги, rolling aggregates.

Пример:

```yaml
temporal_importance: true
```

Тогда признаки могут быть:

```yaml
derived_features:
  - speed_delta_5s
  - bearing_rate
  - acceleration
  - track_drop_rate
  - revisit_time_mean
```

---

# 4. Блок признаков

```yaml
base_features: list
```

Первичные признаки, напрямую взятые из данных.

Пример:

```yaml
base_features:
  - range
  - bearing
  - course
  - speed
  - rcs
  - snr
```

Это признаки, которые не требуют формул.

---

```yaml
derived_features: list
```

Производные признаки, рассчитанные из базовых.

Примеры:

```yaml
derived_features:
  - closing_speed
  - time_to_closest_approach
  - rcs_normalized
  - signal_quality
  - bearing_rate
```

Для сенсоров ваши аналитические документы предлагают признаки вроде `detection_probability_T`, `false_alarm_rate_T`, `avg_position_error`, `track_drop_rate`, `revisit_time_stats`, `performance_drop_by_weather`, `jammed_time_ratio`. 

---

```yaml
interaction_features: list
```

Признаки взаимодействия между базовыми и производными признаками.

Примеры:

```yaml
interaction_features:
  - range_x_snr
  - rcs_x_snr
  - speed_x_heading_angle
  - sea_state_x_radar_performance
  - jamming_x_detection_probability
```

Зачем нужно: многие эффекты нелинейны. Например, `snr` сам по себе важен, но `range_x_snr` может лучше отражать деградацию качества обнаружения на дальности.

---

```yaml
final_features: list
```

Итоговый утверждённый набор признаков.

Пример:

```yaml
final_features:
  - range
  - bearing
  - speed
  - rcs
  - snr
  - closing_speed
  - cpa
  - tcpa
  - range_x_snr
  - track_quality
```

Это главный выход Feature Synthesis Agent и вход для Data Generation Agent, Model Selection Agent и Export Agent.

Важно: `final_features` должны быть подмножеством или вычислимым замыканием:

[
final_features \subseteq base_features \cup derived_features \cup interaction_features.
]

---

# 5. Блок генерации обучающей выборки

```yaml
n_samples: int
```

Число синтетических или целевых обучающих примеров.

Пример:

```yaml
n_samples: 100000
```

Используется Data Generation Agent.

---

```yaml
class_imbalance_ratio: float
```

Индекс дисбаланса классов.

Простой вариант:

[
class_imbalance_ratio =
\frac{\max_c n_c}{\min_c n_c}.
]

Пример:

```yaml
class_imbalance_ratio: 4.0
```

Если самый частый класс встречается в 40% случаев, а самый редкий в 10%, то:

[
\frac{0.4}{0.1}=4.
]

Зачем нужно: если ratio высокий, система должна включить class weights, stratified split, oversampling или специальные метрики.

---

```yaml
noise_level: float
```

Уровень шума при генерации данных или моделировании ошибок измерений.

Пример:

```yaml
noise_level: 0.01
```

Интерпретация:

[
X' = X + \epsilon,
\quad
\epsilon \sim \mathcal{N}(0, \sigma^2).
]

---

```yaml
anomaly_rate: float
```

Доля аномальных примеров в синтетической выборке.

Пример:

```yaml
anomaly_rate: 0.02
```

Означает: 2% объектов будут содержать выбросы, sensor glitches, невозможные значения, rare events или false tracks.

---

# 6. Блок выбора модели

```yaml
recommended_model: string
```

Главная рекомендованная модель.

Примеры:

```yaml
recommended_model: XGBoostClassifier
recommended_model: RandomForestClassifier
recommended_model: BayesianNetwork
recommended_model: LSTM
recommended_model: CNN
recommended_model: YOLOv7
```

Выбирается на основе `task_type`, `data_type`, `data_volume`, `latency`, `interpretability_requirement`.

---

```yaml
model_ranking: list
```

Список top-N моделей с аргументацией.

Пример:

```yaml
model_ranking:
  - model: XGBoostClassifier
    reason: "tabular data, medium data volume, strong baseline"
  - model: RandomForestClassifier
    reason: "robust, interpretable via feature importance"
  - model: BayesianNetwork
    reason: "high interpretability for threat inference"
```

Для surface threat evaluation исходный документ прямо указывает Bayesian Networks, Dynamic Bayesian inference и Fuzzy Logic как подходящие алгоритмы для оценки угроз при неопределённости. 

---

```yaml
training_config: dict
```

Конфигурация обучения.

Пример:

```yaml
training_config:
  split:
    train: 0.7
    validation: 0.15
    test: 0.15
  metrics:
    - f1_macro
    - balanced_accuracy
    - roc_auc_ovr
  class_weight: balanced
  cross_validation: stratified_5_fold
  random_state: 42
```

Это поле должно быть машинно-исполняемым: Export Agent может положить его в `training_config.yaml`.

---

# 7. Блок диалога и обратной связи

```yaml
conversation_id: string
```

Идентификатор пользовательской сессии.

Пример:

```yaml
conversation_id: conv_2026_05_18_001
```

Зачем нужно: связывает все решения, артефакты, вопросы, ответы, RAG evidence и generated files.

---

```yaml
user_feedback: list
```

История уточнений и подтверждений пользователя.

Пример:

```yaml
user_feedback:
  - phase: feature_synthesis
    message: "Исключить временные признаки, каждая отметка независима"
    action: "removed temporal features"
  - phase: model_selection
    message: "Нужна интерпретируемость"
    action: "prioritized BayesianNetwork and XGBoost+SHAP"
```

Зачем нужно: маленькая LLM не должна держать всё в контексте. Она должна читать короткую структурированную память.

---

# 8. Как это выглядит как заполненный ContextMemory

```yaml
task_type: classification
target_variable: target_class
required_latency: "batch/offline"
deployment_context: "prototype"

data_source: radar
data_type: tabular
data_volume: 50000
update_frequency: null
fields:
  - range
  - azimuth
  - elevation
  - rcs
  - snr
  - doppler
missing_data_strategy: none
class_distribution:
  civilian_ship: 0.4
  military_ship: 0.3
  submarine: 0.2
  aircraft: 0.1

domain: naval
critical_factors:
  - rcs
  - snr
  - doppler
  - radar_performance_factor
  - jamming_level
interpretability_requirement: high
temporal_importance: false

base_features:
  - range
  - azimuth
  - elevation
  - rcs
  - snr
  - doppler
derived_features:
  - signal_quality
  - rcs_normalized
  - elevation_category
  - distance_class
interaction_features:
  - range_x_snr
  - rcs_x_snr
  - doppler_x_elevation
final_features:
  - range
  - azimuth
  - elevation
  - rcs
  - snr
  - doppler
  - signal_quality
  - rcs_normalized
  - elevation_category
  - distance_class
  - range_x_snr
  - rcs_x_snr
  - doppler_x_elevation

n_samples: 100000
class_imbalance_ratio: 4.0
noise_level: 0.01
anomaly_rate: 0.02

recommended_model: XGBoostClassifier
model_ranking:
  - model: XGBoostClassifier
    reason: "good for tabular multiclass classification"
  - model: RandomForestClassifier
    reason: "robust baseline and interpretable feature importance"
  - model: BayesianNetwork
    reason: "high interpretability for operator-facing decision support"
training_config:
  split:
    train: 0.7
    validation: 0.15
    test: 0.15
  metrics:
    - f1_macro
    - balanced_accuracy
    - confusion_matrix
  class_weight: balanced
  random_state: 42

conversation_id: conv_001
user_feedback:
  - phase: data_profiling
    message: "No missing values"
    action: "missing_data_strategy set to none"
```

---

# 9. Главный смысл `ContextMemory`

`ContextMemory` должен быть не текстовой историей, а **контрактом состояния**:

[
ContextMemory_t =
{
Task,\ Data,\ Domain,\ Features,\ Generation,\ Model,\ Dialogue
}.
]

Тогда каждый агент работает не со всей перепиской, а с нужной частью:

| Агент                   | Какие поля читает                          | Какие поля пишет                                                              |
| ----------------------- | ------------------------------------------ | ----------------------------------------------------------------------------- |
| NLU Agent               | `conversation_id`, `user_feedback`         | `task_type`, `domain`, `data_source`                                          |
| Data Profiling Agent    | `data_source`, `fields`                    | `data_type`, `data_volume`, `missing_data_strategy`, `class_distribution`     |
| Domain Context Agent    | `domain`, `data_source`                    | `critical_factors`, `interpretability_requirement`, `temporal_importance`     |
| Feature Synthesis Agent | `fields`, `critical_factors`               | `base_features`, `derived_features`, `interaction_features`, `final_features` |
| Data Generation Agent   | `final_features`, `class_distribution`     | `n_samples`, `noise_level`, `anomaly_rate`                                    |
| Model Selection Agent   | `task_type`, `data_type`, `final_features` | `recommended_model`, `model_ranking`, `training_config`                       |
| Export Agent            | всё                                        | файлы и архив                                                                 |

Именно так маленькая LLM сможет устойчиво работать: она не “помнит всё”, а читает компактный state и обновляет только свои поля.


