from typing import List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Lot

class LotRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, lot_id: int) -> Optional[Lot]:
        """Finds a lot by its internal database ID."""
        result = await self.session.execute(
            select(Lot).where(Lot.id == lot_id)
        )
        return result.scalar_one_or_none()

    async def get_by_funpay_id(self, funpay_lot_id: int) -> Optional[Lot]:
        """Finds a lot by its FunPay ID."""
        result = await self.session.execute(
            select(Lot).where(Lot.funpay_lot_id == funpay_lot_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        funpay_lot_id: int,
        title: str,
        price: float = 0.0,
        category_name: Optional[str] = None,
        delivery_template: Optional[str] = None,
        description: Optional[str] = None,
        upload_url: Optional[str] = None,
        upload_storage_type: Optional[str] = None,
    ) -> Lot:
        """Gets existing lot or creates a new lot record."""
        lot = await self.get_by_funpay_id(funpay_lot_id)
        if not lot:
            lot = Lot(
                funpay_lot_id=funpay_lot_id,
                title=title,
                price=price,
                description=description,
                category_name=category_name,
                delivery_template=delivery_template or "Ваш заказ:\n{item}\n\nСпасибо за покупку!",
                upload_url=upload_url,
                upload_storage_type=upload_storage_type,
                auto_delivery_enabled=True,
                is_active=True,
            )
            self.session.add(lot)
            await self.session.commit()
            await self.session.refresh(lot)
        else:
            if description:
                lot.description = description
            if upload_url:
                lot.upload_url = upload_url
            if upload_storage_type:
                lot.upload_storage_type = upload_storage_type
            if price > 0:
                lot.price = price
            await self.session.commit()
        return lot

    async def create_product(
        self,
        title: str,
        price: float = 0.0,
        description: Optional[str] = None,
        delivery_template: Optional[str] = None,
        upload_url: Optional[str] = None,
        upload_storage_type: Optional[str] = None,
        funpay_lot_id: Optional[int] = None,
        category_name: Optional[str] = None,
    ) -> Lot:
        """Creates a new product card with full form data."""
        if not funpay_lot_id:
            import time
            funpay_lot_id = int(time.time())

        lot = Lot(
            funpay_lot_id=funpay_lot_id,
            title=title,
            description=description,
            price=price,
            category_name=category_name or "Цифровые товары",
            delivery_template=delivery_template or "Спасибо за покупку!\nВаш товар / ссылка:\n{link}",
            upload_url=upload_url,
            upload_storage_type=upload_storage_type or "Cloud",
            auto_delivery_enabled=True,
            is_active=True,
        )
        self.session.add(lot)
        await self.session.commit()
        await self.session.refresh(lot)
        return lot

    async def get_all_active(self) -> List[Lot]:
        """Returns all active lots."""
        result = await self.session.execute(
            select(Lot).where(Lot.is_active == True).order_by(Lot.id.desc())  # noqa: E712
        )
        return list(result.scalars().all())

    get_active_lots = get_all_active

    async def get_all(self) -> List[Lot]:
        """Returns all configured lots."""
        result = await self.session.execute(select(Lot).order_by(Lot.id.desc()))
        return list(result.scalars().all())

    async def set_active_status(self, funpay_lot_id: int, is_active: bool) -> bool:
        """Enables or disables a lot in the bot."""
        lot = await self.get_by_funpay_id(funpay_lot_id)
        if lot:
            lot.is_active = is_active
            await self.session.commit()
            return True
        return False

    async def update_template(self, funpay_lot_id: int, template: str) -> bool:
        """Updates the delivery template for a lot."""
        lot = await self.get_by_funpay_id(funpay_lot_id)
        if lot:
            lot.delivery_template = template
            await self.session.commit()
            return True
        return False
