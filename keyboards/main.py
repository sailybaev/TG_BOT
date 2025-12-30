"""
Keyboard Builders
Inline and reply keyboards for bot interactions
"""
from typing import List, Optional, Dict, Any
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from models import Module, Permission
from middlewares.rbac import RBACContext


def get_main_menu(rbac: RBACContext) -> InlineKeyboardMarkup:
    """
    Build main menu keyboard based on user permissions

    Args:
        rbac: RBAC context with user permissions

    Returns:
        InlineKeyboardMarkup with accessible modules
    """
    builder = InlineKeyboardBuilder()

    # Content modules (2 per row for better layout)
    content_buttons = []

    if rbac.can_read(Module.EVENTS):
        content_buttons.append(InlineKeyboardButton(
            text="📅 Мероприятия",
            callback_data="menu:events"
        ))

    if rbac.can_read(Module.COURSES):
        content_buttons.append(InlineKeyboardButton(
            text="🎓 Курсы",
            callback_data="menu:courses"
        ))

    if rbac.can_read(Module.VACANCIES):
        content_buttons.append(InlineKeyboardButton(
            text="💼 Вакансии",
            callback_data="menu:vacancies"
        ))

    if rbac.can_read(Module.NEWS):
        content_buttons.append(InlineKeyboardButton(
            text="📰 Новости",
            callback_data="menu:news"
        ))

    if rbac.can_read(Module.PROJECTS):
        content_buttons.append(InlineKeyboardButton(
            text="🚀 Проекты",
            callback_data="menu:projects"
        ))

    if rbac.can_read(Module.VOLUNTEERS):
        content_buttons.append(InlineKeyboardButton(
            text="🤝 Волонтеры",
            callback_data="menu:volunteers"
        ))

    # Add content buttons in rows of 2
    for i in range(0, len(content_buttons), 2):
        if i + 1 < len(content_buttons):
            builder.row(content_buttons[i], content_buttons[i + 1])
        else:
            builder.row(content_buttons[i])

    # Admin section (full width)
    if rbac.is_admin():
        builder.row(InlineKeyboardButton(
            text="⚙️ Админ панель",
            callback_data="menu:admin"
        ))

    # Logout button (full width)
    builder.row(InlineKeyboardButton(
        text="🚪 Выход",
        callback_data="action:logout"
    ))

    return builder.as_markup()


def get_pagination_keyboard(
    current_page: int,
    total_pages: int,
    callback_prefix: str,
) -> InlineKeyboardMarkup:
    """
    Build pagination keyboard

    Args:
        current_page: Current page number (1-indexed)
        total_pages: Total number of pages
        callback_prefix: Prefix for callback data (e.g., "events")

    Returns:
        InlineKeyboardMarkup with navigation buttons
    """
    builder = InlineKeyboardBuilder()
    buttons = []

    # Previous button
    if current_page > 1:
        buttons.append(InlineKeyboardButton(
            text="◀️ Назад",
            callback_data=f"{callback_prefix}:page:{current_page - 1}"
        ))

    # Page indicator
    buttons.append(InlineKeyboardButton(
        text=f"📄 {current_page}/{total_pages}",
        callback_data="noop"
    ))

    # Next button
    if current_page < total_pages:
        buttons.append(InlineKeyboardButton(
            text="Вперед ▶️",
            callback_data=f"{callback_prefix}:page:{current_page + 1}"
        ))

    builder.row(*buttons)

    # Back to menu
    builder.row(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="menu:main"
    ))

    return builder.as_markup()


def get_item_detail_keyboard(
    item_id: int,
    module: str,
    rbac: RBACContext,
    show_back: bool = True,
) -> InlineKeyboardMarkup:
    """
    Build keyboard for item detail view

    Args:
        item_id: Item ID
        module: Module name (events, courses, etc.)
        rbac: RBAC context
        show_back: Whether to show back button

    Returns:
        InlineKeyboardMarkup with action buttons
    """
    builder = InlineKeyboardBuilder()

    # Action buttons row
    action_buttons = []

    if rbac.can_update(module):
        action_buttons.append(InlineKeyboardButton(
            text="✏️ Редактировать",
            callback_data=f"{module}:edit:{item_id}"
        ))

    if rbac.can_delete(module):
        action_buttons.append(InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"{module}:delete:{item_id}"
        ))

    if action_buttons:
        builder.row(*action_buttons)

    # Refresh button
    builder.row(InlineKeyboardButton(
        text="🔄 Обновить",
        callback_data=f"{module}:view:{item_id}"
    ))

    # Back button
    if show_back:
        builder.row(InlineKeyboardButton(
            text="◀️ Назад к списку",
            callback_data=f"menu:{module}"
        ))

    return builder.as_markup()


def get_confirmation_keyboard(
    action: str,
    item_id: int,
    module: str,
) -> InlineKeyboardMarkup:
    """
    Build confirmation dialog keyboard

    Args:
        action: Action to confirm (e.g., "delete")
        item_id: Item ID
        module: Module name

    Returns:
        InlineKeyboardMarkup with confirm/cancel buttons
    """
    builder = InlineKeyboardBuilder()

    builder.row(
        InlineKeyboardButton(
            text="✅ Подтвердить",
            callback_data=f"{module}:confirm_{action}:{item_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отмена",
            callback_data=f"{module}:view:{item_id}"
        )
    )

    return builder.as_markup()


def get_list_item_keyboard(
    items: List[Dict[str, Any]],
    module: str,
    id_field: str = "id",
    title_field: str = "title",
) -> InlineKeyboardMarkup:
    """
    Build keyboard with list of items

    Args:
        items: List of items
        module: Module name
        id_field: Field name for item ID
        title_field: Field name for item title

    Returns:
        InlineKeyboardMarkup with item buttons
    """
    builder = InlineKeyboardBuilder()

    # Map module to emoji
    module_emoji = {
        "events": "📅",
        "courses": "🎓",
        "vacancies": "💼",
        "news": "📰",
        "projects": "🚀",
        "volunteers": "🤝",
    }
    emoji = module_emoji.get(module, "📌")

    for i, item in enumerate(items, 1):
        item_id = item.get(id_field)
        title = item.get(title_field, f"Элемент {item_id}")

        # Truncate long titles (account for emoji and number)
        max_len = 28
        if len(title) > max_len:
            title = title[:max_len - 3] + "..."

        builder.row(InlineKeyboardButton(
            text=f"{emoji} {title}",
            callback_data=f"{module}:view:{item_id}"
        ))

    return builder.as_markup()


def get_back_keyboard(callback_data: str = "menu:main") -> InlineKeyboardMarkup:
    """Simple back button keyboard"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="◀️ Назад",
        callback_data=callback_data
    ))
    return builder.as_markup()


def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin-specific menu keyboard"""
    builder = InlineKeyboardBuilder()

    # Admin features in 2 columns
    builder.row(
        InlineKeyboardButton(
            text="📊 Панель управления",
            callback_data="admin:stats"
        ),
        InlineKeyboardButton(
            text="👥 Сессии",
            callback_data="admin:sessions"
        )
    )

    # Back button (full width)
    builder.row(InlineKeyboardButton(
        text="🏠 Главное меню",
        callback_data="menu:main"
    ))

    return builder.as_markup()


def remove_keyboard() -> ReplyKeyboardRemove:
    """Remove reply keyboard"""
    return ReplyKeyboardRemove()
