"""Тесты Auth Service (T-S01-007)."""

from __future__ import annotations

import pytest

from fe_bot.auth.permissions import Permission, Role, permissions_for_roles
from fe_bot.auth.service import (
    AuthService,
    ForbiddenError,
    UnauthenticatedError,
)

pytestmark = pytest.mark.unit


class TestPermissionsMatrix:
    def test_user_has_basic_permissions(self) -> None:
        perms = permissions_for_roles(frozenset({Role.USER}))
        assert Permission.KB_SETUP_CREATE in perms
        assert Permission.KB_DOCUMENT_UPLOAD in perms
        assert Permission.KB_PUBLISH not in perms
        assert Permission.KB_CARD_REVIEW not in perms

    def test_domain_expert_can_review(self) -> None:
        perms = permissions_for_roles(frozenset({Role.DOMAIN_EXPERT}))
        assert Permission.KB_CARD_REVIEW in perms
        assert Permission.KB_PUBLISH not in perms

    def test_rag_admin_can_publish(self) -> None:
        perms = permissions_for_roles(frozenset({Role.RAG_ADMIN}))
        assert Permission.KB_PUBLISH in perms
        assert Permission.KB_CARD_REVIEW in perms

    def test_admin_has_all(self) -> None:
        perms = permissions_for_roles(frozenset({Role.ADMIN}))
        assert perms == frozenset(Permission)

    def test_auditor_read_only(self) -> None:
        """T-S03-016: auditor получил read-only доступ к Source Registry."""
        perms = permissions_for_roles(frozenset({Role.AUDITOR}))
        assert perms == frozenset(
            {
                Permission.KB_REPORT_READ,
                Permission.KB_SOURCE_LIST,
                Permission.KB_SOURCE_READ,
                Permission.KB_SOURCE_LINEAGE_READ,
                Permission.KB_SOURCE_LOG_READ,
                # SETUP-04: auditor видит статус парсинга и секции (read-only).
                Permission.KB_PARSE_STATUS_READ,
                Permission.KB_SECTION_READ,
                # SETUP-05: auditor видит карточки + preview + lineage (read-only).
                Permission.KB_RAG_CARD_READ,
                Permission.KB_RAG_CARD_PREVIEW,
                Permission.KB_RAG_CARD_LINEAGE_READ,
            }
        )

    def test_auditor_no_write_permissions(self) -> None:
        """Auditor НЕ имеет write/delete/admin permissions."""
        perms = permissions_for_roles(frozenset({Role.AUDITOR}))
        assert Permission.KB_SOURCE_METADATA_UPDATE not in perms
        assert Permission.KB_SOURCE_REMOVE not in perms
        assert Permission.KB_DOCUMENT_UPLOAD not in perms
        assert Permission.KB_ADMIN_CLEANUP not in perms

    def test_user_has_source_basic_permissions(self) -> None:
        """T-S03-016: user может видеть и редактировать свои источники."""
        perms = permissions_for_roles(frozenset({Role.USER}))
        assert Permission.KB_SOURCE_LIST in perms
        assert Permission.KB_SOURCE_READ in perms
        assert Permission.KB_SOURCE_METADATA_UPDATE in perms
        assert Permission.KB_SOURCE_REMOVE in perms
        # User не получает lineage/log по умолчанию.
        assert Permission.KB_SOURCE_LINEAGE_READ not in perms
        assert Permission.KB_SOURCE_LOG_READ not in perms

    def test_multiple_roles_union(self) -> None:
        perms = permissions_for_roles(frozenset({Role.USER, Role.DOMAIN_EXPERT}))
        assert Permission.KB_CARD_REVIEW in perms
        assert Permission.KB_PUBLISH not in perms


class TestAuthService:
    def setup_method(self) -> None:
        self.svc = AuthService()

    def test_authenticate_missing_user_id(self) -> None:
        with pytest.raises(UnauthenticatedError):
            self.svc.authenticate(user_id=None, roles_header="user")

    def test_authenticate_empty_user_id(self) -> None:
        with pytest.raises(UnauthenticatedError):
            self.svc.authenticate(user_id="", roles_header="user")

    def test_authenticate_defaults_to_user_role(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header=None)
        assert p.roles == frozenset({Role.USER})

    def test_authenticate_parses_multiple_roles(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header="user, rag_admin")
        assert Role.RAG_ADMIN in p.roles
        assert Role.USER in p.roles

    def test_authenticate_ignores_unknown_role(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header="user,wizard")
        assert Role.USER in p.roles
        assert len(p.roles) == 1

    def test_authenticate_empty_roles_fallback_to_user(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header="wizard,wizard")
        assert p.roles == frozenset({Role.USER})

    def test_require_passes_for_admin(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header="admin")
        # не должно бросить
        self.svc.require(p, Permission.KB_PUBLISH)
        self.svc.require(p, Permission.KB_CARD_REVIEW)

    def test_require_raises_forbidden_for_user(self) -> None:
        p = self.svc.authenticate(user_id="u1", roles_header="user")
        with pytest.raises(ForbiddenError) as exc:
            self.svc.require(p, Permission.KB_PUBLISH)
        assert exc.value.permission == Permission.KB_PUBLISH


class TestPrincipal:
    def test_principal_has_permission(self) -> None:
        svc = AuthService()
        p = svc.authenticate(user_id="u1", roles_header="rag_admin")
        assert p.has_permission(Permission.KB_PUBLISH)
        assert p.has_permission(Permission.KB_CARD_REVIEW)
        assert p.has_permission(Permission.KB_REPORT_READ) is not False  # есть у rag_admin

    def test_principal_is_frozen(self) -> None:
        svc = AuthService()
        p = svc.authenticate(user_id="u1", roles_header="user")
        # @dataclass(frozen=True, slots=True) — присваивание должно падать
        with pytest.raises((AttributeError, TypeError)):
            p.user_id = "u2"  # type: ignore[misc]
