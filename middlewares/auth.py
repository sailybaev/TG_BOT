"""
Authentication Middleware
Validates user sessions and injects session data into handler context
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, Update, TelegramObject

from services import get_session_service
from models import UserSession

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    """
    Authentication middleware for aiogram 3.x

    Checks if user has a valid session in Redis.
    If authenticated, injects session into handler data.

    Public handlers (like /start, /login) should handle
    unauthenticated users gracefully.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Extract user ID from event
        user_id = self._get_user_id(event)

        if user_id:
            session_service = await get_session_service()
            session = await session_service.get_session(str(user_id))

            if session:
                # Refresh session activity
                await session_service.update_session(session)
                data["session"] = session
                data["is_authenticated"] = True
                logger.debug(f"User {user_id} authenticated as admin_id={session.admin_id}")
            else:
                data["session"] = None
                data["is_authenticated"] = False
        else:
            data["session"] = None
            data["is_authenticated"] = False

        return await handler(event, data)

    def _get_user_id(self, event: TelegramObject) -> Optional[int]:
        """Extract user ID from various event types"""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            return event.from_user.id if event.from_user else None
        elif isinstance(event, Update):
            if event.message and event.message.from_user:
                return event.message.from_user.id
            elif event.callback_query and event.callback_query.from_user:
                return event.callback_query.from_user.id
        return None


def require_auth(handler: Callable) -> Callable:
    """
    Decorator to require authentication for a handler

    Usage:
        @router.message(Command("secret"))
        @require_auth
        async def secret_handler(message: Message, session: UserSession):
            await message.answer(f"Hello, admin {session.admin_id}!")
    """
    async def wrapper(event: TelegramObject, *args, **kwargs):
        session: Optional[UserSession] = kwargs.get("session")
        is_authenticated: bool = kwargs.get("is_authenticated", False)

        if not is_authenticated or not session:
            if isinstance(event, Message):
                await event.answer(
                    "You are not authenticated.\n"
                    "Please use /login <OTP_TOKEN> to authenticate."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "Session expired. Please re-authenticate.",
                    show_alert=True
                )
            return

        return await handler(event, *args, **kwargs)

    # Preserve handler metadata
    wrapper.__name__ = handler.__name__
    wrapper.__doc__ = handler.__doc__

    return wrapper


class SessionContext:
    """
    Context manager for session access in handlers

    Provides convenient access to session data and authentication status
    """

    def __init__(self, data: Dict[str, Any]):
        self._session: Optional[UserSession] = data.get("session")
        self._is_authenticated: bool = data.get("is_authenticated", False)

    @property
    def session(self) -> Optional[UserSession]:
        return self._session

    @property
    def is_authenticated(self) -> bool:
        return self._is_authenticated

    @property
    def access_token(self) -> Optional[str]:
        return self._session.access_token if self._session else None

    @property
    def admin_id(self) -> Optional[int]:
        return self._session.admin_id if self._session else None

    @property
    def role(self) -> Optional[str]:
        return self._session.role if self._session else None

    @property
    def telegram_user_id(self) -> Optional[str]:
        return self._session.telegram_user_id if self._session else None

    def require_auth(self) -> UserSession:
        """Raise exception if not authenticated"""
        if not self._is_authenticated or not self._session:
            raise PermissionError("Authentication required")
        return self._session


def get_session_context(data: Dict[str, Any]) -> SessionContext:
    """Create SessionContext from handler data"""
    return SessionContext(data)
