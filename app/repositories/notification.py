from __future__ import annotations

from sqlalchemy import select

from app.models import NotificationLog
from app.models.enums import NotificationStatus

from .base import BaseRepository


class NotificationLogRepository(BaseRepository[NotificationLog]):
    model = NotificationLog

    async def pending(self, limit: int = 100) -> list[NotificationLog]:
        stmt = (
            select(NotificationLog)
            .where(NotificationLog.status == NotificationStatus.PENDING)
            .order_by(NotificationLog.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def for_user(self, user_id: int, limit: int = 20) -> list[NotificationLog]:
        stmt = (
            select(NotificationLog)
            .where(NotificationLog.user_id == user_id)
            .order_by(NotificationLog.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
