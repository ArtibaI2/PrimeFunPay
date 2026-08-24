from config.settings import settings
from database.engine import async_session
from database.repositories import UserRepository

async def is_user_authorized(user_id: int) -> bool:
    """Checks if a Telegram user is an admin or has registered a FunPay account."""
    if user_id in settings.TELEGRAM_ADMIN_IDS:
        return True
    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(user_id)
        return user is not None and user.is_active
