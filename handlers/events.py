"""
Events Handlers
View and manage events
"""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from api import get_tabys_client, TabysAPIError
from models import UserSession, Module, Permission
from middlewares import RBACContext, require_permission
from keyboards import (
    get_main_menu,
    get_pagination_keyboard,
    get_item_detail_keyboard,
    get_list_item_keyboard,
)
from utils import format_event, format_list, format_error, get_logger

router = Router(name="events")
logger = get_logger(__name__)


@router.callback_query(F.data == "menu:events")
async def show_events_list(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show list of events"""
    if not is_authenticated or not session:
        await callback.answer("⚠️ Сессия истекла", show_alert=True)
        return

    if not rbac or not rbac.can_read(Module.EVENTS):
        await callback.answer("🚫 Доступ запрещен", show_alert=True)
        return

    await callback.answer("📅 Загрузка мероприятий...")
    await _show_events_page(callback.message, session, rbac, page=1)


@router.callback_query(F.data.startswith("events:page:"))
async def events_pagination(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Handle events pagination"""
    if not is_authenticated or not session:
        await callback.answer("⚠️ Сессия истекла", show_alert=True)
        return

    page = int(callback.data.split(":")[-1])
    await callback.answer(f"📄 Страница {page}")
    await _show_events_page(callback.message, session, rbac, page=page, edit=True)


@router.callback_query(F.data.startswith("events:view:"))
async def view_event(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """View single event"""
    if not is_authenticated or not session:
        await callback.answer("⚠️ Сессия истекла", show_alert=True)
        return

    event_id = int(callback.data.split(":")[-1])
    await callback.answer("📅 Загрузка мероприятия...")

    try:
        client = get_tabys_client()
        event = await client.get_event(session.access_token, event_id)

        await callback.message.edit_text(
            format_event(event),
            reply_markup=get_item_detail_keyboard(event_id, Module.EVENTS, rbac),
            parse_mode="HTML"
        )
    except TabysAPIError as e:
        await callback.message.edit_text(
            f"❌ <b>Ошибка загрузки мероприятия</b>\n\n"
            f"⚠️ {e.detail or e.message}",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )


async def _show_events_page(
    message: Message,
    session: UserSession,
    rbac: RBACContext,
    page: int = 1,
    edit: bool = False,
):
    """Helper to show events page"""
    try:
        client = get_tabys_client()
        response = await client.get_events(
            session.access_token,
            page=page,
            page_size=10
        )

        # Handle different response formats
        if isinstance(response, list):
            items = response
            total = len(response)
            total_pages = 1
        else:
            items = response.get("items", response.get("data", []))
            total = response.get("total", len(items))
            total_pages = response.get("total_pages", (total + 9) // 10)

        # Limit items to prevent message length issues
        MAX_ITEMS_PER_PAGE = 10
        items = items[:MAX_ITEMS_PER_PAGE]

        if not items:
            text = (
                "📅 <b>Мероприятия</b>\n\n"
                "😔 Мероприятия не найдены.\n\n"
                "💡 Проверьте позже!"
            )
            keyboard = get_main_menu(rbac)
        else:
            # Permission indicators
            can_create = rbac.can_create(Module.EVENTS)
            can_edit = rbac.can_update(Module.EVENTS)

            perms_text = []
            if can_create:
                perms_text.append("✏️ Создать")
            if can_edit:
                perms_text.append("📝 Редактировать")
            if not perms_text:
                perms_text.append("👁 Только чтение")

            text = (
                f"📅 <b>Мероприятия</b>\n"
                f"📄 Страница {page}/{max(1, total_pages)} • "
                f"Всего: {total}\n"
                f"🔐 {' • '.join(perms_text)}\n\n"
                f"Выберите мероприятие для просмотра:"
            )

            # Telegram has 4096 char limit - truncate if needed
            MAX_LENGTH = 4000  # Leave margin for keyboard
            if len(text) > MAX_LENGTH:
                text = text[:MAX_LENGTH - 50] + "\n\n... (truncated)"

            keyboard_items = get_list_item_keyboard(items, "events")
            pagination = get_pagination_keyboard(page, max(1, total_pages), "events")

            # Combine keyboards
            from aiogram.utils.keyboard import InlineKeyboardBuilder

            builder = InlineKeyboardBuilder()
            # Add item buttons
            for row in keyboard_items.inline_keyboard:
                builder.row(*row)
            # Add pagination
            for row in pagination.inline_keyboard:
                builder.row(*row)

            keyboard = builder.as_markup()

        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except TabysAPIError as e:
        logger.error(f"Failed to fetch events: {e}")
        text = (
            "❌ <b>Ошибка загрузки мероприятий</b>\n\n"
            f"⚠️ {e.detail or e.message}\n\n"
            "🔄 Попробуйте снова или обратитесь в поддержку."
        )
        await message.edit_text(text, reply_markup=get_main_menu(rbac), parse_mode="HTML")
