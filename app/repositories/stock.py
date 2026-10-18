from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import selectinload

from app.models import ProductVariant, StockItem

from .base import BaseRepository


class StockRepository(BaseRepository[StockItem]):
    model = StockItem

    async def full(self, item_id: int) -> StockItem | None:
        stmt = (
            select(StockItem)
            .where(StockItem.id == item_id)
            .options(
                selectinload(StockItem.product),
                selectinload(StockItem.variant).selectinload(ProductVariant.product),
                selectinload(StockItem.modifier),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    def _active(self, location_id: int):
        now = datetime.now(timezone.utc)
        return (
            StockItem.location_id == location_id,
            or_(StockItem.until.is_(None), StockItem.until > now),
        )

    async def active_for_location(self, location_id: int) -> list[StockItem]:
        stmt = (
            select(StockItem)
            .where(*self._active(location_id))
            .options(
                selectinload(StockItem.product),
                selectinload(StockItem.variant).selectinload(ProductVariant.product),
                selectinload(StockItem.modifier),
            )
            .order_by(StockItem.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def stopped_ids(self, location_id: int) -> tuple[set[int], set[int], set[int]]:
        stmt = select(StockItem.product_id, StockItem.variant_id, StockItem.modifier_id).where(*self._active(location_id))
        rows = (await self.session.execute(stmt)).all()
        products = {r.product_id for r in rows if r.product_id}
        variants = {r.variant_id for r in rows if r.variant_id}
        modifiers = {r.modifier_id for r in rows if r.modifier_id}
        return products, variants, modifiers

    async def delete_expired(self) -> int:
        stmt = delete(StockItem).where(StockItem.until.is_not(None), StockItem.until <= datetime.now(timezone.utc))
        result = await self.session.execute(stmt)
        return result.rowcount
