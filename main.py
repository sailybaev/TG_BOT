"""
Tabys CRM Telegram Bot
Main entry point
"""
import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import settings
from utils import setup_logging, get_logger
from middlewares import AuthMiddleware, RBACMiddleware, RateLimitMiddleware
from services import get_session_service, close_session_service
from api import get_tabys_client, close_tabys_client
from handlers import (
    auth_router,
    events_router,
    courses_router,
    vacancies_router,
    news_router,
    projects_router,
    admin_router,
)

logger = get_logger(__name__)


async def on_startup(bot: Bot):
    """Startup hook"""
    logger.info("Bot starting up...")

    # Initialize services
    await get_session_service()
    get_tabys_client()

    # Get bot info
    bot_info = await bot.get_me()
    logger.info(f"Bot started: @{bot_info.username}")


async def on_shutdown(bot: Bot):
    """Shutdown hook"""
    logger.info("Bot shutting down...")

    # Close services
    await close_session_service()
    await close_tabys_client()

    logger.info("Bot shutdown complete")


def create_dispatcher() -> Dispatcher:
    """Create and configure dispatcher"""
    dp = Dispatcher()

    # Register middlewares (order matters!)
    # 1. Rate limiting (before anything else)
    dp.message.middleware(RateLimitMiddleware())

    # 2. Authentication (check session)
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())

    # 3. RBAC (depends on auth)
    dp.message.middleware(RBACMiddleware())
    dp.callback_query.middleware(RBACMiddleware())

    # Register routers
    dp.include_router(auth_router)
    dp.include_router(events_router)
    dp.include_router(courses_router)
    dp.include_router(vacancies_router)
    dp.include_router(news_router)
    dp.include_router(projects_router)
    dp.include_router(admin_router)

    # Register startup/shutdown handlers
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    return dp


def create_bot() -> Bot:
    """Create bot instance"""
    return Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )


async def main():
    """Main entry point"""
    # Setup logging
    setup_logging()

    logger.info("Initializing Tabys CRM Telegram Bot...")

    # Create bot and dispatcher
    bot = create_bot()
    dp = create_dispatcher()

    try:
        # Delete webhook to use polling
        await bot.delete_webhook(drop_pending_updates=True)

        # Start polling
        logger.info("Starting polling...")
        await dp.start_polling(
            bot,
            allowed_updates=[
                "message",
                "callback_query",
            ]
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
