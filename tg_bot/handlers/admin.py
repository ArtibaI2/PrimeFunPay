import asyncio
import contextlib
from typing import Optional, List, Dict, Any
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from config.settings import settings
from database.engine import async_session
from database.repositories import OrderRepository, LotRepository
from funpay.client import FunPayClient
from funpay.services.market_analytics import MarketAnalyticsService
from tg_bot.keyboards.admin_kb import (
    get_main_menu_keyboard,
    get_settings_keyboard,
    get_stats_keyboard,
    get_market_keyboard,
)

from utils.auth_helper import is_user_authorized

router = Router(name="admin_router")

async def is_admin(user_id: int) -> bool:
    return await is_user_authorized(user_id)

async def build_stats_text(funpay_client: FunPayClient, period_code: str = "today") -> str:
    profile = await funpay_client.check_auth()
    profile_info = "⚠️ Не удалось получить профиль FunPay"
    if profile:
        bal_line = f"💰 <b>Баланс:</b> <code>{profile.balance_rub:,.2f} ₽</code>"
        if profile.balance_available_rub != profile.balance_rub and profile.balance_available_rub > 0:
            bal_line += f" <i>(к выводу: {profile.balance_available_rub:,.2f} ₽)</i>"
        if profile.balance_usd > 0:
            bal_line += f" | <code>{profile.balance_usd:,.2f} $</code>"
        if profile.balance_eur > 0:
            bal_line += f" | <code>{profile.balance_eur:,.2f} €</code>"

        profile_info = (
            f"👤 <b>Аккаунт:</b> {profile.username} (ID: <code>{profile.user_id}</code>)\n"
            f"{bal_line}\n"
            f"📦 <b>Активных заказов:</b> {profile.active_orders_count}\n"
            f"💬 <b>Непрочитанных чатов:</b> {profile.unread_chats_count}"
        )

    days_map = {
        "today": 1,
        "week": 7,
        "month": 30,
        "all": None,
    }
    period_label_map = {
        "today": "за сегодня",
        "week": "за 7 дней",
        "month": "за 30 дней",
        "all": "за всё время",
    }
    days = days_map.get(period_code, 1)
    period_title = period_label_map.get(period_code, "за сегодня")

    async with async_session() as session:
        order_repo = OrderRepository(session)
        stats = await order_repo.get_period_stats(days=days)

    return (
        f"📊 <b>Финансовая аналитика ({period_title}):</b>\n\n"
        f"{profile_info}\n\n"
        f"📈 <b>Показатели торговли ({period_title}):</b>\n"
        f"• Всего заказов: <b>{stats['total_orders']}</b>\n"
        f"• Выполнено заказов: <b>{stats['delivered_orders']}</b>\n"
        f"• Выручка: <b>{stats['total_revenue']:,.2f} ₽</b>\n"
        f"• Средний чек: <b>{stats['avg_check']:,.2f} ₽</b>"
    )

@router.message(F.text == "📊 Статистика")
@router.message(Command("stats"))
async def cmd_stats(message: Message, funpay_client: FunPayClient):
    if not await is_admin(message.from_user.id):
        return

    text = await build_stats_text(funpay_client, "today")
    await message.answer(text, parse_mode="HTML", reply_markup=get_stats_keyboard("today"))

@router.callback_query(F.data.startswith("stats_period:"))
async def cb_stats_period(query: CallbackQuery, funpay_client: FunPayClient):
    period_code = query.data.split(":")[1]
    text = await build_stats_text(funpay_client, period_code)
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_stats_keyboard(period_code))
    await query.answer()

