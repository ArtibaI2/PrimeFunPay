from typing import List, Optional
from aiogram import Bot
from config.settings import settings
from funpay.models import FunPayOrder, ChatMessage, RaiseResult
from tg_bot.keyboards.admin_kb import get_order_action_keyboard
from utils.logger import logger

class TelegramNotifier:
    def __init__(self, bot: Bot):
        self.bot = bot

    async def _send_to_admins(self, text: str, reply_markup=None) -> None:
        for admin_id in settings.TELEGRAM_ADMIN_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
            except Exception as e:
                logger.error(f"Failed to send Telegram alert to admin {admin_id}: {e}")

    async def notify_new_order(self, order: FunPayOrder, delivered_item: Optional[str] = None) -> None:
        """Sends an alert for a new order."""
        status_text = f"✅ <b>Товар автоматически выдан:</b>\n<code>{delivered_item}</code>" if delivered_item else "⏳ <b>Ожидает ручной выдачи</b>"
        text = (
            f"🛒 <b>Новый заказ на FunPay!</b>\n\n"
            f"• <b>Заказ:</b> <code>#{order.order_id}</code>\n"
            f"• <b>Товар:</b> {order.title}\n"
            f"• <b>Сумма:</b> <b>{order.price:,.2f} ₽</b>\n"
            f"• <b>Покупатель:</b> {order.buyer_username}\n\n"
            f"{status_text}"
        )
        kb = get_order_action_keyboard(order.chat_node_id, order.order_id) if order.chat_node_id else None
        await self._send_to_admins(text, reply_markup=kb)

    async def notify_out_of_stock(self, order: FunPayOrder) -> None:
        """Sends an alert when an item is out of stock."""
        text = (
            f"⚠️ <b>ТОВАР ЗАКОНЧИЛСЯ НА СКЛАДЕ!</b>\n\n"
            f"• <b>Заказ:</b> <code>#{order.order_id}</code>\n"
            f"• <b>Товар:</b> {order.title}\n"
            f"• <b>Покупатель:</b> {order.buyer_username}\n"
            f"• <b>Сумма:</b> {order.price:,.2f} ₽\n\n"
            f"Пожалуйста, пополните склад или выдайте товар вручную!"
        )
        kb = get_order_action_keyboard(order.chat_node_id, order.order_id) if order.chat_node_id else None
        await self._send_to_admins(text, reply_markup=kb)

    async def notify_new_chat_message(self, message: ChatMessage) -> None:
        """Sends an alert when a buyer sends a message in FunPay chat."""
        text = (
            f"💬 <b>Новое сообщение от покупателя!</b>\n\n"
            f"👤 <b>Покупатель:</b> {message.sender_username}\n"
            f"🆔 <b>Чат:</b> <code>#{message.chat_node_id}</code>\n\n"
            f"✉️ <i>\"{message.text}\"</i>\n\n"
            f"💡 <i>Ответьте на это сообщение в Telegram (Reply), чтобы отправить ответ покупателю на FunPay.</i>"
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Ответить",
                    callback_data=f"reply_chat:{message.chat_node_id}",
                )
            ]
        ])
        await self._send_to_admins(text, reply_markup=kb)

    async def notify_balance_change(self, old_balance: float, new_balance: float) -> None:
        """Sends an alert on balance change (cash-in or payout)."""
        diff = new_balance - old_balance
        diff_str = f"+{diff:,.2f} ₽" if diff > 0 else f"{diff:,.2f} ₽"
        icon = "💰" if diff > 0 else "💸"
        text = (
            f"{icon} <b>Изменение баланса FunPay!</b>\n\n"
            f"• Изменение: <b>{diff_str}</b>\n"
            f"• Новый баланс: <b>{new_balance:,.2f} ₽</b>"
        )
        await self._send_to_admins(text)

    async def notify_raise_results(self, results: List[RaiseResult]) -> None:
        """Sends auto-raise status report to admins."""
        if not results:
            return
        lines = ["🚀 <b>Отчет о периодическом автоподнятии предложений:</b>\n"]
        for r in results:
            icon = "✅" if r.success else ("⏳" if "подождите" in r.message.lower() else "❌")
            lines.append(f"{icon} <b>{r.category_name}:</b> {r.message}")
        await self._send_to_admins("\n".join(lines))

    async def notify_session_expired(self) -> None:
        """Sends an urgent alert when FunPay golden_key session expires."""
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        text = (
            "🚨 <b>ВНИМАНИЕ: СЕССИЯ FUNPAY ЗАВЕРШЕНА!</b>\n\n"
            "• Ваш <code>golden_key</code> устарел или был сброшен на FunPay.\n"
            "• Автовыдача товаров и автоподнятие лотов <b>приостановлены</b>.\n\n"
            "👇 <i>Пожалуйста, обновите ключ для возобновления работы:</i>"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔑 Обновить golden_key", callback_data="auth_link_account")],
            [InlineKeyboardButton(text="🔄 Проверить сессию", callback_data="auth_refresh_profile")],
        ])
        await self._send_to_admins(text, reply_markup=kb)

    async def notify_review_reward(self, buyer_username: str, order_id: str, promo: str) -> None:
        """Sends an alert when 5-star review bonus is delivered."""
        text = (
            f"⭐ <b>Получен 5★ отзыв от покупателя {buyer_username}!</b>\n\n"
            f"• <b>Заказ:</b> <code>#{order_id}</code>\n"
            f"• 🎁 <b>Бонус покупателю:</b> Промокод <code>{promo}</code> автоматически отправлен в чат FunPay."
        )
        await self._send_to_admins(text)

