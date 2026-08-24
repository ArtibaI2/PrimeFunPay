import asyncio
from typing import Dict, Set, Optional, Callable
from config.settings import settings
from utils.logger import logger
from funpay.client import FunPayClient

class ReviewBoosterService:
    """
    Automated review booster that politely asks for 5★ reviews
    and delivers bonus promo codes / cashback / gifts when buyers leave reviews.
    """

    def __init__(self, client: FunPayClient, on_reward_sent_callback: Optional[Callable] = None):
        self.client = client
        self.on_reward_sent = on_reward_sent_callback
        self.rewarded_orders: Set[str] = set()
        self.pending_review_tasks: Dict[str, asyncio.Task] = {}

    def schedule_review_reminder(self, order_id: str, chat_node_id: int, buyer_username: str, delay_seconds: Optional[int] = None) -> None:
        """Schedules a polite review invitation after order delivery."""
        if not settings.ENABLE_REVIEW_BOOSTER or not chat_node_id:
            return

        delay = delay_seconds or settings.REVIEW_BOOSTER_MIN_DELAY
        task = asyncio.create_task(self._reminder_worker(order_id, chat_node_id, buyer_username, delay))
        self.pending_review_tasks[order_id] = task

    async def _reminder_worker(self, order_id: str, chat_node_id: int, buyer_username: str, delay: int) -> None:
        try:
            await asyncio.sleep(delay)
            if order_id in self.rewarded_orders:
                return

            promo_hint = f"\n🎁 Оставьте 5★ отзыв и получите промокод на скидку: «{settings.REVIEW_BOOSTER_PROMO}» на следующий заказ!" if settings.REVIEW_BOOSTER_PROMO else ""

            msg = (
                f"Здравствуйте, {buyer_username}! ✨\n\n"
                f"Ваш заказ #{order_id} успешно доставлен. "
                f"Если всё прошло отлично, пожалуйста, подтвердите получение и поставьте 5★ отзыв ⭐{promo_hint}\n\n"
                f"Спасибо, что выбираете наш магазин!"
            )
            await self.client.send_chat_message(chat_node_id=chat_node_id, message=msg)
            logger.info(f"⭐ Review Booster reminder sent to {buyer_username} (Order #{order_id}).")
        except Exception as e:
            logger.warning(f"Error in review booster reminder: {e}")

    async def check_and_reward_review(self, order_id: str, chat_node_id: int, buyer_username: str) -> None:
        """Sends a bonus thank-you gift when a 5★ review is confirmed."""
        if order_id in self.rewarded_orders:
            return

        self.rewarded_orders.add(order_id)
        if not settings.ENABLE_REVIEW_BOOSTER:
            return

        promo = settings.REVIEW_BOOSTER_PROMO or "БОНУС10"
        reward_msg = (
            f"🎉 Большое спасибо за ваш отличный 5★ отзыв, {buyer_username}!\n\n"
            f"🎁 Ваш персональный промокод на скидку: «{promo}»\n"
            f"Будем рады видеть вас снова в нашем магазине! Удачных покупок! ⭐"
        )
        try:
            await self.client.send_chat_message(chat_node_id=chat_node_id, message=reward_msg)
            logger.info(f"🎁 Sent review reward to {buyer_username} for order #{order_id}.")
            if self.on_reward_sent:
                await self.on_reward_sent(buyer_username, order_id, promo)
        except Exception as e:
            logger.warning(f"Error sending review reward: {e}")