@router.callback_query(F.data == "stats_top")
async def cb_stats_top(query: CallbackQuery):
    async with async_session() as session:
        order_repo = OrderRepository(session)
        top = await order_repo.get_top_products(limit=7)

    if not top:
        return await query.answer("Нет данных о продажах.", show_alert=True)

    lines = ["🏆 <b>Топ продаваемых товаров:</b>\n"]
    for i, prod in enumerate(top, 1):
        lines.append(
            f"<b>{i}.</b> {prod['title'][:35]}\n"
            f"   📦 Продаж: <b>{prod['count']} шт.</b> | Выручка: <b>{prod['revenue']:,.2f} ₽</b>\n"
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад к статистике", callback_data="stats_period:today")]])
    await query.message.edit_text("\n".join(lines), parse_mode="HTML", reply_markup=kb)
    await query.answer()

market_service_instance: Optional[MarketAnalyticsService] = None

def get_market_service(funpay_client: FunPayClient) -> MarketAnalyticsService:
    global market_service_instance
    if not market_service_instance:
        market_service_instance = MarketAnalyticsService(funpay_client)
    return market_service_instance

@router.message(F.text == "🔥 Анализ рынка (24ч)")
@router.message(F.text == "🔥 Анализ рынка")
@router.message(Command("market"))
@router.message(Command("trends"))
async def cmd_market_analysis(message: Message, funpay_client: FunPayClient):
    if not await is_admin(message.from_user.id):
        return

    load_msg = await message.answer("⏳ <i>Сканирование категорий FunPay и анализ трендов конкурентов за 24 часа...</i>", parse_mode="HTML")

    market_svc = get_market_service(funpay_client)

    categories = {}
    profile = funpay_client.profile or await funpay_client.check_auth()
    if profile:
        user_lots = await funpay_client.get_user_lots(profile.user_id)
        for l in user_lots:
            nid = l.get("node_id")
            cname = l.get("category_name", str(nid))
            if nid:
                categories[nid] = cname

    if not categories:
        categories = {
            923: "Discord Nitro",
            469: "Прочее Apex Legends",
            908: "Прочее Brawl Stars",
            1351: "Прочее Counter-Strike 2",
            1099: "Прочее Minecraft",
        }

    report = await market_svc.generate_market_report(categories)
    text = market_svc.format_telegram_report(report)

    await load_msg.edit_text(text, parse_mode="HTML", reply_markup=get_market_keyboard())

@router.callback_query(F.data == "market_refresh")
async def cb_market_refresh(query: CallbackQuery, funpay_client: FunPayClient):
    await query.answer("Обновление анализа...")
    with contextlib.suppress(Exception):
        await query.message.edit_text("⏳ <i>Обновление анализа рынка по конкурентам...</i>", parse_mode="HTML")

    market_svc = get_market_service(funpay_client)
    categories = {}
    profile = funpay_client.profile or await funpay_client.check_auth()
    if profile:
        user_lots = await funpay_client.get_user_lots(profile.user_id)
        for l in user_lots:
            nid = l.get("node_id")
            cname = l.get("category_name", str(nid))
            if nid:
                categories[nid] = cname

    if not categories:
        categories = {
            923: "Discord Nitro",
            469: "Прочее Apex Legends",
            908: "Прочее Brawl Stars",
            1351: "Прочее Counter-Strike 2",
            1099: "Прочее Minecraft",
        }

    report = await market_svc.generate_market_report(categories, force_refresh=True)
    text = market_svc.format_telegram_report(report)

    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_market_keyboard())

