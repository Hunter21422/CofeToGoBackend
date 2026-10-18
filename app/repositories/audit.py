from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import AuditLog
from app.schemas.audit import AuditFilter

from .base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        actor_user_id: int | None,
        action: str,
        entity_type: str,
        entity_id: int | str | None = None,
        before: dict[str, Any] | None = None,
        after: dict[str, Any] | None = None,
        ip: str | None = None,
    ) -> AuditLog:
        return await self.create(
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            before=before,
            after=after,
            ip=ip,
        )

    async def admin_page(self, f: AuditFilter) -> tuple[list[AuditLog], int]:
        stmt = select(AuditLog).options(selectinload(AuditLog.actor)).order_by(AuditLog.created_at.desc())
        if f.actor_user_id:
            stmt = stmt.where(AuditLog.actor_user_id == f.actor_user_id)
        if f.entity_type:
            stmt = stmt.where(AuditLog.entity_type == f.entity_type)
        if f.entity_id:
            stmt = stmt.where(AuditLog.entity_id == f.entity_id)
        if f.action:
            stmt = stmt.where(AuditLog.action == f.action)
        if f.date_from:
            stmt = stmt.where(func.date(AuditLog.created_at) >= f.date_from)
        if f.date_to:
            stmt = stmt.where(func.date(AuditLog.created_at) <= f.date_to)
        return await self.paginate_stmt(stmt, limit=f.limit, offset=f.offset)
