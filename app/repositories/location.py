from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Location, LocationHours, LocationSpecialDay

from .base import BaseRepository


class LocationRepository(BaseRepository[Location]):
    model = Location

    async def list_active(self) -> list[Location]:
        stmt = (
            select(Location)
            .where(Location.is_active.is_(True))
            .options(selectinload(Location.hours), selectinload(Location.special_days))
            .order_by(Location.sort_order, Location.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[Location]:
        stmt = (
            select(Location)
            .options(selectinload(Location.hours), selectinload(Location.special_days))
            .order_by(Location.sort_order, Location.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def with_hours(self, location_id: int) -> Location | None:
        stmt = (
            select(Location)
            .where(Location.id == location_id)
            .options(selectinload(Location.hours), selectinload(Location.special_days))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_slug(self, slug: str) -> Location | None:
        stmt = select(Location).where(Location.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def special_day(self, location_id: int, day: date) -> LocationSpecialDay | None:
        stmt = select(LocationSpecialDay).where(
            LocationSpecialDay.location_id == location_id,
            LocationSpecialDay.date == day,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_hours(self, location: Location, hours: list[dict]) -> None:
        location.hours.clear()
        await self.session.flush()
        for h in hours:
            location.hours.append(LocationHours(**h))
        await self.session.flush()
