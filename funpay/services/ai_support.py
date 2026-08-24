import re
import aiohttp
from typing import Optional, Dict, Tuple
from config.settings import settings
from utils.logger import logger
from funpay.models import ChatMessage

SYSTEM_PROMPT = """Ты — вежливый и профессиональный AI-консультант продавца на торговой площадке FunPay.
Твоя задача — помогать покупателям с вопросами по цифровым товарам (игры, Discord Nitro, ключи, конфиги, гайды, бусты FPS).

ПРАВИЛА И ОГРАНИЧЕНИЯ:
1. Отвечай кратко, доброжелательно и по делу (1-3 предложения).
2. Никогда не передавай и не запрашивай личные контакты (Telegram, Discord, VK, номер телефона, ссылки на внешние сайты) — это строго запрещено правилами FunPay.
3. Если покупатель сообщает об ошибке товара, вежливо попроси прислать скриншот ошибки прямо в чат FunPay и уточни, что продавец всё проверит и поможет.
4. Если покупатель спрашивает, как активировать товар, объясни стандартный шаг или скажи, что подробная инструкция отправлена в сообщении о покупке.
5. Отвечай на том же языке, на котором пишет покупатель (русский, английский и др.)."""

class AISupportService:
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.AI_API_KEY
        self.model = model or settings.AI_MODEL
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=20))
        return self.session

    async def close(self) -> None:
        if self.session and not self.session.closed:
            await self.session.close()

    def detect_language(self, text: str) -> str:
        """Simple language detector (ru, en, or other)."""
        cyrillic = len(re.findall(r"[\u0400-\u04FF]", text))
        latin = len(re.findall(r"[a-zA-Z]", text))
        if cyrillic > latin:
            return "ru"
        elif latin > 0:
            return "en"
        return "ru"

    async def generate_ai_response(self, user_message: str, chat_history: Optional[str] = None) -> Optional[str]:
        """Generates an intelligent response using configured AI API or smart heuristic fallback."""
        if not settings.ENABLE_AI_SUPPORT:
            return None

        # 1. If API Key is present, call OpenAI-compatible API
        if self.api_key:
            try:
                session = await self._get_session()
                headers = {
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                }
                messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                if chat_history:
                    messages.append({"role": "system", "content": f"Контекст диалога:\n{chat_history}"})
                messages.append({"role": "user", "content": user_message})

                payload = {
                    "model": self.model,
                    "messages": messages,
                    "max_tokens": 250,
                    "temperature": 0.6,
                }
                async with session.post("https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        reply = data["choices"][0]["message"]["content"].strip()
                        return reply
                    else:
                        logger.warning(f"AI API request failed with status {resp.status}")
            except Exception as e:
                logger.error(f"Error querying AI API: {e}")

        # 2. Smart Heuristic NLP Fallback (Works offline without API key)
        return self._heuristic_nlp_response(user_message)

    def _heuristic_nlp_response(self, text: str) -> Optional[str]:
        """Smart contextual heuristic response generator."""
        clean = text.lower().strip()
        lang = self.detect_language(clean)

        if lang == "en":
            if any(w in clean for w in ("how to", "activate", "instruction", "guide", "setup")):
                return "Hello! The activation instructions are provided in your order delivery message. If you encounter any difficulties, please let us know!"
            if any(w in clean for w in ("not working", "broken", "invalid", "error", "wrong")):
                return "Hello! Please send a screenshot of the issue here in the chat, and we will check and replace it if needed."
            if any(w in clean for w in ("thank", "thx", "good", "great")):
                return "You're very welcome! Enjoy your purchase and have a great day! A review would be greatly appreciated ⭐"
            if any(w in clean for w in ("hello", "hi", "hey")):
                return "Hello! Thank you for contacting us. How can we help you with your order?"

        # Russian
        if any(w in clean for w in ("как активировать", "активация", "инструкция", "где ключ", "куда вводить")):
            return "Здравствуйте! Подробная пошаговая инструкция по активации отправлена вам в сообщении с товаром. Если что-то не получается, опишите шаг, мы подскажем!"
        if any(w in clean for w in ("не работает", "неверный", "ошибка", "вылетает", "бан", "не заходит", "сломано")):
            return "Здравствуйте! Пришлите, пожалуйста, скриншот возникающей ошибки прямо сюда в чат. Мы оперативно всё проверим и поможем решить вопрос!"
        if any(w in clean for w in ("спасибо", "спс", "благодарю", "от души", "все супер", "топ")):
            return "Пожалуйста! Приятного использования и отличного настроения! Будем очень признательны за положительный отзыв ⭐"
        if any(w in clean for w in ("привет", "здравствуйте", "добрый день", "ку", "хай", "добрый вечер")):
            return "Здравствуйте! Чем можем вам помочь по вашему заказу?"

        return None
