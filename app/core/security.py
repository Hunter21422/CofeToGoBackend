from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

from app.core.config import get_settings

_hasher = PasswordHasher()


def hash_secret(value: str) -> str:
    return _hasher.hash(value)


def verify_secret(hashed: str, value: str) -> bool:
    try:
        return _hasher.verify(hashed, value)
    except VerificationError:
        return False


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def random_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def create_access_token(user_id: int, sid: int, role: str | None = None, pin: bool = False) -> tuple[str, int]:
    settings = get_settings()
    now = int(time.time())
    ttl = settings.access_ttl_min * 60
    payload: dict[str, Any] = {"sub": str(user_id), "sid": sid, "role": role, "pin": pin, "iat": now, "exp": now + ttl, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256"), ttl


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("not an access token")
    payload["sub"] = int(payload["sub"])
    return payload
