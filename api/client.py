"""
Tabys Backend API Client
Async HTTP client for communicating with Tabys FastAPI backend
"""
import httpx
import logging
import re
from typing import Optional, Any, Dict
from contextlib import asynccontextmanager

from config import settings
from models import OTPVerifyResponse, SessionRestoreResponse

logger = logging.getLogger(__name__)


def _strip_html_tags(text: str) -> str:
    """
    Remove HTML tags from text to prevent Telegram parse errors

    Args:
        text: Text that may contain HTML

    Returns:
        Text with HTML tags removed and truncated if too long
    """
    if not text:
        return text

    # Remove all HTML tags
    clean_text = re.sub(r'<[^>]+>', '', text)

    # Remove extra whitespace
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    # Truncate if too long (Telegram has message length limits)
    max_length = 200
    if len(clean_text) > max_length:
        clean_text = clean_text[:max_length] + "..."

    return clean_text


class TabysAPIError(Exception):
    """Base exception for Tabys API errors"""

    def __init__(self, message: str, status_code: int = None, detail: str = None):
        self.message = message
        self.status_code = status_code
        # Sanitize detail to remove HTML tags
        self.detail = _strip_html_tags(detail) if detail else detail
        super().__init__(self.message)


class TabysClient:
    """
    Async HTTP client for Tabys backend API

    Handles:
    - OTP verification
    - Session management
    - CRUD operations with proper authentication
    """

    def __init__(self):
        self.base_url = settings.tabys_api_url.rstrip("/")
        self.timeout = httpx.Timeout(settings.tabys_api_timeout)
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                }
            )
        return self._client

    async def close(self):
        """Close HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @asynccontextmanager
    async def _request_context(self):
        """Context manager for request error handling"""
        try:
            yield
        except httpx.TimeoutException as e:
            logger.error(f"API timeout: {e}")
            raise TabysAPIError("Backend API timeout", status_code=504)
        except httpx.ConnectError as e:
            logger.error(f"API connection error: {e}")
            raise TabysAPIError("Cannot connect to backend API", status_code=503)
        except httpx.HTTPStatusError as e:
            logger.error(f"API HTTP error: {e.response.status_code} - {e.response.text}")
            detail = None
            try:
                detail = e.response.json().get("detail", str(e))
            except Exception:
                detail = e.response.text
            raise TabysAPIError(
                f"API error: {e.response.status_code}",
                status_code=e.response.status_code,
                detail=detail
            )

    # ==================== Authentication ====================

    async def verify_otp(
        self,
        otp_token: str,
        telegram_user_id: str,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None,
        telegram_last_name: Optional[str] = None,
    ) -> OTPVerifyResponse:
        """
        Verify OTP token and create session

        Args:
            otp_token: 8-character OTP token from admin
            telegram_user_id: Telegram user ID
            telegram_username: Optional Telegram username
            telegram_first_name: Optional first name
            telegram_last_name: Optional last name

        Returns:
            OTPVerifyResponse with access_token and user info
        """
        client = await self._get_client()

        async with self._request_context():
            response = await client.post(
                "/api/v1/telegram-auth/verify-otp",
                json={
                    "otp_token": otp_token.upper().strip(),
                    "telegram_user_id": str(telegram_user_id),
                    "telegram_username": telegram_username,
                    "telegram_first_name": telegram_first_name,
                    "telegram_last_name": telegram_last_name,
                }
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"OTP verified for telegram_user_id={telegram_user_id}")
            return OTPVerifyResponse(**data)

    async def logout(self, telegram_user_id: str) -> bool:
        """
        Logout Telegram session

        Args:
            telegram_user_id: Telegram user ID

        Returns:
            True if logout successful
        """
        client = await self._get_client()

        async with self._request_context():
            response = await client.post(
                "/api/v1/telegram-auth/logout",
                json={"telegram_user_id": str(telegram_user_id)}
            )
            response.raise_for_status()
            logger.info(f"Logged out telegram_user_id={telegram_user_id}")
            return True

    async def restore_session(self, telegram_user_id: str) -> SessionRestoreResponse:
        """
        Restore session after bot restart

        Args:
            telegram_user_id: Telegram user ID

        Returns:
            SessionRestoreResponse with fresh access_token
        """
        client = await self._get_client()

        async with self._request_context():
            response = await client.post(
                "/api/v1/telegram-auth/restore-session",
                json={"telegram_user_id": str(telegram_user_id)}
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Session restored for telegram_user_id={telegram_user_id}")
            return SessionRestoreResponse(**data)

    # ==================== Authenticated API Calls ====================

    async def _auth_request(
        self,
        method: str,
        endpoint: str,
        access_token: str,
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Tabys API

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            access_token: JWT access token
            json_data: Optional JSON body
            params: Optional query parameters

        Returns:
            Response JSON data
        """
        client = await self._get_client()

        headers = {"Authorization": f"Bearer {access_token}"}

        # Log full request details
        full_url = f"{self.base_url}{endpoint}"
        logger.info(f"API Request: {method} {full_url}")
        logger.debug(f"Params: {params}, Headers: {list(headers.keys())}")

        async with self._request_context():
            response = await client.request(
                method=method,
                url=endpoint,
                headers=headers,
                json=json_data,
                params=params,
            )

            logger.info(f"API Response: {response.status_code} from {full_url}")
            response.raise_for_status()

            if response.status_code == 204:
                return {"success": True}

            return response.json()

    # ==================== Events ====================

    async def get_events(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of events"""
        return await self._auth_request(
            "GET",
            "/api/v2/events/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    async def get_event(self, access_token: str, event_id: int) -> Dict[str, Any]:
        """Get single event by ID"""
        return await self._auth_request("GET", f"/api/v2/events/{event_id}/", access_token)

    # ==================== Courses ====================

    async def get_courses(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of courses"""
        return await self._auth_request(
            "GET",
            "/api/v2/courses/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    async def get_course(self, access_token: str, course_id: int) -> Dict[str, Any]:
        """Get single course by ID"""
        return await self._auth_request("GET", f"/api/v2/courses/{course_id}", access_token)

    # ==================== Vacancies ====================

    async def get_vacancies(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of vacancies"""
        return await self._auth_request(
            "GET",
            "/api/v2/vacancies/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    async def get_vacancy(self, access_token: str, vacancy_id: int) -> Dict[str, Any]:
        """Get single vacancy by ID"""
        return await self._auth_request("GET", f"/api/v2/vacancies/{vacancy_id}", access_token)

    # ==================== News ====================

    async def get_news(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of news articles"""
        return await self._auth_request(
            "GET",
            "/api/v2/news/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    async def get_news_article(self, access_token: str, news_id: int) -> Dict[str, Any]:
        """Get single news article by ID"""
        return await self._auth_request("GET", f"/api/v2/news/{news_id}/", access_token)

    # ==================== Projects ====================

    async def get_projects(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of projects"""
        return await self._auth_request(
            "GET",
            "/api/v2/projects/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    async def get_project(self, access_token: str, project_id: int) -> Dict[str, Any]:
        """Get single project by ID"""
        return await self._auth_request("GET", f"/api/v2/projects/{project_id}", access_token)

    # ==================== Volunteers ====================

    async def get_volunteers(
        self,
        access_token: str,
        page: int = 1,
        page_size: int = 10,
    ) -> Dict[str, Any]:
        """Get list of volunteer applications"""
        return await self._auth_request(
            "GET",
            "/api/v2/admin/volunteers/",
            access_token,
            params={"page": page, "page_size": page_size}
        )

    # ==================== Statistics ====================

    async def get_dashboard_stats(self, access_token: str) -> Dict[str, Any]:
        """Get dashboard statistics (for super_admin/administrator)"""
        try:
            return await self._auth_request("GET", "/api/v2/analytics/", access_token)
        except TabysAPIError:
            # Fallback to basic stats
            return {"message": "Statistics not available"}


# Global client instance
_client: Optional[TabysClient] = None


def get_tabys_client() -> TabysClient:
    """Get or create global Tabys client"""
    global _client
    if _client is None:
        _client = TabysClient()
    return _client


async def close_tabys_client():
    """Close global Tabys client"""
    global _client
    if _client:
        await _client.close()
        _client = None
