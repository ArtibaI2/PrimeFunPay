import asyncio
import os
import sys

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from config.settings import settings
from utils.logger import setup_logger, logger
from database.engine import init_db
from funpay.client import FunPayClient
from funpay.runner import FunPayRunner
from tg_bot.bot import TelegramBotService

from webapp.server import WebAppServer

async def main():
    setup_logger(log_level=settings.LOG_LEVEL, log_dir=settings.LOG_DIR)
    logger.info("Starting FunPay Bot Application...")

    await init_db()

    funpay_client = FunPayClient(
        golden_key=settings.FUNPAY_GOLDEN_KEY,
        user_agent=settings.FUNPAY_USER_AGENT,
        proxy=settings.FUNPAY_PROXY,
    )

    tg_service = TelegramBotService(funpay_client=funpay_client)
    webapp_server = WebAppServer(
        funpay_client=funpay_client,
        host=settings.WEBAPP_HOST,
        port=settings.WEBAPP_PORT,
    )

    async def on_order_delivered(order, item):
        if tg_service.notifier:
            await tg_service.notifier.notify_new_order(order, item)

    async def on_order_out_of_stock(order):
        if tg_service.notifier:
            await tg_service.notifier.notify_out_of_stock(order)

    async def on_lots_raised(results):
        if tg_service.notifier:
            await tg_service.notifier.notify_raise_results(results)

    async def on_chat_message(msg):
        if tg_service.notifier:
            await tg_service.notifier.notify_new_chat_message(msg)

    async def on_balance_changed(old_b, new_b):
        if tg_service.notifier:
            await tg_service.notifier.notify_balance_change(old_b, new_b)

    runner = FunPayRunner(
        client=funpay_client,
        on_order_callback=on_order_delivered,
        on_raise_callback=on_lots_raised,
        on_message_callback=on_chat_message,
        on_balance_callback=on_balance_changed,
    )
    runner.auto_delivery.on_out_of_stock = on_order_out_of_stock

    if settings.FUNPAY_GOLDEN_KEY and settings.FUNPAY_GOLDEN_KEY != "your_golden_key_here":
        profile = await runner.initialize()
        if not profile:
            logger.warning("Continuing without active FunPay session (Please check FUNPAY_GOLDEN_KEY in .env).")
    else:
        logger.warning("FUNPAY_GOLDEN_KEY is not set. Fill in .env file to enable FunPay automation.")

    # Start WebApp Dashboard
    await webapp_server.start()

    # Start FunPay Runner if golden_key is configured
    if settings.FUNPAY_GOLDEN_KEY and settings.FUNPAY_GOLDEN_KEY != "your_golden_key_here":
        await runner.start()

    # Start Telegram Bot polling
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_BOT_TOKEN != "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz":
        asyncio.create_task(tg_service.start())
    else:
        logger.warning("TELEGRAM_BOT_TOKEN is not set. Telegram Bot polling skipped.")

    logger.info("✅ All FunPay Bot services are running 24/7.")

    # Keep application running indefinitely
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Received termination signal. Shutting down gracefully...")
    finally:
        runner.stop()
        await tg_service.stop()
        await webapp_server.stop()
        await funpay_client.close()
        logger.info("FunPay Bot has been stopped.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
