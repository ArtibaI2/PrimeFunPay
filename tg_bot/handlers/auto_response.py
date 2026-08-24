from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from config.settings import settings
from database.engine import async_session
from database.repositories import AutoResponseRepository
from tg_bot.keyboards.admin_kb import get_auto_response_keyboard, get_main_menu_keyboard
from utils.auth_helper import is_user_authorized

router = Router(name="auto_response_router")

async def is_admin(user_id: int) -> bool:
    return await is_user_authorized(user_id)

class AutoResponseFSM(StatesGroup):
    waiting_for_rule = State()

async def get_rules_list() -> list:
    async with async_session() as session:
        ar_repo = AutoResponseRepository(session)
        rules = await ar_repo.get_all_rules()
        return [
            {
                "id": r.id,
                "keyword": r.keyword,
                "response_text": r.response_text,
                "is_active": r.is_active,
            }
            for r in rules
        ]

@router.message(F.text == "🤖 Автоответчик")
@router.message(Command("autoresponse"))
async def cmd_auto_response_menu(message: Message):
    if not await is_admin(message.from_user.id):
        return

    rules = await get_rules_list()
    status_text = "🟢 Включен" if settings.ENABLE_AUTO_RESPONSE else "🔴 Выключен (в Настройках)"

    text = (
        "🤖 <b>Управление FAQ Автоответчиком</b>\n\n"
        f"• Статус модуля: <b>{status_text}</b>\n"
        f"• Всего правил в базе: <b>{len(rules)}</b>\n\n"
        "Бот автоматически проверяет сообщения покупателей на наличие ключевых слов и отправляет готовый ответ.\n\n"
        "<i>Нажмите на правило для просмотра или добавьте новое:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_auto_response_keyboard(rules))

@router.callback_query(F.data == "ar_list")
async def cb_ar_list(query: CallbackQuery):
    rules = await get_rules_list()
    status_text = "🟢 Включен" if settings.ENABLE_AUTO_RESPONSE else "🔴 Выключен"
    text = (
        "🤖 <b>Управление FAQ Автоответчиком</b>\n\n"
        f"• Статус модуля: <b>{status_text}</b>\n"
        f"• Всего правил в базе: <b>{len(rules)}</b>\n\n"
        "<i>Список активных шаблонов:</i>"
    )
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_auto_response_keyboard(rules))
    await query.answer()

@router.callback_query(F.data.startswith("ar_rule:"))
async def cb_ar_rule(query: CallbackQuery):
    rule_id = int(query.data.split(":")[1])
    async with async_session() as session:
        ar_repo = AutoResponseRepository(session)
        rule = await ar_repo.get_by_id(rule_id)

    if not rule:
        return await query.answer("Правило не найдено.", show_alert=True)

    text = (
        f"🤖 <b>Правило автоответа:</b>\n\n"
        f"🔑 <b>Ключевое слово / фраза:</b> «{rule.keyword}»\n"
        f"📊 <b>Статус:</b> {'🟢 Активно' if rule.is_active else '⚪️ Отключено'}\n\n"
        f"💬 <b>Текст ответа покупателю:</b>\n"
        f"<code>{rule.response_text}</code>"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="❌ Удалить правило", callback_data=f"ar_del:{rule.id}"),
            InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="ar_list"),
        ]
    ])
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await query.answer()

@router.callback_query(F.data.startswith("ar_del:"))
async def cb_ar_del(query: CallbackQuery):
    rule_id = int(query.data.split(":")[1])
    async with async_session() as session:
        ar_repo = AutoResponseRepository(session)
        await ar_repo.delete_rule(rule_id)

    await query.answer("🗑 Правило успешно удалено!", show_alert=True)
    rules = await get_rules_list()
    text = f"🤖 <b>Управление FAQ Автоответчиком</b>\n\n• Правило удалено. Всего правил: <b>{len(rules)}</b>"
    await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_auto_response_keyboard(rules))

@router.callback_query(F.data == "ar_add")
async def cb_ar_add(query: CallbackQuery, state: FSMContext):
    await state.set_state(AutoResponseFSM.waiting_for_rule)
    text = (
        "➕ <b>Добавление нового правила автоответа:</b>\n\n"
        "Отправьте ключевое слово и текст ответа через вертикальную черту <code>|</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>как активировать | Здравствуйте! Инструкция по активации: 1. Скачайте файл...</code>\n\n"
        "<i>Для отмены отправьте /cancel</i>"
    )
    await query.message.answer(text, parse_mode="HTML")
    await query.answer()

@router.message(AutoResponseFSM.waiting_for_rule, F.text)
async def process_ar_rule_input(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    parts = message.text.split("|", maxsplit=1)
    if len(parts) < 2 or not parts[0].strip() or not parts[1].strip():
        return await message.answer(
            "❌ Неверный формат. Нужно указать ключевое слово и ответ через <code>|</code>\n"
            "Пример: <code>как активировать | Инструкция: ...</code>",
            parse_mode="HTML",
        )

    keyword = parts[0].strip()
    response_text = parts[1].strip()

    async with async_session() as session:
        ar_repo = AutoResponseRepository(session)
        rule = await ar_repo.create_rule(keyword=keyword, response_text=response_text)

    await message.answer(
        f"✅ <b>Правило успешно добавлено!</b>\n\n"
        f"🔑 Ключ: «<b>{keyword}</b>»\n"
        f"💬 Ответ: <code>{response_text[:120]}</code>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
