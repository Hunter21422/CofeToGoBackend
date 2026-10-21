from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import StaffRole

from .common import BaseSchema, Phone
from .location import LocationShort
from .user import UserRead, UserShort


class StaffShort(BaseSchema):
    id: int
    role: StaffRole
    user: UserShort


class StaffRead(StaffShort):
    location_id: int | None
    is_active: bool
    pin_set: bool
    phone_linked: bool = False
    phone: str | None = None
    tg_linked: bool = False
    pin_locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class StaffCreate(BaseModel):
    tg_id: int | None = None
    phone: Phone | None = None
    first_name: str | None = Field(None, max_length=64)
    role: StaffRole = StaffRole.BARISTA
    location_id: int | None = None

    @model_validator(mode="after")
    def tg_or_phone(self):
        if self.tg_id is None and self.phone is None:
            raise ValueError("Укажите Telegram ID или телефон сотрудника")
        return self


class StaffUpdate(BaseModel):
    first_name: str | None = Field(None, min_length=1, max_length=64)
    last_name: str | None = Field(None, max_length=64)
    role: StaffRole | None = None
    location_id: int | None = None
    is_active: bool | None = None
    phone: Phone | None = None


class AdminMe(BaseModel):
    """GET /admin/me — кто вошёл в панель и какие точки ему доступны.
    Работает и без PIN: по нему фронт решает, показать «Задайте PIN» или «Введите PIN»."""

    user: UserRead
    staff: StaffRead
    locations: list[LocationShort]
    pin_set: bool
    pin_verified: bool          # в текущем токене pin=true
    idle_lock_minutes: int = 15  # через сколько минут бездействия снова спросить PIN


class TgLinkOut(BaseModel):
    token: str
    expires_at: datetime
