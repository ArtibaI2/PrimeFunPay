import asyncio
from pathlib import Path
from typing import Optional, Callable
from config.settings import settings
from utils.logger import logger
from database.engine import async_session
from database.repositories import GoodsRepository, LotRepository, OrderRepository
from funpay.client import FunPayClient
from funpay.models import FunPayOrder

from funpay.services.upsell import UpsellService
from funpay.services.auto_stock import AutoStockService

class AutoDeliveryService:
    def __init__(
        self,
        client: FunPayClient,
        on_delivered_callback: Optional[Callable] = None,
        on_out_of_stock_callback: Optional[Callable] = None,
    ):
        self.client = client
        self.on_delivered = on_delivered_callback
        self.on_out_of_stock = on_out_of_stock_callback
        self.upsell = UpsellService()
        self.auto_stock = AutoStockService()

    async def process_order(self, order_summary: FunPayOrder) -> bool:
        """Processes a single order: fetches details, checks stock, and sends delivery message."""
        order_id = order_summary.order_id

        async with async_session() as session:
            order_repo = OrderRepository(session)
            goods_repo = GoodsRepository(session)
            lot_repo = LotRepository(session)

            # Check if already processed
            if await order_repo.is_order_processed(order_id):
                logger.debug(f"Order #{order_id} was already processed. Skipping.")
                return True

            logger.info(f"Processing new order #{order_id} for '{order_summary.title}' from {order_summary.buyer_username}...")

            # Get complete order details (including chat_node_id)
            details = await self.client.get_order_details(order_id)
            if not details or not details.chat_node_id:
                logger.error(f"Could not load chat details for order #{order_id}")
                return False

            # Merge summary metadata if not parsed from order page
            if not details.title:
                details.title = order_summary.title
            if not details.buyer_username or details.buyer_username == "Unknown":
                details.buyer_username = order_summary.buyer_username
            if details.price == 0.0:
                details.price = order_summary.price

            # Record order in database
            await order_repo.record_order(
                funpay_order_id=order_id,
                buyer_username=details.buyer_username,
                buyer_id=details.buyer_id,
                lot_title=details.title,
                price=details.price,
                status=details.status,
            )

            # Try to find lot template if configured
            lot = None
            if details.lot_id:
                lot = await lot_repo.get_by_funpay_id(details.lot_id)

            # Try to get stock item from DB
            item_content = await goods_repo.pop_available_item(
                lot_id=lot.id if lot else None,
                category_identifier=details.title,
                order_id=order_id,
            )

            # If not in DB, fallback to stock file in storage/goods/<safe_title>.txt
            if not item_content:
                item_content = self._pop_item_from_file(details.title)

            # If still not in local stock, check if dynamic auto-stock provider is available
            if not item_content:
                item_content = await self.auto_stock.fetch_item_from_provider(details.title)

            # Fallback: if lot has a configured cloud upload URL (Workupload/Google Drive/Catbox), use it
            if not item_content and lot and lot.upload_url:
                item_content = lot.upload_url

            if item_content:
                # Prepare delivery text
                template = lot.delivery_template if (lot and lot.delivery_template) else (
                    f"Здравствуйте, {details.buyer_username}!\n"
                    f"Ваш товар:\n{item_content}\n\n"
                    f"{settings.AUTO_RESPONSE_AFTER_PURCHASE}"
                )
                
                link_val = (lot.upload_url if lot and lot.upload_url else item_content)
                delivery_message = (
                    template.replace("{item}", item_content)
                    .replace("{key}", item_content)
                    .replace("{link}", link_val)
                    .replace("{title}", details.title)
                    .replace("{username}", details.buyer_username)
                )

                # Send message to FunPay order chat
                sent = await self.client.send_chat_message(
                    chat_node_id=details.chat_node_id,
                    message=delivery_message,
                )

                if sent:
                    await order_repo.mark_delivered(order_id, item_content)
                    logger.info(f"✅ Order #{order_id} successfully delivered to {details.buyer_username}!")

                    # Optional Upsell cross-selling recommendation
                    if settings.ENABLE_UPSELL:
                        try:
                            upsell_msg = await self.upsell.generate_upsell_message(details)
                            if upsell_msg:
                                await asyncio.sleep(2.0)
                                await self.client.send_chat_message(chat_node_id=details.chat_node_id, message=upsell_msg)
                        except Exception as e:
                            logger.error(f"Error sending upsell message: {e}")

                    if self.on_delivered:
                        await self.on_delivered(details, item_content)
                    return True
                else:
                    logger.error(f"Failed to send delivery message for order #{order_id}")
                    return False
            else:
                logger.warning(f"⚠️ OUT OF STOCK for order #{order_id} ('{details.title}')!")
                
                # Send out of stock notice to buyer
                out_of_stock_msg = (
                    f"Здравствуйте, {details.buyer_username}!\n"
                    f"Ваш заказ #{order_id} принят в обработку. Товар временно закончился на автовыдаче. "
                    f"Продавец свяжется с вами и выдаст товар в ближайшее время!"
                )
                await self.client.send_chat_message(
                    chat_node_id=details.chat_node_id,
                    message=out_of_stock_msg,
                )

                # Mark status in DB so we don't repeat notifications
                order_rec = await order_repo.get_by_order_id(order_id)
                if order_rec:
                    order_rec.delivery_status = "out_of_stock"
                    await session.commit()

                if self.on_out_of_stock:
                    await self.on_out_of_stock(details)
                return False

    def _pop_item_from_file(self, title: str) -> Optional[str]:
        """Helper to read and remove the top line from a goods stock file."""
        goods_dir = Path(settings.GOODS_DIR)
        goods_dir.mkdir(parents=True, exist_ok=True)
        
        # Search for exact file or general file
        files = list(goods_dir.glob("*.txt"))
        if not files:
            return None

        # Check for matching filename or take default stock.txt
        target_file = None
        for f in files:
            if f.stem.lower() in title.lower() or title.lower() in f.stem.lower():
                target_file = f
                break
        if not target_file:
            target_file = goods_dir / "stock.txt"
            if not target_file.exists():
                return None

        try:
            with open(target_file, "r", encoding="utf-8") as file:
                lines = [line.strip() for line in file if line.strip()]
            
            if not lines:
                return None

            popped_item = lines[0]
            remaining_lines = lines[1:]

            with open(target_file, "w", encoding="utf-8") as file:
                for line in remaining_lines:
                    file.write(f"{line}\n")

            return popped_item
        except Exception as e:
            logger.error(f"Error reading stock file {target_file}: {e}")
            return None
