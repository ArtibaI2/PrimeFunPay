import re
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from funpay.client import FunPayClient
from utils.auth_helper import is_user_authorized

router = Router(name="chat_center_router")

async def is_admin(user_id: int) -> bool:
    return await is_user_authorized(user_id)

class ReplyFSM(StatesGroup):
    waiting_for_reply = State()

@router.message(F.text == "💬 Чат-центр")
@router.message(Command("chat"))
async def cmd_chat_center(message: Message, funpay_client: FunPayClient):
    if not await is_admin(message.from_user.id):
        return

    profile = await funpay_client.check_auth()
    unread = profile.unread_chats_count if profile else 0

    text = (
        "💬 <b>Чат-центр FunPay</b>\n\n"
        f"• Непрочитанных чатов на FunPay: <b>{unread}</b>\n\n"
        "💡 <b>Как отвечать покупателям:</b>\n"
        "1. При получении нового сообщения от покупателя бот пришлет уведомление в этот чат.\n"
        "2. Просто <b>ответьте (Reply)</b> на уведомление в Telegram — и ваш ответ сразу отправится покупателю на FunPay!\n"
        "3. Или используйте команду:\n"
        "<code>/reply [chat_node_id] [текст сообщения]</code>\n\n"
        "<i>Все ответы отправляются моментально.</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.callback_query(F.data.startswith("reply_chat:"))
async def cb_reply_chat(query: CallbackQuery, state: FSMContext):
    chat_node_id = int(query.data.split(":")[1])
    await state.update_data(active_chat_node_id=chat_node_id)
    await state.set_state(ReplyFSM.waiting_for_reply)

    await query.message.answer(
        f"💬 <b>Ответ в чат #{chat_node_id}:</b>\n\n"
        "Напишите текст ответа покупателю. Сообщение будет мгновенно доставлено на FunPay.\n\n"
        "<i>Для отмены отправьте /cancel</i>",
        parse_mode="HTML",
    )
    await query.answer()

@router.message(ReplyFSM.waiting_for_reply, F.text)
async def process_fsm_reply(message: Message, state: FSMContext, funpay_client: FunPayClient):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    chat_node_id = data.get("active_chat_node_id")
    await state.clear()

    if not chat_node_id:
        return await message.answer("❌ Ошибка: ID чата не найден.")

    sent = await funpay_client.send_chat_message(
        chat_node_id=chat_node_id,
        message=message.text,
    )
    if sent:
        await message.answer(
            f"✅ <b>Сообщение отправлено в чат #{chat_node_id}!</b>\n\n"
            f"✉️ <i>\"{message.text}\"</i>",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ Не удалось отправить сообщение в чат #{chat_node_id} на FunPay.")

@router.message(Command("reply"))
async def cmd_reply_manual(message: Message, funpay_client: FunPayClient):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "ℹ️ <b>Формат команды:</b>\n<code>/reply [chat_node_id] [текст ответа]</code>\n\n"
            "Пример: <code>/reply 283468190 Здравствуйте, ключ активируется в настройках!</code>",
            parse_mode="HTML",
        )

    raw_node, text_to_send = args[1], args[2]
    if not raw_node.isdigit():
        return await message.answer("❌ ID чата должен быть числом.")

    chat_node_id = int(raw_node)
    sent = await funpay_client.send_chat_message(
        chat_node_id=chat_node_id,
        message=text_to_send,
    )
    if sent:
        await message.answer(
            f"✅ <b>Сообщение отправлено в чат #{chat_node_id}!</b>\n\n"
            f"✉️ <i>\"{text_to_send}\"</i>",
            parse_mode="HTML",
        )
    else:
        await message.answer(f"❌ Не удалось отправить сообщение в чат #{chat_node_id} на FunPay.")

@router.message(F.reply_to_message)
async def handle_telegram_reply_to_buyer(message: Message, funpay_client: FunPayClient):
    """Intercepts direct Telegram quote replies to bot notification messages."""
    if not is_admin(message.from_user.id):
        return

    reply_msg = message.reply_to_message
    if not reply_msg or not reply_msg.text:
        return

    # Extract chat node id from quoted notification text
    # Matches patterns like: "Чат: #283468190", "Чат #283468190", "chat_node_id: 283468190"
    m = re.search(r"(?:Чат|chat|чат)[\s:]*#?(\d{6,12})", reply_msg.text)
    if not m:
        return

    chat_node_id = int(m.group(1))
    sent = await funpay_client.send_chat_message(
        chat_node_id=chat_node_id,
        message=message.text,
    )
    if sent:
        await message.reply(
            f"✅ <b>Ответ доставлен покупателю в чат #{chat_node_id}!</b>",
            parse_mode="HTML",
        )
    else:
        await message.reply(
            f"❌ Не удалось отправить сообщение в чат #{chat_node_id} на FunPay.",
            parse_mode="HTML",
        )
