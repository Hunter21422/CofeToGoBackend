from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from app.models import LoyaltyAccount, Order, RefreshToken, User
from app.models.enums import OrderStatus
from app.schemas.user import CustomerFilter

from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def by_tg_id(self, tg_id: int) -> User | None:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_username(self, username: str) -> User | None:
        username = username.replace("@", "")
        stmt = select(User).where(User.username.ilike(username))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_phone(self, phone: str) -> User | None:
        stmt = select(User).where(User.phone == phone)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def with_loyalty(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.loyalty_account))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_guests(self, q: str, limit: int = 8) -> list[User]:
        q = q.replace("@", "").strip()
        if q == "":
            return []

        conditions = [
            User.username.ilike(f"%{q}%"),
            User.first_name.ilike(f"%{q}%"),
            User.last_name.ilike(f"%{q}%"),
        ]

        digits = "".join(ch for ch in q if ch.isdigit())
        if len(digits) >= 3:
            if digits.startswith("8"):
                digits = "7" + digits[1:]
            conditions.append(User.phone.ilike(f"%{digits}%"))

        stmt = (
            select(User)
            .where(or_(*conditions))
            .options(selectinload(User.loyalty_account))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def customer_stats(self, user_id: int) -> tuple[int, int]:
        stmt = select(
            func.count(Order.id),
            func.coalesce(func.sum(Order.total), 0),
        ).where(
            Order.user_id == user_id,
            Order.status == OrderStatus.COMPLETED,
        )
        result = await self.session.execute(stmt)
        orders_count, total_spent = result.one()
        return orders_count, total_spent

    async def list_customers(self, f: CustomerFilter) -> tuple[list, int]:
        orders_count = func.count(Order.id).label("orders_count")
        total_spent = func.coalesce(func.sum(Order.total), 0).label("total_spent")
        last_order_at = func.max(Order.created_at).label("last_order_at")
        stamps = func.coalesce(LoyaltyAccount.stamps, 0).label("stamps")

        orders_on = and_(
            Order.user_id == User.id,
            Order.status == OrderStatus.COMPLETED,
        )
        if f.location_id:
            orders_on = and_(orders_on, Order.location_id == f.location_id)

        stmt = (
            select(User, orders_count, total_spent, stamps, last_order_at)
            .outerjoin(Order, orders_on)
            .outerjoin(LoyaltyAccount, LoyaltyAccount.user_id == User.id)
            .group_by(User.id, LoyaltyAccount.stamps)
        )

        if f.q:
            q = f.q.replace("@", "").strip()
            stmt = stmt.where(
                or_(
                    User.username.ilike(f"%{q}%"),
                    User.first_name.ilike(f"%{q}%"),
                    User.phone.ilike(f"%{q}%"),
                )
            )

        if f.is_blocked is not None:
            stmt = stmt.where(User.is_blocked == f.is_blocked)

        if f.inactive_days:
            border = datetime.now(timezone.utc) - timedelta(days=f.inactive_days)
            stmt = stmt.having(or_(last_order_at.is_(None), last_order_at < border))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        stmt = stmt.order_by(User.id.desc()).limit(f.limit).offset(f.offset)
        rows = (await self.session.execute(stmt)).all()

        return list(rows), total


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def by_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke_all(self, user_id: int) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(timezone.utc))
        )
        await self.session.execute(stmt)

    async def delete_expired(self) -> None:
        stmt = delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(timezone.utc))
        await self.session.execute(stmt)
