import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from database.models import Base
from database.repositories import (
    GoodsRepository,
    LotRepository,
    OrderRepository,
    AutoResponseRepository,
)
from funpay.parser import FunPayParser
from tg_bot.keyboards.admin_kb import get_main_menu_keyboard, get_settings_keyboard

@pytest_asyncio.fixture
async def db_session():
    test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_sessionmaker = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with test_sessionmaker() as session:
        yield session

    await test_engine.dispose()

@pytest.mark.asyncio
async def test_database_and_repositories(db_session: AsyncSession):
    goods_repo = GoodsRepository(db_session)
    lot_repo = LotRepository(db_session)
    order_repo = OrderRepository(db_session)
    auto_resp_repo = AutoResponseRepository(db_session)

    lot = await lot_repo.get_or_create(
        funpay_lot_id=1234567,
        title="Steam Gift Card 1000 RUB",
        price=1100.0,
        category_name="Steam Keys",
    )
    assert lot.funpay_lot_id == 1234567
    assert lot.is_active is True

    keys = ["STEAM-KEY-1111", "STEAM-KEY-2222", "STEAM-KEY-3333"]
    added = await goods_repo.add_stock_items(keys, lot_id=lot.id)
    assert added == 3

    count = await goods_repo.get_available_count(lot_id=lot.id)
    assert count == 3

    popped = await goods_repo.pop_available_item(lot_id=lot.id, order_id="ORDER_TEST_01")
    assert popped == "STEAM-KEY-1111"

    count_after = await goods_repo.get_available_count(lot_id=lot.id)
    assert count_after == 2

    order = await order_repo.record_order(
        funpay_order_id="ORDER_TEST_01",
        buyer_username="GamerBoy2026",
        lot_title=lot.title,
        price=lot.price,
        lot_id=lot.id,
    )
    assert order.funpay_order_id == "ORDER_TEST_01"
    assert await order_repo.is_order_processed("ORDER_TEST_01") is False

    await order_repo.mark_delivered("ORDER_TEST_01", popped)
    assert await order_repo.is_order_processed("ORDER_TEST_01") is True

    # Period analytics test
    period_stats = await order_repo.get_period_stats(days=7)
    assert period_stats["total_orders"] == 1
    assert period_stats["delivered_orders"] == 1
    assert period_stats["total_revenue"] == 1100.0
    assert period_stats["avg_check"] == 1100.0

    top_prods = await order_repo.get_top_products(limit=5)
    assert len(top_prods) == 1
    assert top_prods[0]["title"] == "Steam Gift Card 1000 RUB"

    await auto_resp_repo.add_rule("гарантия", "Гарантия на все товары составляет 24 часа с момента покупки.")
    matched = await auto_resp_repo.find_matching_response("Здравствуйте, а какая у вас гарантия?")
    assert matched is not None
    assert "24 часа" in matched

def test_funpay_parser_profile():
    sample_html_funpay_symbol = """
    <div class="user-link-dropdown">
        <a class="user-link" href="https://funpay.com/users/987654/">SuperSellerПрофиль</a>
        <span class="badge-balance">614 ¤</span>
        <span class="badge-orders">2</span>
        <span class="badge-chat">1</span>
    </div>
    """
    profile_symbol = FunPayParser.parse_user_profile(sample_html_funpay_symbol)
    assert profile_symbol is not None
    assert profile_symbol.balance_rub == 614.0

    sample_balance_page = """
    <h1 class="page-header balances-header page-header-no-hr">
        Финансы
        <span class="balances-list">
            <span class="balances-delimiter">·</span>
            <span class="balances-value">533.70 ¤</span>
            <span class="balances-delimiter">·</span>
            <span class="balances-value">0 $</span>
            <span class="balances-delimiter">·</span>
            <span class="balances-value">0.80 €</span>
        </span>
    </h1>
    """
    rub, usd, eur = FunPayParser.parse_account_balances(sample_balance_page)
    assert rub == 533.70
    assert usd == 0.0
    assert eur == 0.80

