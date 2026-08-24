import io
import os
import re
import contextlib
from pathlib import Path
from typing import List, Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, Document

from config.settings import settings
from database.engine import async_session
from database.repositories import LotRepository, GoodsRepository
from tg_bot.keyboards.admin_kb import (
    get_goods_list_keyboard,
    get_lot_stock_keyboard,
    get_main_menu_keyboard,
    get_product_builder_keyboard,
    get_storage_choice_keyboard,
)
from utils.file_uploader import FileUploader
from utils.product_parser import parse_product_template, format_product_card

from utils.auth_helper import is_user_authorized

router = Router(name="goods_router")

async def is_admin(user_id: int) -> bool:
    return await is_user_authorized(user_id)

class StockFSM(StatesGroup):
    waiting_for_items = State()
    waiting_for_template = State()

class ProductBuilderFSM(StatesGroup):
    waiting_for_template_text = State()
    waiting_for_title = State()
    waiting_for_desc = State()
    waiting_for_delivery = State()
    waiting_for_price = State()
    waiting_for_cloud_link = State()
    waiting_for_file_upload = State()

async def get_lot_stock_info(lot_id: int) -> dict:
    async with async_session() as session:
        lot_repo = LotRepository(session)
        goods_repo = GoodsRepository(session)

        lot = await lot_repo.get_by_id(lot_id)
        if not lot:
            return {}

        db_stock = await goods_repo.count_available(lot_id=lot.id)
        
        # Also check file
        file_stock = 0
        goods_dir = Path(settings.GOODS_DIR)
        for f in goods_dir.glob("*.txt"):
            if f.stem.lower() in lot.title.lower() or lot.title.lower() in f.stem.lower():
                try:
                    with open(f, "r", encoding="utf-8") as file:
                        file_stock = len([l for l in file if l.strip()])
                except Exception:
                    pass
                break

        total_stock = max(db_stock, file_stock)

        return {
            "id": lot.id,
            "funpay_lot_id": lot.funpay_lot_id,
            "title": lot.title,
            "description": lot.description or "Без описания",
            "category_name": lot.category_name or "Без категории",
            "price": lot.price,
            "stock_count": total_stock,
            "template": lot.delivery_template or "Стандартный шаблон",
            "upload_url": lot.upload_url,
            "upload_storage_type": lot.upload_storage_type,
            "auto_delivery": lot.auto_delivery_enabled,
        }

# ----------------- MAIN GOODS MENU -----------------

