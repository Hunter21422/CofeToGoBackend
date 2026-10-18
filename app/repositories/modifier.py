from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Modifier, ModifierGroup

from .base import BaseRepository


class ModifierGroupRepository(BaseRepository[ModifierGroup]):
    model = ModifierGroup

    async def list_with_modifiers(self) -> list[ModifierGroup]:
        stmt = (
            select(ModifierGroup)
            .options(selectinload(ModifierGroup.modifiers))
            .order_by(ModifierGroup.sort_order, ModifierGroup.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def with_modifiers(self, group_id: int) -> ModifierGroup | None:
        stmt = (
            select(ModifierGroup)
            .where(ModifierGroup.id == group_id)
            .options(selectinload(ModifierGroup.modifiers))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def modifiers_by_ids(self, ids: list[int]) -> list[Modifier]:
        if not ids:
            return []
        stmt = select(Modifier).where(Modifier.id.in_(ids)).options(selectinload(Modifier.group))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