def test_funpay_parser_orders():
    sample_orders_html = """
    <div class="tc-order-item">
        <div class="tc-order">#A1B2C3D4</div>
        <div class="order-desc">Telegram Premium 3 Months</div>
        <div class="tc-user media-user-name">BuyerIvan</div>
        <div class="tc-price">450.00 ₽</div>
        <div class="tc-status">Оплачен</div>
    </div>
    """
    orders = FunPayParser.parse_trade_orders(sample_orders_html)
    assert len(orders) == 1
    assert orders[0].order_id == "A1B2C3D4"
    assert orders[0].buyer_username == "BuyerIvan"
    assert orders[0].price == 450.00
    assert orders[0].is_paid is True

def test_telegram_keyboards():
    main_kb = get_main_menu_keyboard()
    assert len(main_kb.keyboard) > 0

    settings_kb = get_settings_keyboard(True, False, True, True, True, True, True)
    assert len(settings_kb.inline_keyboard) == 5

@pytest.mark.asyncio
async def test_ai_support_service():
    from funpay.services.ai_support import AISupportService
    ai_service = AISupportService()
    
    assert ai_service.detect_language("Hello how to activate my key?") == "en"
    assert ai_service.detect_language("Здравствуйте, как активировать?") == "ru"

    resp_ru = await ai_service.generate_ai_response("Здравствуйте, как активировать товар?")
    assert resp_ru is not None
    assert "активации" in resp_ru.lower() or "инструкция" in resp_ru.lower()

    resp_en = await ai_service.generate_ai_response("How to activate my product?")
    assert resp_en is not None
    assert "instruction" in resp_en.lower() or "order" in resp_en.lower()

def test_night_surge_service():
    from funpay.services.night_surge import NightSurgeService
    from config.settings import settings
    
    surge = NightSurgeService(surge_percent=15.0)
    settings.ENABLE_NIGHT_SURGE = True
    
    # 02:00 is night
    assert surge.is_night_time(2) is True
    # 14:00 is day
    assert surge.is_night_time(14) is False

    base_price = 100.0
    surged = surge.calculate_surge_price(base_price)
    assert surged >= 100.0

def test_auto_stock_validator():
    from funpay.services.auto_stock import AutoStockService
    stock_service = AutoStockService()

    raw_lines = [
        "KEY-AAAA-BBBB-CCCC",
        "  KEY-AAAA-BBBB-CCCC  ",  # duplicate
        "KEY-DDDD-EEEE-FFFF",
        "ab",  # too short / invalid
        "",    # empty
    ]

    valid, invalid = stock_service.clean_and_validate_items(raw_lines)
    assert len(valid) == 2
    assert "KEY-AAAA-BBBB-CCCC" in valid
    assert "KEY-DDDD-EEEE-FFFF" in valid
    assert "ab" in invalid

def test_product_template_parser():
    from utils.product_parser import parse_product_template, format_product_card
    raw = """
    Название: Steam Gift Card 1000 RUB
    Описание: Автоматическая доставка ключа 24/7
    Сообщение после покупки: Спасибо за покупку! Ваш ключ: {key}
    Цена: 1100 руб
    """
    parsed = parse_product_template(raw)
    assert parsed["title"] == "Steam Gift Card 1000 RUB"
    assert "Автоматическая доставка" in parsed["description"]
    assert "Спасибо за покупку!" in parsed["delivery_template"]
    assert parsed["price"] == 1100.0

    card = format_product_card(
        title=parsed["title"],
        description=parsed["description"],
        delivery_template=parsed["delivery_template"],
        price=parsed["price"],
        storage_type="Workupload / Google Drive",
    )
    assert "Steam Gift Card 1000 RUB" in card
    assert "1,100.00" in card

def test_market_analytics_report_formatting():
    from funpay.services.market_analytics import MarketAnalyticsService
    
    mock_service = MarketAnalyticsService(client=None)
    sample_report = {
        "categories": [
            {
                "category_name": "Discord Nitro",
                "min_price": 176.0,
                "avg_price": 1120.0,
                "recommended_price": 172.48,
                "total_offers": 150,
                "demand_level": "🔥 ВЫСОКИЙ",
                "top_keywords": ["Full 3 Month", "Gift", "Boost"],
                "autodelivery_percent": 85,
            }
        ],
        "recommendations": [
            "Самый высокий спрос зафиксирован в категории «Discord Nitro»."
        ]
    }
    text = mock_service.format_telegram_report(sample_report)
    assert "АНАЛИЗ РЫНКА FUNPAY ЗА 24 ЧАСА" in text
    assert "Discord Nitro" in text
    assert "176.00" in text
    assert "🔥 ВЫСОКИЙ" in text