@router.message(F.text == "📋 Последние заказы")
@router.message(Command("orders"))
async def cmd_recent_orders(message: Message, funpay_client: FunPayClient):
    if not await is_admin(message.from_user.id):
        return

    # 1. Fetch live recent orders directly from FunPay
    orders = await funpay_client.get_trade_orders()

    if orders:
        status_map = {
            "closed": ("✅", "Закрыт"),
            "paid": ("⏳", "Оплачен"),
            "refunded": ("↩️", "Возврат"),
            "disputed": ("⚠️", "Спор"),
        }
        lines = ["📋 <b>Последние заказы FunPay:</b>\n"]
        for ord in orders[:8]:
            icon, status_label = status_map.get(ord.status, ("📦", ord.status))
            lines.append(
                f"{icon} <code>#{ord.order_id}</code> | <b>{ord.price:,.2f} ₽</b>\n"
                f"   📦 {ord.title[:35]}\n"
                f"   👤 {ord.buyer_username} | <i>{status_label}</i>\n"
            )
        return await message.answer("\n".join(lines), parse_mode="HTML")

    # 2. Fallback to database if FunPay is unreachable
    async with async_session() as session:
        order_repo = OrderRepository(session)
        db_orders = await order_repo.get_recent_orders(limit=8)

    if not db_orders:
        return await message.answer("📋 История заказов пока пуста.")

    lines = ["📋 <b>Последние сохраненные заказы:</b>\n"]
    for ord in db_orders:
        status_icon = "✅" if ord.delivery_status in ("success", "delivered") else ("⏳" if ord.delivery_status == "out_of_stock" else "📦")
        lines.append(
            f"{status_icon} <code>#{ord.funpay_order_id}</code> | <b>{ord.price:,.2f} ₽</b>\n"
            f"   📦 {ord.lot_title[:35]}\n"
            f"   👤 {ord.buyer_username} | {ord.created_at.strftime('%d.%m %H:%M')}\n"
        )

    await message.answer("\n".join(lines), parse_mode="HTML")

@router.message(F.text == "📱 Web-Панель")
@router.message(Command("webapp"))
async def cmd_webapp(message: Message):
    if not await is_admin(message.from_user.id):
        return

    url = settings.WEBAPP_URL or f"http://localhost:{settings.WEBAPP_PORT}"
    text = (
        "📱 <b>Web-Дашборд FunPay Bot</b>\n\n"
        "Современная панель управления со складами, живыми графиками и настройками:\n"
        f"🔗 <b>Открыть в браузере:</b> <a href=\"{url}\">{url}</a>\n\n"
        "<i>Поддерживает мгновенное пополнение складов и мониторинг в реальном времени.</i>"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    if settings.WEBAPP_URL:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Открыть WebApp", web_app=WebAppInfo(url=settings.WEBAPP_URL))]
        ])
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Открыть в браузере", url=url)]
        ])
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

def _render_current_settings_kb():
    return get_settings_keyboard(
        auto_delivery=settings.ENABLE_AUTO_DELIVERY,
        auto_raise=settings.ENABLE_AUTO_RAISE,
        auto_response=settings.ENABLE_AUTO_RESPONSE,
        smart_pricing=settings.ENABLE_SMART_PRICING,
        ai_support=settings.ENABLE_AI_SUPPORT,
        upsell=settings.ENABLE_UPSELL,
        night_surge=settings.ENABLE_NIGHT_SURGE,
        review_booster=settings.ENABLE_REVIEW_BOOSTER,
    )

@router.message(F.text == "⚙️ Настройки")
@router.message(Command("settings"))
async def cmd_settings(message: Message):
    if not await is_admin(message.from_user.id):
        return
    await message.answer("⚙️ <b>Настройки автоматизации:</b>", parse_mode="HTML", reply_markup=_render_current_settings_kb())

@router.callback_query(F.data == "toggle_delivery")
async def cb_toggle_delivery(query: CallbackQuery):
    settings.ENABLE_AUTO_DELIVERY = not settings.ENABLE_AUTO_DELIVERY
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Автовыдача: {'Включена' if settings.ENABLE_AUTO_DELIVERY else 'Выключена'}")

@router.callback_query(F.data == "toggle_raise")
async def cb_toggle_raise(query: CallbackQuery):
    settings.ENABLE_AUTO_RAISE = not settings.ENABLE_AUTO_RAISE
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Автоподнятие: {'Включено' if settings.ENABLE_AUTO_RAISE else 'Выключено'}")

@router.callback_query(F.data == "toggle_response")
async def cb_toggle_response(query: CallbackQuery):
    settings.ENABLE_AUTO_RESPONSE = not settings.ENABLE_AUTO_RESPONSE
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"FAQ Ответы: {'Включены' if settings.ENABLE_AUTO_RESPONSE else 'Выключены'}")

