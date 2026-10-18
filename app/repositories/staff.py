from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models import Staff, User

from .base import BaseRepository


class StaffRepository(BaseRepository[Staff]):
    model = Staff

    async def by_user_id(self, user_id: int) -> Staff | None:
        stmt = (
            select(Staff)
            .where(Staff.user_id == user_id)
            .options(selectinload(Staff.user), selectinload(Staff.location))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_tg_id(self, tg_id: int) -> Staff | None:
        stmt = (
            select(Staff)
            .join(User, Staff.user_id == User.id)
            .where(User.tg_id == tg_id)
            .options(selectinload(Staff.user), selectinload(Staff.location))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_team(self, location_id: int | None = None) -> list[Staff]:
        stmt = (
            select(Staff)
            .options(selectinload(Staff.user), selectinload(Staff.location))
            .order_by(Staff.role, Staff.id)
        )
        if location_id is not None:
            stmt = stmt.where(Staff.location_id == location_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_pin(self, staff: Staff, pin_hash: str) -> None:
        staff.pin_hash = pin_hash
        staff.pin_set_at = datetime.now(timezone.utc)
        staff.pin_failed_attempts = 0
        staff.pin_locked_until = None
        await self.session.flush()

    async def pin_failed(self, staff_id: int) -> int:
        stmt = (
            update(Staff)
            .where(Staff.id == staff_id)
            .values(pin_failed_attempts=Staff.pin_failed_attempts + 1)
            .returning(Staff.pin_failed_attempts)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def lock_pin(self, staff_id: int, until: datetime) -> None:
        stmt = update(Staff).where(Staff.id == staff_id).values(pin_locked_until=until)
        await self.session.execute(stmt)

    async def pin_ok(self, staff: Staff) -> None:
        staff.pin_failed_attempts = 0
        staff.pin_locked_until = None
        staff.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def reset_pin(self, staff: Staff) -> None:
        staff.pin_hash = None
        staff.pin_set_at = None
        staff.pin_failed_attempts = 0
        staff.pin_locked_until = None
        await self.session.flush()

    async def revoke_sessions(self, staff: Staff) -> None:
        staff.tokens_valid_after = datetime.now(timezone.utc)
        await self.session.flush()
