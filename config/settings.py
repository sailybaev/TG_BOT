"""
Bot Configuration Settings
Pydantic-based configuration from environment variables
"""
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Telegram Bot
    telegram_bot_token: str = Field(..., description="Telegram Bot API token")
    telegram_webhook_url: Optional[str] = Field(None, description="Webhook URL for production")
    telegram_webhook_secret: Optional[str] = Field(None, description="Webhook secret token")

    # Tabys Backend API
    tabys_api_url: str = Field(
        default="http://localhost:8000",
        description="Tabys backend API base URL"
    )
    tabys_api_timeout: int = Field(default=30, description="API request timeout in seconds")

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    redis_session_ttl: int = Field(
        default=86400,  # 24 hours
        description="Session TTL in seconds"
    )

    # Rate Limiting
    login_rate_limit: int = Field(
        default=5,
        description="Max login attempts per minute"
    )
    general_rate_limit: int = Field(
        default=30,
        description="Max requests per minute for general operations"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(
        default="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        description="Log message format"
    )

    # Debug mode
    debug: bool = Field(default=False, description="Enable debug mode")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


# Convenience access
settings = get_settings()
