from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import extract, func, or_, select

from app.models import Banner, Broadcast, LoyaltyAccount, Order, User
from app.models.enums import BroadcastStatus, OrderStatus

from .base import BaseRepository


class BannerRepository(BaseRepository[Banner]):
    model = Banner

    async def active(self, location_id: int) -> list[Banner]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(Banner)
            .where(
                Banner.is_active.is_(True),
                or_(Banner.starts_at.is_(None), Banner.starts_at <= now),
                or_(Banner.ends_at.is_(None), Banner.ends_at > now),
                or_(Banner.location_ids.is_(None), Banner.location_ids.any(location_id)),
            )
            .order_by(Banner.sort_order, Banner.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Banner]:
        stmt = select(Banner).order_by(Banner.sort_order, Banner.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class BroadcastRepository(BaseRepository[Broadcast]):
    model = Broadcast

    async def list_all(self, limit: int, offset: int) -> tuple[list[Broadcast], int]:
        stmt = select(Broadcast).order_by(Broadcast.created_at.desc())
        return await self.paginate_stmt(stmt, limit=limit, offset=offset)

    async def due(self) -> list[Broadcast]:
        stmt = (
            select(Broadcast)
            .where(
                Broadcast.status == BroadcastStatus.SCHEDULED,
                Broadcast.scheduled_at <= datetime.now(timezone.utc),
            )
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def segment_stmt(self, segment: dict):
        orders = (
            select(
                Order.user_id.label("user_id"),
                func.count(Order.id).label("orders"),
                func.max(Order.created_at).label("last_at"),
            )
            .where(Order.status == OrderStatus.COMPLETED)
            .group_by(Order.user_id)
        )
        if segment.get("location_ids"):
            orders = orders.where(Order.location_id.in_(segment["location_ids"]))
        orders = orders.subquery()

        stmt = (
            select(User.id, User.tg_id)
            .outerjoin(orders, orders.c.user_id == User.id)
            .outerjoin(LoyaltyAccount, LoyaltyAccount.user_id == User.id)
            .where(User.tg_id.is_not(None), User.is_blocked.is_(False))
        )
        now = datetime.now(timezone.utc)
        if segment.get("only_marketing_consent", True):
            stmt = stmt.where(User.marketing_consent.is_(True))
        if segment.get("location_ids"):
            stmt = stmt.where(orders.c.user_id.is_not(None))
        if segment.get("inactive_days"):
            border = now - timedelta(days=segment["inactive_days"])
            stmt = stmt.where(or_(orders.c.last_at.is_(None), orders.c.last_at < border))
        if segment.get("active_days"):
            border = now - timedelta(days=segment["active_days"])
            stmt = stmt.where(orders.c.last_at >= border)
        if segment.get("min_orders"):
            stmt = stmt.where(orders.c.orders >= segment["min_orders"])
        if segment.get("stamps_gte") is not None:
            stmt = stmt.where(LoyaltyAccount.stamps >= segment["stamps_gte"])
        if segment.get("has_gift") is True:
            stmt = stmt.where(LoyaltyAccount.gifts_available > 0)
        if segment.get("has_gift") is False:
            stmt = stmt.where(or_(LoyaltyAccount.gifts_available.is_(None), LoyaltyAccount.gifts_available == 0))
        if segment.get("birthday_month"):
            stmt = stmt.where(extract("month", User.birth_date) == segment["birthday_month"])
        return stmt

    async def segment_count(self, segment: dict) -> int:
        stmt = select(func.count()).select_from(self.segment_stmt(segment).subquery())
        return (await self.session.execute(stmt)).scalar_one()
