import asyncio
from typing import Optional
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config.settings import settings
from utils.logger import logger
from funpay.client import FunPayClient
from .handlers import register_all_handlers
from .notifier import TelegramNotifier

class TelegramBotService:
    def __init__(self, funpay_client: FunPayClient):
        self.funpay_client = funpay_client
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.notifier: Optional[TelegramNotifier] = None
        self.is_running = False

        if settings.TELEGRAM_BOT_TOKEN:
            self.bot = Bot(
                token=settings.TELEGRAM_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
            self.dp = Dispatcher()
            self.dp["funpay_client"] = self.funpay_client
            register_all_handlers(self.dp)
            self.notifier = TelegramNotifier(self.bot)
            logger.info("Telegram Bot service initialized.")
        else:
            self.notifier = TelegramNotifier(None)
            logger.warning("TELEGRAM_BOT_TOKEN is not configured. Telegram management is disabled.")

    async def start(self) -> None:
        """Starts Telegram bot polling with auto-reconnection if token is configured."""
        if not self.bot or not self.dp:
            return

        self.is_running = True
        logger.info("Starting Telegram Bot polling...")
        
        while self.is_running:
            try:
                await self.bot.delete_webhook(drop_pending_updates=True)
                await self.dp.start_polling(self.bot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Telegram polling exception: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5.0)

    async def stop(self) -> None:
        """Stops the Telegram bot."""
        self.is_running = False
        if self.bot:
            try:
                await self.bot.session.close()
            except Exception:
                pass
            logger.info("Telegram Bot stopped.")
