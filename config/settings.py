from pathlib import Path
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # FunPay Account Settings
    FUNPAY_GOLDEN_KEY: str = Field(
        default="",
        description="Golden Key cookie value for FunPay authentication",
    )
    FUNPAY_USER_AGENT: str = Field(
        default="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        description="User-Agent string for FunPay HTTP requests",
    )
    FUNPAY_PROXY: Optional[str] = Field(
        default=None,
        description="HTTP or SOCKS5 proxy URL (e.g. http://user:pass@ip:port)",
    )

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Telegram bot token from @BotFather",
    )
    TELEGRAM_ADMIN_IDS: List[int] = Field(
        default_factory=list,
        description="List of admin Telegram user IDs",
    )

    @field_validator("TELEGRAM_ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip().isdigit()]
        elif isinstance(v, int):
            return [v]
        elif isinstance(v, list):
            return [int(x) for x in v]
        return []

    # Automation Flags
    ENABLE_AUTO_DELIVERY: bool = Field(
        default=True,
        description="Enable automatic product delivery upon order payment",
    )
    ENABLE_AUTO_RAISE: bool = Field(
        default=True,
        description="Enable automatic lot raising by timer",
    )
    ENABLE_AUTO_RESPONSE: bool = Field(
        default=True,
        description="Enable automatic replies to buyer messages",
    )
    ENABLE_STOCK_SYNC: bool = Field(
        default=True,
        description="Enable syncing stock text files with database",
    )
    ENABLE_SMART_PRICING: bool = Field(
        default=False,
        description="Enable automatic competitor price monitoring and undercutting",
    )
    ENABLE_AI_SUPPORT: bool = Field(
        default=True,
        description="Enable AI assistant & auto-translator for customer support",
    )
    AI_API_KEY: Optional[str] = Field(
        default=None,
        description="OpenAI / Gemini / Anthropic API Key for AI-support",
    )
    AI_MODEL: str = Field(
        default="gpt-4o-mini",
        description="AI model identifier for support completions",
    )
    ENABLE_UPSELL: bool = Field(
        default=True,
        description="Enable cross-sell product recommendations after delivery",
    )
    ENABLE_NIGHT_SURGE: bool = Field(
        default=False,
        description="Enable night surge pricing during low-competition hours",
    )
    NIGHT_SURGE_PERCENT: float = Field(
        default=15.0,
        description="Percentage to increase prices during night surge (23:00 - 07:00)",
    )
    WEBAPP_HOST: str = Field(
        default="0.0.0.0",
        description="Web dashboard host bind",
    )
    WEBAPP_PORT: int = Field(
        default=8080,
        description="Web dashboard HTTP port",
    )
    WEBAPP_URL: Optional[str] = Field(
        default=None,
        description="Public HTTPS URL for Telegram WebApp",
    )

    # Auto-Raise & Polling Timers
    AUTO_RAISE_INTERVAL: int = Field(
        default=7200,
        description="Interval between lot raises in seconds (FunPay limit is ~2 hours)",
    )
    POLL_INTERVAL: float = Field(
        default=3.0,
        description="Interval in seconds for polling FunPay orders and chats",
    )

    # Auto-Response Templates
    AUTO_RESPONSE_GREETING: str = Field(
        default="Здравствуйте! Спасибо за обращение. Если у вас возник вопрос по заказу, пожалуйста, уточните детали.",
        description="Greeting sent on first message from a buyer",
    )
    AUTO_RESPONSE_AFTER_PURCHASE: str = Field(
        default="Спасибо за покупку! Ваш заказ обрабатывается. Пожалуйста, подтвердите получение после проверки.",
        description="Follow-up message sent after delivery",
    )

    # Storage Paths
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///storage/sqlite.db",
        description="SQLAlchemy database connection URL",
    )
    GOODS_DIR: str = Field(
        default="storage/goods",
        description="Directory for local goods files",
    )
    LOG_DIR: str = Field(
        default="storage/logs",
        description="Directory for application logs",
    )
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )

settings = Settings()
