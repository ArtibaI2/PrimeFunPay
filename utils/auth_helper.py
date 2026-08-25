from config.settings import settings
from database.engine import async_session
from database.repositories import UserRepository
from funpay.client import FunPayClient

async def is_user_authorized(user_id: int) -> bool:
    """Checks if a Telegram user is an admin or has registered a FunPay account."""
    if user_id in settings.TELEGRAM_ADMIN_IDS:
        return True
    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(user_id)
        return user is not None and user.is_active

async def get_or_create_client_for_user(tg_id: int, fallback_client: FunPayClient) -> FunPayClient:
    """Returns a FunPayClient instance initialized with the user's specific golden_key if registered."""
    async with async_session() as session:
        user_repo = UserRepository(session)
        user = await user_repo.get_by_tg_id(tg_id)
        if user and user.golden_key:
            return FunPayClient(
                golden_key=user.golden_key,
                user_agent=settings.FUNPAY_USER_AGENT,
                proxy=user.proxy or settings.FUNPAY_PROXY,
            )
    return fallback_client

