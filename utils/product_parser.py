import re
from typing import Dict, Any, Optional

def parse_product_template(text: str) -> Dict[str, Any]:
    """
    Parses product information from a template text in format:
    Название: <name>
    Описание: <description>
    Сообщение после покупки: <after purchase message>
    Цена: <price>
    """
    result = {
        "title": "",
        "description": "",
        "delivery_template": "",
        "price": 0.0,
        "upload_url": "",
    }
    
    if not text:
        return result

    # Normalize text
    lines = [l.strip() for l in text.split("\n")]
    current_key = None
    buffers = {
        "title": [],
        "description": [],
        "delivery_template": [],
        "price": [],
        "upload_url": [],
    }

    key_patterns = {
        "title": re.compile(r"^(?:название|заголовок|товар|title|name)\s*:\s*(.*)$", re.IGNORECASE),
        "description": re.compile(r"^(?:описание|инфо|категория|description|desc)\s*:\s*(.*)$", re.IGNORECASE),
        "delivery_template": re.compile(r"^(?:сообщение\s+после\s+покупки|текст\s+выдачи|выдача|шаблон|сообщение|message|delivery|template)\s*:\s*(.*)$", re.IGNORECASE),
        "price": re.compile(r"^(?:цена|стоимость|price|cost)\s*:\s*(.*)$", re.IGNORECASE),
        "upload_url": re.compile(r"^(?:ссылка|облако|диск|файл|link|url)\s*:\s*(.*)$", re.IGNORECASE),
    }

    for line in lines:
        matched_key = None
        for key, pattern in key_patterns.items():
            m = pattern.match(line)
            if m:
                matched_key = key
                current_key = key
                val = m.group(1).strip()
                if val:
                    buffers[key].append(val)
                break
        
        if not matched_key and current_key and line:
            # Continuation line of current field
            buffers[current_key].append(line)

    result["title"] = " ".join(buffers["title"]).strip()
    result["description"] = "\n".join(buffers["description"]).strip()
    result["delivery_template"] = "\n".join(buffers["delivery_template"]).strip()
    
    # Parse price
    price_str = "".join(buffers["price"]).replace(" ", "").replace("₽", "").replace("руб", "").replace(",", ".").strip()
    if price_str:
        try:
            p_match = re.search(r"(\d+(?:\.\d+)?)", price_str)
            if p_match:
                result["price"] = float(p_match.group(1))
        except ValueError:
            result["price"] = 0.0

    # Parse URL if provided directly or embedded in text
    if buffers["upload_url"]:
        result["upload_url"] = buffers["upload_url"][0].strip()
    else:
        # Check if URL exists anywhere in text
        url_match = re.search(r"(https?://\S+)", text)
        if url_match:
            result["upload_url"] = url_match.group(1)

    return result

def format_product_card(
    title: str = "",
    description: str = "",
    delivery_template: str = "",
    price: float = 0.0,
    upload_url: str = "",
    storage_type: str = "Workupload / Google Drive",
    attached_filename: Optional[str] = None,
) -> str:
    """Formats the interactive product summary card for Telegram."""
    t_title = title if title else "<i>[Не указано]</i>"
    t_desc = description if description else "<i>[Не указано]</i>"
    t_deliv = delivery_template if delivery_template else "<i>[Стандартный шаблон выдачи]</i>"
    t_price = f"{price:,.2f} ₽" if price > 0 else "<i>[0.00 ₽]</i>"
    
    source_info = storage_type
    if attached_filename:
        source_info = f"📎 Прикреплен файл: <code>{attached_filename}</code> ({storage_type})"
    elif upload_url:
        source_info = f"🔗 <a href='{upload_url}'>{upload_url[:40]}...</a> ({storage_type})"

    return (
        "📦 <b>Конструктор карточки товара FunPay:</b>\n\n"
        f"📌 <b>Название:</b> {t_title}\n"
        f"📄 <b>Описание:</b> {t_desc}\n"
        f"💬 <b>Сообщение после покупки:</b>\n<blockquote>{t_deliv}</blockquote>\n"
        f"💰 <b>Цена:</b> <code>{t_price}</code>\n"
        f"🌐 <b>Хранилище / Ссылка:</b> {source_info}\n\n"
        "<i>Нажимайте кнопки ниже для редактирования или отправьте заполненный шаблон одним сообщением.</i>"
    )
