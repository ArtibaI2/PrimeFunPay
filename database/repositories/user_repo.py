from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import UserAccount
from utils.logger import logger

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> Optional[UserAccount]:
        """Fetches a user account by their Telegram ID."""
        query = select(UserAccount).where(UserAccount.telegram_id == tg_id)
        res = await self.session.execute(query)
        return res.scalar_one_or_none()

    async def get_all_active(self) -> List[UserAccount]:
        """Fetches all active registered users."""
        query = select(UserAccount).where(UserAccount.is_active == True)
        res = await self.session.execute(query)
        return list(res.scalars().all())

    async def register_or_update(
        self,
        telegram_id: int,
        golden_key: str,
        funpay_user_id: Optional[int] = None,
        funpay_username: Optional[str] = None,
        telegram_username: Optional[str] = None,
        proxy: Optional[str] = None,
    ) -> UserAccount:
        """Registers a new user or updates an existing one."""
        user = await self.get_by_tg_id(telegram_id)
        if user:
            user.golden_key = golden_key
            if funpay_user_id:
                user.funpay_user_id = funpay_user_id
            if funpay_username:
                user.funpay_username = funpay_username
            if telegram_username:
                user.telegram_username = telegram_username
            if proxy is not None:
                user.proxy = proxy
            user.is_active = True
            user.last_active_at = datetime.now(timezone.utc)
        else:
            user = UserAccount(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                golden_key=golden_key,
                funpay_user_id=funpay_user_id,
                funpay_username=funpay_username,
                proxy=proxy,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                last_active_at=datetime.now(timezone.utc),
            )
            self.session.add(user)

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_settings(
        self,
        telegram_id: int,
        auto_delivery: Optional[bool] = None,
        auto_raise: Optional[bool] = None,
        auto_response: Optional[bool] = None,
        smart_pricing: Optional[bool] = None,
    ) -> Optional[UserAccount]:
        user = await self.get_by_tg_id(telegram_id)
        if not user:
            return None
        if auto_delivery is not None:
            user.auto_delivery = auto_delivery
        if auto_raise is not None:
            user.auto_raise = auto_raise
        if auto_response is not None:
            user.auto_response = auto_response
        if smart_pricing is not None:
            user.smart_pricing = smart_pricing
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete_user(self, telegram_id: int) -> bool:
        stmt = delete(UserAccount).where(UserAccount.telegram_id == telegram_id)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount > 0
