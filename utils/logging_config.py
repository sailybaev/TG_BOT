"""
Logging Configuration
Structured logging setup for the bot
"""
import logging
import sys
from typing import Optional

from config import settings


def setup_logging(level: Optional[str] = None) -> None:
    """
    Configure logging for the application

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = level or settings.log_level
    log_format = settings.log_format

    # Root logger configuration
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Set levels for noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured with level: {log_level}")


class BotLogger:
    """
    Structured logger wrapper for bot events

    Provides consistent logging format with context
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def user_action(
        self,
        action: str,
        user_id: int,
        extra: Optional[dict] = None,
    ):
        """Log user action"""
        msg = f"[USER:{user_id}] {action}"
        if extra:
            msg += f" | {extra}"
        self.logger.info(msg)

    def api_call(
        self,
        method: str,
        endpoint: str,
        status_code: Optional[int] = None,
        error: Optional[str] = None,
    ):
        """Log API call"""
        if error:
            self.logger.error(f"[API] {method} {endpoint} | ERROR: {error}")
        elif status_code:
            self.logger.info(f"[API] {method} {endpoint} | {status_code}")
        else:
            self.logger.debug(f"[API] {method} {endpoint}")

    def auth_event(
        self,
        event: str,
        user_id: int,
        success: bool,
        detail: Optional[str] = None,
    ):
        """Log authentication event"""
        status = "SUCCESS" if success else "FAILED"
        msg = f"[AUTH:{status}] {event} | user_id={user_id}"
        if detail:
            msg += f" | {detail}"

        if success:
            self.logger.info(msg)
        else:
            self.logger.warning(msg)

    def permission_denied(
        self,
        user_id: int,
        role: str,
        module: str,
        permission: str,
    ):
        """Log permission denied event"""
        self.logger.warning(
            f"[RBAC:DENIED] user_id={user_id} role={role} "
            f"| cannot {permission} {module}"
        )

    def error(self, msg: str, exc_info: bool = False):
        """Log error"""
        self.logger.error(msg, exc_info=exc_info)

    def warning(self, msg: str):
        """Log warning"""
        self.logger.warning(msg)

    def info(self, msg: str):
        """Log info"""
        self.logger.info(msg)

    def debug(self, msg: str):
        """Log debug"""
        self.logger.debug(msg)


def get_logger(name: str) -> BotLogger:
    """Get a BotLogger instance"""
    return BotLogger(name)
