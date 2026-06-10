# Доменная модель

## Назначение

Зафиксировать ключевые концепции, отношения между ними и инварианты, на которые опирается код, контракты и валидаторы. Доменная модель не привязана к Pydantic-схемам один-в-один — Pydantic-схема может объединять несколько концепций или, наоборот, проецировать одну концепцию на несколько схем.

## Высокоуровневая карта

```text
SourceDocument ──► ParsedSection ──► RAGCard ──► RAGChunk ──► VectorIndex
                                          │
                                          ▼
                                     EvidencePack ◄──── RAGRetrievalAgent
                                          │
                                          ▼
Conversation ──► ContextMemory ──► AgentRun ──► FeatureCandidate ──► FeatureSpec
                                                                          │
                                                                          ▼
                                                                   GenerationSpec ──► GeneratedDataset
                                                                                              │
                                                                                              ▼
                                                                                       ModelRecommendation
                                                                                              │
                                                                                              ▼
                                                                                       ExportManifest
                                                                                              │
                                                                                              ▼
                                                                                          archive.zip
                                                                                          (Artifact)
```

Сквозной актор: `AuditNode` цепляется к каждой стрелке, превращая граф в proveable audit trail.

## Стадийная принадлежность

| Концепция | Setup | Runtime | Analytics |
| --- | --- | --- | --- |
| `SourceDocument` | владеет | читает | читает |
| `ParsedSection` | владеет | — | читает |
| `RAGCard` | владеет, версионирует | читает (через `EvidencePack`) | читает |
| `RAGChunk` | владеет | читает | читает |
| `KnowledgeBaseVersion` | владеет, публикует | привязка conversation | читает |
| `Conversation` / `ContextMemory` | — | владеет | читает |
| `AgentRun` | — | владеет | читает |
| `FeatureCandidate` / `FeatureSpec` | — | владеет | читает |
| `ValidationReport` | используется (валидация карточек) | владеет (валидация признаков/данных) | читает |
| `GenerationSpec` / `GeneratedDataset` | — | владеет | читает |
| `ModelRecommendation` / `TrainingConfig` | — | владеет | читает |
| `Artifact` / `ExportManifest` | — | владеет | читает |
| `AuditNode` / `AuditChain` | владеет | владеет | читает |

## Связанные документы

- [entities.md](entities.md) — детальное описание сущностей.
- [value-objects.md](value-objects.md) — value-types, не имеющие identity.
- [domain-events.md](domain-events.md) — что происходит в системе.
- [invariants.md](invariants.md) — что обязано оставаться истинным.
- [../01-business/glossary.md](../01-business/glossary.md)
