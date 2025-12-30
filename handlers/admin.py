"""
Admin Handlers
Admin-specific functionality (statistics, session management)
"""
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery

from api import get_tabys_client, TabysAPIError
from models import UserSession, Role
from middlewares import RBACContext, require_role
from keyboards import get_main_menu, get_admin_menu_keyboard, get_back_keyboard
from utils import escape_html, format_error, get_logger

router = Router(name="admin")
logger = get_logger(__name__)


@router.callback_query(F.data == "menu:admin")
async def show_admin_menu(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show admin menu"""
    if not is_authenticated or not session:
        await callback.answer("Session expired", show_alert=True)
        return

    if not rbac or not rbac.is_admin():
        await callback.answer("Admin access required", show_alert=True)
        return

    await callback.answer()
    await callback.message.edit_text(
        "<b>Admin Panel</b>\n\n"
        "Select an option:",
        reply_markup=get_admin_menu_keyboard(),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "admin:stats")
async def show_dashboard_stats(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show dashboard statistics"""
    if not is_authenticated or not session:
        await callback.answer("Session expired", show_alert=True)
        return

    if not rbac or not rbac.is_admin():
        await callback.answer("Admin access required", show_alert=True)
        return

    await callback.answer()

    try:
        client = get_tabys_client()
        stats = await client.get_dashboard_stats(session.access_token)

        if isinstance(stats, dict) and "message" in stats:
            text = f"<b>Dashboard Statistics</b>\n\n{escape_html(stats['message'])}"
        else:
            # Format statistics
            text = "<b>Dashboard Statistics</b>\n\n"

            if isinstance(stats, dict):
                for key, value in stats.items():
                    if key.startswith("_"):
                        continue
                    formatted_key = key.replace("_", " ").title()
                    text += f"<b>{formatted_key}:</b> {value}\n"
            else:
                text += "Statistics data format not recognized."

        await callback.message.edit_text(
            text,
            reply_markup=get_back_keyboard("menu:admin"),
            parse_mode="HTML"
        )

    except TabysAPIError as e:
        logger.error(f"Failed to fetch stats: {e}")
        await callback.message.edit_text(
            format_error(e.detail or e.message),
            reply_markup=get_back_keyboard("menu:admin"),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "admin:sessions")
async def show_active_sessions(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show active Telegram sessions (super_admin only)"""
    if not is_authenticated or not session:
        await callback.answer("Session expired", show_alert=True)
        return

    if not rbac or not rbac.is_admin():
        await callback.answer("Admin access required", show_alert=True)
        return

    await callback.answer()

    # Note: This would require a custom endpoint or using the existing one
    text = (
        "<b>Active Telegram Sessions</b>\n\n"
        "To view active sessions, use the Tabys admin panel:\n"
        "GET /api/v1/telegram-auth/sessions\n\n"
        "This feature provides visibility into who is currently "
        "using the Telegram bot with admin access."
    )

    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard("menu:admin"),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu:volunteers")
async def show_volunteers_menu(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Show volunteers section"""
    if not is_authenticated or not session:
        await callback.answer("Session expired", show_alert=True)
        return

    from models import Module
    if not rbac or not rbac.can_read(Module.VOLUNTEERS):
        await callback.answer("Access denied", show_alert=True)
        return

    await callback.answer()

    try:
        client = get_tabys_client()
        response = await client.get_volunteers(session.access_token, page=1, page_size=10)

        if isinstance(response, list):
            items = response
            total = len(response)
        else:
            items = response.get("items", response.get("data", []))
            total = response.get("total", len(items))

        text = f"<b>Volunteers</b>\n\nTotal: {total} applications\n\n"

        if items:
            for i, item in enumerate(items[:10], 1):
                name = item.get("name", item.get("full_name", f"Volunteer {item.get('id')}"))
                status = item.get("status", "unknown")
                text += f"{i}. {escape_html(name)} - {status}\n"
        else:
            text += "No volunteer applications found."

        await callback.message.edit_text(
            text,
            reply_markup=get_back_keyboard("menu:main"),
            parse_mode="HTML"
        )

    except TabysAPIError as e:
        logger.error(f"Failed to fetch volunteers: {e}")
        await callback.message.edit_text(
            format_error(e.detail or e.message),
            reply_markup=get_back_keyboard("menu:main"),
            parse_mode="HTML"
        )


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """No-op callback for non-interactive buttons"""
    await callback.answer()
