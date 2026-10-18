from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator

from .common import Phone

from app.models.enums import StaffRole


class TelegramAuthIn(BaseModel):
    init_data: str


# ---------- вход на сайте (вне Telegram) ----------
class SmsSendIn(BaseModel):
    phone: Phone


class SmsSendOut(BaseModel):
    expires_in: int  # сек, сколько живёт код
    resend_in: int  # сек, когда можно запросить снова


class SmsVerifyIn(BaseModel):
    phone: Phone
    code: Annotated[str, Field(pattern=r"^\d{4}$")]


class TelegramWidgetIn(BaseModel):
    """Данные Telegram Login Widget. Проверка: app.core.telegram_auth.verify_login_widget"""

    id: int
    first_name: str
    last_name: str | None = None
    username: str | None = None
    photo_url: str | None = None
    auth_date: int
    hash: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPayload(BaseModel):
    sub: int  # user_id
    role: StaffRole | None = None
    sid: int | None = None   # id refresh-сессии — по нему отзываем
    pin: bool = False         # второй фактор пройден (нужно для /admin/*, кроме /admin/me и /admin/auth/*)
    iat: int
    exp: int
    type: Literal["access", "refresh"]


class MagicLoginIn(BaseModel):
    """Вход в панель из браузера: бот по команде /admin присылает одноразовую ссылку (живёт 2 минуты)"""

    token: str = Field(min_length=16, max_length=128)


Pin = Annotated[str, Field(pattern=r"^\d{6}$", description="6 цифр")]

WEAK_PINS = {
    "000000", "111111", "123456", "654321", "121212", "112233", "123123", "999999", "666666", "777777",
}


class PinSetupIn(BaseModel):
    pin: Pin
    pin_repeat: Pin

    @model_validator(mode="after")
    def check(self):
        if self.pin != self.pin_repeat:
            raise ValueError("PIN-коды не совпадают")
        if self.pin in WEAK_PINS or len(set(self.pin)) == 1:
            raise ValueError("Слишком простой PIN — придумайте другой")
        return self


class PinVerifyIn(BaseModel):
    pin: Pin


class PinVerifyOut(BaseModel):
    ok: bool
    tokens: TokenPair | None = None        # при ok — новый access с pin=true
    attempts_left: int | None = None       # при ошибке
    locked_until: datetime | None = None   # после 5 ошибок — блок на 15 минут
