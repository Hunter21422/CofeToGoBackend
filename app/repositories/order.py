from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Row, cast, extract, func, or_, select, String
from sqlalchemy.orm import selectinload

from app.models import Order, OrderItem, OrderStatusHistory, User
from app.models.enums import ACTIVE_ORDER_STATUSES, OrderPaymentStatus, OrderStatus
from app.schemas.order import AdminOrderFilter

from .base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    def _full_options(self):
        return (
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.user),
            selectinload(Order.location),
            selectinload(Order.review),
        )

    async def next_number(self, location_id: int, day: date) -> int:
        key = location_id * 100_000 + day.toordinal() % 100_000
        await self.session.execute(select(func.pg_advisory_xact_lock(key)))
        stmt = select(func.coalesce(func.max(Order.number), 0)).where(
            Order.location_id == location_id,
            Order.business_date == day,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one() + 1

    async def full(self, order_id: int, for_update: bool = False) -> Order | None:
        stmt = select(Order).where(Order.id == order_id).options(*self._full_options())
        if for_update:
            stmt = stmt.with_for_update(of=Order)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def for_user_one(self, order_id: int, user_id: int) -> Order | None:
        stmt = select(Order).where(Order.id == order_id, Order.user_id == user_id).options(*self._full_options())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_idempotency_key(self, user_id: int, key: str) -> Order | None:
        stmt = select(Order).where(Order.user_id == user_id, Order.idempotency_key == key)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def queue(self, location_id: int) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.location_id == location_id, Order.status.in_(ACTIVE_ORDER_STATUSES))
            .options(selectinload(Order.items), selectinload(Order.user))
            .order_by(Order.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def active_for_user(self, user_id: int) -> list[Order]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id, Order.status.in_(ACTIVE_ORDER_STATUSES))
            .options(selectinload(Order.items), selectinload(Order.location))
            .order_by(Order.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def page_for_user(
        self, user_id: int, statuses: list[OrderStatus], limit: int, offset: int
    ) -> tuple[list[Order], int]:
        stmt = (
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.items), selectinload(Order.location))
            .order_by(Order.created_at.desc())
        )
        if statuses:
            stmt = stmt.where(Order.status.in_(statuses))
        return await self.paginate_stmt(stmt, limit=limit, offset=offset)

    async def admin_page(self, f: AdminOrderFilter) -> tuple[list[Order], int]:
        stmt = (
            select(Order)
            .join(User, Order.user_id == User.id)
            .options(selectinload(Order.items), selectinload(Order.user), selectinload(Order.location))
            .order_by(Order.created_at.desc())
        )
        if f.location_id:
            stmt = stmt.where(Order.location_id == f.location_id)
        if f.status:
            stmt = stmt.where(Order.status.in_(f.status))
        if f.payment_status:
            stmt = stmt.where(Order.payment_status == f.payment_status)
        if f.source:
            stmt = stmt.where(Order.source == f.source)
        if f.date_from:
            stmt = stmt.where(Order.business_date >= f.date_from)
        if f.date_to:
            stmt = stmt.where(Order.business_date <= f.date_to)
        if f.user_id:
            stmt = stmt.where(Order.user_id == f.user_id)
        if f.q:
            q = f.q.strip().lstrip("#")
            stmt = stmt.where(
                or_(
                    cast(Order.number, String) == q,
                    User.phone.ilike(f"%{q}%"),
                    User.first_name.ilike(f"%{q}%"),
                    User.username.ilike(f"%{q}%"),
                )
            )
        return await self.paginate_stmt(stmt, limit=f.limit, offset=f.offset)

    async def add_status(
        self, order: Order, to: OrderStatus, changed_by_id: int | None = None, comment: str | None = None
    ) -> OrderStatusHistory:
        row = OrderStatusHistory(
            order_id=order.id,
            from_status=order.status,
            to_status=to,
            changed_by_id=changed_by_id,
            comment=comment,
        )
        order.status = to
        self.session.add(row)
        await self.session.flush()
        return row

    async def unpaid_before(self, border: datetime) -> list[Order]:
        stmt = (
            select(Order)
            .where(
                Order.status == OrderStatus.PENDING_PAYMENT,
                Order.payment_status != OrderPaymentStatus.PAID,
                Order.created_at < border,
            )
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def not_accepted_before(self, border: datetime) -> list[Order]:
        stmt = select(Order).where(Order.status == OrderStatus.NEW, Order.created_at < border)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def _done(self, location_id: int | None, d1: date, d2: date):
        conds = [Order.status == OrderStatus.COMPLETED, Order.business_date.between(d1, d2)]
        if location_id:
            conds.append(Order.location_id == location_id)
        return conds

    async def kpi(self, location_id: int | None, d1: date, d2: date) -> Row:
        stmt = select(
            func.count(Order.id).label("orders"),
            func.coalesce(func.sum(Order.total), 0).label("revenue"),
            func.count(func.distinct(Order.user_id)).label("guests"),
            func.avg(func.extract("epoch", Order.ready_at - Order.accepted_at)).label("avg_prep_sec"),
        ).where(*self._done(location_id, d1, d2))
        result = await self.session.execute(stmt)
        return result.one()

    async def revenue_by_day(self, location_id: int | None, d1: date, d2: date) -> list[Row]:
        stmt = (
            select(
                Order.business_date.label("day"),
                func.count(Order.id).label("orders"),
                func.coalesce(func.sum(Order.total), 0).label("revenue"),
            )
            .where(*self._done(location_id, d1, d2))
            .group_by(Order.business_date)
            .order_by(Order.business_date)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def top_products(self, location_id: int | None, d1: date, d2: date, limit: int = 10) -> list[Row]:
        stmt = (
            select(
                OrderItem.product_id,
                OrderItem.product_name.label("name"),
                func.sum(OrderItem.quantity).label("quantity"),
                func.sum(OrderItem.line_total).label("revenue"),
            )
            .join(Order, OrderItem.order_id == Order.id)
            .where(*self._done(location_id, d1, d2))
            .group_by(OrderItem.product_id, OrderItem.product_name)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def heatmap(self, location_id: int | None, d1: date, d2: date, tz: str = "Europe/Moscow") -> list[Row]:
        local = func.timezone(tz, Order.created_at)
        weekday = (extract("isodow", local) - 1).label("weekday")
        hour = extract("hour", local).label("hour")
        stmt = (
            select(weekday, hour, func.count(Order.id).label("orders"))
            .where(*self._done(location_id, d1, d2))
            .group_by(weekday, hour)
        )
        result = await self.session.execute(stmt)
        return list(result.all())

    async def payment_methods(self, location_id: int | None, d1: date, d2: date) -> dict[str, int]:
        stmt = (
            select(Order.payment_method, func.count(Order.id))
            .where(*self._done(location_id, d1, d2))
            .group_by(Order.payment_method)
        )
        result = await self.session.execute(stmt)
        return {str(getattr(m, "value", m)): int(n) for m, n in result.all()}

    async def count_in_period(self, location_id: int | None, d1: date, d2: date, statuses: list[OrderStatus] | None = None) -> int:
        stmt = select(func.count(Order.id)).where(Order.business_date.between(d1, d2))
        if location_id:
            stmt = stmt.where(Order.location_id == location_id)
        if statuses:
            stmt = stmt.where(Order.status.in_(statuses))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def new_customers(self, location_id: int | None, d1: date, d2: date) -> int:
        first = select(Order.user_id, func.min(Order.business_date).label("first_day")).where(Order.status == OrderStatus.COMPLETED)
        if location_id:
            first = first.where(Order.location_id == location_id)
        first = first.group_by(Order.user_id).subquery()
        stmt = select(func.count()).select_from(first).where(first.c.first_day.between(d1, d2))
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def series(self, location_id: int | None, d1: date, d2: date, group_by: str) -> list[Row]:
        if group_by == "hour":
            bucket = func.date_trunc("hour", Order.created_at)
        else:
            bucket = func.date_trunc(group_by, Order.business_date)
        stmt = (
            select(bucket.label("ts"), func.count(Order.id).label("orders"), func.coalesce(func.sum(Order.total), 0).label("revenue"))
            .where(*self._done(location_id, d1, d2))
            .group_by(bucket)
            .order_by(bucket)
        )
        result = await self.session.execute(stmt)
        return list(result.all())