@router.callback_query(F.data == "toggle_pricing")
async def cb_toggle_pricing(query: CallbackQuery):
    settings.ENABLE_SMART_PRICING = not settings.ENABLE_SMART_PRICING
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Смарт-цена: {'Включена' if settings.ENABLE_SMART_PRICING else 'Выключена'}")

@router.callback_query(F.data == "toggle_ai")
async def cb_toggle_ai(query: CallbackQuery):
    settings.ENABLE_AI_SUPPORT = not settings.ENABLE_AI_SUPPORT
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"AI-Консультант: {'Включен' if settings.ENABLE_AI_SUPPORT else 'Выключен'}")

@router.callback_query(F.data == "toggle_night")
async def cb_toggle_night(query: CallbackQuery):
    settings.ENABLE_NIGHT_SURGE = not settings.ENABLE_NIGHT_SURGE
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Ночной Surge: {'Включен' if settings.ENABLE_NIGHT_SURGE else 'Выключен'}")

@router.callback_query(F.data == "toggle_booster")
async def cb_toggle_booster(query: CallbackQuery):
    settings.ENABLE_REVIEW_BOOSTER = not settings.ENABLE_REVIEW_BOOSTER
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Буст 5★ отзывов: {'Включен' if settings.ENABLE_REVIEW_BOOSTER else 'Выключен'}")

@router.callback_query(F.data == "toggle_upsell")
async def cb_toggle_upsell(query: CallbackQuery):
    settings.ENABLE_UPSELL = not settings.ENABLE_UPSELL
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer(f"Допродажи (Upsell): {'Включены' if settings.ENABLE_UPSELL else 'Выключены'}")

@router.callback_query(F.data == "refresh_settings")
async def cb_refresh_settings(query: CallbackQuery):
    with contextlib.suppress(Exception):
        await query.message.edit_reply_markup(reply_markup=_render_current_settings_kb())
    await query.answer("Настройки обновлены")

@router.message(F.text == "🚀 Поднять лоты")
@router.message(Command("raise"))
async def cmd_raise_now(message: Message, funpay_client: FunPayClient):
    if not await is_admin(message.from_user.id):
        return

    msg = await message.answer("🚀 <i>Запуск процесса поднятия предложений по всем категориям...</i>", parse_mode="HTML")
    
    profile = funpay_client.profile or await funpay_client.check_auth()
    if not profile:
        return await msg.edit_text("❌ Ошибка авторизации FunPay.")

    user_lots = await funpay_client.get_user_lots(profile.user_id)
    categories = {}
    for l in user_lots:
        nid = l.get("node_id")
        cname = l.get("category_name", str(nid))
        if nid:
            categories[nid] = cname

    if not categories:
        return await msg.edit_text("❌ У вас не найдено активных лотов/категорий для поднятия.")

    results = []
    for nid, cname in categories.items():
        res = await funpay_client.raise_lots(node_id=nid, category_name=cname)
        results.append(res)
        await asyncio.sleep(1.5)

    lines = ["🚀 <b>Результаты автоподнятия лотов:</b>\n"]
    for r in results:
        icon = "✅" if r.success else ("⏳" if "подождите" in r.message.lower() else "❌")
        lines.append(f"{icon} <b>{r.category_name}:</b> {r.message}")

    await msg.edit_text("\n".join(lines), parse_mode="HTML")

@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    if not await is_admin(message.from_user.id):
        return

    help_text = (
        "ℹ️ <b>Команды и функции бота:</b>\n\n"
        "• <b>/stats</b> — Баланс FunPay и статистика выданных заказов\n"
        "• <b>/orders</b> — Список последних заказов\n"
        "• <b>/goods</b> — Остатки цифровых товаров на складе\n"
        "• <b>/addstock</b> — Добавить товар/ключи на склад\n"
        "• <b>/raise</b> — Принудительно поднять все предложения сейчас\n"
        "• <b>/reply [chat_id] [текст]</b> — Ответить покупателю в чат FunPay\n"
        "• <b>/settings</b> — Настройки модулей автовыдачи и поднятия\n"
    )
    await message.answer(help_text, parse_mode="HTML")
