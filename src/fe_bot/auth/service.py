"""Auth Service stub (SVC-03) для MVP.

В MVP пользователь идентифицируется через HTTP-заголовки
`X-User-Id` и `X-Roles` (comma-separated). Полноценный OIDC отложен.
Все production-проверки токенов — TODO[ADR-013].

Source of truth — docs/03-architecture/services/user-frontend.md (SVC-03).
"""

from __future__ import annotations

from dataclasses import dataclass

from fe_bot.auth.permissions import Permission, Role, permissions_for_roles


@dataclass(frozen=True, slots=True)
class Principal:
    """Аутентифицированный пользователь."""

    user_id: str
    roles: frozenset[Role]

    @property
    def permissions(self) -> frozenset[Permission]:
        return permissions_for_roles(self.roles)

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.permissions


class AuthError(Exception):
    """Базовый класс ошибок аутентификации/авторизации."""


class UnauthenticatedError(AuthError):
    """Нет валидного `X-User-Id` (или эквивалента)."""


class ForbiddenError(AuthError):
    """Аутентифицирован, но нет нужного permission."""

    def __init__(self, permission: Permission) -> None:
        self.permission = permission
        super().__init__(f"Permission denied: {permission.value} required")


class AuthService:
    """Стаб Auth Service. Парсит заголовки и валидирует роли."""

    def authenticate(self, user_id: str | None, roles_header: str | None) -> Principal:
        """Создаёт Principal из заголовков HTTP-запроса."""
        if not user_id:
            raise UnauthenticatedError("Missing X-User-Id header")
        roles = _parse_roles(roles_header)
        return Principal(user_id=user_id, roles=roles)

    def require(self, principal: Principal, permission: Permission) -> None:
        """Бросает ForbiddenError, если у principal нет permission."""
        if not principal.has_permission(permission):
            raise ForbiddenError(permission)


def _parse_roles(raw: str | None) -> frozenset[Role]:
    if not raw:
        return frozenset({Role.USER})  # по умолчанию — обычный пользователь
    parsed: set[Role] = set()
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            parsed.add(Role(item))
        except ValueError:
            # Неизвестная роль — игнорируем (warning должен логироваться в реальном AuthService).
            continue
    return frozenset(parsed) if parsed else frozenset({Role.USER})
