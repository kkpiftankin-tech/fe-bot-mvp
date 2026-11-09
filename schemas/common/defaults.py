"""Дефолты для открытых вопросов SETUP-01 §22.3.

Каждая константа — это временное решение до соответствующего ADR.
TODO-маркеры явно показывают, что ждёт формального решения.
"""

from __future__ import annotations

# TODO[ADR-006]: Максимальный размер одного файла. Согласовать с Product Owner.
MAX_FILE_SIZE_BYTES: int = 100 * 1024 * 1024  # 100 MB

# TODO[ADR-007]: Embedding-модель по умолчанию.
# nomic-embed-text — 768d, lightweight, есть в Ollama.
DEFAULT_EMBEDDING_MODEL: str = "nomic-embed-text"
DEFAULT_EMBEDDING_DIMENSION: int = 768

# Generation-модель по умолчанию для лёгких узких LLM-задач (RAG card
# generation, черновик описания класса классификатора и т.п.) — единая
# точка правды вместо копии строки "llama3.2" в каждом потребителе
# (LLMGateway.DEFAULT_MODEL, card_generator, rag_card_generation,
# classifier.description_generator, GenerateRAGCardsRequest.llm_model).
DEFAULT_LLM_MODEL: str = "llama3.2"

# Модель для многоуровневой классификации фрагмента по дереву
# классификаторов (SETUP-13 / ADR-HTC-09) — НЕ равна DEFAULT_LLM_MODEL
# осознанно: llama3.2 (3.2B) на живых тестах систематически не различал
# содержание фрагментов (стабильно уходил в один и тот же класс, включая
# заведомо нерелевантные тексты) — см. ADR-HTC-09 §"Реализовано" и
# docs/02-system/features/SETUP-13-classifier-library.md §7 для деталей
# эксперимента. qwen2.5:7b даёт содержательно верную классификацию,
# заметно медленнее (~2-3x latency на уровень дерева).
DEFAULT_CLASSIFIER_MODEL: str = "qwen2.5:7b"

# TODO[ADR-008]: Разрешена ли публикация KB с warning-ами retrieval-тестов.
ALLOW_PUBLISH_WITH_WARNINGS: bool = False

# TODO[ADR-009]: OCR для PDF в MVP. Решение: out of scope.
ENABLE_OCR: bool = False

# TODO[ADR-010]: Хранилище RAG-карточек. Решение: MinIO (Object Storage) для MVP.
RAG_CARDS_STORAGE: str = "object_storage"  # "git" | "object_storage" | "postgres"

# TODO[ADR-011]: Несколько active KB на проект. MVP: одна active KB на проект.
ALLOW_MULTIPLE_ACTIVE_KB_PER_PROJECT: bool = False

# TODO[ADR-012]: Минимальный pass rate retrieval smoke tests для публикации.
MIN_RETRIEVAL_RECALL_AT_5: float = 0.85
MIN_RETRIEVAL_PRECISION_AT_5: float = 0.70
MAX_NO_CONTEXT_RATE: float = 0.05

# Поддерживаемые форматы исходных файлов (MVP).
SUPPORTED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        "text/markdown",
        "text/plain",
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/csv",
        "application/json",
    }
)

SUPPORTED_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {"md", "txt", "pdf", "docx", "xlsx", "csv", "json"}
)

# TODO[SETUP-02-Q2]: Максимальное количество файлов в одном batch-upload.
# Согласовать с Architect (см. SETUP-02 §22.3).
MAX_BATCH_FILES_COUNT: int = 50

# TODO[SETUP-02-Q3]: Максимальный суммарный размер batch-upload.
# Согласовать с Architect (см. SETUP-02 §22.3).
MAX_TOTAL_BATCH_SIZE_BYTES: int = 500 * 1024 * 1024  # 500 MB
