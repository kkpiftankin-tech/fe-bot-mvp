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
        }
    ),
}


def permissions_for_roles(roles: frozenset[Role]) -> frozenset[Permission]:
    """Сворачивает permissions всех ролей в одно множество."""
    result: set[Permission] = set()
    for role in roles:
        result.update(_ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(result)
