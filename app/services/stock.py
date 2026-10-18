from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import StockItem
from app.repositories import LocationRepository, ModifierGroupRepository, ProductRepository, StockRepository
from app.schemas.stock import StockItemCreate

from .errors import NotFound, ServiceError


class StockService:
    def __init__(self, session: AsyncSession):
        self.stock = StockRepository(session)
        self.locations = LocationRepository(session)
        self.products = ProductRepository(session)
        self.modifiers = ModifierGroupRepository(session)
    async def list_for_location(self, location_id: int) -> list[StockItem]:
        return await self.stock.active_for_location(location_id)
    async def stop(self, location_id: int, data: StockItemCreate, staff_id: int | None = None) -> StockItem:
        location = await self.locations.get(location_id)
        if location is None:
            raise NotFound("Кофейня не найдена")
        if data.product_id and await self.products.get(data.product_id) is None:
            raise NotFound("Товар не найден")
        if data.variant_id and not await self.products.variants_by_ids([data.variant_id]):
            raise NotFound("Размер не найден")
        if data.modifier_id and not await self.modifiers.modifiers_by_ids([data.modifier_id]):
            raise NotFound("Добавка не найдена")
        until = data.until
        if data.until_end_of_day:
            tz = ZoneInfo(location.timezone)
            tomorrow = datetime.now(tz).date() + timedelta(days=1)
            until = datetime.combine(tomorrow, time(0, 0), tzinfo=tz)
        if until is not None and until <= datetime.now(until.tzinfo):
            raise ServiceError("Время окончания уже прошло")
        item = await self.stock.create(
            location_id=location_id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            modifier_id=data.modifier_id,
            until=until,
            reason=data.reason,
            created_by_id=staff_id,
        )
        return await self.stock.full(item.id)
    async def resume(self, location_id: int, item_id: int) -> None:
        item = await self.stock.get(item_id)
        if item is None or item.location_id != location_id:
            raise NotFound("Позиция стоп-листа не найдена")
        await self.stock.delete(item)
    async def cleanup(self) -> int:
        return await self.stock.delete_expired()
