from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func, select

from app.models import LoyaltyAccount, LoyaltyTransaction
from app.models.enums import LoyaltyTxType

from .base import BaseRepository


class LoyaltyRepository(BaseRepository[LoyaltyAccount]):
    model = LoyaltyAccount

    async def by_user(self, user_id: int) -> LoyaltyAccount | None:
        stmt = select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create(self, user_id: int) -> LoyaltyAccount:
        account = await self.by_user(user_id)
        if account is None:
            account = await self.create(user_id=user_id)
        return account

    async def lock(self, user_id: int) -> LoyaltyAccount:
        stmt = select(LoyaltyAccount).where(LoyaltyAccount.user_id == user_id).with_for_update()
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if account is None:
            account = await self.create(user_id=user_id)
        return account

    async def add_tx(
        self,
        account: LoyaltyAccount,
        type: LoyaltyTxType,
        stamps_delta: int = 0,
        gifts_delta: int = 0,
        order_id: int | None = None,
        staff_id: int | None = None,
        location_id: int | None = None,
        reason: str | None = None,
    ) -> LoyaltyTransaction:
        tx = LoyaltyTransaction(
            user_id=account.user_id,
            type=type,
            stamps_delta=stamps_delta,
            gifts_delta=gifts_delta,
            stamps_after=account.stamps,
            gifts_after=account.gifts_available,
            order_id=order_id,
            staff_id=staff_id,
            location_id=location_id,
            reason=reason,
        )
        self.session.add(tx)
        await self.session.flush()
        return tx

    async def history(
        self, user_id: int, types: list[LoyaltyTxType], limit: int, offset: int
    ) -> tuple[list[LoyaltyTransaction], int]:
        stmt = (
            select(LoyaltyTransaction)
            .where(LoyaltyTransaction.user_id == user_id)
            .order_by(LoyaltyTransaction.created_at.desc(), LoyaltyTransaction.id.desc())
        )
        if types:
            stmt = stmt.where(LoyaltyTransaction.type.in_(types))
        return await self.paginate_stmt(stmt, limit=limit, offset=offset)

    async def stamps_given_by_order(self, order_id: int) -> bool:
        stmt = select(LoyaltyTransaction.id).where(
            LoyaltyTransaction.order_id == order_id,
            LoyaltyTransaction.type == LoyaltyTxType.STAMP_EARNED,
        )
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def stale(self, border: datetime, gifts: bool = False) -> list[LoyaltyAccount]:
        has = LoyaltyAccount.gifts_available > 0 if gifts else LoyaltyAccount.stamps > 0
        since = func.coalesce(LoyaltyAccount.last_activity_at, LoyaltyAccount.created_at)
        stmt = (
            select(LoyaltyAccount)
            .where(has, since < border)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_tx(self, type: LoyaltyTxType, d1: date, d2: date, location_id: int | None = None) -> int:
        stmt = select(func.count(LoyaltyTransaction.id)).where(
            LoyaltyTransaction.type == type,
            func.date(LoyaltyTransaction.created_at).between(d1, d2),
        )
        if location_id:
            stmt = stmt.where(LoyaltyTransaction.location_id == location_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()
