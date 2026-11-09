# PLATFORM-05. RAG Retrieval и Evidence Pack

## Назначение

Единая точка, через которую каждый Runtime-агент получает знания из активной базы знаний: по текущей фазе и срезу `ContextMemory` строится retrieval-запрос с metadata-фильтрами, выполняется поиск в Vector DB, а результат сжимается в `EvidencePack`. Агенты видят только этот пакет, а не сырые карточки.

## Бизнес-ценность

Маленькая LLM (4k–8k токенов контекста) не справляется с «полными» карточками и склонна выдумывать факты, если контекста нет. Фича даёт агентам компактный, отфильтрованный по домену и фазе контекст, а пользователю — возможность увидеть, на каких документах основана рекомендация признака или модели (цели [G-02](../../01-business/goals.md), [G-04](../../01-business/goals.md)).

## Вход и выход

- **Вход.** Запрос агента: имя агента, текущая фаза, срез `ContextMemory` (`domain`, `data_source`, `task_type`), подсказки по слотам; активная `kb_version`.
- **Выход.** `EvidencePack` — список элементов с `doc_id`, `chunk_id`, `chunk_type`, `slot`, `snippet` (≤ 800 символов), `metadata_summary`, `score`; либо сигнал «контекста нет» (`need_more_context = true`), если подходящих карточек не найдено.

## Пользовательский сценарий

Пользователь retrieval напрямую не вызывает. Он видит его результат: рядом с каждым предложенным признаком, моделью или уточняющим вопросом доступны `evidence_doc_ids` — ответ на вопрос «почему система это предложила». Если база знаний не содержит нужного, система не угадывает, а просит уточнить.

## Связанные требования

- BR-FR-020 (RAG используется на всех содержательных этапах: нормализация терминов, доменный контекст, feature patterns, проверка физического смысла, рекомендации моделей, шаблоны вопросов, объяснения).
- BR-FR-021 (структура RAG-индекса: коллекции по назначению; см. «Открытые вопросы»).
- BR-FR-022 (обязательная metadata каждого RAG-документа — [metadata-schema.md](../../06-rag/metadata-schema.md)).
- BR-FR-023 (рекомендации основаны на evidence; при его отсутствии — `need_more_context = true`).
- FR-RAG-001..004 — фильтры по metadata, план retrieval по политикам, `EvidencePack` вместо сырых результатов, валидированная metadata.
- NFR-Perf-002 (vector search ≤ 50 мс p95), NFR-Rel-002 (нет контекста → generic-режим и `need_more_context`), NFR-Rel-004 (retry с backoff), NFR-Obs-003 (audit retrieval).

## Связанные агенты / сервисы

- `RAGRetrievalAgent` ([спецификация](../../05-agents/rag-retrieval-agent.md)).
- RAG Retrieval Service (SVC-21), Evidence Pack Builder (SVC-22), Knowledge Base Registry (SVC-15), Vector DB (Qdrant).

## Связанные контракты

- `EvidencePack`, `EvidenceItem` — [evidence-pack.md](../../06-rag/evidence-pack.md).
- `RetrievalQueryDTO`, `RetrievedChunkDTO`, `EvidencePackDTO` — [data-transfer-objects.md](../../03-architecture/services/data-transfer-objects.md).

## Связанные RAG-документы

- [retrieval-policies.md](../../06-rag/retrieval-policies.md) — шаблон запроса для каждой пары (агент, фаза): фильтры, top-K, порог похожести.
- [document-types.md](../../06-rag/document-types.md) — какие типы карточек читает какой агент.

## Критерии приёмки

- Retrieval ОБЯЗАН возвращать только карточки, чья metadata соответствует текущим фильтрам `phase`, `domain`, `data_source`, `task_type`; фильтрация по metadata предшествует семантическому поиску.
- Агент ОБЯЗАН получать `EvidencePack`; сырые карточки не передаются. Каждый `snippet` — не длиннее 800 символов; из каждого `chunk_type` берётся ограниченное число лучших элементов.
- `evidence_doc_ids` в выводе агента ОБЯЗАНЫ быть подмножеством `doc_id` из выданного `EvidencePack`.
- При нуле найденных документов retrieval ОБЯЗАН вернуть `need_more_context = true`. Допустимо ослабить фильтры по `data_source` и `task_type`, но не по `domain`.
- При недоступности Vector DB — три повтора с backoff (200 мс / 1 с / 5 с), затем структурированная ошибка `vector_db_unavailable`.
- Каждый вызов ОБЯЗАН попадать в audit: `rag_query_id`, `retrieved_doc_ids`, `retrieved_chunk_ids`, применённые фильтры.
- Тесты: `tests/component/test_rag_retrieval_agent.py`, кейсы в `tests/rag_eval/`.

## Открытые вопросы

- `BR-FR-021` перечисляет восемь коллекций индекса. Пять из них соответствуют типам документов (`domain_profiles` → `domain_profile`, `feature_library` → `feature_pattern_card`, `model_recommendations` → `model_recommendation_card`, `question_templates` → `question_template_card`, `glossary` → `glossary_term`). Для `model_configs`, `feature_analysis` и `response_templates` типов документов в [document-types.md](../../06-rag/document-types.md) нет. Нужно решить, добавлять ли такие типы или исключить их из требования.

## Вне scope

- Построение индекса и публикация базы знаний — стадия Setup ([SETUP-09](SETUP-09-embeddings-index.md), [SETUP-11](SETUP-11-publish-kb.md)).
- Аналитика качества retrieval — [ANALYTICS-02](ANALYTICS-02-rag-quality.md).
