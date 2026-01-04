"""
Session and User Models
Pydantic models for session management and data transfer
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Role(str, Enum):
    """User roles matching Tabys backend RBAC"""
    CLIENT = "client"
    VOLUNTEER_ADMIN = "volunteer_admin"
    MSB = "msb"
    NPO = "npo"
    GOVERNMENT = "government"
    ADMINISTRATOR = "administrator"
    SUPER_ADMIN = "super_admin"


class Module(str, Enum):
    """Available modules matching Tabys backend"""
    VOLUNTEERS = "volunteers"
    VACANCIES = "vacancies"
    LEISURE = "leisure"
    PROJECTS = "projects"
    EVENTS = "events"
    NEWS = "news"
    USERS = "users"
    COURSES = "courses"
    CERTIFICATES = "certificates"
    EXPERTS = "experts"
    RESUMES = "resumes"


class Permission(str, Enum):
    """Permission types"""
    READ = "read"
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class UserSession(BaseModel):
    """User session stored in Redis"""
    telegram_user_id: str
    admin_id: int
    role: str
    access_token: str
    admin_name: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)

    def update_activity(self):
        """Update last activity timestamp"""
        self.last_activity = datetime.utcnow()


class OTPVerifyResponse(BaseModel):
    """Response from OTP verification API"""
    access_token: str
    token_type: str = "bearer"
    admin_id: int
    admin_name: str
    role: str
    telegram_user_id: str
    session_created: bool


class SessionRestoreResponse(BaseModel):
    """Response from session restore API"""
    access_token: str
    token_type: str = "bearer"
    admin_id: int
    admin_name: str
    role: str
    telegram_user_id: str
    session_created: bool


class PaginatedRequest(BaseModel):
    """Pagination parameters"""
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)
    search: Optional[str] = None


class PaginatedResponse(BaseModel):
    """Paginated response wrapper"""
    items: list
    total: int
    page: int
    page_size: int
    total_pages: int

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1
