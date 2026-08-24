from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import OrderHistory

class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_order_id(self, funpay_order_id: str) -> Optional[OrderHistory]:
        """Gets an order by its FunPay ID (e.g. 'ABCD1234')."""
        result = await self.session.execute(
            select(OrderHistory).where(OrderHistory.funpay_order_id == funpay_order_id)
        )
        return result.scalar_one_or_none()

    async def is_order_processed(self, funpay_order_id: str) -> bool:
        """Checks whether the order has already been recorded/processed."""
        order = await self.get_by_order_id(funpay_order_id)
        return order is not None and order.delivery_status in ("success", "delivered", "out_of_stock", "manual")

    async def record_order(
        self,
        funpay_order_id: str,
        buyer_username: str,
        lot_title: str,
        price: float = 0.0,
        buyer_id: Optional[int] = None,
        lot_id: Optional[int] = None,
        status: str = "paid",
    ) -> OrderHistory:
        """Creates or returns an order record."""
        order = await self.get_by_order_id(funpay_order_id)
        if not order:
            order = OrderHistory(
                funpay_order_id=funpay_order_id,
                buyer_username=buyer_username,
                buyer_id=buyer_id,
                lot_id=lot_id,
                lot_title=lot_title,
                price=price,
                status=status,
                delivery_status="pending",
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(order)
            await self.session.commit()
            await self.session.refresh(order)
        return order

    async def mark_delivered(self, funpay_order_id: str, delivered_content: str) -> bool:
        """Marks an order as successfully delivered."""
        order = await self.get_by_order_id(funpay_order_id)
        if order:
            order.delivery_status = "success"
            order.delivered_content = delivered_content
            order.updated_at = datetime.now(timezone.utc)
            await self.session.commit()
            return True
        return False

    async def get_recent_orders(self, limit: int = 10) -> List[OrderHistory]:
        """Retrieves recent orders."""
        result = await self.session.execute(
            select(OrderHistory).order_by(desc(OrderHistory.created_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def get_period_stats(self, days: Optional[int] = None) -> dict:
        """Calculates sales revenue, order counts, and averages for a given time period."""
        query = select(OrderHistory)
        if days is not None:
            from datetime import timedelta
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(OrderHistory.created_at >= start_date)

        # Count total
        count_q = select(func.count(OrderHistory.id))
        if days is not None:
            count_q = count_q.where(OrderHistory.created_at >= start_date)
        total_count = (await self.session.execute(count_q)).scalar_one_or_none() or 0

        # Count successful / closed
        success_q = select(func.count(OrderHistory.id)).where(
            OrderHistory.status.in_(["closed", "delivered"]) | (OrderHistory.delivery_status == "success")
        )
        if days is not None:
            success_q = success_q.where(OrderHistory.created_at >= start_date)
        delivered_count = (await self.session.execute(success_q)).scalar_one_or_none() or 0

        # Revenue
        rev_q = select(func.sum(OrderHistory.price)).where(
            OrderHistory.status.in_(["closed", "delivered"]) | (OrderHistory.delivery_status == "success")
        )
        if days is not None:
            rev_q = rev_q.where(OrderHistory.created_at >= start_date)
        total_revenue = (await self.session.execute(rev_q)).scalar_one_or_none() or 0.0

        avg_check = (total_revenue / delivered_count) if delivered_count > 0 else 0.0

        return {
            "total_orders": total_count,
            "delivered_orders": delivered_count,
            "total_revenue": total_revenue,
            "avg_check": avg_check,
        }

    async def get_top_products(self, limit: int = 5, days: Optional[int] = None) -> List[dict]:
        """Retrieves top selling products ranked by sales count and revenue."""
        query = (
            select(
                OrderHistory.lot_title,
                func.count(OrderHistory.id).label("sales_count"),
                func.sum(OrderHistory.price).label("total_rev"),
            )
            .where(
                OrderHistory.status.in_(["closed", "delivered"]) | (OrderHistory.delivery_status == "success")
            )
            .group_by(OrderHistory.lot_title)
            .order_by(desc("sales_count"), desc("total_rev"))
            .limit(limit)
        )
        if days is not None:
            from datetime import timedelta
            start_date = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.where(OrderHistory.created_at >= start_date)

        res = await self.session.execute(query)
        rows = res.all()
        return [
            {
                "title": row[0],
                "count": row[1],
                "revenue": row[2] or 0.0,
            }
            for row in rows
        ]

    async def get_stats(self) -> dict:
        """Calculates total sales revenue and order counts."""
        return await self.get_period_stats(days=None)
