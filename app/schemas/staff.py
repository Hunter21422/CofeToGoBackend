from datetime import datetime

from pydantic import BaseModel

from app.models.enums import StaffRole

from .common import BaseSchema
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
    pin_locked_until: datetime | None
    last_login_at: datetime | None
    created_at: datetime


class StaffCreate(BaseModel):
    tg_id: int
    role: StaffRole = StaffRole.BARISTA
    location_id: int | None = None


class StaffUpdate(BaseModel):
    role: StaffRole | None = None
    location_id: int | None = None
    is_active: bool | None = None


class AdminMe(BaseModel):
    """GET /admin/me — кто вошёл в панель и какие точки ему доступны.
    Работает и без PIN: по нему фронт решает, показать «Задайте PIN» или «Введите PIN»."""

    user: UserRead
    staff: StaffRead
    locations: list[LocationShort]
    pin_set: bool
    pin_verified: bool          # в текущем токене pin=true
    idle_lock_minutes: int = 15  # через сколько минут бездействия снова спросить PIN
