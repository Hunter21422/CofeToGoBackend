from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, or_, select, update

from app.models import PromoCode, PromoRedemption
from app.schemas.promo import PromoFilter

from .base import BaseRepository


class PromoRepository(BaseRepository[PromoCode]):
    model = PromoCode

    async def by_code(self, code: str, for_update: bool = False) -> PromoCode | None:
        stmt = select(PromoCode).where(PromoCode.code == code.strip().upper())
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def codes_exist(self, codes: list[str]) -> set[str]:
        stmt = select(PromoCode.code).where(PromoCode.code.in_(codes))
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def admin_page(self, f: PromoFilter) -> tuple[list[PromoCode], int]:
        stmt = select(PromoCode).order_by(PromoCode.id.desc())
        if f.q:
            stmt = stmt.where(PromoCode.code.ilike(f"%{f.q.upper()}%"))
        if f.is_active is not None:
            stmt = stmt.where(PromoCode.is_active.is_(f.is_active))
        if f.type:
            stmt = stmt.where(PromoCode.type == f.type)
        if f.expired is not None:
            now = datetime.now(timezone.utc)
            expired = PromoCode.ends_at < now
            stmt = stmt.where(expired if f.expired else or_(PromoCode.ends_at.is_(None), ~expired))
        return await self.paginate_stmt(stmt, limit=f.limit, offset=f.offset)

    async def use(self, promo_id: int) -> int:
        stmt = (
            update(PromoCode)
            .where(PromoCode.id == promo_id)
            .values(used_count=PromoCode.used_count + 1)
            .returning(PromoCode.used_count)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def unuse(self, promo_id: int) -> None:
        stmt = (
            update(PromoCode)
            .where(PromoCode.id == promo_id, PromoCode.used_count > 0)
            .values(used_count=PromoCode.used_count - 1)
        )
        await self.session.execute(stmt)

    async def user_uses(self, promo_id: int, user_id: int) -> int:
        stmt = select(func.count(PromoRedemption.id)).where(
            PromoRedemption.promo_code_id == promo_id,
            PromoRedemption.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def redemption_by_order(self, order_id: int) -> PromoRedemption | None:
        stmt = select(PromoRedemption).where(PromoRedemption.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
