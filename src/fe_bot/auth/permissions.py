"""Permissions для SETUP-01.

Permissions перечислены в docs/02-system/features/SETUP-01-setup-wizard.md §5.3.
Связь role → permissions фиксируется здесь же.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    """Минимальный набор permissions для SETUP-01 (см. §5.3)."""

    KB_SETUP_CREATE = "kb.setup.create"
    KB_DOCUMENT_UPLOAD = "kb.document.upload"
    KB_DOCUMENT_DELETE = "kb.document.delete"  # SETUP-02 / T-S02-014
    KB_SETUP_RUN = "kb.setup.run"
    KB_CARD_REVIEW = "kb.card.review"
    KB_PUBLISH = "kb.publish"
    KB_REPORT_READ = "kb.report.read"
    KB_ADMIN_CLEANUP = "kb.admin.cleanup"  # SETUP-02 / T-S02-023

    # SETUP-03 / T-S03-016: source registry permissions family.
    KB_SOURCE_LIST = "kb.source.list"
    KB_SOURCE_READ = "kb.source.read"
    KB_SOURCE_METADATA_UPDATE = "kb.source.metadata.update"
    KB_SOURCE_REMOVE = "kb.source.remove"
    KB_SOURCE_LINEAGE_READ = "kb.source.lineage.read"
    KB_SOURCE_LOG_READ = "kb.source.log.read"

    # SETUP-04 / T-S04-023: document parsing permissions family.
    KB_PARSE_RUN = "kb.parse.run"
    KB_PARSE_STATUS_READ = "kb.parse.status.read"
    KB_SECTION_READ = "kb.section.read"
    KB_PARSE_RETRY = "kb.parse.retry"
    KB_PARSE_CANCEL = "kb.parse.cancel"

    # SETUP-05 / T-S05-026: RAG card generation permissions family.
    KB_RAG_CARD_GENERATE = "kb.rag_card.generate"
    KB_RAG_CARD_READ = "kb.rag_card.read"
    KB_RAG_CARD_REGENERATE = "kb.rag_card.regenerate"
    KB_RAG_CARD_PREVIEW = "kb.rag_card.preview"
    KB_RAG_CARD_LINEAGE_READ = "kb.rag_card.lineage.read"

    # SETUP-06 / T-S06-024: RAG card review permissions family.
    KB_RAG_CARD_LIST = "kb.rag_card.list"
    KB_RAG_CARD_EDIT = "kb.rag_card.edit"
    KB_RAG_CARD_APPROVE = "kb.rag_card.approve"
    KB_RAG_CARD_REJECT = "kb.rag_card.reject"
    KB_RAG_CARD_VERSION_READ = "kb.rag_card.version.read"
    KB_RAG_CARD_DIFF_READ = "kb.rag_card.diff.read"
    KB_RAG_CARD_REVIEW_LOG_READ = "kb.rag_card.review_log.read"
    KB_RAG_CARD_VALIDATION_READ = "kb.rag_card.validation.read"
    KB_RAG_CARD_SOURCE_TRACE_READ = "kb.rag_card.source_trace.read"
    KB_RAG_CARD_BULK_REVIEW = "kb.rag_card.bulk_review"

    # SETUP-07 / T-S07-011: metadata validation permissions family.
    KB_VALIDATION_READ = "kb.validation.read"
    KB_VALIDATION_RUN = "kb.validation.run"
    KB_VALIDATION_REFRESH = "kb.validation.refresh"

    # SETUP-08 / T-S08-011: chunking permissions family.
    KB_CHUNKING_READ = "kb.chunking.read"
    KB_CHUNKING_RUN = "kb.chunking.run"
    KB_CHUNKING_REFRESH = "kb.chunking.refresh"

    # SETUP-12 / T-S12-070: hierarchical taxonomy read.
    KB_TAXONOMY_READ = "kb.taxonomy.read"

    # SETUP-13: classifier library (generic tree + per-node prompts).
    KB_CLASSIFIER_READ = "kb.classifier.read"
    KB_CLASSIFIER_WRITE = "kb.classifier.write"


class Role(StrEnum):
    USER = "user"
    DOMAIN_EXPERT = "domain_expert"
    RAG_ADMIN = "rag_admin"
    ADMIN = "admin"
    AUDITOR = "auditor"


# Какие permissions даёт каждая роль.
_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.USER: frozenset(
        {
            Permission.KB_SETUP_CREATE,
            Permission.KB_DOCUMENT_UPLOAD,
            # user может удалять свои документы в pre-pipeline состоянии
            Permission.KB_DOCUMENT_DELETE,
            Permission.KB_SETUP_RUN,
            Permission.KB_REPORT_READ,
            # SETUP-03: user видит и редактирует свои документы.
            Permission.KB_SOURCE_LIST,
            Permission.KB_SOURCE_READ,
            Permission.KB_SOURCE_METADATA_UPDATE,
            Permission.KB_SOURCE_REMOVE,
            # SETUP-04: user может запускать парсинг и читать его результат.
            Permission.KB_PARSE_RUN,
            Permission.KB_PARSE_STATUS_READ,
            Permission.KB_SECTION_READ,
            # SETUP-05: user может генерировать карточки и читать preview.
            Permission.KB_RAG_CARD_GENERATE,
            Permission.KB_RAG_CARD_READ,
            Permission.KB_RAG_CARD_PREVIEW,
            # SETUP-06: user может проверять, принимать, отклонять и редактировать
            # карточки своих setup jobs.
            Permission.KB_RAG_CARD_LIST,
            Permission.KB_RAG_CARD_APPROVE,
            Permission.KB_RAG_CARD_REJECT,
            Permission.KB_RAG_CARD_EDIT,
            Permission.KB_RAG_CARD_VERSION_READ,
            Permission.KB_RAG_CARD_DIFF_READ,
            Permission.KB_RAG_CARD_REVIEW_LOG_READ,
            Permission.KB_RAG_CARD_VALIDATION_READ,
            Permission.KB_RAG_CARD_SOURCE_TRACE_READ,
            # SETUP-07: user может читать validation reports + запускать
            # валидацию по своему setup_job + перевалидировать карточки.
            Permission.KB_VALIDATION_READ,
            Permission.KB_VALIDATION_RUN,
            Permission.KB_VALIDATION_REFRESH,
            # SETUP-08: user — полный chunking цикл по своему setup_job.
            Permission.KB_CHUNKING_READ,
            Permission.KB_CHUNKING_RUN,
            Permission.KB_CHUNKING_REFRESH,
            # SETUP-12: read-only доступ к таксономии для отображения дерева.
            Permission.KB_TAXONOMY_READ,
            # SETUP-13: полный доступ к библиотеке классификаторов (новый шаг мастера).
            Permission.KB_CLASSIFIER_READ,
            Permission.KB_CLASSIFIER_WRITE,
        }
    ),
    Role.DOMAIN_EXPERT: frozenset(
        {
            Permission.KB_SETUP_CREATE,
            Permission.KB_DOCUMENT_UPLOAD,
            Permission.KB_DOCUMENT_DELETE,
            Permission.KB_SETUP_RUN,
            Permission.KB_CARD_REVIEW,
            Permission.KB_REPORT_READ,
            # Эксперт видит lineage/log для проверки источников.
            Permission.KB_SOURCE_LIST,
            Permission.KB_SOURCE_READ,
            Permission.KB_SOURCE_METADATA_UPDATE,
            Permission.KB_SOURCE_LINEAGE_READ,
            Permission.KB_SOURCE_LOG_READ,
            # SETUP-04: эксперт может ретраить упавшие документы.
            Permission.KB_PARSE_RUN,
            Permission.KB_PARSE_STATUS_READ,
            Permission.KB_SECTION_READ,
            Permission.KB_PARSE_RETRY,
            # SETUP-05: эксперт может регенерировать карточки и читать lineage.
            Permission.KB_RAG_CARD_GENERATE,
            Permission.KB_RAG_CARD_READ,
            Permission.KB_RAG_CARD_PREVIEW,
            Permission.KB_RAG_CARD_REGENERATE,
            Permission.KB_RAG_CARD_LINEAGE_READ,
            # SETUP-06: эксперт — полный review-цикл.
            Permission.KB_RAG_CARD_LIST,
            Permission.KB_RAG_CARD_APPROVE,
            Permission.KB_RAG_CARD_REJECT,
            Permission.KB_RAG_CARD_EDIT,
            Permission.KB_RAG_CARD_VERSION_READ,
            Permission.KB_RAG_CARD_DIFF_READ,
            Permission.KB_RAG_CARD_REVIEW_LOG_READ,
            Permission.KB_RAG_CARD_VALIDATION_READ,
            Permission.KB_RAG_CARD_SOURCE_TRACE_READ,
            # SETUP-07: эксперт — полный validation цикл.
            Permission.KB_VALIDATION_READ,
            Permission.KB_VALIDATION_RUN,
            Permission.KB_VALIDATION_REFRESH,
            # SETUP-08: эксперт — полный chunking цикл.
            Permission.KB_CHUNKING_READ,
            Permission.KB_CHUNKING_RUN,
            Permission.KB_CHUNKING_REFRESH,
            # SETUP-12: read-only доступ к таксономии.
            Permission.KB_TAXONOMY_READ,
            # SETUP-13: полный доступ к библиотеке классификаторов.
            Permission.KB_CLASSIFIER_READ,
            Permission.KB_CLASSIFIER_WRITE,
        }
    ),
    Role.RAG_ADMIN: frozenset(
        {
            Permission.KB_SETUP_CREATE,
            Permission.KB_DOCUMENT_UPLOAD,
            Permission.KB_DOCUMENT_DELETE,
            Permission.KB_SETUP_RUN,
            Permission.KB_CARD_REVIEW,
            Permission.KB_PUBLISH,
            Permission.KB_REPORT_READ,
            # RAG-админ имеет полный доступ к Source Registry.
            Permission.KB_SOURCE_LIST,
            Permission.KB_SOURCE_READ,
            Permission.KB_SOURCE_METADATA_UPDATE,
            Permission.KB_SOURCE_REMOVE,
            Permission.KB_SOURCE_LINEAGE_READ,
            Permission.KB_SOURCE_LOG_READ,
            # SETUP-04: RAG-админ — полный доступ к парсингу.
            Permission.KB_PARSE_RUN,
            Permission.KB_PARSE_STATUS_READ,
            Permission.KB_SECTION_READ,
            Permission.KB_PARSE_RETRY,
            Permission.KB_PARSE_CANCEL,
            # SETUP-05: RAG-админ — полный доступ к card generation.
            Permission.KB_RAG_CARD_GENERATE,
            Permission.KB_RAG_CARD_READ,
            Permission.KB_RAG_CARD_PREVIEW,
            Permission.KB_RAG_CARD_REGENERATE,
            Permission.KB_RAG_CARD_LINEAGE_READ,
            # SETUP-06: RAG-админ — полный review-цикл + bulk approve.
            Permission.KB_RAG_CARD_LIST,
            Permission.KB_RAG_CARD_APPROVE,
            Permission.KB_RAG_CARD_REJECT,
            Permission.KB_RAG_CARD_EDIT,
            Permission.KB_RAG_CARD_VERSION_READ,
            Permission.KB_RAG_CARD_DIFF_READ,
            Permission.KB_RAG_CARD_REVIEW_LOG_READ,
            Permission.KB_RAG_CARD_VALIDATION_READ,
            Permission.KB_RAG_CARD_SOURCE_TRACE_READ,
            Permission.KB_RAG_CARD_BULK_REVIEW,
            # SETUP-07: RAG-админ — полный validation цикл.
            Permission.KB_VALIDATION_READ,
            Permission.KB_VALIDATION_RUN,
            Permission.KB_VALIDATION_REFRESH,
            # SETUP-08: RAG-админ — полный chunking цикл.
            Permission.KB_CHUNKING_READ,
            Permission.KB_CHUNKING_RUN,
            Permission.KB_CHUNKING_REFRESH,
            # SETUP-12: read-only доступ к таксономии.
            Permission.KB_TAXONOMY_READ,
            # SETUP-13: полный доступ к библиотеке классификаторов.
            Permission.KB_CLASSIFIER_READ,
            Permission.KB_CLASSIFIER_WRITE,
        }
    ),
    Role.ADMIN: frozenset(Permission),  # все
    Role.AUDITOR: frozenset(
        {
            Permission.KB_REPORT_READ,
            # Auditor — read-only по всему Source Registry.
            Permission.KB_SOURCE_LIST,
            Permission.KB_SOURCE_READ,
            Permission.KB_SOURCE_LINEAGE_READ,
            Permission.KB_SOURCE_LOG_READ,
            # SETUP-04: auditor видит статус парсинга и секции.
            Permission.KB_PARSE_STATUS_READ,
            Permission.KB_SECTION_READ,
            # SETUP-05: auditor видит карточки + preview + lineage (read-only).
            Permission.KB_RAG_CARD_READ,
            Permission.KB_RAG_CARD_PREVIEW,
            Permission.KB_RAG_CARD_LINEAGE_READ,
            # SETUP-06: auditor — read-only по review log/versions/diff.
            Permission.KB_RAG_CARD_LIST,
            Permission.KB_RAG_CARD_VERSION_READ,
            Permission.KB_RAG_CARD_DIFF_READ,
            Permission.KB_RAG_CARD_REVIEW_LOG_READ,
            Permission.KB_RAG_CARD_VALIDATION_READ,
            Permission.KB_RAG_CARD_SOURCE_TRACE_READ,
            # SETUP-07: auditor — read-only по validation reports.
            Permission.KB_VALIDATION_READ,
            # SETUP-08: auditor — read-only по manifest.
            Permission.KB_CHUNKING_READ,
            # SETUP-12: read-only доступ к таксономии.
            Permission.KB_TAXONOMY_READ,
            # SETUP-13: read-only доступ к библиотеке классификаторов.
            Permission.KB_CLASSIFIER_READ,
        }
    ),
}


def permissions_for_roles(roles: frozenset[Role]) -> frozenset[Permission]:
    """Сворачивает permissions всех ролей в одно множество."""
    result: set[Permission] = set()
    for role in roles:
        result.update(_ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(result)
