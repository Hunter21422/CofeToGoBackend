from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.repositories import LocationRepository, UserRepository
from app.schemas.user import CustomerFilter, UserUpdate

from .errors import Conflict, NotFound, ServiceError


class UserService:
    def __init__(self, session: AsyncSession):
        self.users = UserRepository(session)
        self.locations = LocationRepository(session)
    async def get_user(self, user_id: int) -> User:
        user = await self.users.with_loyalty(user_id)
        if user is None:
            raise NotFound("Гость не найден")
        return user
    async def update_me(self, user_id: int, data: UserUpdate) -> User:
        user = await self.get_user(user_id)
        fields = data.model_dump(exclude_unset=True)
        if "birth_date" in fields and user.birth_date is not None and fields["birth_date"] != user.birth_date:
            raise ServiceError("День рождения можно указать только один раз")
        if fields.get("favorite_location_id") is not None:
            location = await self.locations.get(fields["favorite_location_id"])
            if location is None or not location.is_active:
                raise NotFound("Кофейня не найдена")
        await self.users.update(user, **fields)
        return user
    async def set_phone(self, user_id: int, phone: str) -> User:
        user = await self.get_user(user_id)
        if user.phone == phone:
            return user
        owner = await self.users.by_phone(phone)
        if owner is not None and owner.id != user_id:
            raise Conflict("Этот номер уже привязан к другому аккаунту")
        await self.users.update(user, phone=phone)
        return user
    async def search_guests(self, q: str) -> list[User]:
        if len(q.strip().lstrip("@")) < 2:
            return []
        return await self.users.search_guests(q)
    async def list_customers(self, f: CustomerFilter) -> tuple[list, int]:
        return await self.users.list_customers(f)
    async def customer_card(self, user_id: int) -> tuple[User, int, int]:
        user = await self.get_user(user_id)
        orders_count, total_spent = await self.users.customer_stats(user_id)
        return user, orders_count, total_spent
    async def block(self, user_id: int, is_blocked: bool, reason: str | None = None) -> User:
        user = await self.get_user(user_id)
        await self.users.update(user, is_blocked=is_blocked, blocked_reason=reason if is_blocked else None)
        return user
