from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from config.settings import settings
from funpay.client import FunPayClient

router = Router(name="reply_router")

def is_admin(user_id: int) -> bool:
    return user_id in settings.TELEGRAM_ADMIN_IDS

@router.callback_query(F.data.startswith("reply_chat:"))
async def cb_reply_prompt(query: CallbackQuery):
    chat_node_id = query.data.split(":", 1)[1]
    await query.message.answer(
        f"✍️ <b>Чтобы отправить ответ покупателю в чат <code>{chat_node_id}</code>:</b>\n\n"
        f"Отправьте команду:\n"
        f"<code>/reply {chat_node_id} Ваш текст ответа</code>",
        parse_mode="HTML",
    )
    await query.answer()

@router.message(Command("reply"))
async def cmd_reply_message(message: Message, funpay_client: FunPayClient):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.answer(
            "ℹ️ <b>Формат команды /reply:</b>\n"
            "<code>/reply [chat_id] [текст сообщения]</code>\n\n"
            "Пример:\n"
            "<code>/reply 283468190 Здравствуйте, ваш товар отправлен!</code>",
            parse_mode="HTML",
        )

    raw_chat_id = args[1].strip()
    reply_text = args[2].strip()

    if not raw_chat_id.isdigit():
        return await message.answer("❌ ID чата должен содержать только цифры.")

    chat_node_id = int(raw_chat_id)
    success = await funpay_client.send_chat_message(chat_node_id=chat_node_id, message=reply_text)

    if success:
        await message.answer(f"✅ Сообщение успешно отправлено в чат <code>{chat_node_id}</code>!", parse_mode="HTML")
    else:
        await message.answer(f"❌ Не удалось отправить сообщение в чат <code>{chat_node_id}</code>. Проверьте логи.", parse_mode="HTML")
