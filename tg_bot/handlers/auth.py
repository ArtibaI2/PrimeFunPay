import asyncio
import contextlib
import re
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config.settings import settings
from database.engine import async_session
from database.repositories import UserRepository
from funpay.client import FunPayClient
from tg_bot.keyboards.admin_kb import (
    get_main_menu_keyboard,
    get_onboarding_keyboard,
    get_account_profile_keyboard,
)

router = Router(name="auth_router")

class UserAuthFSM(StatesGroup):
    waiting_golden_key = State()
    waiting_proxy = State()

async def get_or_create_client_for_user(tg_id: int, fallback_client: FunPayClient) -> FunPayClient:
    """Returns a FunPayClient instance initialized with the user's specific golden_key if registered."""
    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)
        if user and user.golden_key:
            return FunPayClient(
                golden_key=user.golden_key,
                user_agent=settings.FUNPAY_USER_AGENT,
                proxy=user.proxy or settings.FUNPAY_PROXY,
            )
    return fallback_client

@router.message(CommandStart())
async def cmd_start_handler(message: Message, state: FSMContext, funpay_client: FunPayClient):
    await state.clear()
    tg_id = message.from_user.id

    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)

    # If already registered or is in admin list with active global client
    if user and user.golden_key:
        profile_client = await get_or_create_client_for_user(tg_id, funpay_client)
        profile = await profile_client.check_auth()
        if profile_client != funpay_client:
            await profile_client.close()

        bal_info = f"<b>{profile.balance_rub:,.2f} ₽</b>" if profile else "<i>(загрузка...)</i>"
        user_name = profile.username if profile else (user.funpay_username or "Пользователь")

        await message.answer(
            f"👋 С возвращением, <b>{user_name}</b>!\n\n"
            f"💰 Ваш баланс на FunPay: {bal_info}\n"
            f"⚡ Бот активен и готов к автоматизации торговли.\n\n"
            f"Выберите нужный раздел в меню ниже 👇",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    # Check if global admin without DB record
    if tg_id in settings.TELEGRAM_ADMIN_IDS and settings.FUNPAY_GOLDEN_KEY:
        profile = await funpay_client.check_auth()
        bal_info = f"<b>{profile.balance_rub:,.2f} ₽</b>" if profile else ""
        user_name = profile.username if profile else "Администратор"

        # Automatically record admin into user_accounts
        if profile:
            async with async_session() as session:
                user_repo = UserRepository(session)
                await user_repo.register_or_update(
                    telegram_id=tg_id,
                    golden_key=settings.FUNPAY_GOLDEN_KEY,
                    funpay_user_id=profile.user_id,
                    funpay_username=profile.username,
                    telegram_username=message.from_user.username,
                    proxy=settings.FUNPAY_PROXY,
                )

        await message.answer(
            f"👋 Добро пожаловать, <b>{user_name}</b>!\n\n"
            f"💰 Баланс: {bal_info}\n"
            f"🤖 Вы вошли как администратор. Все функции доступны в меню ниже 👇",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    # New unregistered user onboarding
    await message.answer(
        "👋 <b>Добро пожаловать в FunPay Automation Bot!</b>\n\n"
        "Этот бот позволяет полностью автоматизировать ваши продажи на FunPay:\n"
        "• ⚡ <b>Автовыдача 24/7</b> (аккаунты, ключи, ссылки Workupload / Google Drive)\n"
        "• 🚀 <b>Автоподнятие предложений</b> во всех ваших категориях\n"
        "• 💬 <b>Автоответчик покупателям</b> и чат-центр\n"
        "• 🔥 <b>Анализ рынка</b> и трендов конкурентов за 24 часа\n\n"
        "👉 Чтобы начать пользоваться ботом, привяжите ваш аккаунт FunPay с помощью <code>golden_key</code>.",
        parse_mode="HTML",
        reply_markup=get_onboarding_keyboard(),
    )

@router.callback_query(F.data == "auth_how_to_key")
async def cb_how_to_key(query: CallbackQuery):
    text = (
        "📖 <b>Как получить <code>golden_key</code> от FunPay:</b>\n\n"
        "1. Откройте сайт <a href='https://funpay.com'>FunPay.com</a> в браузере на ПК и войдите в свой аккаунт.\n"
        "2. Нажмите клавишу <b>F12</b> (или Ctrl+Shift+I), чтобы открыть панель разработчика.\n"
        "3. Перейдите во вкладку <b>Application</b> (Приложение) или <b>Storage</b> (Память).\n"
        "4. В левом меню раскройте <b>Cookies</b> -> выберите <code>https://funpay.com</code>.\n"
        "5. Найдите строку с именем <code>golden_key</code> и скопируйте её 32-значное значение (например: <code>a1b2c3d4e5f6...</code>).\n\n"
        "⚠️ <i>Никому не передавайте свой golden_key. Бот использует его исключительно для работы с вашим магазином.</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔑 Привязать аккаунт", callback_data="auth_link_account")]])
    await query.message.answer(text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True)
    await query.answer()

