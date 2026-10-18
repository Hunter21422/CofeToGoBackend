from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Modifier, ModifierGroup
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
