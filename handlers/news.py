"""
News Handlers
View and manage news articles - Single article view with navigation
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

router = Router(name="news")
logger = get_logger(__name__)

# In-memory cache for news (simple dict without Redis)
# Structure: {user_id: {"data": [...], "page": int, "timestamp": datetime}}
_news_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL_MINUTES = 10  # Cache expires after 10 minutes


def _get_cached_news(user_id: str, page: int) -> Optional[Dict[str, Any]]:
    """Get cached news for user"""
    cache_key = f"{user_id}:{page}"
    if cache_key in _news_cache:
        cache_entry = _news_cache[cache_key]
        # Check if cache is still valid
        if datetime.now() - cache_entry["timestamp"] < timedelta(minutes=CACHE_TTL_MINUTES):
            logger.info(f"Using cached news for user {user_id}, page {page}")
            return {"items": cache_entry["data"], "total": cache_entry["total"]}
        else:
            # Cache expired, remove it
            del _news_cache[cache_key]
    return None


def _cache_news(user_id: str, page: int, data: List[Dict[str, Any]], total: int):
    """Cache news data for user"""
    cache_key = f"{user_id}:{page}"
    _news_cache[cache_key] = {
        "data": data,
        "total": total,
        "timestamp": datetime.now()
    }
    logger.info(f"Cached news for user {user_id}, page {page}, {len(data)} items, total {total}")

    # Clean old cache entries (simple cleanup)
    _cleanup_old_cache()


def _cleanup_old_cache():
    """Remove expired cache entries"""
    now = datetime.now()
    expired_keys = [
        key for key, value in _news_cache.items()
        if now - value["timestamp"] > timedelta(minutes=CACHE_TTL_MINUTES)
    ]
    for key in expired_keys:
        del _news_cache[key]
    if expired_keys:
        logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")


def format_news_caption(article: Dict[str, Any], current: int, total: int) -> str:
    """Format news article for display with caption"""
    title = article.get("title_ru") or article.get("title_kz") or article.get("title") or "Untitled"
    title = escape_html(title)

    content = article.get("content_ru") or article.get("content_kz") or article.get("content") or ""
    content = escape_html(content)

    category = escape_html(article.get("category", "News"))
    source = escape_html(article.get("source", "Unknown"))

    published_at = article.get("published_at") or article.get("created_at")
    date_str = format_datetime(published_at) if published_at else "N/A"

    # Telegram caption has 1024 char limit
    MAX_CONTENT_LENGTH = 700
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "..."

    caption = (
        f"📰 <b>{title}</b>\n\n"
        f"📅 {date_str} • 🏷 {category}\n"
        f"📍 {source}\n\n"
        f"{content}\n\n"
        f"📊 Article {current} of {total}"
    )

    # Ensure total caption is under 1024 chars
    if len(caption) > 1020:
        caption = caption[:1017] + "..."

    return caption


def get_news_navigation_keyboard_paginated(
    page: int,
    index: int,
    page_items: int,
    page_size: int,
    total: int,
    article_id: Optional[int] = None,
    article_url: Optional[str] = None,
    rbac: Optional[RBACContext] = None,
) -> InlineKeyboardBuilder:
    """Build navigation keyboard for news articles with pagination"""
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
                    callback_data=f"news:nav:{page}:{index - 1}"
                )
            )
        else:
            # Previous page, last item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="⬅️ Предыдущая",
                    callback_data=f"news:nav:{page - 1}:{page_size - 1}"
                )
            )

    if not is_last_item:
        # Next button
        if index < page_items - 1:
            # Next item on same page
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"news:nav:{page}:{index + 1}"
                )
            )
        else:
            # Next page, first item
            nav_buttons.append(
                InlineKeyboardButton(
                    text="Следующая ➡️",
                    callback_data=f"news:nav:{page + 1}:0"
                )
            )

    if nav_buttons:
        builder.row(*nav_buttons)

    # Read full article button - links to Saryarqa Jastary website
    if article_id:
        builder.row(
            InlineKeyboardButton(
                text="📖 Читать полностью",
                url=f"https://www.saryarqa-jastary.kz/ru/news/{article_id}"
            )
        )

    # Original source link button (if available)
    if article_url and article_url != f"https://www.saryarqa-jastary.kz/ru/news/{article_id}":
        builder.row(
            InlineKeyboardButton(text="🔗 Источник", url=article_url)
        )

    # Main menu button
    builder.row(
        InlineKeyboardButton(text="🏠 Главное меню", callback_data="menu:main")
    )

    return builder


@router.callback_query(F.data == "menu:news")
async def show_news_list(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show first news article"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    if not rbac or not rbac.can_read(Module.NEWS):
        await callback.answer("Доступ запрещен", show_alert=True)
        return

    await callback.answer("📰 Загрузка новостей...")
    await _show_news_article(callback, session, rbac, page=1, index=0)


@router.callback_query(F.data.startswith("news:nav:"))
async def news_navigation(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Handle news navigation (previous/next)"""
    if not is_authenticated or not session:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    # Parse page:index from callback data
    parts = callback.data.split(":")
    page = int(parts[2])
    index = int(parts[3])

    await callback.answer()
    await _show_news_article(callback, session, rbac, page=page, index=index)


async def _show_news_article(
    callback: CallbackQuery,
    session: UserSession,
    rbac: RBACContext,
    page: int = 1,
    index: int = 0,
):
    """Helper to show a single news article with image"""
    try:
        PAGE_SIZE = 10  # Load only 10 articles per page for speed
        user_id = str(callback.from_user.id)

        # Try to get from cache first
        cached_response = _get_cached_news(user_id, page)

        if cached_response is not None:
            # Use cached data
            items = cached_response["items"]
            total = cached_response["total"]
        else:
            # Load from API
            client = get_tabys_client()
            response = await client.get_news(
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
            _cache_news(user_id, page, items, total)

        if not items:
            await callback.message.edit_text(
                "📰 <b>Новости</b>\n\nНовости не найдены.",
                reply_markup=get_main_menu(rbac).as_markup(),
                parse_mode="HTML"
            )
            return

        # Ensure index is within bounds
        index = max(0, min(index, len(items) - 1))
        article = items[index]

        # Calculate absolute position (across all pages)
        absolute_position = (page - 1) * PAGE_SIZE + index + 1

        # Get article data
        article_id = article.get("id")
        image_url = article.get("photo_url")  # Use photo_url from API response
        article_url = article.get("url") or article.get("source_url") or article.get("link")

        # Format caption
        caption = format_news_caption(article, absolute_position, total)

        # Build keyboard with pagination support
        keyboard = get_news_navigation_keyboard_paginated(
            page,
            index,
            len(items),
            PAGE_SIZE,
            total,
            article_id,
            article_url,
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
        logger.error(f"Failed to fetch news: {e}")
        error_text = (
            "❌ <b>Error Loading News</b>\n\n"
            f"⚠️ {e.detail or e.message}"
        )

        try:
            if callback.message.photo:
                await callback.message.delete()
                await callback.message.answer(
                    error_text,
                    reply_markup=get_main_menu(rbac).as_markup(),
                    parse_mode="HTML"
                )
            else:
                await callback.message.edit_text(
                    error_text,
                    reply_markup=get_main_menu(rbac).as_markup(),
                    parse_mode="HTML"
                )
        except Exception:
            await callback.message.answer(
                error_text,
                reply_markup=get_main_menu(rbac).as_markup(),
                parse_mode="HTML"
            )
