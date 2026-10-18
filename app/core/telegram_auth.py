"""Проверка подписи данных от Telegram: Mini App (initData) и Login Widget на сайте."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    pass


def verify_init_data(init_data: str, bot_token: str, max_age_sec: int) -> dict[str, Any]:
    """Mini App: secret = HMAC_SHA256("WebAppData", bot_token). Возвращает user из initData."""
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received = pairs.pop("hash", None)
    if not received:
        raise TelegramAuthError("Нет подписи")
    check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise TelegramAuthError("Подпись не сошлась")
    if time.time() - int(pairs.get("auth_date", 0)) > max_age_sec:
        raise TelegramAuthError("Данные устарели")
    return json.loads(pairs.get("user", "{}"))


def verify_login_widget(data: dict[str, Any], bot_token: str, max_age_sec: int = 86400) -> dict[str, Any]:
    """Login Widget на сайте: secret = SHA256(bot_token), подписаны все поля, кроме hash."""
    fields = {k: v for k, v in data.items() if v is not None}
    received = str(fields.pop("hash", ""))
    if not received:
        raise TelegramAuthError("Нет подписи")
    check = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret = hashlib.sha256(bot_token.encode()).digest()
    expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise TelegramAuthError("Подпись не сошлась")
    if time.time() - int(fields.get("auth_date", 0)) > max_age_sec:
        raise TelegramAuthError("Данные устарели")
    return fields
