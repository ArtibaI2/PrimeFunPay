from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import GoodStock, Lot
from utils.logger import logger

class GoodsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_stock_items(self, items: List[str], lot_id: Optional[int] = None, category_identifier: Optional[str] = None) -> int:
        """Adds a list of stock item strings (keys/accounts) to the database."""
        added_count = 0
        for item in items:
            clean_item = item.strip()
            if not clean_item:
                continue
            stock = GoodStock(
                lot_id=lot_id,
                category_identifier=category_identifier,
                content=clean_item,
                is_used=False,
                added_at=datetime.now(timezone.utc),
            )
            self.session.add(stock)
            added_count += 1
        await self.session.commit()
        return added_count

    # Alias for convenience
    add_items = add_stock_items

    async def get_available_count(self, lot_id: Optional[int] = None, category_identifier: Optional[str] = None) -> int:
        """Returns the number of unused items available for a specific lot or category."""
        query = select(func.count(GoodStock.id)).where(GoodStock.is_used == False)  # noqa: E712
        if lot_id is not None:
            query = query.where(GoodStock.lot_id == lot_id)
        elif category_identifier is not None:
            query = query.where(GoodStock.category_identifier == category_identifier)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() or 0

    async def pop_available_item(self, lot_id: Optional[int] = None, category_identifier: Optional[str] = None, order_id: Optional[str] = None) -> Optional[str]:
        """Atomically fetches and marks the next available stock item as used."""
        query = select(GoodStock).where(GoodStock.is_used == False)  # noqa: E712
        if lot_id is not None:
            query = query.where(GoodStock.lot_id == lot_id)
        elif category_identifier is not None:
            query = query.where(GoodStock.category_identifier == category_identifier)
        
        query = query.order_by(GoodStock.id.asc()).limit(1).with_for_update()

        result = await self.session.execute(query)
        stock_item = result.scalar_one_or_none()

        if stock_item:
            stock_item.is_used = True
            stock_item.used_at = datetime.now(timezone.utc)
            stock_item.order_id_used = order_id
            await self.session.commit()
            return stock_item.content
        return None

    async def get_all_stock_summary(self) -> List[dict]:
        """Returns summary of available stocks across all lots."""
        query = (
            select(
                GoodStock.lot_id,
                GoodStock.category_identifier,
                func.count(GoodStock.id).label("total"),
                func.sum(func.case((GoodStock.is_used == False, 1), else_=0)).label("available"),
            )
            .group_by(GoodStock.lot_id, GoodStock.category_identifier)
        )
        result = await self.session.execute(query)
        rows = result.all()
        summary = []
        for r in rows:
            summary.append({
                "lot_id": r.lot_id,
                "category_identifier": r.category_identifier,
                "total": r.total,
                "available": r.available or 0,
            })
        return summary

    async def clear_unused(self, lot_id: Optional[int] = None, category_identifier: Optional[str] = None) -> int:
        """Deletes all unused stock items for a lot."""
        from sqlalchemy import delete
        stmt = delete(GoodStock).where(GoodStock.is_used == False)
        if lot_id is not None:
            stmt = stmt.where(GoodStock.lot_id == lot_id)
        elif category_identifier is not None:
            stmt = stmt.where(GoodStock.category_identifier == category_identifier)
        res = await self.session.execute(stmt)
        await self.session.commit()
        return res.rowcount

    count_available = get_available_count