@router.message(F.text == "📦 Склад товаров")
@router.message(Command("goods"))
async def cmd_goods_menu(message: Message):
    if not await is_admin(message.from_user.id):
        return

    async with async_session() as session:
        lot_repo = LotRepository(session)
        goods_repo = GoodsRepository(session)
        lots = await lot_repo.get_all_active()

        lots_data = []
        for l in lots:
            cnt = await goods_repo.count_available(lot_id=l.id)
            lots_data.append({
                "id": l.id,
                "title": l.title,
                "stock_count": cnt,
            })

    text = (
        "📦 <b>Управление товарами и складом FunPay:</b>\n\n"
        "🟢 — товар есть в наличии / активна автовыдача\n"
        "🔴 — товар закончился (требуется пополнение)\n\n"
        "<i>Нажмите <b>➕ Создать / Залить товар</b> для добавления нового лота или выберите товар из списка:</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_goods_list_keyboard(lots_data))

@router.callback_query(F.data == "stock_list")
async def cb_stock_list(query: CallbackQuery, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        lot_repo = LotRepository(session)
        goods_repo = GoodsRepository(session)
        lots = await lot_repo.get_all_active()

        lots_data = []
        for l in lots:
            cnt = await goods_repo.count_available(lot_id=l.id)
            lots_data.append({
                "id": l.id,
                "title": l.title,
                "stock_count": cnt,
            })

    text = (
        "📦 <b>Управление товарами и складом:</b>\n\n"
        "🟢 — в наличии\n"
        "🔴 — требуется пополнение\n\n"
        "Выберите товар для настройки или создайте новый:"
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_goods_list_keyboard(lots_data))
    await query.answer()

# ----------------- PRODUCT BUILDER / UPLOAD WIZARD -----------------

@router.message(F.text == "➕ Добавить товар")
@router.message(Command("add"))
@router.message(Command("new_lot"))
@router.callback_query(F.data == "product_create")
async def cb_product_create(event, state: FSMContext):
    # Initialize empty product in FSM state
    user_id = event.from_user.id if hasattr(event, "from_user") else event.message.from_user.id
    if not is_admin(user_id):
        return

    await state.set_state(ProductBuilderFSM.waiting_for_template_text)
    default_data = {
        "title": "",
        "description": "",
        "delivery_template": "Спасибо за покупку!\nВаша ссылка / товар:\n{link}",
        "price": 0.0,
        "upload_url": "",
        "storage_type": "Workupload / Google Drive",
        "attached_filename": None,
    }
    await state.update_data(**default_data)

    card_text = format_product_card(**default_data)
    if isinstance(event, CallbackQuery):
        with contextlib.suppress(Exception):
            await event.message.edit_text(card_text, parse_mode="HTML", reply_markup=get_product_builder_keyboard(False))
        await event.answer()
    else:
        await event.answer(card_text, parse_mode="HTML", reply_markup=get_product_builder_keyboard(False))

@router.callback_query(F.data == "prod_show_card")
async def cb_prod_show_card(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", "Workupload / Google Drive"),
        attached_filename=data.get("attached_filename"),
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(card_text, parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))
    await query.answer()

@router.callback_query(F.data == "product_paste_template")
async def cb_product_paste_template(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_template_text)
    template_example = (
        "📋 <b>Отправьте данные товара одним сообщением или файлом с подписью:</b>\n\n"
        "<code>Название: Apex Legends 1000 Coins\n"
        "Описание: Моментальная доставка 24/7, официальный ключ\n"
        "Сообщение после покупки: Спасибо! Ваш ключ/ссылка: {link}\n"
        "Цена: 750</code>\n\n"
        "<i>💡 Если товар в виде архива/файла — просто прикрепите документ к сообщению!</i>"
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(template_example, parse_mode="HTML")
    await query.answer()

# ----------------- EDIT SPECIFIC FIELDS -----------------

@router.callback_query(F.data == "prod_edit_title")
async def cb_prod_edit_title(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_title)
    await query.message.answer("✏️ <b>Введите название товара/лота:</b>", parse_mode="HTML")
    await query.answer()

@router.message(ProductBuilderFSM.waiting_for_title, F.text)
async def process_prod_title(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(title=message.text.strip())
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", "Workupload / Google Drive"),
        attached_filename=data.get("attached_filename"),
    )
    await message.answer(f"✅ Название сохранено: <b>{message.text.strip()}</b>\n\n{card_text}", parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))

@router.callback_query(F.data == "prod_edit_desc")
async def cb_prod_edit_desc(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_desc)
    await query.message.answer("📄 <b>Введите описание товара:</b>", parse_mode="HTML")
    await query.answer()

@router.message(ProductBuilderFSM.waiting_for_desc, F.text)
async def process_prod_desc(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(description=message.text.strip())
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", "Workupload / Google Drive"),
        attached_filename=data.get("attached_filename"),
    )
    await message.answer(f"✅ Описание сохранено.\n\n{card_text}", parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))

@router.callback_query(F.data == "prod_edit_delivery")
async def cb_prod_edit_delivery(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_delivery)
    hint = (
        "💬 <b>Введите сообщение, отправляемое покупателю сразу после покупки:</b>\n\n"
        "<i>Доступные теги:</i>\n"
        "• <code>{link}</code> — ссылка на скачивание файла / облако\n"
        "• <code>{item}</code> или <code>{key}</code> — выданный ключ / строка\n"
        "• <code>{username}</code> — логин покупателя\n"
        "• <code>{title}</code> — название товара"
    )
    await query.message.answer(hint, parse_mode="HTML")
    await query.answer()

@router.message(ProductBuilderFSM.waiting_for_delivery, F.text)
async def process_prod_delivery(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.update_data(delivery_template=message.text.strip())
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", "Workupload / Google Drive"),
        attached_filename=data.get("attached_filename"),
    )
    await message.answer(f"✅ Сообщение после покупки сохранено.\n\n{card_text}", parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))

