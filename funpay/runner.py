import asyncio
from typing import Callable, List, Optional, Set
from config.settings import settings
from utils.logger import logger
from database.engine import async_session
from database.repositories import LotRepository, OrderRepository
from .client import FunPayClient
from .models import FunPayOrder, ChatMessage, UserProfile
from .services.auto_delivery import AutoDeliveryService
from .services.auto_raise import AutoRaiseService
from .services.auto_response import AutoResponseService
from .services.smart_pricing import SmartPricingService
from .services.night_surge import NightSurgeService
from .services.review_booster import ReviewBoosterService
from .services.session_monitor import SessionMonitorService

class FunPayRunner:
    def __init__(
        self,
        client: FunPayClient,
        on_order_callback: Optional[Callable] = None,
        on_message_callback: Optional[Callable] = None,
        on_raise_callback: Optional[Callable] = None,
        on_balance_callback: Optional[Callable] = None,
        on_session_expired_callback: Optional[Callable] = None,
        on_review_reward_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.on_order = on_order_callback
        self.on_message = on_message_callback
        self.on_raise = on_raise_callback
        self.on_balance = on_balance_callback
        self.on_session_expired = on_session_expired_callback
        self.on_review_reward = on_review_reward_callback

        self.auto_delivery = AutoDeliveryService(
            client=self.client,
            on_delivered_callback=self._handle_delivered_order,
        )
        self.auto_raise = AutoRaiseService(
            client=self.client,
            on_raise_callback=self.on_raise,
        )
        self.auto_response = AutoResponseService(
            client=self.client,
            on_response_sent_callback=self._handle_auto_response_sent,
        )
        self.smart_pricing = SmartPricingService(
            client=self.client,
        )
        self.night_surge = NightSurgeService()
        self.review_booster = ReviewBoosterService(
            client=self.client,
            on_reward_sent_callback=self.on_review_reward,
        )
        self.session_monitor = SessionMonitorService(
            client=self.client,
            on_session_expired_callback=self.on_session_expired,
        )

        self.is_running = False
        self.known_order_ids: Set[str] = set()
        self.last_balance: Optional[float] = None
        self._background_tasks: List[asyncio.Task] = []

    async def _handle_delivered_order(self, order: FunPayOrder, item_content: Optional[str]) -> None:
        """Callback triggered after successful auto-delivery."""
        if self.on_order:
            await self.on_order(order, item_content)

        # Schedule Review Booster 5-star invitation
        if order.chat_node_id:
            self.review_booster.schedule_review_reminder(
                order_id=order.order_id,
                chat_node_id=order.chat_node_id,
                buyer_username=order.buyer_username,
            )

    async def _schedule_review_reminder(self, chat_node_id: int, buyer_username: str, delay_seconds: int = 900) -> None:
        """Sends a polite review and confirmation reminder 15 minutes after delivery."""
        await asyncio.sleep(delay_seconds)
        reminder_text = (
            f"Здравствуйте, {buyer_username}!\n"
            f"Если всё прошло отлично и товар получен, пожалуйста, подтвердите заказ и оставьте отзыв ⭐\n"
            f"Спасибо, что выбрали нас!"
        )
        try:
            await self.client.send_chat_message(chat_node_id=chat_node_id, message=reminder_text)
            logger.info(f"Sent review reminder to {buyer_username} in chat {chat_node_id}.")
        except Exception as e:
            logger.error(f"Error sending review reminder: {e}")

    async def _handle_auto_response_sent(self, message: ChatMessage, response_text: str) -> None:
        """Notifies admin that an auto-response was triggered."""
        if self.on_message:
            await self.on_message(message)

    async def initialize(self) -> Optional[UserProfile]:
        """Validates credentials, syncs all account offers into DB, and auto-delivers pre-existing pending orders."""
        logger.info("Initializing FunPay synchronization...")
        profile = await self.client.check_auth()
        if not profile:
            logger.error("FunPay runner failed to start: authentication unsuccessful.")
            return None

        self.last_balance = profile.balance_rub

        # 1. Initialize default auto-response rules if empty
        await self.auto_response.init_defaults()

        # 2. Synchronize all active user offers/lots into database
        try:
            user_lots = await self.client.get_user_lots(profile.user_id)
            logger.info(f"Synchronizing {len(user_lots)} active FunPay offers into database...")
            
            async with async_session() as session:
                lot_repo = LotRepository(session)
                for lot_data in user_lots:
                    await lot_repo.get_or_create(
                        funpay_lot_id=lot_data["lot_id"],
                        title=lot_data["title"],
                        price=lot_data["price"],
                        category_name=lot_data.get("category_name"),
                    )
                    node_id = lot_data.get("node_id")
                    if node_id:
                        self.auto_raise.add_category(node_id, lot_data.get("category_name", str(node_id)))
            
            logger.info(f"✅ Synchronized {len(user_lots)} lots and {len(self.auto_raise.categories)} categories for auto-raise.")
        except Exception as e:
            logger.error(f"Error during lot synchronization: {e}")

        # 3. Synchronize all trade orders
        try:
            orders = await self.client.get_trade_orders()
            logger.info(f"Checking {len(orders)} recent trade orders for unfulfilled purchases...")

            async with async_session() as session:
                order_repo = OrderRepository(session)
                unfulfilled_orders = []

                for order in orders:
                    self.known_order_ids.add(order.order_id)
                    if order.is_paid:
                        is_processed = await order_repo.is_order_processed(order.order_id)
                        if not is_processed:
                            unfulfilled_orders.append(order)

            if unfulfilled_orders:
                logger.info(f"⚡ Found {len(unfulfilled_orders)} unfulfilled pre-existing orders! Processing auto-delivery...")
                for pending_order in unfulfilled_orders:
                    if settings.ENABLE_AUTO_DELIVERY:
                        await self.auto_delivery.process_order(pending_order)
                    elif self.on_order:
                        await self.on_order(pending_order, None)
            else:
                logger.info("All pre-existing trade orders are already processed or closed.")
        except Exception as e:
            logger.error(f"Error during order synchronization: {e}")

        return profile

    async def run_order_checker(self) -> None:
        """Continuously polls trade orders list for newly paid orders with auto-reconnect."""
        logger.info("Order checker task started.")
        while self.is_running:
            try:
                orders = await self.client.get_trade_orders()
                for order in orders:
                    if order.order_id not in self.known_order_ids:
                        self.known_order_ids.add(order.order_id)
                        if order.is_paid:
                            logger.info(f"⚡ New order detected: #{order.order_id} - '{order.title[:40]}' ({order.price} RUB)")
                            if settings.ENABLE_AUTO_DELIVERY:
                                await self.auto_delivery.process_order(order)
                            elif self.on_order:
                                await self.on_order(order, None)
                    else:
                        if order.is_paid:
                            async with async_session() as session:
                                order_repo = OrderRepository(session)
                                if not await order_repo.is_order_processed(order.order_id):
                                    if settings.ENABLE_AUTO_DELIVERY:
                                        await self.auto_delivery.process_order(order)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in order checker loop: {e}")
                await asyncio.sleep(5.0)

            await asyncio.sleep(settings.POLL_INTERVAL)

    async def run_balance_checker(self) -> None:
        """Periodically checks account balance and alerts on change."""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                profile = await self.client.check_auth()
                if profile and self.last_balance is not None:
                    if profile.balance_rub != self.last_balance:
                        old_b = self.last_balance
                        self.last_balance = profile.balance_rub
                        if self.on_balance:
                            await self.on_balance(old_b, profile.balance_rub)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error checking balance: {e}")

    async def start(self) -> None:
        """Starts the FunPay runner, services, and polling loops."""
        self.is_running = True
        logger.info("Starting FunPay Runner...")
        
        if settings.ENABLE_AUTO_RAISE:
            self.auto_raise.start()

        self.smart_pricing.start(categories_provider=lambda: self.auto_raise.categories)
        self.session_monitor.start()
        self._background_tasks.append(asyncio.create_task(self.run_balance_checker()))

        await self.run_order_checker()

    def stop(self) -> None:
        """Stops all running tasks in FunPay runner."""
        self.is_running = False
        self.auto_raise.stop()
        self.smart_pricing.stop()
        self.session_monitor.stop()
        for t in self._background_tasks:
            if not t.done():
                t.cancel()
        logger.info("FunPay Runner stopped.")
