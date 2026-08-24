from dataclasses import dataclass
from typing import Optional
from datetime import datetime

@dataclass
class UserProfile:
    user_id: int
    username: str
    balance_rub: float = 0.0
    balance_usd: float = 0.0
    balance_eur: float = 0.0
    balance_available_rub: float = 0.0
    balance_available_usd: float = 0.0
    balance_available_eur: float = 0.0
    active_orders_count: int = 0
    unread_chats_count: int = 0
    is_authenticated: bool = False

@dataclass
class FunPayOrder:
    order_id: str
    lot_id: Optional[int] = None
    title: str = ""
    buyer_username: str = "Unknown"
    buyer_id: Optional[int] = None
    price: float = 0.0
    currency: str = "RUB"
    status: str = "paid"  # paid, closed, refunded, disputed
    chat_node_id: Optional[int] = None
    is_closed: bool = False
    is_paid: bool = True
    url: str = ""
    created_at: Optional[datetime] = None

@dataclass
class ChatMessage:
    message_id: int
    chat_node_id: int
    sender_username: str
    sender_id: int
    text: str
    is_my_message: bool = False
    is_system: bool = False
    created_at: Optional[datetime] = None

@dataclass
class RaiseResult:
    game_id: int
    node_id: int
    game_name: str = ""
    category_name: str = ""
    success: bool = False
    message: str = ""
    wait_time_seconds: Optional[int] = None