@router.callback_query(F.data == "prod_edit_price")
async def cb_prod_edit_price(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_price)
    await query.message.answer("💰 <b>Введите цену товара в рублях (например, 250):</b>", parse_mode="HTML")
    await query.answer()

@router.message(ProductBuilderFSM.waiting_for_price, F.text)
async def process_prod_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    val = message.text.replace(" ", "").replace(",", ".").replace("₽", "").strip()
    try:
        price = float(val)
    except ValueError:
        return await message.answer("⚠️ Пожалуйста, введите корректное число (например: <code>350</code> или <code>499.90</code>).")

    await state.update_data(price=price)
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", "Workupload / Google Drive"),
        attached_filename=data.get("attached_filename"),
    )
    await message.answer(f"✅ Цена сохранена: <b>{price:,.2f} ₽</b>\n\n{card_text}", parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))

# ----------------- STORAGE CHOICE & CLOUD UPLOAD -----------------

@router.callback_query(F.data == "prod_choose_storage")
async def cb_prod_choose_storage(query: CallbackQuery):
    text = (
        "🌐 <b>Выберите, куда залить файл или источник товара:</b>\n\n"
        "• 🚀 <b>Workupload</b> — популярный файлообменник\n"
        "• 🐱 <b>Catbox.moe</b> — прямая быстрая ссылка\n"
        "• 📁 <b>Gofile.io</b> — облачное хранилище\n"
        "• 🌐 <b>Google Диск</b> — вставить прямую ссылку на Google Drive\n"
        "• ☁️ <b>Своя ссылка</b> — Яндекс Диск, Mega, DropMeFiles и др.\n"
        "• 🔑 <b>Текстовые ключи</b> — построчные коды / аккаунты\n\n"
        "Выберите желаемый вариант:"
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_storage_choice_keyboard())
    await query.answer()

@router.callback_query(F.data.startswith("storage_set:"))
async def cb_storage_set(query: CallbackQuery, state: FSMContext):
    stype = query.data.split(":", 1)[1]
    stype_map = {
        "workupload": "Workupload",
        "catbox": "Catbox.moe",
        "gofile": "Gofile.io",
        "gdrive": "Google Диск",
        "custom": "Облако / Своя ссылка",
        "keys": "Текстовые ключи",
    }
    label = stype_map.get(stype, "Облако")
    await state.update_data(storage_type=label)

    if stype in ("gdrive", "custom", "workupload"):
        await state.set_state(ProductBuilderFSM.waiting_for_cloud_link)
        await query.message.answer(
            f"🌐 <b>Выбрано: {label}</b>\n\nОтправьте ссылку на скачивание товара (или прикрепите файл документом для автозагрузки):",
            parse_mode="HTML",
        )
    elif stype == "keys":
        await query.message.answer(
            "🔑 <b>Выбран режим текстовых ключей.</b>\nПосле сохранения карточки вы сможете загрузить список ключей построчно.",
            parse_mode="HTML",
        )
        await cb_prod_show_card(query, state)
    else:
        # Catbox or Gofile: prompt file
        await state.set_state(ProductBuilderFSM.waiting_for_file_upload)
        await query.message.answer(
            f"📤 <b>Выбрано: {label}</b>\n\nПрикрепите и отправьте файл товара (zip, rar, txt, exe, cfg, apk и т.д.):",
            parse_mode="HTML",
        )
    await query.answer()

