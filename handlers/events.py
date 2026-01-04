"""
Events Handlers
View and manage events - Single event view with navigation (like news)
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

router = Router(name="events")
logger = get_logger(__name__)

# In-memory cache for events (simple dict without Redis)
# Structure: {user_id: {"data": [...], "page": int, "timestamp": datetime}}
_events_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_MINUTES = 10  # Cache expires after 10 minutes


def _get_cached_events(user_id: str, page: int) -> Optional[Dict[str, Any]]:
    """Get cached events for user"""
    cache_key = f"{user_id}:{page}"
    if cache_key in _events_cache:
        cache_entry = _events_cache[cache_key]
        # Check if cache is still valid
        if datetime.now() - cache_entry["timestamp"] < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info(f"Using cached events for user {user_id}, page {page}")
            return {"items": cache_entry["data"], "total": cache_entry["total"]}
        else:
            # Cache expired, remove it
            del _events_cache[cache_key]
    return None


def _cache_events(user_id: str, page: int, data: List[Dict[str, Any]], total: int):
    """Cache events data for user"""
    cache_key = f"{user_id}:{page}"
    _events_cache[cache_key] = {
        "data": data,
        "total": total,
        "timestamp": datetime.now()
    }
    logger.info(f"Cached events for user {user_id}, page {page}, {len(data)} items, total {total}")

    # Clean old cache entries (simple cleanup)
    _cleanup_old_cache()


def _cleanup_old_cache():
    """Remove expired cache entries"""
    now = datetime.now()
    expired_keys = [
        key for key, value in _events_cache.items()
        if now - value["timestamp"] > timedelta(minutes=CACHE_TTL_MINUTES)
    ]
    for key in expired_keys:
        del _events_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


def format_event_caption(event: Dict[str, Any], current: int, total: int) -> str:
    """Format event for display with caption"""
    title = event.get("title_ru") or event.get("title_kz") or event.get("title") or "Untitled"
    title = escape_html(title)

    description = event.get("description_ru") or event.get("description_kz") or event.get("description") or ""
    description = escape_html(description)

    # Get event details
    location = escape_html(event.get("location", "Not specified"))
    category = escape_html(event.get("category", "Event"))

    # Date handling
    start_date = event.get("start_date") or event.get("date") or event.get("created_at")
    end_date = event.get("end_date")

    if start_date and end_date:
        date_str = f"{format_datetime(start_date)} - {format_datetime(end_date)}"
    elif start_date:
        date_str = format_datetime(start_date)
    else:
        date_str = "N/A"

    # Telegram caption has 1024 char limit
    MAX_DESCRIPTION_LENGTH = 700
    if len(description) > MAX_DESCRIPTION_LENGTH:
        description = description[:MAX_DESCRIPTION_LENGTH] + "..."

    caption = (
        f"📅 <b>{title}</b>\n\n"
        f"📆 {date_str}\n"
        f"📍 {location} • 🏷 {category}\n\n"
        f"{description}\n\n"
        f"📊 Event {current} of {total}"
    )

    # Ensure total caption is under 1024 chars
    if len(caption) > 1020:
        caption = caption[:1017] + "..."

    return caption


def get_event_navigation_keyboard_paginated(
    page: int,
    index: int,
    page_items: int,
    page_size: int,
    total: int,
    event_id: Optional[int] = None,
    rbac: Optional[RBACContext] = None,
) -> InlineKeyboardBuilder:
    """Build navigation keyboard for events with pagination"""
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
                    text="⬅️ Предыдущее",
                    callback_data=f"events:nav:{page}:{index - 1}"
                )
            )
        else:
            # Previous page, last item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущее",
                    callback_data=f"events:nav:{page - 1}:{page_size - 1}"
                )
            )

    if not is_last_item:
        # Next button
        if index < page_items - 1:
            # Next item on same page
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующее ➡️",
                    callback_data=f"events:nav:{page}:{index + 1}"
                )
            )
        else:
            # Next page, first item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующее ➡️",
                    callback_data=f"events:nav:{page + 1}:0"
                )
            )

    if nav_buttons:
        builder.row(*nav_buttons)

    # Read full event button - links to Saryarqa Jastary website
    if event_id:
        builder.row(
            InlineKeyboardButton(
                text="📖 Читать полностью",
                url=f"https://www.saryarqa-jastary.kz/ru/events/{event_id}"
            )
        )

    # Main menu button
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )

    return builder


@router.callback_query(F.data == "menu:events")
async def show_events_list(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show first event"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    if not rbac or not rbac.can_read(Module.EVENTS):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await callback.answer("📅 Загрузка мероприятий...")
    await _show_event_article(callback, session, rbac, page=1, index=0)


@router.callback_query(F.data.startswith("events:nav:"))
async def events_navigation(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Handle events navigation (previous/next)"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    # Parse page:index from callback data
    parts = callback.data.split(":")
    page = int(parts[2])
    index = int(parts[3])

    await callback.answer()
    await _show_event_article(callback, session, rbac, page=page, index=index)


async def _show_event_article(
    callback: CallbackQuery,
    session: UserSession,
    rbac: RBACContext,
    page: int = 1,
    index: int = 0,
):
    """Helper to show a single event with image"""
    try:
        PAGE_SIZE = 10  # Load only 10 events per page for speed
        user_id = str(callback.from_user.id)

        # Try to get from cache first
        cached_response = _get_cached_events(user_id, page)

        if cached_response is not None:
            # Use cached data
            items = cached_response["items"]
            total = cached_response["total"]
        else:
            # Load from API
            client = get_tabys_client()
            response = await client.get_events(
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
            _cache_events(user_id, page, items, total)

        if not items:
            await callback.message.edit_text(
                "📅 <b>Мероприятия</b>\n\nМероприятия не найдены.",
                reply_markup=get_main_menu(rbac),
                parse_mode="HTML"
            )
            return

        # Ensure index is within bounds
        index = max(0, min(index, len(items) - 1))
        event = items[index]

        # Calculate absolute position (across all pages)
        absolute_position = (page - 1) * PAGE_SIZE + index + 1

        # Get event data
        event_id = event.get("id")
        image_url = event.get("photo_url") or event.get("image_url") or event.get("image")

        # Format caption
        caption = format_event_caption(event, absolute_position, total)

        # Build keyboard with pagination support
        keyboard = get_event_navigation_keyboard_paginated(
            page,
            index,
            len(items),
            PAGE_SIZE,
            total,
            event_id,
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
        logger.error(f"Failed to fetch events: {e}")
        error_text = (
            "❌ <b>Error Loading Events</b>\n\n"
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
