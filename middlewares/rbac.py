"""
Role-Based Access Control Middleware
Mirrors Tabys backend RBAC permissions
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Set, Optional, List

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from models import Role, Module, Permission, UserSession

logger = logging.getLogger(__name__)


# Role permissions mapping (mirrors Tabys backend app/rbac/permissions.py)
ROLE_PERMISSIONS: Dict[str, Dict[str, Set[str]]] = {
    Role.CLIENT: {},

    Role.VOLUNTEER_ADMIN: {
        Module.VOLUNTEERS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
    },

    Role.MSB: {
        Module.VACANCIES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.LEISURE: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
    },

    Role.NPO: {
        Module.PROJECTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.EVENTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
    },

    Role.GOVERNMENT: {
        # Read-only access to everything
        Module.VOLUNTEERS: {Permission.READ},
        Module.VACANCIES: {Permission.READ},
        Module.LEISURE: {Permission.READ},
        Module.PROJECTS: {Permission.READ},
        Module.EVENTS: {Permission.READ},
        Module.NEWS: {Permission.READ},
        Module.USERS: {Permission.READ},
        Module.COURSES: {Permission.READ},
        Module.CERTIFICATES: {Permission.READ},
        Module.EXPERTS: {Permission.READ},
        Module.RESUMES: {Permission.READ},
    },

    Role.ADMINISTRATOR: {
        Module.NEWS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.USERS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.VOLUNTEERS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.VACANCIES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.LEISURE: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.PROJECTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.EVENTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.COURSES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.CERTIFICATES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.EXPERTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.RESUMES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
    },

    Role.SUPER_ADMIN: {
        # Full access to everything
        Module.VOLUNTEERS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.VACANCIES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.LEISURE: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.PROJECTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.EVENTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.NEWS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.USERS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.COURSES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.CERTIFICATES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.EXPERTS: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
        Module.RESUMES: {Permission.READ, Permission.CREATE, Permission.UPDATE, Permission.DELETE},
    },
}

# Role hierarchy (higher number = more privileges)
ROLE_HIERARCHY: Dict[str, int] = {
    Role.CLIENT: 0,
    Role.VOLUNTEER_ADMIN: 1,
    Role.MSB: 1,
    Role.NPO: 1,
    Role.GOVERNMENT: 2,
    Role.ADMINISTRATOR: 3,
    Role.SUPER_ADMIN: 4,
}


def has_permission(role: str, module: str, permission: str) -> bool:
    """
    Check if a role has a specific permission for a module

    Args:
        role: User's role
        module: Module name
        permission: Permission type

    Returns:
        bool: True if role has permission
    """
    if role not in ROLE_PERMISSIONS:
        return False

    module_permissions = ROLE_PERMISSIONS.get(role, {}).get(module, set())
    return permission in module_permissions


def get_accessible_modules(role: str) -> List[str]:
    """
    Get list of modules a role can access

    Args:
        role: User's role

    Returns:
        List of module names
    """
    if role not in ROLE_PERMISSIONS:
        return []

    return list(ROLE_PERMISSIONS[role].keys())


def is_read_only(role: str, module: str) -> bool:
    """Check if role has only read access to a module"""
    if role not in ROLE_PERMISSIONS:
        return False

    module_permissions = ROLE_PERMISSIONS.get(role, {}).get(module, set())

    return (
        Permission.READ in module_permissions and
        not any(p in module_permissions for p in [
            Permission.CREATE, Permission.UPDATE, Permission.DELETE
        ])
    )


def has_higher_or_equal_privilege(user_role: str, required_role: str) -> bool:
    """Check if user role has higher or equal privilege than required role"""
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    return user_level >= required_level


class RBACMiddleware(BaseMiddleware):
    """
    RBAC middleware that injects permission checker into handler data

    Usage in handlers:
        async def handler(message: Message, rbac: RBACContext):
            if rbac.can(Module.EVENTS, Permission.READ):
                # ... show events
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session: Optional[UserSession] = data.get("session")

        if session:
            data["rbac"] = RBACContext(session.role)
        else:
            data["rbac"] = RBACContext(None)

        return await handler(event, data)