@router.callback_query(F.data == "prod_upload_file")
async def cb_prod_upload_file(query: CallbackQuery, state: FSMContext):
    await state.set_state(ProductBuilderFSM.waiting_for_file_upload)
    await query.message.answer(
        "📎 <b>Отправьте файл товара (документ, архив, конфиг, txt):</b>\nБот автоматически загрузит его в облако и создаст ссылку для выдачи.",
        parse_mode="HTML",
    )
    await query.answer()

@router.message(ProductBuilderFSM.waiting_for_cloud_link, F.text)
async def process_cloud_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = message.text.strip()
    await state.update_data(upload_url=link)
    data = await state.get_data()
    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=link,
        storage_type=data.get("storage_type", "Google Диск / Workupload"),
        attached_filename=data.get("attached_filename"),
    )
    await message.answer(f"✅ Ссылка на облако сохранена: <code>{link}</code>\n\n{card_text}", parse_mode="HTML", reply_markup=get_product_builder_keyboard(True))

# ----------------- FILE ATTACHMENT & AUTO-UPLOAD -----------------

@router.message(F.document)
async def handle_incoming_document(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    doc: Document = message.document
    filename = doc.file_name or "product_file"
    caption = message.caption or ""

    # Check if caption contains template
    parsed = {}
    if caption and ("название:" in caption.lower() or "цена:" in caption.lower()):
        parsed = parse_product_template(caption)

    load_msg = await message.answer(f"⏳ <i>Загрузка и отправка файла «{filename}» в облачное хранилище...</i>", parse_mode="HTML")

    file_io = io.BytesIO()
    await bot.download(doc.file_id, destination=file_io)
    file_bytes = file_io.getvalue()

    # Upload to file host (Catbox / Gofile / Workupload)
    curr_data = await state.get_data()
    pref_storage = curr_data.get("storage_type", "auto")
    url, s_name = await FileUploader.upload(file_bytes, filename, service=pref_storage)

    if not url:
        # Save locally as fallback
        goods_dir = Path(settings.GOODS_DIR)
        goods_dir.mkdir(parents=True, exist_ok=True)
        local_path = goods_dir / filename
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        url = f"storage/goods/{filename}"
        s_name = "Локальное хранилище бота"

    # Also save copy in storage/goods for redundancy
    try:
        goods_dir = Path(settings.GOODS_DIR)
        goods_dir.mkdir(parents=True, exist_ok=True)
        with open(goods_dir / filename, "wb") as f:
            f.write(file_bytes)
    except Exception:
        pass

    # Update state data
    updates = {
        "upload_url": url,
        "storage_type": s_name,
        "attached_filename": filename,
    }
    if parsed.get("title"):
        updates["title"] = parsed["title"]
    elif not curr_data.get("title"):
        updates["title"] = filename.rsplit(".", 1)[0].replace("_", " ")

    if parsed.get("description"):
        updates["description"] = parsed["description"]
    if parsed.get("price"):
        updates["price"] = parsed["price"]
    if parsed.get("delivery_template"):
        updates["delivery_template"] = parsed["delivery_template"]

    await state.update_data(**updates)
    data = await state.get_data()

    card_text = format_product_card(
        title=data.get("title", ""),
        description=data.get("description", ""),
        delivery_template=data.get("delivery_template", ""),
        price=data.get("price", 0.0),
        upload_url=data.get("upload_url", ""),
        storage_type=data.get("storage_type", s_name),
        attached_filename=filename,
    )

    await load_msg.edit_text(
        f"✅ <b>Файл «{filename}» успешно загружен в {s_name}!</b>\n🔗 Ссылка: <code>{url}</code>\n\n{card_text}",
        parse_mode="HTML",
        reply_markup=get_product_builder_keyboard(True),
    )

# ----------------- PARSE WHOLE TEMPLATE TEXT -----------------

@router.message(F.text.regexp(r"(?i)^(?:название|title|товар)\s*:"))
@router.message(ProductBuilderFSM.waiting_for_template_text, F.text)
async def handle_pasted_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    parsed = parse_product_template(message.text)
    if not parsed.get("title") and not parsed.get("price"):
        return await message.answer("⚠️ Не удалось распознать шаблон. Убедитесь, что указаны <code>Название:</code> и <code>Цена:</code>.")

    curr_data = await state.get_data()
    merged = {
        "title": parsed["title"] or curr_data.get("title", ""),
        "description": parsed["description"] or curr_data.get("description", ""),
        "delivery_template": parsed["delivery_template"] or curr_data.get("delivery_template", "Спасибо за покупку!\nВаш товар / ссылка:\n{link}"),
        "price": parsed["price"] if parsed["price"] > 0 else curr_data.get("price", 0.0),
        "upload_url": parsed["upload_url"] or curr_data.get("upload_url", ""),
        "storage_type": curr_data.get("storage_type", "Workupload / Google Drive"),
        "attached_filename": curr_data.get("attached_filename"),
    }
    await state.update_data(**merged)

    card_text = format_product_card(**merged)
    await message.answer(
        f"✅ <b>Шаблон успешно распознан!</b>\n\n{card_text}",
        parse_mode="HTML",
        reply_markup=get_product_builder_keyboard(True),
    )

# ----------------- SAVE & PUBLISH PRODUCT -----------------

@router.callback_query(F.data == "prod_save_lot")
async def cb_prod_save_lot(query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    title = data.get("title", "").strip()
    if not title:
        return await query.answer("⚠️ Укажите название товара перед сохранением!", show_alert=True)

    price = data.get("price", 0.0)
    desc = data.get("description", "")
    template = data.get("delivery_template", "Спасибо за покупку!\nВаш товар:\n{link}")
    upload_url = data.get("upload_url", "")
    storage_type = data.get("storage_type", "Cloud")

    async with async_session() as session:
        lot_repo = LotRepository(session)
        lot = await lot_repo.create_product(
            title=title,
            price=price,
            description=desc,
            delivery_template=template,
            upload_url=upload_url,
            upload_storage_type=storage_type,
            category_name=desc[:50] if desc else "Цифровые товары",
        )

    await state.clear()

    text = (
        "🎉 <b>Товар успешно создан и настроен в боте!</b>\n\n"
        f"📦 <b>Название:</b> {lot.title}\n"
        f"💰 <b>Цена:</b> {lot.price:,.2f} ₽\n"
        f"🌐 <b>Хранилище/Ссылка:</b> {upload_url or 'Текстовые ключи'}\n"
        f"⚡ <b>Автовыдача:</b> Включена\n"
        f"💬 <b>Текст выдачи:</b>\n<blockquote>{lot.delivery_template}</blockquote>\n\n"
        "<i>При покупке этого товара бот моментально выдаст покупателю ссылку или ключ!</i>"
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_menu_keyboard())
    await query.answer("Товар сохранен!")

# ----------------- EXISTING LOT MANAGEMENT -----------------

@router.callback_query(F.data.startswith("stock_select:"))
async def cb_stock_select(query: CallbackQuery):
    lot_id = int(query.data.split(":", 1)[1])
    info = await get_lot_stock_info(lot_id)
    if not info:
        return await query.answer("Лот не найден.")

    status_icon = "🟢" if info["stock_count"] > 0 or info.get("upload_url") else "🔴"
    text = (
        f"📦 <b>Карточка товара: {info['title']}</b>\n\n"
        f"🆔 Внутренний ID: <code>{info['id']}</code>\n"
        f"🏷 FunPay ID: <code>{info['funpay_lot_id']}</code>\n"
        f"📁 Категория: <b>{info['category_name']}</b>\n"
        f"💰 Цена: <b>{info['price']:,.2f} ₽</b>\n"
        f"📊 Остаток: {status_icon} <b>{info['stock_count']} шт.</b>\n"
    )
    if info.get("upload_url"):
        text += f"🌐 Ссылка на файл: <code>{info['upload_url']}</code>\n"
    text += f"⚡ Автовыдача: {'Включена' if info['auto_delivery'] else 'Выключена'}\n\n"
    text += f"📝 <b>Шаблон выдачи:</b>\n<blockquote>{info['template']}</blockquote>"

    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML", reply_markup=get_lot_stock_keyboard(lot_id))
    await query.answer()

@router.callback_query(F.data.startswith("stock_add:"))
async def cb_stock_add(query: CallbackQuery, state: FSMContext):
    lot_id = int(query.data.split(":", 1)[1])
    await state.set_state(StockFSM.waiting_for_items)
    await state.update_data(active_lot_id=lot_id)

    text = (
        "➕ <b>Пополнение склада:</b>\n\n"
        "Отправьте ключи/аккаунты <b>текстовым сообщением</b> (каждый товар с новой строки) "
        "или прикрепите <b>.txt файл</b> с ключами."
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML")
    await query.answer()

@router.callback_query(F.data.startswith("stock_template:"))
async def cb_stock_template(query: CallbackQuery, state: FSMContext):
    lot_id = int(query.data.split(":", 1)[1])
    await state.set_state(StockFSM.waiting_for_template)
    await state.update_data(active_lot_id=lot_id)

    text = (
        "📝 <b>Редактирование шаблона выдачи товара:</b>\n\n"
        "Отправьте новый текст шаблона. Поддерживаются переменные:\n"
        "• <code>{key}</code> или <code>{item}</code> — выданный ключ/аккаунт\n"
        "• <code>{link}</code> — ссылка на скачивание файла\n"
        "• <code>{username}</code> — никнейм покупателя\n"
        "• <code>{title}</code> — название товара"
    )
    with contextlib.suppress(Exception):
        await query.message.edit_text(text, parse_mode="HTML")
    await query.answer()

@router.callback_query(F.data.startswith("stock_clear:"))
async def cb_stock_clear(query: CallbackQuery):
    lot_id = int(query.data.split(":", 1)[1])
    async with async_session() as session:
        goods_repo = GoodsRepository(session)
        await goods_repo.clear_unused(lot_id=lot_id)

    await query.answer("Остаток очищен!", show_alert=True)
    # Refresh view
    await cb_stock_select(query)

@router.message(StockFSM.waiting_for_items, F.text)
async def process_stock_text(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    lot_id = data.get("active_lot_id")
    await state.clear()

    lines = [line.strip() for line in message.text.splitlines() if line.strip()]
    if not lines:
        return await message.answer("⚠️ Вы не ввели ни одной строки товара.")

    async with async_session() as session:
        goods_repo = GoodsRepository(session)
        lot_repo = LotRepository(session)
        lot = await lot_repo.get_by_id(lot_id)
        lot_title = lot.title if lot else "Товар"
        added_count = await goods_repo.add_items(lines, lot_id=lot_id, category_identifier=lot_title)

    await message.answer(
        f"✅ <b>Склад успешно пополнен!</b>\n\n"
        f"📦 Товар: <b>{lot_title}</b>\n"
        f"➕ Добавлено: <b>{added_count} шт.</b>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )

@router.message(StockFSM.waiting_for_template, F.text)
async def process_stock_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    lot_id = data.get("active_lot_id")
    await state.clear()

    async with async_session() as session:
        lot_repo = LotRepository(session)
        lot = await lot_repo.get_by_id(lot_id)
        if lot:
            lot.delivery_template = message.text
            await session.commit()
            lot_title = lot.title
        else:
            lot_title = "Товар"

    await message.answer(
        f"✅ <b>Шаблон выдачи обновлен!</b>\n\n"
        f"📦 Товар: <b>{lot_title}</b>\n"
        f"📝 Новый шаблон:\n<code>{message.text}</code>",
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )
