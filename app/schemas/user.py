from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import StaffRole

from .common import BaseSchema, Money, Name, PaginationParams, Phone


class UserShort(BaseSchema):
    id: int
    first_name: str
    last_name: str | None
    username: str | None
    photo_url: str | None


class UserRead(UserShort):
    tg_id: int | None
    phone: str | None
    email: str | None
    birth_date: date | None
    language_code: str
    favorite_location_id: int | None
    referral_code: str
    marketing_consent: bool
    notifications_enabled: bool
    role: StaffRole | None = None
    created_at: datetime


class UserUpdate(BaseModel):
    first_name: Name | None = None
    last_name: str | None = Field(None, max_length=128)
    email: EmailStr | None = None
    birth_date: date | None = None
    favorite_location_id: int | None = None
    marketing_consent: bool | None = None
    notifications_enabled: bool | None = None
    language_code: Literal["ru", "en"] | None = None

    @field_validator("birth_date")
    @classmethod
    def birth_date_in_past(cls, v: date | None) -> date | None:
        if v and v >= date.today():
            raise ValueError("Дата рождения должна быть в прошлом")
        return v


class PhoneIn(BaseModel):
    phone: Phone


class CustomerFilter(PaginationParams):
    q: str | None = None
    location_id: int | None = None
    inactive_days: int | None = Field(None, ge=1)
    is_blocked: bool | None = None


class CustomerListItem(BaseSchema):
    id: int
    first_name: str
    username: str | None
    phone: str | None
    orders_count: int
    total_spent: Money
    stamps: int
    last_order_at: datetime | None


class UserBlockIn(BaseModel):
    is_blocked: bool
    reason: str | None = Field(None, max_length=255)
