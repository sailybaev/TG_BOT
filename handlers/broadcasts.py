"""
Broadcast Handlers
Receive and display broadcast messages from CRM
"""
from typing import Optional
import asyncio

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import get_tabys_client, TabysAPIError
from models import UserSession
from middlewares import RBACContext
from utils import get_logger

router = Router(name="broadcasts")
logger = get_logger(__name__)


async def send_broadcast_to_user(
    bot,
    telegram_user_id: str,
    message_text: str,
    broadcast_id: int
) -> bool:
    """
    Send broadcast message to a single user

    Args:
        bot: Telegram Bot instance
        telegram_user_id: Telegram user ID
        message_text: Message content (HTML formatted)
        broadcast_id: Broadcast ID for tracking

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        # Build keyboard with "Mark as read" callback
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(
                text="✅ Отметить как прочитано",
                callback_data=f"broadcast:read:{broadcast_id}"
            )
        )

        await bot.send_message(
            chat_id=int(telegram_user_id),
            text=f"📢 <b>Объявление от администрации</b>\n\n{message_text}",
            parse_mode="HTML",
            reply_markup=builder.as_markup()
        )

        logger.info(f"Broadcast {broadcast_id} sent to user {telegram_user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send broadcast {broadcast_id} to user {telegram_user_id}: {e}")
        return False


@router.callback_query(F.data.startswith("broadcast:read:"))
async def mark_broadcast_as_read(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
):
    """Mark broadcast as read"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    # Parse broadcast_id from callback data
    parts = callback.data.split(":")
    broadcast_id = int(parts[2])

    try:
        # TODO: Send read confirmation to backend API
        # client = get_tabys_client()
        # await client.mark_broadcast_as_read(session.access_token, broadcast_id)

        await callback.answer("✅ Отмечено как прочитано", show_alert=True)

        # Update message to remove button
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass

    except Exception as e:
        logger.error(f"Failed to mark broadcast as read: {e}")
        await callback.answer("❌ Ошибка", show_alert=True)


# Note: The actual broadcast sending is triggered from the backend
# The backend calls this function via webhook or direct bot API integration
