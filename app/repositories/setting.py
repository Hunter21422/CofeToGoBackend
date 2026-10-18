from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models import Setting

from .base import BaseRepository


class SettingRepository(BaseRepository[Setting]):
    model = Setting

    async def _row(self, key: str, location_id: int | None) -> Setting | None:
        stmt = select(Setting).where(Setting.key == key)
        if location_id is None:
            stmt = stmt.where(Setting.location_id.is_(None))
        else:
            stmt = stmt.where(Setting.location_id == location_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_value(self, key: str, location_id: int | None = None, default: Any = None) -> Any:
        if location_id is not None:
            row = await self._row(key, location_id)
            if row is not None:
                return row.value
        row = await self._row(key, None)
        return row.value if row is not None else default

    async def set_value(self, key: str, value: Any, location_id: int | None = None) -> Setting:
        row = await self._row(key, location_id)
        if row is None:
            return await self.create(key=key, value=value, location_id=location_id)
        row.value = value
        await self.session.flush()
        return row

    async def all_global(self) -> dict[str, Any]:
        stmt = select(Setting).where(Setting.location_id.is_(None))
        result = await self.session.execute(stmt)
        return {s.key: s.value for s in result.scalars().all()}
