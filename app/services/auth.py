from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

import httpx
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, random_token, sha256
from app.core.telegram_auth import TelegramAuthError, verify_init_data, verify_login_widget
from app.models import RefreshToken, Staff, User
from app.models.enums import StaffRole
from app.repositories import LoyaltyRepository, RefreshTokenRepository, StaffRepository, UserRepository
from app.schemas.auth import SmsSendOut, TelegramWidgetIn, TokenPair

from .errors import Forbidden, ServiceError, TooMany

log = logging.getLogger(__name__)


class Unauthorized(ServiceError):
    status = 401


class SmsSender(Protocol):
    channel: str

    async def send(self, phone: str, text: str) -> None: ...

    async def send_code(self, phone: str, ip: str | None) -> str: ...


def _new_code() -> str:
    return f"{secrets.randbelow(10_000):04d}"


class SmsRuSender:
    def __init__(self, api_id: str, mode: str = "call"):
        self.api_id = api_id
        self.channel = "call" if mode == "call" else "sms"

    async def send(self, phone: str, text: str) -> None:
        params = {"api_id": self.api_id, "to": phone.lstrip("+"), "msg": text, "json": 1}
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get("https://sms.ru/sms/send", params=params)
        data = r.json() if r.status_code == 200 else {}
        item = (data.get("sms") or {}).get(phone.lstrip("+"), {})
        if data.get("status") != "OK" or item.get("status") != "OK":
            log.warning("sms.ru: %s", data)
            raise ServiceError(item.get("status_text") or "Не получилось отправить SMS, попробуйте позже")

    async def send_code(self, phone: str, ip: str | None) -> str:
        if self.channel == "sms":
            code = _new_code()
            await self.send(phone, f"{code} — код для входа в «{get_settings().app_name}»")
            return code
        params = {"api_id": self.api_id, "phone": phone.lstrip("+"), "ip": ip or "-1", "json": 1}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get("https://sms.ru/code/call", params=params)
        data = r.json() if r.status_code == 200 else {}
        if data.get("status") != "OK" or not data.get("code"):
            log.warning("sms.ru call: %s", data)
            raise ServiceError("Не получилось позвонить, попробуйте через минуту")
        return str(data["code"])[-4:]


class LogSender:
    channel = "log"

    async def send(self, phone: str, text: str) -> None:
        log.warning("SMS to %s: %s", phone, text)

    async def send_code(self, phone: str, ip: str | None) -> str:
        code = _new_code()
        log.warning("SMS to %s: код для входа %s", phone, code)
        return code


def default_sender() -> SmsSender:
    s = get_settings()
    return SmsRuSender(s.sms_ru_api_id, s.sms_ru_mode) if s.sms_ru_api_id else LogSender()


