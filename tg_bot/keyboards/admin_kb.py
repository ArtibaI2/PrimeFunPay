from typing import List, Optional
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from config.settings import settings

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Returns the persistent main menu keyboard for admins."""
    webapp_btn = None
    if settings.WEBAPP_URL:
        webapp_btn = KeyboardButton(text="📱 Web-Панель", web_app=WebAppInfo(url=settings.WEBAPP_URL))
    else:
        webapp_btn = KeyboardButton(text="📱 Web-Панель")

    kb = [
        [
            KeyboardButton(text="📊 Статистика"),
            KeyboardButton(text="🔥 Анализ рынка (24ч)"),
        ],
        [
            KeyboardButton(text="📦 Склад товаров"),
            KeyboardButton(text="📋 Последние заказы"),
        ],
        [
            KeyboardButton(text="💬 Чат-центр"),
            KeyboardButton(text="🤖 Автоответчик"),
        ],
        [
            KeyboardButton(text="🚀 Поднять лоты"),
            KeyboardButton(text="👤 Мой FunPay аккаунт"),
        ],
        [
            webapp_btn,
            KeyboardButton(text="⚙️ Настройки"),
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_onboarding_keyboard() -> InlineKeyboardMarkup:
    """Returns onboarding keyboard for new users."""
    inline_kb = [
        [
            InlineKeyboardButton(text="🔑 Привязать FunPay аккаунт", callback_data="auth_link_account"),
        ],
        [
            InlineKeyboardButton(text="ℹ️ Как получить golden_key?", callback_data="auth_how_to_key"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_account_profile_keyboard() -> InlineKeyboardMarkup:
    """Returns management keyboard for user's linked FunPay account."""
    inline_kb = [
        [
            InlineKeyboardButton(text="🔄 Обновить статус", callback_data="auth_refresh_profile"),
            InlineKeyboardButton(text="🔑 Сменить golden_key", callback_data="auth_link_account"),
        ],
        [
            InlineKeyboardButton(text="🌐 Настроить прокси", callback_data="auth_set_proxy"),
            InlineKeyboardButton(text="🚪 Отвязать аккаунт", callback_data="auth_unlink_account"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_market_keyboard() -> InlineKeyboardMarkup:
    """Returns management buttons for market analytics."""
    inline_kb = [
        [
            InlineKeyboardButton(text="🔄 Обновить анализ", callback_data="market_refresh"),
            InlineKeyboardButton(text="➕ Создать товар по тренду", callback_data="product_create"),
        ],
        [
            InlineKeyboardButton(text="📊 Топ продаваемых у вас", callback_data="stats_top"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_stats_keyboard(active_period: str = "today") -> InlineKeyboardMarkup:
    """Returns period selector buttons for statistics."""
    periods = [
        ("today", "📅 За сегодня"),
        ("week", "🗓 7 дней"),
        ("month", "📆 30 дней"),
        ("all", "📈 За всё время"),
    ]
    buttons = []
    for code, label in periods:
        prefix = "• " if code == active_period else ""
        buttons.append(InlineKeyboardButton(text=f"{prefix}{label}", callback_data=f"stats_period:{code}"))
    
    inline_kb = [
        [buttons[0], buttons[1]],
        [buttons[2], buttons[3]],
        [InlineKeyboardButton(text="🏆 Топ продаваемых товаров", callback_data="stats_top")],
        [InlineKeyboardButton(text="🔄 Обновить", callback_data=f"stats_period:{active_period}")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_settings_keyboard(
    auto_delivery: bool,
    auto_raise: bool,
    auto_response: bool,
    smart_pricing: bool = False,
    ai_support: bool = True,
    upsell: bool = True,
    night_surge: bool = True,
    review_booster: bool = True,
) -> InlineKeyboardMarkup:
    """Returns inline toggles for bot settings."""
    delivery_status = "✅ Вкл" if auto_delivery else "❌ Выкл"
    raise_status = "✅ Вкл" if auto_raise else "❌ Выкл"
    response_status = "✅ Вкл" if auto_response else "❌ Выкл"
    pricing_status = "✅ Вкл" if smart_pricing else "❌ Выкл"
    ai_status = "✅ Вкл" if ai_support else "❌ Выкл"
    upsell_status = "✅ Вкл" if upsell else "❌ Выкл"
    surge_status = "✅ Вкл" if night_surge else "❌ Выкл"
    booster_status = "✅ Вкл" if review_booster else "❌ Выкл"

    inline_kb = [
        [
            InlineKeyboardButton(text=f"⚡ Автовыдача: {delivery_status}", callback_data="toggle_delivery"),
            InlineKeyboardButton(text=f"🚀 Автоподнятие: {raise_status}", callback_data="toggle_raise"),
        ],
        [
            InlineKeyboardButton(text=f"🤖 FAQ Ответы: {response_status}", callback_data="toggle_response"),
            InlineKeyboardButton(text=f"🧠 AI-Саппорт: {ai_status}", callback_data="toggle_ai"),
        ],
        [
            InlineKeyboardButton(text=f"🎯 Смарт-цена: {pricing_status}", callback_data="toggle_pricing"),
            InlineKeyboardButton(text=f"🌙 Ночь Surge: {surge_status}", callback_data="toggle_night"),
        ],
        [
            InlineKeyboardButton(text=f"⭐ Буст 5★ отзывов: {booster_status}", callback_data="toggle_booster"),
            InlineKeyboardButton(text=f"🎁 Допродажи: {upsell_status}", callback_data="toggle_upsell"),
        ],
        [
            InlineKeyboardButton(text="🔄 Обновить статус", callback_data="refresh_settings"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_lot_stock_keyboard(lot_id: int) -> InlineKeyboardMarkup:
    """Returns management buttons for a specific lot's stock."""
    inline_kb = [
        [
            InlineKeyboardButton(text="➕ Пополнить склад", callback_data=f"stock_add:{lot_id}"),
            InlineKeyboardButton(text="📝 Шаблон выдачи", callback_data=f"stock_template:{lot_id}"),
        ],
        [
            InlineKeyboardButton(text="👁 Посмотреть остаток", callback_data=f"stock_view:{lot_id}"),
            InlineKeyboardButton(text="🗑 Очистить остаток", callback_data=f"stock_clear:{lot_id}"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад к списку товаров", callback_data="stock_list"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_goods_list_keyboard(lots_data: List[dict]) -> InlineKeyboardMarkup:
    """Returns a list of lots as inline buttons with an Add Product button."""
    inline_kb = [
        [InlineKeyboardButton(text="➕ Создать / Залить товар", callback_data="product_create")],
    ]
    for item in lots_data[:12]:
        stock_count = item.get("stock_count", 0)
        indicator = "🟢" if stock_count > 0 else "🔴"
        title = item.get("title", "Товар")[:28]
        inline_kb.append([
            InlineKeyboardButton(
                text=f"{indicator} {title} ({stock_count} шт.)",
                callback_data=f"stock_select:{item['id']}",
            )
        ])
    inline_kb.append([
        InlineKeyboardButton(text="🔄 Обновить склад", callback_data="stock_list"),
        InlineKeyboardButton(text="📋 Заполнить шаблоном", callback_data="product_paste_template"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_product_builder_keyboard(has_data: bool = False) -> InlineKeyboardMarkup:
    """Returns the interactive product builder keyboard."""
    inline_kb = [
        [
            InlineKeyboardButton(text="✏️ Название", callback_data="prod_edit_title"),
            InlineKeyboardButton(text="📄 Описание", callback_data="prod_edit_desc"),
        ],
        [
            InlineKeyboardButton(text="💬 Выдача после покупки", callback_data="prod_edit_delivery"),
            InlineKeyboardButton(text="💰 Цена", callback_data="prod_edit_price"),
        ],
        [
            InlineKeyboardButton(text="🌐 Куда залить / Ссылка", callback_data="prod_choose_storage"),
            InlineKeyboardButton(text="📎 Отправить файл", callback_data="prod_upload_file"),
        ],
        [
            InlineKeyboardButton(text="📋 Заполнить всё сообщением", callback_data="product_paste_template"),
        ],
        [
            InlineKeyboardButton(text="✅ Сохранить и выставить", callback_data="prod_save_lot"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="stock_list"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_storage_choice_keyboard() -> InlineKeyboardMarkup:
    """Returns cloud file storage choices."""
    inline_kb = [
        [
            InlineKeyboardButton(text="🚀 Workupload", callback_data="storage_set:workupload"),
            InlineKeyboardButton(text="🐱 Catbox.moe (Быстрое)", callback_data="storage_set:catbox"),
        ],
        [
            InlineKeyboardButton(text="📁 Gofile.io", callback_data="storage_set:gofile"),
            InlineKeyboardButton(text="🌐 Google Диск (Ссылка)", callback_data="storage_set:gdrive"),
        ],
        [
            InlineKeyboardButton(text="☁️ Своя ссылка (Mega, Яндекс и др.)", callback_data="storage_set:custom"),
            InlineKeyboardButton(text="🔑 Текстовые ключи (в боте)", callback_data="storage_set:keys"),
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад к карточке товара", callback_data="prod_show_card"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_auto_response_keyboard(rules: List[dict]) -> InlineKeyboardMarkup:
    """Returns management buttons for FAQ auto-response rules."""
    inline_kb = []
    for r in rules[:8]:
        status_icon = "🟢" if r.get("is_active", True) else "⚪️"
        kw = r.get("keyword", "")[:20]
        inline_kb.append([
            InlineKeyboardButton(
                text=f"{status_icon} «{kw}»",
                callback_data=f"ar_rule:{r['id']}",
            ),
            InlineKeyboardButton(
                text="❌ Удалить",
                callback_data=f"ar_del:{r['id']}",
            ),
        ])
    inline_kb.append([
        InlineKeyboardButton(text="➕ Добавить новое правило", callback_data="ar_add"),
        InlineKeyboardButton(text="🔄 Обновить", callback_data="ar_list"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)

def get_order_action_keyboard(chat_node_id: int, order_id: str) -> InlineKeyboardMarkup:
    """Returns inline action buttons for an order notification."""
    inline_kb = [
        [
            InlineKeyboardButton(
                text="💬 Ответить покупателю",
                callback_data=f"reply_chat:{chat_node_id}",
            ),
            InlineKeyboardButton(
                text="🔗 Открыть на FunPay",
                url=f"https://funpay.com/orders/{order_id.replace('#', '')}/",
            ),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=inline_kb)
