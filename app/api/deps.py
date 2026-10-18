from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import Staff, User
from app.models.enums import StaffRole
from app.services import AuthService, Forbidden, Unauthorized
from app.services.payment import PaymentGateway, default_gateway

_redis: Redis | None = None
_gateway: PaymentGateway | None = None


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _redis


def get_gateway() -> PaymentGateway:
    global _gateway
    if _gateway is None:
        _gateway = default_gateway()
    return _gateway


SessionDep = Annotated[AsyncSession, Depends(get_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
GatewayDep = Annotated[PaymentGateway, Depends(get_gateway)]


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent")


def client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def token_payload(authorization: Annotated[str | None, Header()] = None) -> dict[str, Any]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise Unauthorized("Нужно войти")
    try:
        return decode_access_token(authorization[7:])
    except jwt.PyJWTError:
        raise Unauthorized("Сессия устарела")


PayloadDep = Annotated[dict[str, Any], Depends(token_payload)]


async def current_user(session: SessionDep, redis: RedisDep, payload: PayloadDep) -> User:
    return await AuthService(session, redis).check_session(payload)


CurrentUser = Annotated[User, Depends(current_user)]

RANK = {StaffRole.BARISTA: 1, StaffRole.MANAGER: 2, StaffRole.OWNER: 3}


@dataclass
class StaffContext:
    user: User
    staff: Staff
    payload: dict[str, Any]


async def staff_no_pin(user: CurrentUser, payload: PayloadDep) -> StaffContext:
    staff = user.staff
    if staff is None or not staff.is_active:
        raise Forbidden("Вы не в команде этой кофейни")
    if staff.tokens_valid_after and payload["iat"] < int(staff.tokens_valid_after.timestamp()):
        raise Unauthorized("Сессия завершена владельцем, войдите снова", code="session_revoked")
    return StaffContext(user=user, staff=staff, payload=payload)


StaffNoPin = Annotated[StaffContext, Depends(staff_no_pin)]


def require_role(min_role: StaffRole):
    async def dep(ctx: StaffNoPin) -> StaffContext:
        if not ctx.payload.get("pin"):
            raise Forbidden("Введите PIN, чтобы продолжить", code="pin_required")
        if RANK[ctx.staff.role] < RANK[min_role]:
            raise Forbidden("Недостаточно прав")
        return ctx

    return dep


Barista = Annotated[StaffContext, Depends(require_role(StaffRole.BARISTA))]
Manager = Annotated[StaffContext, Depends(require_role(StaffRole.MANAGER))]
Owner = Annotated[StaffContext, Depends(require_role(StaffRole.OWNER))]


def check_location(ctx: StaffContext, location_id: int) -> None:
    staff = ctx.staff
    if staff.role != StaffRole.OWNER and staff.location_id and staff.location_id != location_id:
        raise Forbidden("Нет доступа к этой кофейне")
