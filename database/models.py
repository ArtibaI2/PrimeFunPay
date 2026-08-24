from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    Boolean,
    Text,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def get_utc_now():
    return datetime.now(timezone.utc)

class UserAccount(Base):
    """Represents a Telegram user with their linked FunPay account (Multi-User SaaS)."""
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    telegram_username = Column(String(128), nullable=True)

    golden_key = Column(String(255), nullable=False)
    funpay_user_id = Column(BigInteger, nullable=True)
    funpay_username = Column(String(128), nullable=True)
    proxy = Column(String(255), nullable=True)

    is_active = Column(Boolean, default=True)
    auto_delivery = Column(Boolean, default=True)
    auto_raise = Column(Boolean, default=True)
    auto_response = Column(Boolean, default=True)
    smart_pricing = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    last_active_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    def __repr__(self):
        return f"<UserAccount(tg_id={self.telegram_id}, funpay_user='{self.funpay_username}')>"

class Lot(Base):
    """Represents a FunPay lot / product offer."""
    __tablename__ = "lots"

    id = Column(Integer, primary_key=True)
    funpay_lot_id = Column(BigInteger, unique=True, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category_name = Column(String(255), nullable=True)
    price = Column(Float, default=0.0)
    
    # Auto-delivery & file storage settings
    auto_delivery_enabled = Column(Boolean, default=True)
    delivery_template = Column(Text, nullable=True)  # E.g. "Ваш ключ: {key}\nИнструкция: ..."
    stock_file_name = Column(String(255), nullable=True)  # Filename in storage/goods/
    upload_url = Column(String(512), nullable=True)  # Direct cloud link (Workupload, Google Drive, Catbox, etc.)
    upload_storage_type = Column(String(64), nullable=True)  # 'workupload', 'gdrive', 'catbox', 'gofile', 'custom'
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    # Relationships
    stocks = relationship("GoodStock", back_populates="lot", cascade="all, delete-orphan")
    orders = relationship("OrderHistory", back_populates="lot")

    def __repr__(self):
        return f"<Lot(id={self.id}, funpay_lot_id={self.funpay_lot_id}, title='{self.title[:20]}')>"


class GoodStock(Base):
    """Represents a single digital item in stock (e.g. key, account login/pass, code)."""
    __tablename__ = "goods_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="SET NULL"), nullable=True, index=True)
    category_identifier = Column(String(255), nullable=True, index=True)  # For lot-independent stock matching
    
    content = Column(Text, nullable=False)  # The key/account line
    is_used = Column(Boolean, default=False, index=True)
    order_id_used = Column(String(64), nullable=True)
    
    added_at = Column(DateTime(timezone=True), default=get_utc_now)
    used_at = Column(DateTime(timezone=True), nullable=True)

    lot = relationship("Lot", back_populates="stocks")

    def __repr__(self):
        return f"<GoodStock(id={self.id}, is_used={self.is_used})>"


class OrderHistory(Base):
    """Represents a FunPay order processed by the bot."""
    __tablename__ = "orders_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    funpay_order_id = Column(String(64), unique=True, index=True, nullable=False)
    buyer_username = Column(String(128), nullable=False)
    buyer_id = Column(BigInteger, nullable=True)
    
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="SET NULL"), nullable=True)
    lot_title = Column(String(255), nullable=False)
    price = Column(Float, default=0.0)
    
    status = Column(String(64), default="paid")  # paid, delivered, closed, disputed, refunded
    delivered_content = Column(Text, nullable=True)
    delivery_status = Column(String(64), default="pending")  # pending, success, failed, manual
    
    created_at = Column(DateTime(timezone=True), default=get_utc_now)
    updated_at = Column(DateTime(timezone=True), default=get_utc_now, onupdate=get_utc_now)

    lot = relationship("Lot", back_populates="orders")

    def __repr__(self):
        return f"<OrderHistory(order_id='{self.funpay_order_id}', buyer='{self.buyer_username}', status='{self.status}')>"


class AutoResponseRule(Base):
    """Rules for auto-responding to buyer messages."""
    __tablename__ = "auto_response_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    keyword = Column(String(255), nullable=False, index=True)
    response_text = Column(Text, nullable=False)
    is_regex = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=get_utc_now)

    def __repr__(self):
        return f"<AutoResponseRule(keyword='{self.keyword}', active={self.is_active})>"
