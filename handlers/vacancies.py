"""
Vacancies Handlers
View and manage vacancies - Single vacancy view with navigation (like news)
"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InputMediaPhoto, URLInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from api import get_tabys_client, TabysAPIError
from models import UserSession, Module
from middlewares import RBACContext
from keyboards import get_main_menu
from utils import format_error, get_logger, escape_html, format_datetime

router = Router(name="vacancies")
logger = get_logger(__name__)

# In-memory cache for vacancies (simple dict without Redis)
# Structure: {user_id: {"data": [...], "page": int, "timestamp": datetime}}
_vacancies_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_MINUTES = 10  # Cache expires after 10 minutes


def _get_cached_vacancies(user_id: str, page: int) -> Optional[Dict[str, Any]]:
    """Get cached vacancies for user"""
    cache_key = f"{user_id}:{page}"
    if cache_key in _vacancies_cache:
        cache_entry = _vacancies_cache[cache_key]
        # Check if cache is still valid
        if datetime.now() - cache_entry["timestamp"] < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info(f"Using cached vacancies for user {user_id}, page {page}")
            return {"items": cache_entry["data"], "total": cache_entry["total"]}
        else:
            # Cache expired, remove it
            del _vacancies_cache[cache_key]
    return None


def _cache_vacancies(user_id: str, page: int, data: List[Dict[str, Any]], total: int):
    """Cache vacancies data for user"""
    cache_key = f"{user_id}:{page}"
    _vacancies_cache[cache_key] = {
        "data": data,
        "total": total,
        "timestamp": datetime.now()
    }
    logger.info(f"Cached vacancies for user {user_id}, page {page}, {len(data)} items, total {total}")

    # Clean old cache entries (simple cleanup)
    _cleanup_old_cache()


def _cleanup_old_cache():
    """Remove expired cache entries"""
    now = datetime.now()
    expired_keys = [
        key for key, value in _vacancies_cache.items()
        if now - value["timestamp"] > timedelta(minutes=CACHE_TTL_MINUTES)
    ]
    for key in expired_keys:
        del _vacancies_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


def format_vacancy_caption(vacancy: Dict[str, Any], current: int, total: int) -> str:
    """Format vacancy for display with caption"""
    title = vacancy.get("title_ru") or vacancy.get("title_kz") or vacancy.get("title") or "Untitled"
    title = escape_html(title)

    description = vacancy.get("description_ru") or vacancy.get("description_kz") or vacancy.get("description") or ""
    description = escape_html(description)

    # Get vacancy details
    company = escape_html(vacancy.get("company", "Not specified"))
    location = escape_html(vacancy.get("location", "Not specified"))
    salary = vacancy.get("salary")
    salary_str = escape_html(str(salary)) if salary else "По договоренности"

    employment_type = escape_html(vacancy.get("employment_type", "Full-time"))
    experience = escape_html(vacancy.get("experience", "Not specified"))

    # Date handling
    created_at = vacancy.get("created_at") or vacancy.get("published_at")
    deadline = vacancy.get("deadline") or vacancy.get("expires_at")

    date_info = []
    if created_at:
        date_info.append(f"📅 Опубликовано: {format_datetime(created_at)}")
    if deadline:
        date_info.append(f"⏰ Срок: {format_datetime(deadline)}")

    date_str = "\n".join(date_info) if date_info else "📅 N/A"

    # Telegram caption has 1024 char limit
    MAX_DESCRIPTION_LENGTH = 500
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH] + "..."

    caption = (
        f"💼 <b>{title}</b>\n\n"
        f"🏢 {company}\n"
        f"📍 {location}\n"
        f"💰 {salary_str}\n"
        f"👔 {employment_type} • 📊 Опыт: {experience}\n\n"
        f"{date_str}\n\n"
        f"{description}\n\n"
        f"📊 Vacancy {current} of {total}"
    )

    # Ensure total caption is under 1024 chars
    if len(caption) > 1020:
        caption = caption[:1017] + "..."

    return caption


def get_vacancy_navigation_keyboard_paginated(
    page: int,
    index: int,
    page_items: int,
    page_size: int,
    total: int,
    vacancy_id: Optional[int] = None,
    rbac: Optional[RBACContext] = None,
) -> InlineKeyboardBuilder:
    """Build navigation keyboard for vacancies with pagination"""
    builder = InlineKeyboardBuilder()

    # Calculate navigation
    is_first_item = (page == 1 and index == 0)
    is_last_item = (index == page_items - 1 and (page - 1) * page_size + page_items >= total)

    # Navigation row
    nav_buttons = []
    if not is_first_item:
        # Previous button
        if index > 0:
            # Previous item on same page
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущая",
                    callback_data=f"vacancies:nav:{page}:{index - 1}"
                )
            )
        else:
            # Previous page, last item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущая",
                    callback_data=f"vacancies:nav:{page - 1}:{page_size - 1}"
                )
            )

    if not is_last_item:
        # Next button
        if index < page_items - 1:
            # Next item on same page
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"vacancies:nav:{page}:{index + 1}"
                )
            )
        else:
            # Next page, first item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"vacancies:nav:{page + 1}:0"
                )
            )

    if nav_buttons:
        builder.row(*nav_buttons)

    # Read full vacancy button - links to Saryarqa Jastary website
    if vacancy_id:
        builder.row(
            InlineKeyboardButton(
                text="📖 Читать полностью",
                url=f"https://www.saryarqa-jastary.kz/ru/vacancies/{vacancy_id}"
            )
        )

    # Main menu button
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )

    return builder


@router.callback_query(F.data == "menu:vacancies")
async def show_vacancies_list(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show first vacancy"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    if not rbac or not rbac.can_read(Module.VACANCIES):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await callback.answer("💼 Загрузка вакансий...")
    await _show_vacancy_article(callback, session, rbac, page=1, index=0)


@router.callback_query(F.data.startswith("vacancies:nav:"))
async def vacancies_navigation(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Handle vacancies navigation (previous/next)"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    # Parse page:index from callback data
    parts = callback.data.split(":")
    page = int(parts[2])
    index = int(parts[3])

    await callback.answer()
    await _show_vacancy_article(callback, session, rbac, page=page, index=index)


async def _show_vacancy_article(
    callback: CallbackQuery,
    session: UserSession,
    rbac: RBACContext,
    page: int = 1,
    index: int = 0,
):
    """Helper to show a single vacancy with image"""
    try:
        PAGE_SIZE = 10  # Load only 10 vacancies per page for speed
        user_id = str(callback.from_user.id)

        # Try to get from cache first
        cached_response = _get_cached_vacancies(user_id, page)

        if cached_response is not None:
            # Use cached data
            items = cached_response["items"]
            total = cached_response["total"]
        else:
            # Load from API
            client = get_tabys_client()
            response = await client.get_vacancies(
                session.access_token,
                page=page,
                page_size=PAGE_SIZE
            )

            # Handle different response formats
            if isinstance(response, list):
                items = response
                total = len(response)
            else:
                items = response.get("items", response.get("data", []))
                total = response.get("total", len(items))

            # Cache the response
            _cache_vacancies(user_id, page, items, total)

        if not items:
            await callback.message.edit_text(
                "💼 <b>Вакансии</b>\n\nВакансии не найдены.",
                reply_markup=get_main_menu(rbac),
                parse_mode="HTML"
            )
            return

        # Ensure index is within bounds
        index = max(0, min(index, len(items) - 1))
        vacancy = items[index]

        # Calculate absolute position (across all pages)
        absolute_position = (page - 1) * PAGE_SIZE + index + 1

        # Get vacancy data
        vacancy_id = vacancy.get("id")
        image_url = vacancy.get("photo_url") or vacancy.get("image_url") or vacancy.get("image") or vacancy.get("company_logo")

        # Format caption
        caption = format_vacancy_caption(vacancy, absolute_position, total)

        # Build keyboard with pagination support
        keyboard = get_vacancy_navigation_keyboard_paginated(
            page,
            index,
            len(items),
            PAGE_SIZE,
            total,
            vacancy_id,
            rbac
        )

        # Send or edit message
        if image_url:
            try:
                # Try to edit existing message with photo
                if callback.message.photo:
                    # Edit existing photo message
                    await callback.message.edit_media(
                        media=InputMediaPhoto(
                            media=URLInputFile(image_url),
                            caption=caption,
                            parse_mode="HTML"
                        ),
                        reply_markup=keyboard.as_markup()
                    )
                else:
                    # Delete text message and send new photo message
                    await callback.message.delete()
                    await callback.message.answer_photo(
                        photo=URLInputFile(image_url),
                        caption=caption,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
            except Exception as e:
                logger.warning(f"Failed to send photo: {e}, falling back to text")
                # Fallback to text message if photo fails
                text = f"🖼 [Image unavailable]\n\n{caption}"
                if callback.message.photo:
                    await callback.message.delete()
                    await callback.message.answer(
                        text,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
                else:
                    await callback.message.edit_text(
                        text,
                        reply_markup=keyboard.as_markup(),
                        parse_mode="HTML"
                    )
        else:
            # No image, just show text
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    caption,
                    reply_markup=keyboard.as_markup(),
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    caption,
                    reply_markup=keyboard.as_markup(),
                    parse_mode="HTML"
                )

    except TabysAPIError as e:
        logger.error(f"Failed to fetch vacancies: {e}")
        error_text = (
            "❌ <b>Error Loading Vacancies</b>\n\n"
            f"⚠️ {e.detail or e.message}"
        )

        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    error_text,
                    reply_markup=get_main_menu(rbac),
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    error_text,
                    reply_markup=get_main_menu(rbac),
                    parse_mode="HTML"
                )
        except Exception:
            await callback.message.answer(
                error_text,
                reply_markup=get_main_menu(rbac),
                parse_mode="HTML"
            )
