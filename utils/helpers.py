import re
from datetime import datetime
from typing import Optional

def clean_html(raw_html: str) -> str:
    """Removes HTML tags and normalizes whitespace."""
    if not raw_html:
        return ""
    clean = re.sub(r"<.*?>", "", raw_html)
    return " ".join(clean.split())

def format_rub(amount: float) -> str:
    """Formats amount as Russian Rubles string."""
    return f"{amount:,.2f} ₽".replace(",", " ")

def escape_tg_markdown(text: str) -> str:
    """Escapes special characters for Telegram MarkdownV2."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", str(text))

def safe_filename(name: str) -> str:
    """Creates a safe filename from a lot/category title."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(" ", "_")

__all__ = ["clean_html", "format_rub", "escape_tg_markdown", "safe_filename"]