@router.callback_query(F.data == "auth_link_account")
async def cb_auth_link_account(query: CallbackQuery, state: FSMContext):
    await state.set_state(UserAuthFSM.waiting_golden_key)
    cancel_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="auth_cancel")]])
    await query.message.answer(
        "🔑 <b>Введите ваш <code>golden_key</code> от FunPay:</b>\n\n"
        "<i>Отправьте 32-значный ключ cookie в ответном сообщении:</i>",
        parse_mode="HTML",
        reply_markup=cancel_kb,
    )
    await query.answer()

@router.callback_query(F.data == "auth_cancel")
async def cb_auth_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text("❌ Привязка аккаунта отменена.")
    await query.answer()

@router.message(UserAuthFSM.waiting_golden_key)
async def process_golden_key(message: Message, state: FSMContext):
    raw_key = message.text.strip()
    if len(raw_key) < 16:
        await message.answer("⚠️ Слишком короткий ключ. <code>golden_key</code> обычно состоит из 32 символов. Попробуйте еще раз:")
        return

    load_msg = await message.answer("⏳ <i>Проверка авторизации на FunPay... Пожалуйста, подождите...</i>", parse_mode="HTML")

    test_client = FunPayClient(
        golden_key=raw_key,
        user_agent=settings.FUNPAY_USER_AGENT,
        proxy=settings.FUNPAY_PROXY,
    )

    try:
        profile = await test_client.check_auth()
    except Exception as e:
        profile = None

    await test_client.close()

    if not profile or not profile.is_authenticated:
        await load_msg.edit_text(
            "❌ <b>Не удалось авторизоваться на FunPay с этим ключом!</b>\n\n"
            "Возможные причины:\n"
            "• Ключ скопирован с ошибкой или устарел\n"
            "• Вы вышли из аккаунта на сайте FunPay (после чего ключ сбрасывается)\n\n"
            "Пожалуйста, скопируйте актуальный <code>golden_key</code> из браузера и отправьте снова:",
            parse_mode="HTML",
        )
        return

    # Success! Save to database
    async with async_session() as session:
        user_repo = UserRepository(session)
        await user_repo.register_or_update(
            telegram_id=message.from_user.id,
            golden_key=raw_key,
            funpay_user_id=profile.user_id,
            funpay_username=profile.username,
            telegram_username=message.from_user.username,
            proxy=None,
        )

    await state.clear()

    bal_str = f"{profile.balance_rub:,.2f} ₽"
    avail_str = f" <i>(доступно к выводу: {profile.balance_available_rub:,.2f} ₽)</i>" if profile.balance_available_rub != profile.balance_rub and profile.balance_available_rub > 0 else ""

    await load_msg.edit_text(
        f"🎉 <b>Аккаунт FunPay успешно привязан!</b>\n\n"
        f"👤 <b>Продавец:</b> <code>{profile.username}</code> (ID: <code>{profile.user_id}</code>)\n"
        f"💰 <b>Баланс:</b> <code>{bal_str}</code>{avail_str}\n"
        f"📦 <b>Активных предложений:</b> <code>{profile.active_orders_count}</code>\n\n"
        f"Теперь все функции бота доступны для вашего магазина! Выберите действие в меню ниже 👇",
        parse_mode="HTML",
    )
    await message.answer("📱 Главное меню активировано:", reply_markup=get_main_menu_keyboard())

