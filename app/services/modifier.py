from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Modifier, ModifierGroup, Product, ProductModifierGroup
from app.repositories import ModifierGroupRepository
from app.schemas.modifier import ModifierGroupCreate, ModifierGroupUpdate

from .errors import NotFound, ServiceError


class ModifierService:
    def __init__(self, session: AsyncSession):
        self.groups = ModifierGroupRepository(session)

    async def list_groups(self) -> list[ModifierGroup]:
        return await self.groups.list_with_modifiers()

    async def get_group(self, group_id: int) -> ModifierGroup:
        group = await self.groups.with_modifiers(group_id)
        if group is None:
            raise NotFound("Группа добавок не найдена")
        return group

    async def create_group(self, data: ModifierGroupCreate) -> ModifierGroup:
        group = ModifierGroup(
            name=data.name, min_select=data.min_select, max_select=data.max_select, sort_order=data.sort_order,
            modifiers=[Modifier(**m.model_dump(exclude={"id", "sort_order"}), sort_order=i) for i, m in enumerate(data.modifiers)],
        )
        await self.groups.add(group)
        return await self.get_group(group.id)

    async def update_group(self, group_id: int, data: ModifierGroupUpdate) -> ModifierGroup:
        group = await self.get_group(group_id)
        fields = data.model_dump(exclude_unset=True, exclude={"modifiers"})
        await self.groups.update(group, **fields)
        if data.modifiers is not None:
            current = {m.id: m for m in group.modifiers}
            keep = []
            for i, m in enumerate(data.modifiers):
                values = m.model_dump(exclude={"id", "sort_order"})
                modifier = current.get(m.id) if m.id else None
                if modifier is None:
                    modifier = Modifier(**values)
                else:
                    for k, v in values.items():
                        setattr(modifier, k, v)
                modifier.sort_order = i
                keep.append(modifier)
            group.modifiers[:] = keep
        if group.max_select < group.min_select:
            raise ServiceError("«Максимум» не может быть меньше «минимума»")
        await self.groups.session.flush()
        group_id = group.id
        self.groups.session.expire(group)
        return await self.get_group(group_id)

    async def delete_group(self, group_id: int) -> None:
        group = await self.get_group(group_id)
        await self.groups.delete(group)

    async def product_ids(self, group_id: int) -> list[int]:
        await self.get_group(group_id)
        rows = await self.groups.session.execute(select(ProductModifierGroup.product_id).where(ProductModifierGroup.group_id == group_id))
        return [r[0] for r in rows.all()]

    async def set_products(self, group_id: int, product_ids: list[int]) -> list[int]:
        await self.get_group(group_id)
        session = self.groups.session
        wanted = set(product_ids)
        if wanted:
            found = set((await session.execute(select(Product.id).where(Product.id.in_(wanted)))).scalars().all())
            if found != wanted:
                raise NotFound("Часть товаров не найдена")
        current = set(await self.product_ids(group_id))
        gone = current - wanted
        if gone:
            await session.execute(delete(ProductModifierGroup).where(ProductModifierGroup.group_id == group_id, ProductModifierGroup.product_id.in_(gone)))
        for product_id in wanted - current:
            last = (await session.execute(select(func.max(ProductModifierGroup.sort_order)).where(ProductModifierGroup.product_id == product_id))).scalar()
            session.add(ProductModifierGroup(product_id=product_id, group_id=group_id, sort_order=(last if last is not None else -1) + 1, modifier_ids=None))
        await session.flush()
        return sorted(wanted)
