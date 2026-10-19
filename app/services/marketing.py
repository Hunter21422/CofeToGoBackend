from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Banner, Broadcast
from app.models.enums import BroadcastStatus
from app.repositories import BannerRepository, BroadcastRepository
from app.schemas.marketing import BannerCreate, BannerUpdate, BroadcastCreate, BroadcastSegment, BroadcastUpdate

from .errors import Conflict, NotFound, ServiceError

EDITABLE = (BroadcastStatus.DRAFT, BroadcastStatus.SCHEDULED)


class MarketingService:
    def __init__(self, session: AsyncSession):
        self.banners = BannerRepository(session)
        self.broadcasts = BroadcastRepository(session)
    async def get_banner(self, banner_id: int) -> Banner:
        banner = await self.banners.get(banner_id)
        if banner is None:
            raise NotFound("Баннер не найден")
        return banner
    async def active_banners(self, location_id: int) -> list[Banner]:
        return await self.banners.active(location_id)
    async def list_banners(self) -> list[Banner]:
        return await self.banners.list_all()
    async def create_banner(self, data: BannerCreate) -> Banner:
        return await self.banners.create(**data.model_dump())
    async def update_banner(self, banner_id: int, data: BannerUpdate) -> Banner:
        banner = await self.get_banner(banner_id)
        await self.banners.update(banner, **data.model_dump(exclude_unset=True))
        return banner
    async def delete_banner(self, banner_id: int) -> None:
        banner = await self.get_banner(banner_id)
        await self.banners.delete(banner)
    async def get_broadcast(self, broadcast_id: int) -> Broadcast:
        broadcast = await self.broadcasts.get(broadcast_id)
        if broadcast is None:
            raise NotFound("Рассылка не найдена")
        return broadcast
    async def list_broadcasts(self, limit: int, offset: int) -> tuple[list[Broadcast], int]:
        return await self.broadcasts.list_all(limit, offset)
    async def create_broadcast(self, data: BroadcastCreate, created_by_id: int) -> Broadcast:
        fields = data.model_dump()
        if fields.get("button_text") and not fields.get("button_url"):
            fields["button_url"] = get_settings().webapp_url
        status = BroadcastStatus.SCHEDULED if data.scheduled_at else BroadcastStatus.DRAFT
        if data.scheduled_at and data.scheduled_at <= datetime.now(timezone.utc):
            raise ServiceError("Время отправки уже прошло")
        return await self.broadcasts.create(**fields, status=status, created_by_id=created_by_id)
    async def update_broadcast(self, broadcast_id: int, data: BroadcastUpdate) -> Broadcast:
        broadcast = await self.get_broadcast(broadcast_id)
        if broadcast.status not in EDITABLE:
            raise Conflict("Рассылка уже отправляется или отправлена")
        fields = data.model_dump(exclude_unset=True)
        if "scheduled_at" in fields:
            if fields["scheduled_at"] and fields["scheduled_at"] <= datetime.now(timezone.utc):
                raise ServiceError("Время отправки уже прошло")
            fields["status"] = BroadcastStatus.SCHEDULED if fields["scheduled_at"] else BroadcastStatus.DRAFT
        await self.broadcasts.update(broadcast, **fields)
        return broadcast
    async def send_now(self, broadcast_id: int) -> Broadcast:
        broadcast = await self.get_broadcast(broadcast_id)
        if broadcast.status not in EDITABLE:
            raise Conflict("Рассылка уже отправляется или отправлена")
        await self.broadcasts.update(broadcast, status=BroadcastStatus.SCHEDULED, scheduled_at=datetime.now(timezone.utc))
        return broadcast
    async def segment_count(self, segment: BroadcastSegment) -> int:
        return await self.broadcasts.segment_count(segment.model_dump())
    async def delete_broadcast(self, broadcast_id: int) -> None:
        broadcast = await self.get_broadcast(broadcast_id)
        if broadcast.status not in EDITABLE:
            raise Conflict("Отправленную рассылку удалить нельзя")
        await self.broadcasts.delete(broadcast)
