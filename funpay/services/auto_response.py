from typing import Optional, Callable
from config.settings import settings
from utils.logger import logger
from database.engine import async_session
from database.repositories import AutoResponseRepository
from funpay.client import FunPayClient
from funpay.models import ChatMessage
from funpay.services.ai_support import AISupportService

class AutoResponseService:
    def __init__(
        self,
        client: FunPayClient,
        on_response_sent_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.on_response_sent = on_response_sent_callback
        self.replied_message_ids = set()
        self.ai_support = AISupportService()

    async def init_defaults(self) -> None:
        """Seeds default FAQ rules if the database is empty."""
        async with async_session() as session:
            repo = AutoResponseRepository(session)
            rules = await repo.get_all_rules()
            if not rules:
                defaults = [
                    ("активация", "Здравствуйте! Инструкция по активации товара отправлена вам в сообщении выше. Если возникли вопросы, напишите подробнее!"),
                    ("не работает", "Здравствуйте! Опишите, пожалуйста, какая именно ошибка возникает (желательно со скриншотом), и мы оперативно решим проблему!"),
                    ("замена", "Здравствуйте! Отправьте, пожалуйста, скриншот проблемы, мы всё проверим и при необходимости выполним замену."),
                    ("спасибо", "Пожалуйста! Приятного использования! Будем очень благодарны за положительный отзыв ⭐"),
                    ("где товар", "Здравствуйте! Товар выдается автоматически сразу после оплаты в этом диалоге. Пожалуйста, проверьте сообщения выше!"),
                ]
                for kw, ans in defaults:
                    await repo.add_rule(keyword=kw, response_text=ans)
                logger.info(f"Initialized {len(defaults)} default auto-response rules.")

    async def handle_message(self, message: ChatMessage) -> bool:
        """Evaluates incoming buyer message and sends an automated response (FAQ or AI)."""
        if not settings.ENABLE_AUTO_RESPONSE and not settings.ENABLE_AI_SUPPORT:
            return False

        # Ignore own messages or system notices
        if message.is_my_message or message.is_system:
            return False

        if message.message_id in self.replied_message_ids:
            return False

        self.replied_message_ids.add(message.message_id)

        matched_text = None

        # 1. Check static database FAQ rules
        if settings.ENABLE_AUTO_RESPONSE:
            async with async_session() as session:
                repo = AutoResponseRepository(session)
                matched_text = await repo.find_matching_response(message.text)

        # 2. If no FAQ rule matched, check AI Support
        if not matched_text and settings.ENABLE_AI_SUPPORT:
            matched_text = await self.ai_support.generate_ai_response(message.text)

        # 3. Fallback greeting
        if not matched_text and message.text.strip().lower() in ("привет", "здравствуйте", "ку", "hello", "hi"):
            matched_text = settings.AUTO_RESPONSE_GREETING

        if matched_text:
            logger.info(f"Auto-responding to {message.sender_username} in chat {message.chat_node_id}...")
            sent = await self.client.send_chat_message(
                chat_node_id=message.chat_node_id,
                message=matched_text,
                last_message_id=message.message_id,
            )
            if sent and self.on_response_sent:
                await self.on_response_sent(message, matched_text)
            return sent

        return False
