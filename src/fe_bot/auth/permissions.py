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
    KB_SETUP_RUN = "kb.setup.run"
    KB_CARD_REVIEW = "kb.card.review"
    KB_PUBLISH = "kb.publish"
    KB_REPORT_READ = "kb.report.read"


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
            Permission.KB_SETUP_RUN,
            Permission.KB_REPORT_READ,
        }
    ),
    Role.DOMAIN_EXPERT: frozenset(
        {
            Permission.KB_SETUP_CREATE,
            Permission.KB_DOCUMENT_UPLOAD,
            Permission.KB_SETUP_RUN,
            Permission.KB_CARD_REVIEW,
            Permission.KB_REPORT_READ,
        }
    ),
    Role.RAG_ADMIN: frozenset(
        {
            Permission.KB_SETUP_CREATE,
            Permission.KB_DOCUMENT_UPLOAD,
            Permission.KB_SETUP_RUN,
            Permission.KB_CARD_REVIEW,
            Permission.KB_PUBLISH,
            Permission.KB_REPORT_READ,
        }
    ),
    Role.ADMIN: frozenset(Permission),  # все
    Role.AUDITOR: frozenset({Permission.KB_REPORT_READ}),
}


def permissions_for_roles(roles: frozenset[Role]) -> frozenset[Permission]:
    """Сворачивает permissions всех ролей в одно множество."""
    result: set[Permission] = set()
    for role in roles:
        result.update(_ROLE_PERMISSIONS.get(role, frozenset()))
    return frozenset(result)
