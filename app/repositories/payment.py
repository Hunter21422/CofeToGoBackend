from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Payment, Refund

from .base import BaseRepository


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def by_external_id(self, external_id: str, for_update: bool = False) -> Payment | None:
        stmt = select(Payment).where(Payment.external_id == external_id).options(selectinload(Payment.order))
        if for_update:
            stmt = stmt.with_for_update(of=Payment)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def for_order(self, order_id: int) -> list[Payment]:
        stmt = (
            select(Payment)
            .where(Payment.order_id == order_id)
            .options(selectinload(Payment.refunds))
            .order_by(Payment.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RefundRepository(BaseRepository[Refund]):
    model = Refund

    async def by_external_id(self, external_id: str) -> Refund | None:
        stmt = select(Refund).where(Refund.external_id == external_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