class AuthService:
    def __init__(self, session: AsyncSession, redis: Redis, sms: SmsSender | None = None):
        self.users = UserRepository(session)
        self.tokens = RefreshTokenRepository(session)
        self.staff = StaffRepository(session)
        self.loyalty = LoyaltyRepository(session)
        self.redis = redis
        self.sms = sms or default_sender()
        self.settings = get_settings()

    async def issue_tokens(self, user: User, pin: bool = False, user_agent: str | None = None) -> TokenPair:
        refresh = random_token()
        row = await self.tokens.create(
            user_id=user.id,
            token_hash=sha256(refresh),
            user_agent=(user_agent or "")[:512] or None,
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.settings.refresh_ttl_days),
        )
        staff = await self.staff.by_user_id(user.id)
        role = staff.role.value if staff and staff.is_active else None
        access, ttl = create_access_token(user.id, row.id, role=role, pin=pin and role is not None)
        return TokenPair(access_token=access, refresh_token=f"{row.id}.{refresh}", expires_in=ttl)

    async def _new_user(self, **fields: Any) -> User:
        for _ in range(10):
            code = secrets.token_hex(4).upper()
            if not await self.users.exists(User.referral_code == code):
                break
        user = await self.users.create(referral_code=code, **fields)
        await self.loyalty.get_or_create(user.id)
        return user

    async def _ensure_owner(self, user: User) -> None:
        if user.tg_id and user.tg_id in self.settings.owner_tg_ids:
            staff = await self.staff.by_user_id(user.id)
            if staff is None:
                await self.staff.create(user_id=user.id, role=StaffRole.OWNER)

    async def _upsert_telegram(self, tg: dict[str, Any]) -> User:
        fields = {
            "first_name": tg.get("first_name") or "",
            "last_name": tg.get("last_name"),
            "username": tg.get("username"),
            "photo_url": tg.get("photo_url"),
        }
        user = await self.users.by_tg_id(int(tg["id"]))
        if user is None:
            user = await self._new_user(tg_id=int(tg["id"]), **fields)
        else:
            keep_name = bool(user.first_name) and user.first_name != "Гость"
            changes = {k: v for k, v in fields.items() if v and not (keep_name and k in ("first_name", "last_name"))}
            await self.users.update(user, **changes)
        user.last_seen_at = datetime.now(timezone.utc)
        await self._ensure_owner(user)
        return user

    async def login_telegram(self, init_data: str, user_agent: str | None = None) -> TokenPair:
        if self.settings.dev_mode and init_data.startswith("dev="):
            tg = {"id": int(init_data[4:] or 1), "first_name": "Dev"}
        else:
            try:
                tg = verify_init_data(init_data, self.settings.bot_token, self.settings.init_data_ttl_hours * 3600)
            except TelegramAuthError as e:
                raise Unauthorized(f"Telegram не подтвердил вход: {e}")
        if not tg.get("id"):
            raise Unauthorized("Telegram не передал пользователя")
        user = await self._upsert_telegram(tg)
        return await self.issue_tokens(user, user_agent=user_agent)

    async def login_widget(self, data: TelegramWidgetIn, user_agent: str | None = None) -> TokenPair:
        try:
            tg = verify_login_widget(data.model_dump(), self.settings.bot_token)
        except TelegramAuthError as e:
            raise Unauthorized(f"Telegram не подтвердил вход: {e}")
        user = await self._upsert_telegram(tg)
        return await self.issue_tokens(user, user_agent=user_agent)

    async def sms_send(self, phone: str, ip: str | None = None) -> SmsSendOut:
        s = self.settings
        if await self.redis.exists(f"sms:wait:{phone}"):
            ttl = await self.redis.ttl(f"sms:wait:{phone}")
            raise TooMany(f"Новый код можно запросить через {max(ttl, 1)} с")
        day_key = f"sms:day:{phone}"
        sent_today = await self.redis.incr(day_key)
        if sent_today == 1:
            await self.redis.expire(day_key, 86400)
        if sent_today > s.sms_daily_limit_per_phone:
            raise TooMany("Слишком много кодов за сутки, попробуйте завтра")
        if ip:
            ip_key = f"sms:ip:{ip}"
            per_ip = await self.redis.incr(ip_key)
            if per_ip == 1:
                await self.redis.expire(ip_key, 3600)
            if per_ip > 20:
                raise TooMany("Слишком много запросов, попробуйте позже")

        await self.redis.set(f"sms:wait:{phone}", 1, ex=s.sms_resend_sec)
        try:
            code = await self.sms.send_code(phone, ip)
        except Exception:
            await self.redis.delete(f"sms:wait:{phone}")
            raise
        await self.redis.hset(f"sms:code:{phone}", mapping={"hash": sha256(f"{phone}:{code}"), "attempts": 0})
        await self.redis.expire(f"sms:code:{phone}", s.sms_code_ttl_sec)
        return SmsSendOut(expires_in=s.sms_code_ttl_sec, resend_in=s.sms_resend_sec, channel=self.sms.channel)

    async def staff_phone_send(self, phone: str, ip: str | None = None) -> SmsSendOut:
        user = await self.users.by_phone(phone)
        staff = await self.staff.by_user_id(user.id) if user else None
        if staff is None or not staff.is_active:
            raise ServiceError("Этот номер не привязан к сотруднику. Привяжите телефон в профиле приложения кофейни")
        return await self.sms_send(phone, ip)

    async def sms_verify(self, phone: str, code: str, user_agent: str | None = None) -> TokenPair:
        key = f"sms:code:{phone}"
        saved = await self.redis.hgetall(key)
        if not saved:
            raise ServiceError("Код устарел, запросите новый", code="code_expired")
        saved = {(k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v) for k, v in saved.items()}
        attempts = await self.redis.hincrby(key, "attempts", 1)
        if attempts > self.settings.sms_max_attempts:
            await self.redis.delete(key)
            raise TooMany("Слишком много попыток, запросите новый код")
        if not secrets.compare_digest(saved["hash"], sha256(f"{phone}:{code}")):
            raise ServiceError("Неверный код", code="bad_code")
        await self.redis.delete(key)

        user = await self.users.by_phone(phone)
        if user is None:
            user = await self._new_user(phone=phone, first_name="Гость")
        user.last_seen_at = datetime.now(timezone.utc)
        return await self.issue_tokens(user, user_agent=user_agent)

    async def _session_by_refresh(self, refresh_token: str) -> RefreshToken:
        sid, _, secret = refresh_token.partition(".")
        if not sid.isdigit() or not secret:
            raise Unauthorized("Сессия устарела, войдите снова")
        row = await self.tokens.get(int(sid))
        now = datetime.now(timezone.utc)
        if row is None or row.token_hash != sha256(secret) or row.revoked_at is not None or row.expires_at <= now:
            raise Unauthorized("Сессия устарела, войдите снова")
        return row

    async def refresh(self, refresh_token: str, user_agent: str | None = None) -> TokenPair:
        row = await self._session_by_refresh(refresh_token)
        user = await self.users.get(row.user_id)
        if user is None or user.is_blocked:
            raise Unauthorized("Сессия устарела, войдите снова")
        staff = await self.staff.by_user_id(user.id)
        if staff and staff.tokens_valid_after and row.created_at < staff.tokens_valid_after:
            raise Unauthorized("Сессия завершена владельцем, войдите снова")
        row.revoked_at = datetime.now(timezone.utc)
        return await self.issue_tokens(user, user_agent=user_agent)

    async def logout(self, sid: int) -> None:
        row = await self.tokens.get(sid)
        if row is not None and row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)

    async def check_session(self, payload: dict[str, Any]) -> User:
        row = await self.tokens.get(payload["sid"])
        if row is None or row.revoked_at is not None:
            raise Unauthorized("Сессия завершена, войдите снова", code="session_revoked")
        user = await self.users.get(payload["sub"])
        if user is None or user.is_blocked:
            raise Unauthorized("Аккаунт недоступен", code="session_revoked")
        return user

    async def magic_create(self, user_id: int) -> str:
        token = random_token(24)
        await self.redis.set(f"magic:{token}", user_id, ex=120)
        return f"{self.settings.admin_url}#/login?t={token}"

    async def magic_login(self, token: str, user_agent: str | None = None) -> TokenPair:
        raw = await self.redis.getdel(f"magic:{token}")
        if raw is None:
            raise Unauthorized("Ссылка устарела — отправьте /admin боту ещё раз")
        user = await self.users.get(int(raw))
        staff = await self.staff.by_user_id(user.id) if user else None
        if user is None or staff is None or not staff.is_active:
            raise Unauthorized("Вы не в команде этой кофейни")
        return await self.issue_tokens(user, user_agent=user_agent)

    async def require_staff(self, user_id: int) -> Staff:
        staff = await self.staff.by_user_id(user_id)
        if staff is None or not staff.is_active:
            raise Forbidden("Вы не в команде этой кофейни")
        return staff