@router.message(F.text == "👤 Мой FunPay аккаунт")
@router.message(Command("profile"))
@router.message(Command("account"))
async def cmd_my_account(message: Message, funpay_client: FunPayClient):
    tg_id = message.from_user.id
    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)

    client = await get_or_create_client_for_user(tg_id, funpay_client)
    profile = await client.check_auth()
    if client != funpay_client:
        await client.close()

    if not profile and not user:
        await message.answer(
            "⚠️ У вас пока не привязан аккаунт FunPay.",
            reply_markup=get_onboarding_keyboard(),
        )
        return

    uname = profile.username if profile else (user.funpay_username if user else "Unknown")
    uid = profile.user_id if profile else (user.funpay_user_id if user else "N/A")
    bal = f"{profile.balance_rub:,.2f} ₽" if profile else "N/A"
    avail = f" <i>(к выводу: {profile.balance_available_rub:,.2f} ₽)</i>" if profile and profile.balance_available_rub > 0 else ""
    proxy_info = user.proxy if (user and user.proxy) else "Прямое подключение (без прокси)"

    text = (
        f"👤 <b>ВАШ ПРИВЯЗАННЫЙ FUNPAY АККАУНТ</b>\n\n"
        f"• Логин FunPay: <b>{uname}</b>\n"
        f"• ID пользователя: <code>{uid}</code>\n"
        f"• 💰 Баланс: <b>{bal}</b>{avail}\n"
        f"• 🌐 Прокси: <code>{proxy_info}</code>\n"
        f"• ⚡ Статус автовыдачи: <b>Включена</b>\n"
        f"• 🚀 Статус автоподнятия: <b>Включено</b>\n\n"
        f"<i>Используйте кнопки ниже для управления вашим аккаунтом:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_account_profile_keyboard())

@router.callback_query(F.data == "auth_refresh_profile")
async def cb_refresh_profile(query: CallbackQuery, funpay_client: FunPayClient):
    tg_id = query.from_user.id
    client = await get_or_create_client_for_user(tg_id, funpay_client)
    profile = await client.check_auth()
    if client != funpay_client:
        await client.close()

    if profile:
        await query.answer("✅ Данные аккаунта обновлены!")
        bal = f"{profile.balance_rub:,.2f} ₽"
        avail = f" <i>(к выводу: {profile.balance_available_rub:,.2f} ₽)</i>" if profile.balance_available_rub > 0 else ""
        text = (
            f"👤 <b>ВАШ ПРИВЯЗАННЫЙ FUNPAY АККАУНТ</b>\n\n"
            f"• Логин FunPay: <b>{profile.username}</b>\n"
            f"• ID пользователя: <code>{profile.user_id}</code>\n"
            f"• 💰 Баланс: <b>{bal}</b>{avail}\n"
            f"• 📦 Активных заказов: <code>{profile.active_orders_count}</code>\n"
            f"• 💬 Непрочитанных чатов: <code>{profile.unread_chats_count}</code>\n\n"
            f"<i>Используйте кнопки ниже для управления вашим аккаунтом:</i>"
        )
        with contextlib.suppress(Exception):
            await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_account_profile_keyboard())
    else:
        await query.answer("⚠️ Не удалось обновить профиль.", show_alert=True)

@router.callback_query(F.data == "auth_unlink_account")
async def cb_unlink_account(query: CallbackQuery):
    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗑 Да, отвязать", callback_data="auth_confirm_unlink"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="auth_cancel_unlink"),
        ]
    ])
    await query.message.edit_text(
        "⚠️ <b>Вы уверены, что хотите отвязать ваш FunPay аккаунт от этого Telegram?</b>\n\n"
        "Бот перестанет обслуживать ваши лоты и отвечать покупателям до повторной привязки.",
        parse_mode="HTML",
        reply_markup=confirm_kb,
    )
    await query.answer()

@router.callback_query(F.data == "auth_confirm_unlink")
async def cb_confirm_unlink(query: CallbackQuery):
    async with async_session() as session:
        user_repo = UserRepository(session)
        await user_repo.delete_user(query.from_user.id)

    await query.message.edit_text(
        "✅ <b>Аккаунт успешно отвязан.</b>\n\nВы можете привязать новый аккаунт в любое время командой /start.",
        parse_mode="HTML",
    )
    await query.answer()

@router.callback_query(F.data == "auth_cancel_unlink")
async def cb_cancel_unlink(query: CallbackQuery, funpay_client: FunPayClient):
    await cb_refresh_profile(query, funpay_client)
