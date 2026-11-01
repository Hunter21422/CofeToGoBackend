from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, Order, Staff
from app.repositories import LocationRepository
from app.schemas.location import LocationCreate, LocationHoursUpdate, LocationUpdate

from .errors import Conflict, NotFound


class LocationService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.locations = LocationRepository(session)
    async def get_location(self, location_id: int) -> Location:
        location = await self.locations.with_hours(location_id)
        if location is None or location.deleted_at is not None:
            raise NotFound("Кофейня не найдена")
        return location
    async def list_for_guest(self) -> list[Location]:
        return await self.locations.list_active()
    async def list_for_admin(self) -> list[Location]:
        return await self.locations.list_all()
    async def create_location(self, data: LocationCreate) -> Location:
        existing = await self.locations.by_slug(data.slug)
        if existing is not None:
            raise Conflict("Точка с таким адресом уже есть")
        location = await self.locations.create(**data.model_dump(exclude={"hours"}))
        return await self.get_location(location.id)
    async def update_location(self, location_id: int, data: LocationUpdate) -> Location:
        location = await self.get_location(location_id)
        if data.slug is not None and data.slug != location.slug:
            existing = await self.locations.by_slug(data.slug)
            if existing is not None:
                raise Conflict("Точка с таким адресом уже есть")
        await self.locations.update(location, **data.model_dump(exclude_unset=True))
        return location
    async def set_hours(self,location_id: int, data: LocationHoursUpdate)->Location:
        location=await self.get_location(location_id)
        await self.locations.set_hours(location, [h.model_dump() for h in data.hours])
        return await self.get_location(location_id)
    async def delete_location(self, location_id: int) -> bool:
        location = await self.get_location(location_id)
        staff = await self.session.scalar(select(func.count(Staff.id)).where(Staff.location_id == location_id, Staff.is_active.is_(True)))
        if staff:
            raise Conflict(f"К точке привязаны сотрудники ({staff}). Переведите их на другую точку в разделе «Команда» и удалите снова")
        orders = await self.session.scalar(select(func.count(Order.id)).where(Order.location_id == location_id))
        if not orders:
            await self.locations.delete(location)
            return True
        location.deleted_at = datetime.now(timezone.utc)
        location.is_active = False
        location.accepts_orders = False
        location.slug = f"{location.slug}-del{location.id}"[:64]
        await self.session.flush()
        return False
