import datetime as dt

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import PaymentMethod

from .common import BaseSchema, Name, Phone, Slug


class LocationHoursSchema(BaseSchema):
    weekday: int = Field(ge=0, le=6)  # 0 = понедельник
    opens_at: dt.time | None = None
    closes_at: dt.time | None = None
    is_closed: bool = False

    @model_validator(mode="after")
    def times_required_if_open(self):
        if not self.is_closed and (self.opens_at is None or self.closes_at is None):
            raise ValueError("Для рабочего дня нужны opens_at и closes_at")
        return self


class SpecialDaySchema(BaseSchema):
    date: dt.date
    opens_at: dt.time | None = None
    closes_at: dt.time | None = None
    is_closed: bool = False
    comment: str | None = Field(None, max_length=255)


class LocationShort(BaseSchema):
    id: int
    name: str
    address: str


class LocationRead(LocationShort):
    slug: str
    lat: float | None
    lng: float | None
    phone: str | None
    photo_url: str | None
    timezone: str
    accepts_orders: bool
    payment_methods: list[PaymentMethod]
    avg_prep_minutes: int
    hours: list[LocationHoursSchema]
    is_open_now: bool = False  # считается в сервисе


class LocationFilter(BaseModel):
    lat: float | None = None
    lng: float | None = None
    only_open: bool = False


class LocationCreate(BaseModel):
    name: Name
    slug: Slug
    address: str = Field(min_length=3, max_length=255)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    phone: Phone | None = None
    photo_url: str | None = Field(None, max_length=512)
    timezone: str = "Europe/Moscow"
    payment_methods: list[PaymentMethod] = Field(min_length=1)
    avg_prep_minutes: int = Field(7, ge=1, le=120)
    min_pickup_minutes: int = Field(5, ge=0, le=240)
    max_orders_per_slot: int | None = Field(None, ge=1)


class LocationUpdate(BaseModel):
    name: Name | None = None
    slug: Slug | None = None
    address: str | None = Field(None, min_length=3, max_length=255)
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    phone: Phone | None = None
    photo_url: str | None = Field(None, max_length=512)
    timezone: str | None = None
    payment_methods: list[PaymentMethod] | None = Field(None, min_length=1)
    avg_prep_minutes: int | None = Field(None, ge=1, le=120)
    min_pickup_minutes: int | None = Field(None, ge=0, le=240)
    max_orders_per_slot: int | None = Field(None, ge=1)
    is_active: bool | None = None
    accepts_orders: bool | None = None


class LocationHoursUpdate(BaseModel):
    hours: list[LocationHoursSchema] = Field(min_length=7, max_length=7)

    @field_validator("hours")
    @classmethod
    def all_weekdays_once(cls, v: list[LocationHoursSchema]) -> list[LocationHoursSchema]:
        if sorted(h.weekday for h in v) != list(range(7)):
            raise ValueError("Нужны все 7 дней недели без повторов")
        return v


class LocationToggleOrders(BaseModel):
    accepts_orders: bool
