"""
Authentication Handlers
/start, /login, /logout commands
"""
import logging
from typing import Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart, CommandObject

from api import get_tabys_client, TabysAPIError
from services import get_session_service
from models import UserSession
from middlewares import LoginRateLimitMiddleware, RBACContext
from keyboards import get_main_menu, get_back_keyboard
from utils import format_session_info, get_logger, format_datetime

router = Router(name="auth")
logger = get_logger(__name__)


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """
    /start command handler

    Shows authentication status and main menu if logged in
    """
    user = message.from_user
    logger.user_action("start", user.id)

    if is_authenticated and session:
        # Map roles to emojis
        role_emoji = {
            "super_admin": "👑",
            "administrator": "⚡",
            "government": "🏛",
            "npo": "🌟",
            "msb": "💼",
            "volunteer_admin": "🤝",
        }
        role_icon = role_emoji.get(session.role, "👤")

        await message.answer(
            f"👋 <b>С возвращением!</b>\n\n"
            f"{role_icon} <b>{session.admin_name or f'Админ #{session.admin_id}'}</b>\n"
            f"🎭 Роль: <code>{session.role}</code>\n\n"
            "📱 <b>Используйте меню ниже для навигации:</b>",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "🤖 <b>Добро пожаловать в Tabys CRM Bot!</b>\n\n"
            "🔐 <b>Требуется авторизация</b>\n\n"
            "📋 <b>Как войти:</b>\n"
            "1️⃣ Войдите в админ-панель Tabys\n"
            "2️⃣ Сгенерируйте OTP токен\n"
            "3️⃣ Отправьте: <code>/login ВАШ_OTP_ТОКЕН</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/login A7B9C3D5</code>\n\n"
            "❓ Нужна помощь? Используйте /help",
            parse_mode="HTML"
        )


