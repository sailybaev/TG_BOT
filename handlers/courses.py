"""
Courses Handlers
View and manage courses
"""
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import get_tabys_client, TabysAPIError
from models import UserSession, Module
from middlewares import RBACContext
from keyboards import (
    get_main_menu,
    get_pagination_keyboard,
    get_item_detail_keyboard,
    get_list_item_keyboard,
)
from utils import format_course, format_list, format_error, get_logger

router = Router(name="courses")
logger = get_logger(__name__)


@router.callback_query(F.data == "menu:courses")
async def show_courses_list(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show list of courses"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    if not rbac or not rbac.can_read(Module.COURSES):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await callback.answer()
    await _show_courses_page(callback.message, session, rbac, page=1)


@router.callback_query(F.data.startswith("courses:page:"))
async def courses_pagination(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Handle courses pagination"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    page = int(callback.data.split(":")[-1])
    await callback.answer()
    await _show_courses_page(callback.message, session, rbac, page=page, edit=True)


@router.callback_query(F.data.startswith("courses:view:"))
async def view_course(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """View single course"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    course_id = int(callback.data.split(":")[-1])
    await callback.answer()

    try:
        client = get_tabys_client()
        course = await client.get_course(session.access_token, course_id)

        await callback.message.edit_text(
            format_course(course),
            reply_markup=get_item_detail_keyboard(course_id, Module.COURSES, rbac),
            parse_mode="HTML"
        )
    except TabysAPIError as e:
        await callback.message.edit_text(
            format_error(e.detail or e.message),
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )


async def _show_courses_page(
    message: Message,
    session: UserSession,
    rbac: RBACContext,
    page: int = 1,
    edit: bool = False,
):
    """Helper to show courses page"""
    try:
        client = get_tabys_client()
        response = await client.get_courses(
            session.access_token,
            page=page,
            page_size=10
        )

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
            text = "🎓 <b>Courses</b>\n\nNo courses found."
            keyboard = get_main_menu(rbac)
        else:
            text = f"🎓 <b>Courses</b> (Page {page}/{max(1, total_pages)})\n\n"
            text += format_list(items, "courses", page)

            # Telegram has 4096 char limit - truncate if needed
            MAX_LENGTH = 4000  # Leave margin for keyboard
            if len(text) > MAX_LENGTH:
                text = text[:MAX_LENGTH - 50] + "\n\n... (truncated)"

            keyboard_items = get_list_item_keyboard(items, "courses")
            pagination = get_pagination_keyboard(page, max(1, total_pages), "courses")

            builder = InlineKeyboardBuilder()
            for row in keyboard_items.inline_keyboard:
                builder.row(*row)
            for row in pagination.inline_keyboard:
                builder.row(*row)

            keyboard = builder.as_markup()

        await message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")

    except TabysAPIError as e:
        logger.error(f"Failed to fetch courses: {e}")
        await message.edit_text(
            format_error(e.detail or e.message),
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )
