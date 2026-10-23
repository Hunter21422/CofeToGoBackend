from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import LoyaltyAccount, LoyaltyTransaction
from app.models.enums import LoyaltyTxType
from app.repositories import LoyaltyRepository, SettingRepository
from app.schemas.loyalty import LoyaltyRead

from .notify import NotifyService
from .errors import Conflict, Forbidden, NotFound, ServiceError

CODE_TTL_SEC = 300
VISIT_TTL_SEC = 600
MAX_STAMPS_PER_VISIT = 1
MAX_CASH_STAMPS_PER_DAY = 10


class LoyaltyService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None):
        self.loyalty = LoyaltyRepository(session)
        self.settings = SettingRepository(session)
        self.redis = redis

    async def stamps_per_gift(self) -> int:
        return int(await self.settings.get_value("loyalty.stamps_per_gift", default=5))

    async def account(self, user_id: int) -> LoyaltyAccount:
        return await self.loyalty.get_or_create(user_id)

    async def expire_days(self) -> tuple[int | None, int | None]:
        stamps = await self.settings.get_value("loyalty.stamps_expire_days", default=None)
        gifts = await self.settings.get_value("loyalty.gift_expire_days", default=None)
        return (int(stamps) if stamps else None), (int(gifts) if gifts else None)

    async def read(self, user_id: int) -> LoyaltyRead:
        account = await self.account(user_id)
        loyalty = LoyaltyRead.model_validate(account)
        loyalty.stamps_per_gift = await self.stamps_per_gift()
        stamps_days, gift_days = await self.expire_days()
        loyalty.stamps_expire_days, loyalty.gift_expire_days = stamps_days, gift_days
        since = account.last_activity_at or account.created_at
        if since is not None:
            if stamps_days and account.stamps > 0:
                loyalty.stamps_expire_at = since + timedelta(days=stamps_days)
            if gift_days and account.gifts_available > 0:
                loyalty.gifts_expire_at = since + timedelta(days=gift_days)
        return loyalty

    async def add_stamps(
        self,
        user_id: int,
        count: int,
        order_id: int | None = None,
        staff_id: int | None = None,
        location_id: int | None = None,
        type: LoyaltyTxType = LoyaltyTxType.STAMP_EARNED,
        reason: str | None = None,
    ) -> LoyaltyAccount:
        if count <= 0:
            raise ServiceError("Количество штампов должно быть больше нуля")
        per_gift = await self.stamps_per_gift()
        account = await self.loyalty.lock(user_id)

        account.stamps += count
        account.lifetime_stamps += count
        account.last_activity_at = datetime.now(timezone.utc)
        await self.loyalty.add_tx(
            account, type, stamps_delta=count, order_id=order_id,
            staff_id=staff_id, location_id=location_id, reason=reason,
        )

        unlocked = False
        while account.stamps >= per_gift:
            account.stamps -= per_gift
            account.gifts_available += 1
            account.lifetime_gifts += 1
            unlocked = True
            await self.loyalty.add_tx(
                account, LoyaltyTxType.GIFT_UNLOCKED, stamps_delta=-per_gift, gifts_delta=1,
                order_id=order_id, staff_id=staff_id, location_id=location_id,
            )
        if unlocked:
            await NotifyService(self.loyalty.session).gift_unlocked(user_id)

        return account

    async def redeem_gift(self, user_id: int, order_id: int | None = None, staff_id: int | None = None, location_id: int | None = None) -> LoyaltyAccount:
        account = await self.loyalty.lock(user_id)
        if account.gifts_available < 1:
            raise ServiceError("Подарков на карте нет", code="no_gift")
        account.gifts_available -= 1
        account.last_activity_at = datetime.now(timezone.utc)
        await self.loyalty.add_tx(account, LoyaltyTxType.GIFT_REDEEMED, gifts_delta=-1, order_id=order_id, staff_id=staff_id, location_id=location_id)
        return account

    async def return_gift(self, user_id: int, order_id: int) -> LoyaltyAccount:
        account = await self.loyalty.lock(user_id)
        account.gifts_available += 1
        await self.loyalty.add_tx(
            account, LoyaltyTxType.GIFT_RETURNED, gifts_delta=1, order_id=order_id, reason="Заказ отменён"
        )
        return account

    async def adjust(
        self, user_id: int, stamps: int, gifts: int, reason: str, staff_id: int, location_id: int | None = None
    ) -> LoyaltyAccount:
        if not reason.strip():
            raise ServiceError("Укажите причину")
        if stamps == 0 and gifts == 0:
            raise ServiceError("Нечего менять")
        account = await self.loyalty.lock(user_id)
        if account.stamps + stamps < 0 or account.gifts_available + gifts < 0:
            raise ServiceError("Нельзя уйти в минус")
        account.stamps += stamps
        account.gifts_available += gifts
        if stamps > 0:
            account.lifetime_stamps += stamps
        await self.loyalty.add_tx(
            account, LoyaltyTxType.MANUAL_ADJUST, stamps_delta=stamps, gifts_delta=gifts,
            staff_id=staff_id, location_id=location_id, reason=reason.strip(),
        )
        per_gift = await self.stamps_per_gift()
        while account.stamps >= per_gift:
            account.stamps -= per_gift
            account.gifts_available += 1
            account.lifetime_gifts += 1
            await self.loyalty.add_tx(
                account, LoyaltyTxType.GIFT_UNLOCKED, stamps_delta=-per_gift, gifts_delta=1,
                staff_id=staff_id, location_id=location_id,
            )
        return account

    async def history(
        self, user_id: int, types: list[LoyaltyTxType], limit: int, offset: int
    ) -> tuple[list[LoyaltyTransaction], int]:
        return await self.loyalty.history(user_id, types, limit, offset)

    def _need_redis(self) -> Redis:
        if self.redis is None:
            raise RuntimeError("LoyaltyService: для кодов нужен redis")
        return self.redis

    async def issue_code(self, user_id: int) -> tuple[str, datetime]:
        redis = self._need_redis()
        user_key = f"loyalty:user_code:{user_id}"
        old = await redis.get(user_key)
        if old:
            ttl = await redis.ttl(user_key)
            if ttl > 30:
                code = old.decode() if isinstance(old, bytes) else old
                return code, datetime.now(timezone.utc) + timedelta(seconds=ttl)
            await redis.delete(f"loyalty:code:{old.decode() if isinstance(old, bytes) else old}")

        for _ in range(20):
            code = f"{secrets.randbelow(1_000_000):06d}"
            if await redis.set(f"loyalty:code:{code}", user_id, ex=CODE_TTL_SEC, nx=True):
                await redis.set(user_key, code, ex=CODE_TTL_SEC)
                return code, datetime.now(timezone.utc) + timedelta(seconds=CODE_TTL_SEC)
        raise ServiceError("Не получилось выдать код, попробуйте ещё раз")

    async def identify_code(self, code: str) -> int:
        redis = self._need_redis()
        code = code.strip()
        if not (len(code) == 6 and code.isdigit()):
            raise ServiceError("Код — это 6 цифр", code="bad_code")
        raw = await redis.getdel(f"loyalty:code:{code}")
        if raw is None:
            raise NotFound("Код не найден или уже использован. Попросите гостя обновить карту", code="bad_code")
        user_id = int(raw)
        await redis.delete(f"loyalty:user_code:{user_id}")
        return user_id

    async def open_visit(self, user_id: int, staff_id: int, location_id: int) -> str:
        redis = self._need_redis()
        token = secrets.token_urlsafe(16)
        await redis.set(f"loyalty:visit:{token}", f"{user_id}:{staff_id}:{location_id}", ex=VISIT_TTL_SEC)
        return token

    async def _check_visit(self, token: str, user_id: int, staff_id: int, location_id: int) -> None:
        raw = await self._need_redis().get(f"loyalty:visit:{token}")
        if raw is None:
            raise ServiceError("Код гостя устарел. Попросите его обновить карту и назвать новый код", code="visit_expired")
        raw = raw.decode() if isinstance(raw, bytes) else raw
        if raw != f"{user_id}:{staff_id}:{location_id}":
            raise Forbidden("Этот код подтверждали не вы или на другой точке", code="visit_mismatch")

    async def _use_visit(self, token: str, action: str) -> None:
        if not await self._need_redis().set(f"loyalty:visit:{token}:{action}", 1, ex=VISIT_TTL_SEC, nx=True):
            text = "По этому коду штампы уже поставлены" if action == "stamp" else "По этому коду подарок уже выдан"
            raise Conflict(f"{text}. Для следующей покупки нужен новый код гостя", code="visit_used")

    async def stamp_visit(self, token: str, user_id: int, count: int, staff_id: int, location_id: int) -> LoyaltyAccount:
        if count > MAX_STAMPS_PER_VISIT:
            raise ServiceError(f"За одну покупку — не больше {MAX_STAMPS_PER_VISIT} штампов")
        await self._check_visit(token, user_id, staff_id, location_id)
        redis = self._need_redis()
        day_key = f"loyalty:cash:{user_id}:{datetime.now(timezone.utc).date().isoformat()}"
        total = await redis.incrby(day_key, count)
        await redis.expire(day_key, 2 * 86400)
        if total > MAX_CASH_STAMPS_PER_DAY:
            await redis.decrby(day_key, count)
            raise Conflict(f"Гостю сегодня уже поставили {total - count} штампов на кассе. Больше {MAX_CASH_STAMPS_PER_DAY} в день нельзя — если покупка правда большая, обратитесь к менеджеру", code="daily_limit")
        try:
            await self._use_visit(token, "stamp")
        except Conflict:
            await redis.decrby(day_key, count)
            raise
        return await self.add_stamps(user_id, count, staff_id=staff_id, location_id=location_id, reason="Касса")

    async def redeem_visit(self, token: str, user_id: int, staff_id: int, location_id: int) -> LoyaltyAccount:
        await self._check_visit(token, user_id, staff_id, location_id)
        if (await self.account(user_id)).gifts_available < 1:
            raise ServiceError("Подарков на карте нет", code="no_gift")
        await self._use_visit(token, "redeem")
        return await self.redeem_gift(user_id, staff_id=staff_id, location_id=location_id)

    async def accept_code(self, code: str, staff_id: int, location_id: int) -> LoyaltyAccount:
        redis = self._need_redis()
        code = code.strip()
        if not (len(code) == 6 and code.isdigit()):
            raise ServiceError("Код — это 6 цифр", code="bad_code")
        raw = await redis.getdel(f"loyalty:code:{code}")
        if raw is None:
            raise NotFound("Код не найден или уже использован. Попросите гостя обновить карту", code="bad_code")
        user_id = int(raw)
        await redis.delete(f"loyalty:user_code:{user_id}")
        return await self.add_stamps(user_id, 1, staff_id=staff_id, location_id=location_id, reason="Код на кассе")

    async def expire_old(self) -> int:
        stamps_days, gift_days = await self.expire_days()
        now = datetime.now(timezone.utc)
        count = 0
        if stamps_days:
            for account in await self.loyalty.stale(now - timedelta(days=stamps_days)):
                burned = account.stamps
                account.stamps = 0
                await self.loyalty.add_tx(account, LoyaltyTxType.EXPIRED, stamps_delta=-burned, reason=f"Штампы сгорели: нет заказов {stamps_days} дн.")
                count += 1
        if gift_days:
            for account in await self.loyalty.stale(now - timedelta(days=gift_days), gifts=True):
                burned = account.gifts_available
                account.gifts_available = 0
                await self.loyalty.add_tx(account, LoyaltyTxType.EXPIRED, gifts_delta=-burned, reason=f"Подарок сгорел: нет заказов {gift_days} дн.")
                count += 1
        return count