class RBACContext:
    """
    Context for RBAC permission checking in handlers

    Provides convenient methods to check permissions
    """

    def __init__(self, role: Optional[str]):
        self._role = role

    @property
    def role(self) -> Optional[str]:
        return self._role

    def can(self, module: str, permission: str = Permission.READ) -> bool:
        """Check if user can perform action on module"""
        if not self._role:
            return False
        return has_permission(self._role, module, permission)

    def can_read(self, module: str) -> bool:
        """Check if user can read module"""
        return self.can(module, Permission.READ)

    def can_create(self, module: str) -> bool:
        """Check if user can create in module"""
        return self.can(module, Permission.CREATE)

    def can_update(self, module: str) -> bool:
        """Check if user can update in module"""
        return self.can(module, Permission.UPDATE)

    def can_delete(self, module: str) -> bool:
        """Check if user can delete in module"""
        return self.can(module, Permission.DELETE)

    def is_read_only(self, module: str) -> bool:
        """Check if user has only read access"""
        if not self._role:
            return False
        return is_read_only(self._role, module)

    def get_accessible_modules(self) -> List[str]:
        """Get list of accessible modules"""
        if not self._role:
            return []
        return get_accessible_modules(self._role)

    def has_role(self, *roles: str) -> bool:
        """Check if user has one of the specified roles"""
        if not self._role:
            return False
        return self._role in roles

    def is_admin(self) -> bool:
        """Check if user is administrator or super_admin"""
        return self.has_role(Role.ADMINISTRATOR, Role.SUPER_ADMIN)

    def is_super_admin(self) -> bool:
        """Check if user is super_admin"""
        return self.has_role(Role.SUPER_ADMIN)

    def require_permission(self, module: str, permission: str = Permission.READ):
        """Raise exception if user doesn't have permission"""
        if not self.can(module, permission):
            raise PermissionError(
                f"Access denied: {self._role or 'guest'} cannot {permission} {module}"
            )

    def require_role(self, *roles: str):
        """Raise exception if user doesn't have one of the roles"""
        if not self.has_role(*roles):
            raise PermissionError(
                f"Access denied: requires one of {roles}, got {self._role or 'guest'}"
            )


def require_permission(module: str, permission: str = Permission.READ):
    """
    Decorator to require specific permission for a handler

    Usage:
        @router.message(Command("events"))
        @require_permission(Module.EVENTS, Permission.READ)
        async def events_handler(message: Message, session: UserSession):
            ...
    """
    def decorator(handler: Callable) -> Callable:
        async def wrapper(event: TelegramObject, *args, **kwargs):
            rbac: Optional[RBACContext] = kwargs.get("rbac")

            if not rbac or not rbac.can(module, permission):
                role = rbac.role if rbac else "guest"
                if isinstance(event, Message):
                    await event.answer(
                        f"Access denied.\n"
                        f"Your role ({role}) cannot {permission} {module}."
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        f"Access denied: {role} cannot {permission} {module}",
                        show_alert=True
                    )
                return

            return await handler(event, *args, **kwargs)

        wrapper.__name__ = handler.__name__
        wrapper.__doc__ = handler.__doc__
        return wrapper

    return decorator


def require_role(*roles: str):
    """
    Decorator to require specific role(s) for a handler

    Usage:
        @router.message(Command("admin"))
        @require_role(Role.ADMINISTRATOR, Role.SUPER_ADMIN)
        async def admin_handler(message: Message):
            ...
    """
    def decorator(handler: Callable) -> Callable:
        async def wrapper(event: TelegramObject, *args, **kwargs):
            rbac: Optional[RBACContext] = kwargs.get("rbac")

            if not rbac or not rbac.has_role(*roles):
                current_role = rbac.role if rbac else "guest"
                if isinstance(event, Message):
                    await event.answer(
                        f"Access denied.\n"
                        f"Required roles: {', '.join(roles)}\n"
                        f"Your role: {current_role}"
                    )
                elif isinstance(event, CallbackQuery):
                    await event.answer(
                        f"Access denied: requires {', '.join(roles)}",
                        show_alert=True
                    )
                return

            return await handler(event, *args, **kwargs)

        wrapper.__name__ = handler.__name__
        wrapper.__doc__ = handler.__doc__
        return wrapper

    return decorator
