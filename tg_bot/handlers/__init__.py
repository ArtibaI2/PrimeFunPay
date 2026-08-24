from aiogram import Dispatcher
from .auth import router as auth_router
from .admin import router as admin_router
from .goods import router as goods_router
from .chat import router as chat_center_router
from .auto_response import router as auto_response_router
from .reply import router as reply_router

def register_all_handlers(dp: Dispatcher) -> None:
    dp.include_router(auth_router)
    dp.include_router(admin_router)
    dp.include_router(goods_router)
    dp.include_router(chat_center_router)
    dp.include_router(auto_response_router)
    dp.include_router(reply_router)

__all__ = [
    "register_all_handlers",
    "auth_router",
    "admin_router",
    "goods_router",
    "chat_center_router",
    "auto_response_router",
    "reply_router",
]
