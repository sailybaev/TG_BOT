"""Handlers module"""
from .auth import router as auth_router
from .events import router as events_router
from .courses import router as courses_router
from .vacancies import router as vacancies_router
from .news import router as news_router
from .projects import router as projects_router
from .admin import router as admin_router
from .broadcasts import router as broadcasts_router
from .user_link import router as user_link_router

__all__ = [
    "auth_router",
    "events_router",
    "courses_router",
    "vacancies_router",
    "news_router",
    "projects_router",
    "admin_router",
    "broadcasts_router",
    "user_link_router",
]
