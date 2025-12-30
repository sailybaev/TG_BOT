"""
Redis Session Management Service
Handles user session storage, retrieval, and invalidation
"""
import json
import logging
from typing import Optional
from datetime import datetime

import redis.asyncio as redis
from redis.asyncio import Redis

from config import settings
from models import UserSession

logger = logging.getLogger(__name__)


class SessionService:
    """
    Redis-based session management

    Session keys: tg_session:{telegram_user_id}
    Rate limit keys: tg_rate:{telegram_user_id}:{action}
    """

    SESSION_PREFIX = "tg_session:"
    RATE_LIMIT_PREFIX = "tg_rate:"

    def __init__(self):
        self._redis: Optional[Redis] = None

    async def connect(self):
        """Connect to Redis"""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            # Test connection
            await self._redis.ping()
            logger.info("Connected to Redis")

    async def close(self):
        """Close Redis connection"""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
            logger.info("Redis connection closed")

    def _session_key(self, telegram_user_id: str) -> str:
        """Generate session key for user"""
        return f"{self.SESSION_PREFIX}{telegram_user_id}"

    def _rate_key(self, telegram_user_id: str, action: str) -> str:
        """Generate rate limit key"""
        return f"{self.RATE_LIMIT_PREFIX}{telegram_user_id}:{action}"

    # ==================== Session Management ====================

    async def create_session(
        self,
        telegram_user_id: str,
        admin_id: int,
        role: str,
        access_token: str,
        admin_name: Optional[str] = None,
    ) -> UserSession:
        """
        Create new user session in Redis

        Args:
            telegram_user_id: Telegram user ID
            admin_id: Backend admin ID
            role: User role from backend
            access_token: JWT access token
            admin_name: Optional admin name

        Returns:
            Created UserSession
        """
        session = UserSession(
            telegram_user_id=str(telegram_user_id),
            admin_id=admin_id,
            role=role,
            access_token=access_token,
            admin_name=admin_name,
            created_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
        )

        key = self._session_key(telegram_user_id)
        session_data = session.model_dump_json()

        await self._redis.setex(
            key,
            settings.redis_session_ttl,
            session_data,
        )

        logger.info(f"Session created for telegram_user_id={telegram_user_id}")
        return session

    async def get_session(self, telegram_user_id: str) -> Optional[UserSession]:
        """
        Retrieve user session from Redis

        Args:
            telegram_user_id: Telegram user ID

        Returns:
            UserSession if exists, None otherwise
        """
        key = self._session_key(telegram_user_id)
        session_data = await self._redis.get(key)

        if not session_data:
            return None

        try:
            data = json.loads(session_data)
            return UserSession(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse session data: {e}")
            await self._redis.delete(key)
            return None

    async def update_session(self, session: UserSession) -> bool:
        """
        Update existing session (refresh activity)

        Args:
            session: UserSession to update

        Returns:
            True if updated successfully
        """
        session.update_activity()
        key = self._session_key(session.telegram_user_id)

        await self._redis.setex(
            key,
            settings.redis_session_ttl,
            session.model_dump_json(),
        )
        return True

    async def delete_session(self, telegram_user_id: str) -> bool:
        """
        Delete user session from Redis

        Args:
            telegram_user_id: Telegram user ID

        Returns:
            True if deleted, False if not found
        """
        key = self._session_key(telegram_user_id)
        result = await self._redis.delete(key)
        if result:
            logger.info(f"Session deleted for telegram_user_id={telegram_user_id}")
        return result > 0

    async def session_exists(self, telegram_user_id: str) -> bool:
        """Check if session exists"""
        key = self._session_key(telegram_user_id)
        return await self._redis.exists(key) > 0

    async def refresh_session_ttl(self, telegram_user_id: str) -> bool:
        """Refresh session TTL without modifying data"""
        key = self._session_key(telegram_user_id)
        return await self._redis.expire(key, settings.redis_session_ttl)

    # ==================== Rate Limiting ====================

    async def check_rate_limit(
        self,
        telegram_user_id: str,
        action: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Check rate limit for user action

        Args:
            telegram_user_id: Telegram user ID
            action: Action identifier (e.g., "login", "api_call")
            max_requests: Maximum allowed requests in window
            window_seconds: Time window in seconds

        Returns:
            Tuple of (is_allowed, remaining_requests)
        """
        key = self._rate_key(telegram_user_id, action)

        # Use Redis pipeline for atomic operations
        async with self._redis.pipeline(transaction=True) as pipe:
            await pipe.incr(key)
            await pipe.ttl(key)
            results = await pipe.execute()

        current_count = results[0]
        ttl = results[1]

        # Set expiry if first request in window
        if ttl == -1:
            await self._redis.expire(key, window_seconds)

        is_allowed = current_count <= max_requests
        remaining = max(0, max_requests - current_count)

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for user={telegram_user_id} action={action}"
            )

        return is_allowed, remaining

    async def reset_rate_limit(self, telegram_user_id: str, action: str):
        """Reset rate limit counter for user action"""
        key = self._rate_key(telegram_user_id, action)
        await self._redis.delete(key)


# Global service instance
_session_service: Optional[SessionService] = None


async def get_session_service() -> SessionService:
    """Get or create global session service"""
    global _session_service
    if _session_service is None:
        _session_service = SessionService()
        await _session_service.connect()
    return _session_service


async def close_session_service():
    """Close global session service"""
    global _session_service
    if _session_service:
        await _session_service.close()
        _session_service = None
