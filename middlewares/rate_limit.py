"""
Rate Limiting Middleware
Prevents abuse of bot commands
"""
import logging
from typing import Callable, Dict, Any, Awaitable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from config import settings
from services import get_session_service

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseMiddleware):
    """
    Rate limiting middleware for bot commands

    Limits request frequency per user to prevent abuse
    """

    def __init__(
        self,
        max_requests: int = None,
        window_seconds: int = 60,
        action: str = "general"
    ):
        self.max_requests = max_requests or settings.general_rate_limit
        self.window_seconds = window_seconds
        self.action = action

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = self._get_user_id(event)

        if user_id:
            session_service = await get_session_service()
            is_allowed, remaining = await session_service.check_rate_limit(
                str(user_id),
                self.action,
                self.max_requests,
                self.window_seconds,
            )

            data["rate_limit_remaining"] = remaining

            if not is_allowed:
                if isinstance(event, Message):
                    await event.answer(
                        f"Too many requests. Please wait {self.window_seconds} seconds."
                    )
                return

        return await handler(event, data)

    def _get_user_id(self, event: TelegramObject) -> Optional[int]:
        """Extract user ID from event"""
        if isinstance(event, Message):
            return event.from_user.id if event.from_user else None
        return None


class LoginRateLimitMiddleware(RateLimitMiddleware):
    """Specialized rate limiter for login attempts"""

    def __init__(self):
        super().__init__(
            max_requests=settings.login_rate_limit,
            window_seconds=60,
            action="login"
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = self._get_user_id(event)

        if user_id:
            session_service = await get_session_service()
            is_allowed, remaining = await session_service.check_rate_limit(
                str(user_id),
                self.action,
                self.max_requests,
                self.window_seconds,
            )

            if not is_allowed:
                logger.warning(f"Login rate limit exceeded for user {user_id}")
                if isinstance(event, Message):
                    await event.answer(
                        "Too many login attempts.\n"
                        f"Please wait {self.window_seconds} seconds before trying again."
                    )
                return

        return await handler(event, data)