@router.message(Command("login"))
async def cmd_login(
    message: Message,
    command: CommandObject,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """
    /login <OTP_TOKEN> command handler

    Verifies OTP token and creates session
    """
    user = message.from_user

    # Check if already authenticated
    if is_authenticated and session:
        await message.answer(
            f"✅ <b>Вы уже авторизованы</b>\n\n"
            f"🎭 Текущая роль: <code>{session.role}</code>\n\n"
            "💡 Используйте /logout если хотите сменить аккаунт.",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )
        return

    # Check for OTP token in command arguments
    otp_token = command.args.strip() if command.args else None

    if not otp_token:
        await message.answer(
            "❌ <b>Отсутствует OTP токен</b>\n\n"
            "📝 <b>Использование:</b>\n"
            "<code>/login ВАШ_OTP_ТОКЕН</code>\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/login A7B9C3D5</code>\n\n"
            "🔑 Получите OTP в админ-панели Tabys.",
            parse_mode="HTML"
        )
        return

    # Validate OTP format (8 alphanumeric characters)
    otp_token = otp_token.upper().strip()
    if len(otp_token) != 8 or not otp_token.isalnum():
        await message.answer(
            "⚠️ <b>Неверный формат OTP</b>\n\n"
            "📏 OTP должен содержать 8 буквенно-цифровых символов.\n\n"
            "💡 <b>Пример:</b>\n"
            "<code>/login A7B9C3D5</code>",
            parse_mode="HTML"
        )
        logger.auth_event("login", user.id, False, "Invalid OTP format")
        return

    # Verify OTP with backend
    try:
        client = get_tabys_client()
        result = await client.verify_otp(
            otp_token=otp_token,
            telegram_user_id=str(user.id),
            telegram_username=user.username,
            telegram_first_name=user.first_name,
            telegram_last_name=user.last_name,
        )

        # Create session in Redis
        session_service = await get_session_service()
        session = await session_service.create_session(
            telegram_user_id=str(user.id),
            admin_id=result.admin_id,
            role=result.role,
            access_token=result.access_token,
        )

        # Create RBAC context for menu
        new_rbac = RBACContext(session.role)

        logger.auth_event(
            "login", user.id, True,
            f"admin_id={result.admin_id} role={result.role}"
        )

        # Role-specific emoji
        role_emoji = {
            "super_admin": "👑",
            "administrator": "⚡",
            "government": "🏛",
            "npo": "🌟",
            "msb": "💼",
            "volunteer_admin": "🤝",
        }
        role_icon = role_emoji.get(result.role, "👤")

        await message.answer(
            f"✅ <b>Вход выполнен успешно!</b>\n\n"
            f"{role_icon} <b>Роль:</b> <code>{result.role}</code>\n"
            f"🆔 <b>ID админа:</b> <code>{result.admin_id}</code>\n\n"
            "🎉 <b>Добро пожаловать в Tabys CRM!</b>\n"
            "Используйте меню ниже для начала работы:",
            reply_markup=get_main_menu(new_rbac),
            parse_mode="HTML"
        )

    except TabysAPIError as e:
        logger.auth_event("login", user.id, False, e.detail or e.message)

        error_emoji = "❌"
        if e.status_code == 401:
            error_msg = f"{error_emoji} <b>Ошибка авторизации</b>\n\n🔒 Неверный или истекший OTP токен.\n\n💡 Сгенерируйте новый OTP в админ-панели."
        elif e.status_code == 404:
            error_msg = f"{error_emoji} <b>OTP не найден</b>\n\n🔍 Токен не существует или уже использован.\n\n💡 Сгенерируйте новый OTP."
        else:
            error_msg = f"{error_emoji} <b>Ошибка входа</b>\n\n⚠️ {e.detail or e.message}"

        await message.answer(error_msg, parse_mode="HTML")


@router.message(Command("logout"))
async def cmd_logout(
    message: Message,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
):
    """
    /logout command handler

    Removes session from Redis and notifies backend
    """
    user = message.from_user

    if not is_authenticated or not session:
        await message.answer(
            "ℹ️ <b>Вы не авторизованы</b>\n\n"
            "🔐 Используйте <code>/login ВАШ_OTP</code> для входа.",
            parse_mode="HTML"
        )
        return

    try:
        # Notify backend
        client = get_tabys_client()
        await client.logout(str(user.id))
    except TabysAPIError as e:
        logger.warning(f"Backend logout failed: {e.message}")
        # Continue with local logout even if backend fails

    # Remove Redis session
    session_service = await get_session_service()
    await session_service.delete_session(str(user.id))

    logger.auth_event("logout", user.id, True)

    await message.answer(
        "👋 <b>Выход выполнен успешно</b>\n\n"
        "✅ Ваша сессия завершена.\n\n"
        "🔐 Используйте <code>/login ВАШ_OTP</code> для входа.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "action:logout")
async def callback_logout(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
):
    """Logout via callback button"""
    user = callback.from_user

    if not is_authenticated or not session:
        await callback.answer("Вы не авторизованы", show_alert=True)
        await callback.message.edit_text(
            "Вы не авторизованы.\n"
            "Используйте /login <OTP_ТОКЕН> для входа."
        )
        return

    try:
        client = get_tabys_client()
        await client.logout(str(user.id))
    except TabysAPIError:
        pass

    session_service = await get_session_service()
    await session_service.delete_session(str(user.id))

    logger.auth_event("logout", user.id, True)

    await callback.answer("Выход выполнен")
    await callback.message.edit_text(
        "Вы успешно вышли из системы.\n\n"
        "Используйте /login <OTP_ТОКЕН> для входа."
    )


@router.message(Command("status"))
async def cmd_status(
    message: Message,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """
    /status command handler

    Shows current authentication and session status
    """
    user = message.from_user

    if is_authenticated and session:
        # Role-specific emoji
        role_emoji = {
            "super_admin": "👑",
            "administrator": "⚡",
            "government": "🏛",
            "npo": "🌟",
            "msb": "💼",
            "volunteer_admin": "🤝",
        }
        role_icon = role_emoji.get(session.role, "👤")

        # Calculate session age
        from datetime import datetime
        age = datetime.utcnow() - session.created_at
        hours = int(age.total_seconds() // 3600)
        minutes = int((age.total_seconds() % 3600) // 60)

        await message.answer(
            f"📊 <b>Статус сессии</b>\n\n"
            f"✅ <b>Статус:</b> Авторизован\n"
            f"{role_icon} <b>Роль:</b> <code>{session.role}</code>\n"
            f"🆔 <b>ID админа:</b> <code>{session.admin_id}</code>\n"
            f"👤 <b>Telegram ID:</b> <code>{session.telegram_user_id}</code>\n\n"
            f"⏱ <b>Время сессии:</b> {hours}ч {minutes}м\n"
            f"🕒 <b>Создана:</b> {format_datetime(session.created_at)}\n"
            f"🔄 <b>Последняя активность:</b> {format_datetime(session.last_activity)}\n\n"
            f"🔐 <b>Доступные модули:</b>\n"
            f"{_format_accessible_modules(rbac)}",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "📊 <b>Статус сессии</b>\n\n"
            "❌ <b>Статус:</b> Не авторизован\n\n"
            "🔐 Используйте <code>/login ВАШ_OTP</code> для входа.",
            parse_mode="HTML"
        )


def _format_accessible_modules(rbac: RBACContext) -> str:
    """Format accessible modules with emojis"""
    module_emoji = {
        "events": "📅",
        "courses": "🎓",
        "vacancies": "💼",
        "news": "📰",
        "projects": "🚀",
        "volunteers": "🤝",
        "users": "👥",
        "leisure": "🎮",
        "certificates": "🎖",
        "experts": "👨‍💼",
        "resumes": "📄",
    }

    modules = rbac.get_accessible_modules()
    if not modules:
        return "• Нет"

    # Format in 2 columns
    module_names_ru = {
        "events": "Мероприятия",
        "courses": "Курсы",
        "vacancies": "Вакансии",
        "news": "Новости",
        "projects": "Проекты",
        "volunteers": "Волонтеры",
        "users": "Пользователи",
        "leisure": "Досуг",
        "certificates": "Сертификаты",
        "experts": "Эксперты",
        "resumes": "Резюме",
    }

    lines = []
    for i in range(0, len(modules), 2):
        left = f"{module_emoji.get(modules[i], '•')} {module_names_ru.get(modules[i], modules[i].title())}"
        if i + 1 < len(modules):
            right = f"{module_emoji.get(modules[i+1], '•')} {module_names_ru.get(modules[i+1], modules[i+1].title())}"
            lines.append(f"• {left}  {right}")
        else:
            lines.append(f"• {left}")

    return "\n".join(lines)


@router.message(Command("menu"))
async def cmd_menu(
    message: Message,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """
    /menu command handler

    Shows main menu if authenticated
    """
    if not is_authenticated or not session:
        await message.answer(
            "🔐 <b>Требуется авторизация</b>\n\n"
            "Используйте <code>/login ВАШ_OTP</code> для входа.",
            parse_mode="HTML"
        )
        return

    await message.answer(
        "📱 <b>Главное меню</b>\n\n"
        "Выберите модуль для начала работы:",
        reply_markup=get_main_menu(rbac),
        parse_mode="HTML"
    )


@router.callback_query(F.data == "menu:main")
async def callback_main_menu(
    callback: CallbackQuery,
    session: Optional[UserSession] = None,
    is_authenticated: bool = False,
    rbac: Optional[RBACContext] = None,
):
    """Return to main menu via callback"""
    if not is_authenticated or not session:
        await callback.answer("⚠️ Сессия истекла", show_alert=True)
        try:
            await callback.message.edit_text(
                "⏱ <b>Сессия истекла</b>\n\n"
                "🔐 Пожалуйста, выполните <code>/login</code> снова.",
                parse_mode="HTML"
            )
        except Exception:
            await callback.message.delete()
            await callback.message.answer(
                "⏱ <b>Сессия истекла</b>\n\n"
                "🔐 Пожалуйста, выполните <code>/login</code> снова.",
                parse_mode="HTML"
            )
        return

    await callback.answer("🏠 Главное меню")

    # Try to edit text first, if fails - delete and send new
    try:
        await callback.message.edit_text(
            "📱 <b>Главное меню</b>\n\n"
            "Выберите модуль:",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )
    except Exception:
        # Message has photo or can't be edited - delete and send new
        await callback.message.delete()
        await callback.message.answer(
            "📱 <b>Главное меню</b>\n\n"
            "Выберите модуль:",
            reply_markup=get_main_menu(rbac),
            parse_mode="HTML"
        )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """
    /help command handler

    Shows available commands
    """
    await message.answer(
        "📚 <b>Tabys CRM Bot - Помощь</b>\n\n"
        "🤖 <b>Доступные команды:</b>\n"
        "├ /start - Запустить бота\n"
        "├ /login &lt;OTP&gt; - Войти с помощью OTP\n"
        "├ /logout - Завершить сессию\n"
        "├ /status - Просмотр информации о сессии\n"
        "├ /menu - Показать главное меню\n"
        "└ /help - Это сообщение помощи\n\n"
        "🔐 <b>Шаги авторизации:</b>\n"
        "1️⃣ Откройте админ-панель Tabys\n"
        "2️⃣ Нажмите 'Сгенерировать Telegram OTP'\n"
        "3️⃣ Скопируйте команду <code>/login</code>\n"
        "4️⃣ Отправьте её этому боту\n\n"
        "💡 <b>Безопасность:</b>\n"
        "• OTP истекает через 10 минут\n"
        "• Одноразовое использование\n"
        "• Сессия действительна 24 часа\n\n"
        "❓ <b>Нужна поддержка?</b>\n"
        "Свяжитесь с системным администратором",
        parse_mode="HTML"
    )
