"""
User Telegram Account Linking Handler
Handles /start link_<TOKEN> command for regular users
"""
import logging
from typing import Optional

from aiogram import Router
from aiogram.types import Message
from aiogram.filters import CommandStart

from api import get_tabys_client, TabysAPIError
from config import settings
from utils import get_logger

router = Router(name="user_link")
logger = get_logger(__name__)


@router.message(CommandStart(deep_link=True))
async def handle_deep_link(message: Message):
    """
    Handle /start link_<TOKEN> deep link for user telegram linking

    This is separate from admin OTP authentication.
    Regular users click a link from the web profile page.
    """
    user = message.from_user
    deep_link = message.text.split()[1] if len(message.text.split()) > 1 else None

    # Check if this is a user linking request
    if not deep_link or not deep_link.startswith("link_"):
        # Not a linking request, let auth handler deal with it
        return

    # Extract token
    token = deep_link[5:]  # Remove "link_" prefix

    if not token:
        await message.answer(
            "❌ <b>Неверная ссылка</b>\n\n"
            "Пожалуйста, получите новую ссылку для привязки в вашем профиле.",
            parse_mode="HTML"
        )
        return

    logger.info(f"User {user.id} attempting to link with token {token[:8]}...")

    # Prepare data for backend
    link_data = {
        "token": token,
        "telegram_chat_id": str(user.id),
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
    }

    try:
        # Call backend confirm-link endpoint
        client = get_tabys_client()

        # Make direct request with X-Bot-Secret header
        import httpx

        headers = {
            "X-Bot-Secret": settings.telegram_bot_link_secret,
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as http_client:
            response = await http_client.post(
                f"{settings.tabys_api_url}/api/v2/telegram/confirm-link",
                json=link_data,
                headers=headers,
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(
                    f"User {user.id} successfully linked to user_id={result.get('user_id')}"
                )

                await message.answer(
                    "✅ <b>Telegram успешно привязан!</b>\n\n"
                    "🎉 Теперь вы будете получать уведомления от Saryarqa Jastary.\n\n"
                    "💡 Вы можете закрыть этот чат или использовать его для "
                    "получения обновлений о ваших мероприятиях, курсах и заявках.",
                    parse_mode="HTML"
                )
            elif response.status_code == 404:
                logger.warning(f"Token not found for user {user.id}")
                await message.answer(
                    "❌ <b>Ссылка недействительна</b>\n\n"
                    "Возможные причины:\n"
                    "• Ссылка истекла (действует 10 минут)\n"
                    "• Ссылка уже была использована\n"
                    "• Токен не существует\n\n"
                    "💡 Получите новую ссылку в вашем профиле на сайте.",
                    parse_mode="HTML"
                )
            elif response.status_code == 400:
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                logger.warning(f"Bad request for user {user.id}: {error_detail}")
                await message.answer(
                    f"⚠️ <b>Ошибка привязки</b>\n\n"
                    f"{error_detail}\n\n"
                    "💡 Получите новую ссылку в вашем профиле.",
                    parse_mode="HTML"
                )
            elif response.status_code == 409:
                logger.warning(f"Telegram account {user.id} already linked to another user")
                await message.answer(
                    "⚠️ <b>Аккаунт уже привязан</b>\n\n"
                    "Этот Telegram аккаунт уже привязан к другому пользователю.\n\n"
                    "💡 Если это ваш аккаунт, сначала отвяжите его в профиле, "
                    "затем привяжите заново.",
                    parse_mode="HTML"
                )
            elif response.status_code == 403:
                logger.error(f"Invalid bot secret when linking user {user.id}")
                await message.answer(
                    "❌ <b>Ошибка конфигурации</b>\n\n"
                    "Пожалуйста, обратитесь к администратору системы.",
                    parse_mode="HTML"
                )
            else:
                error_text = response.text
                logger.error(
                    f"Unexpected error linking user {user.id}: "
                    f"status={response.status_code} body={error_text}"
                )
                await message.answer(
                    "❌ <b>Произошла ошибка</b>\n\n"
                    "Пожалуйста, попробуйте позже или обратитесь в поддержку.",
                    parse_mode="HTML"
                )

    except Exception as e:
        logger.error(f"Exception while linking user {user.id}: {e}", exc_info=True)
        await message.answer(
            "❌ <b>Произошла ошибка</b>\n\n"
            "Не удалось связаться с сервером. Попробуйте позже.",
            parse_mode="HTML"
        )
