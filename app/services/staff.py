from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_secret, verify_secret
from app.models import LoyaltyAccount, Location, Order, Review, Staff, User
from app.models.enums import StaffRole
from app.repositories import LocationRepository, RefreshTokenRepository, StaffRepository, UserRepository
from app.schemas.auth import PinVerifyOut, TokenPair
from app.schemas.staff import StaffCreate, StaffUpdate

from .errors import Conflict, Forbidden, NotFound, ServiceError

MAX_PIN_ATTEMPTS = 5
PIN_LOCK_MINUTES = 15
TG_LINK_TTL_SEC = 86400


class StaffService:
    def __init__(self, session: AsyncSession):
        self.staff = StaffRepository(session)
        self.users = UserRepository(session)
        self.locations = LocationRepository(session)
        self.tokens = RefreshTokenRepository(session)

    async def get_staff(self, staff_id: int) -> Staff:
        staff = await self.staff.get(staff_id)
        if staff is None:
            raise NotFound("Сотрудник не найден")
        return staff

    async def me(self, user_id: int) -> tuple[Staff, list[Location]]:
        staff = await self.staff.by_user_id(user_id)
        if staff is None or not staff.is_active:
            raise Forbidden("Вы не в команде этой кофейни")
        locations = await self.locations.list_active()
        if staff.role != StaffRole.OWNER and staff.location_id:
            locations = [l for l in locations if l.id == staff.location_id]
        return staff, locations

    def _pin_tokens(self, staff: Staff, sid: int, refresh_token: str | None) -> TokenPair:
        access, ttl = create_access_token(staff.user_id, sid, role=staff.role.value, pin=True)
        return TokenPair(access_token=access, refresh_token=refresh_token or "", expires_in=ttl)

    async def pin_setup(self, user_id: int, sid: int, pin: str) -> PinVerifyOut:
        staff, _ = await self.me(user_id)
        if staff.pin_set:
            raise Conflict("PIN уже задан. Сбросить его может владелец")
        await self.staff.set_pin(staff, hash_secret(pin))
        await self.staff.pin_ok(staff)
        return PinVerifyOut(ok=True, tokens=self._pin_tokens(staff, sid, None))

    async def pin_verify(self, user_id: int, sid: int, pin: str) -> PinVerifyOut:
        staff, _ = await self.me(user_id)
        if not staff.pin_set:
            raise ServiceError("Сначала придумайте PIN", code="pin_not_set")
        now = datetime.now(timezone.utc)
        if staff.pin_locked(now):
            return PinVerifyOut(ok=False, attempts_left=0, locked_until=staff.pin_locked_until)
        if verify_secret(staff.pin_hash, pin):
            await self.staff.pin_ok(staff)
            return PinVerifyOut(ok=True, tokens=self._pin_tokens(staff, sid, None))

        attempts = await self.staff.pin_failed(staff.id)
        if attempts >= MAX_PIN_ATTEMPTS:
            until = now + timedelta(minutes=PIN_LOCK_MINUTES)
            await self.staff.lock_pin(staff.id, until)
            await self.staff.update(staff, pin_failed_attempts=0)
            return PinVerifyOut(ok=False, attempts_left=0, locked_until=until)
        return PinVerifyOut(ok=False, attempts_left=MAX_PIN_ATTEMPTS - attempts)

    def lock(self, staff: Staff, sid: int) -> TokenPair:
        access, ttl = create_access_token(staff.user_id, sid, role=staff.role.value, pin=False)
        return TokenPair(access_token=access, refresh_token="", expires_in=ttl)

    async def list_team(self, location_id: int | None = None) -> list[Staff]:
        return await self.staff.list_team(location_id)

    async def _set_phone(self, user: User, phone: str) -> None:
        if user.phone == phone:
            return
        other = await self.users.by_phone(phone)
        if other is not None and other.id != user.id:
            if await self.staff.by_user_id(other.id) is not None:
                raise Conflict("Этот номер уже у другого сотрудника")
            await self.users.update(other, phone=None)
        await self.users.update(user, phone=phone)

    async def add_staff(self, owner: Staff, data: StaffCreate) -> Staff:
        if data.tg_id is not None:
            user = await self.users.by_tg_id(data.tg_id)
            if user is None:
                raise NotFound("Человек ещё не открывал бота. Попросите его зайти в бота и нажать «Старт» или добавьте по телефону")
            if data.phone:
                await self._set_phone(user, data.phone)
        else:
            user = await self.users.by_phone(data.phone)
            if user is None:
                user = await self.users.create(phone=data.phone, first_name=(data.first_name or "").strip() or "Сотрудник", referral_code=secrets.token_hex(4).upper())
        if data.first_name and data.first_name.strip() and user.first_name in ("", "Гость", "Сотрудник"):
            await self.users.update(user, first_name=data.first_name.strip())
        if await self.staff.by_user_id(user.id) is not None:
            raise Conflict("Этот человек уже в команде")
        if data.location_id is not None and await self.locations.get(data.location_id) is None:
            raise NotFound("Кофейня не найдена")
        staff = await self.staff.create(user_id=user.id, role=data.role, location_id=data.location_id, created_by_id=owner.user_id)
        return await self.staff.by_user_id(user.id) or staff

    async def update_staff(self, owner: Staff, staff_id: int, data: StaffUpdate) -> Staff:
        staff = await self.get_staff(staff_id)
        fields = data.model_dump(exclude_unset=True)
        if "phone" in fields:
            phone = fields.pop("phone")
            if phone:
                await self._set_phone(staff.user, phone)
            else:
                await self.users.update(staff.user, phone=None)
        names = {k: fields.pop(k) for k in ("first_name", "last_name") if k in fields}
        if names.get("first_name") is not None:
            names["first_name"] = names["first_name"].strip()
            if not names["first_name"]:
                raise ServiceError("Имя не может быть пустым")
        elif "first_name" in names:
            names.pop("first_name")
        if "last_name" in names:
            names["last_name"] = (names["last_name"] or "").strip() or None
        if names:
            await self.users.update(staff.user, **names)
        demoting = staff.role == StaffRole.OWNER and (fields.get("role", StaffRole.OWNER) != StaffRole.OWNER or fields.get("is_active") is False)
        if demoting:
            owners = [s for s in await self.staff.list_team() if s.role == StaffRole.OWNER and s.is_active]
            if len(owners) <= 1:
                raise Conflict("Нельзя убрать последнего владельца")
        if staff.id == owner.id and fields.get("is_active") is False:
            raise Conflict("Нельзя отключить самого себя")
        if fields.get("location_id") is not None and await self.locations.get(fields["location_id"]) is None:
            raise NotFound("Кофейня не найдена")
        await self.staff.update(staff, **fields)
        if fields.get("is_active") is False:
            await self.revoke_sessions(staff_id)
        return staff

    async def tg_link_create(self, redis: Redis, staff_id: int) -> tuple[str, datetime]:
        staff = await self.get_staff(staff_id)
        token = secrets.token_urlsafe(16)
        await redis.set(f"staff:tglink:{token}", staff.id, ex=TG_LINK_TTL_SEC)
        return token, datetime.now(timezone.utc) + timedelta(seconds=TG_LINK_TTL_SEC)

    async def _has_history(self, user_id: int) -> bool:
        session = self.staff.session
        orders = (await session.execute(select(func.count(Order.id)).where(Order.user_id == user_id))).scalar_one()
        reviews = (await session.execute(select(func.count(Review.id)).where(Review.user_id == user_id))).scalar_one()
        card = await session.get(LoyaltyAccount, user_id)
        return bool(orders or reviews or (card and (card.lifetime_stamps or card.stamps or card.gifts_available)))

    async def tg_link_use(self, redis: Redis, token: str, tg: dict) -> Staff:
        raw = await redis.getdel(f"staff:tglink:{token}")
        if raw is None:
            raise NotFound("Ссылка устарела или уже использована. Попросите владельца прислать новую")
        staff = await self.get_staff(int(raw))
        target = staff.user
        other = await self.users.by_tg_id(tg["id"])
        if other is not None and other.id != target.id:
            if await self.staff.by_user_id(other.id) is not None:
                raise Conflict("Этот Telegram уже привязан к другому сотруднику")
            if not await self._has_history(other.id):
                await self.users.update(other, tg_id=None, username=None)
            elif not await self._has_history(target.id):
                phone = target.phone
                await self.users.update(target, phone=None)
                fields = {"phone": phone} if phone else {}
                if not other.first_name or other.first_name in ("Гость", "Сотрудник"):
                    fields["first_name"] = target.first_name
                    fields["last_name"] = target.last_name
                if fields:
                    await self.users.update(other, **fields)
                await self.staff.update(staff, user_id=other.id)
                await self.tokens.revoke_all(target.id)
                self.staff.session.expire(staff)
                return await self.staff.by_user_id(other.id) or staff
            else:
                raise Conflict("У этого Telegram и у сотрудника уже есть свои заказы — объединить автоматически нельзя. Напишите разработчику")
        if other is None or other.id != target.id:
            await self.users.update(target, tg_id=tg["id"], username=tg.get("username"))
        return staff

    async def reset_pin(self, staff_id: int) -> Staff:
        staff = await self.get_staff(staff_id)
        await self.staff.reset_pin(staff)
        await self.revoke_sessions(staff_id)
        return staff

    async def revoke_sessions(self, staff_id: int) -> None:
        staff = await self.get_staff(staff_id)
        await self.staff.revoke_sessions(staff)
        await self.tokens.revoke_all(staff.user_id)
