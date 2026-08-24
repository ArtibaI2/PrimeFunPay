import random
from typing import List, Optional, Dict
from config.settings import settings
from utils.logger import logger
from database.engine import async_session
from database.repositories import LotRepository
from funpay.models import FunPayOrder

class UpsellService:
    def __init__(self):
        pass

    async def generate_upsell_message(self, order: FunPayOrder) -> Optional[str]:
        """Generates a contextual cross-sell message recommending another related product."""
        if not settings.ENABLE_UPSELL:
            return None

        async with async_session() as session:
            lot_repo = LotRepository(session)
            active_lots = await lot_repo.get_active_lots()

        # Find complementary lots (exclude the same lot that was purchased)
        complimentary = [l for l in active_lots if l.title.strip().lower() != order.title.strip().lower()]
        if not complimentary:
            return None

        # Pick matching or random relevant lot
        recommended = random.choice(complimentary)

        templates = [
            (
                f"💡 <b>Рекомендуем к этому товару:</b>\n"
                f"🔥 <i>«{recommended.title}»</i> всего за <b>{recommended.price:,.2f} ₽</b>\n"
                f"🔗 Посмотреть предложение: https://funpay.com/lots/offer?id={recommended.funpay_lot_id}"
            ),
            (
                f"🎁 <b>Специальное предложение для вас:</b>\n"
                f"⭐ <i>«{recommended.title}»</i> (от <b>{recommended.price:,.2f} ₽</b>)\n"
                f"🔗 Ссылка на лот: https://funpay.com/lots/offer?id={recommended.funpay_lot_id}"
            ),
        ]

        return random.choice(templates)
