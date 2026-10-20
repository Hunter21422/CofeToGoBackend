from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import LoyaltyTxType, OrderStatus
from app.repositories import LoyaltyRepository, OrderRepository, ReviewRepository
from app.schemas.stats import DashboardOut, HourHeatmapCell, KpiOut, StatsFilter, TimeSeriesPoint, TopProductOut

BAD_STATUSES = [OrderStatus.CANCELLED, OrderStatus.REJECTED, OrderStatus.EXPIRED]


class StatsService:
    def __init__(self, session: AsyncSession):
        self.orders = OrderRepository(session)
        self.reviews = ReviewRepository(session)
        self.loyalty = LoyaltyRepository(session)
    async def kpi(self, location_id: int | None, d1, d2) -> KpiOut:
        k = await self.orders.kpi(location_id, d1, d2)
        all_orders = await self.orders.count_in_period(location_id, d1, d2)
        bad = await self.orders.count_in_period(location_id, d1, d2, BAD_STATUSES)
        new = await self.orders.new_customers(location_id, d1, d2)
        return KpiOut(
            revenue=k.revenue,
            orders_count=k.orders,
            avg_check=round(k.revenue / k.orders) if k.orders else 0,
            new_customers=new,
            returning_customers=max(k.guests - new, 0),
            gifts_redeemed=await self.loyalty.count_tx(LoyaltyTxType.GIFT_REDEEMED, d1, d2, location_id),
            stamps_issued=await self.loyalty.count_tx(LoyaltyTxType.STAMP_EARNED, d1, d2, location_id),
            avg_prep_seconds=round(k.avg_prep_sec or 0),
            cancel_rate=round(bad / all_orders, 4) if all_orders else 0.0,
            avg_rating=await self.reviews.avg_rating(location_id),
        )
    async def dashboard(self, f: StatsFilter) -> DashboardOut:
        kpi = await self.kpi(f.location_id, f.date_from, f.date_to)
        days = (f.date_to - f.date_from).days + 1
        prev_to = f.date_from - timedelta(days=1)
        prev_from = prev_to - timedelta(days=days - 1)
        kpi.prev_period = await self.kpi(f.location_id, prev_from, prev_to)
        rows = await self.orders.series(f.location_id, f.date_from, f.date_to, f.group_by)
        series = [
            TimeSeriesPoint(ts=r.ts if r.ts.tzinfo else r.ts.replace(tzinfo=timezone.utc), revenue=r.revenue, orders=r.orders)
            for r in rows
        ]
        top = [
            TopProductOut(product_id=r.product_id, name=r.name, quantity=r.quantity, revenue=r.revenue)
            for r in await self.orders.top_products(f.location_id, f.date_from, f.date_to)
        ]
        return DashboardOut(
            kpi=kpi,
            series=series,
            top_products=top,
            heatmap=await self.heatmap(f),
            payment_methods=await self.orders.payment_methods(f.location_id, f.date_from, f.date_to),
        )
    async def heatmap(self, f: StatsFilter) -> list[HourHeatmapCell]:
        rows = await self.orders.heatmap(f.location_id, f.date_from, f.date_to)
        return [HourHeatmapCell(weekday=int(r.weekday), hour=int(r.hour), orders=r.orders) for r in rows]
