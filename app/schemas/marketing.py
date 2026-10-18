from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import BannerLinkType, BroadcastStatus

from .common import BaseSchema, Name


# ---------- Баннеры ----------
class BannerRead(BaseSchema):
    id: int
    title: str
    subtitle: str | None
    image_url: str
    link_type: BannerLinkType
    link_value: str | None


class BannerAdminRead(BannerRead):
    location_ids: list[int] | None
    starts_at: datetime | None
    ends_at: datetime | None
    sort_order: int
    is_active: bool


class BannerCreate(BaseModel):
    title: Name
    subtitle: str | None = Field(None, max_length=255)
    image_url: str = Field(max_length=512)
    link_type: BannerLinkType = BannerLinkType.NONE
    link_value: str | None = Field(None, max_length=512)
    location_ids: list[int] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def check(self):
        if self.link_type != BannerLinkType.NONE and not self.link_value:
            raise ValueError("Для ссылки нужен link_value")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at должен быть позже starts_at")
        return self


class BannerUpdate(BaseModel):
    title: Name | None = None
    subtitle: str | None = Field(None, max_length=255)
    image_url: str | None = Field(None, max_length=512)
    link_type: BannerLinkType | None = None
    link_value: str | None = Field(None, max_length=512)
    location_ids: list[int] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: int | None = None
    is_active: bool | None = None


# ---------- Рассылки ----------
class BroadcastSegment(BaseModel):
    location_ids: list[int] | None = None
    inactive_days: int | None = Field(None, ge=1)  # не заказывали N дней
    active_days: int | None = Field(None, ge=1)    # заказывали за последние N дней
    stamps_gte: int | None = Field(None, ge=0)     # близки к подарку
    has_gift: bool | None = None
    birthday_month: int | None = Field(None, ge=1, le=12)
    min_orders: int | None = Field(None, ge=1)
    only_marketing_consent: bool = True


class BroadcastCreate(BaseModel):
    title: Name
    text: str = Field(min_length=1, max_length=1024)
    image_url: str | None = Field(None, max_length=512)
    button_text: str | None = Field(None, max_length=64)
    button_url: str | None = Field(None, max_length=512)
    segment: BroadcastSegment = BroadcastSegment()
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def button_pair(self):
        if bool(self.button_text) != bool(self.button_url):
            raise ValueError("button_text и button_url задаются вместе")
        return self


class BroadcastUpdate(BaseModel):
    title: Name | None = None
    text: str | None = Field(None, min_length=1, max_length=1024)
    image_url: str | None = Field(None, max_length=512)
    button_text: str | None = Field(None, max_length=64)
    button_url: str | None = Field(None, max_length=512)
    segment: BroadcastSegment | None = None
    scheduled_at: datetime | None = None


class BroadcastRead(BaseSchema):
    id: int
    title: str
    text: str
    image_url: str | None
    button_text: str | None
    button_url: str | None
    segment: BroadcastSegment
    status: BroadcastStatus
    scheduled_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    total_count: int
    sent_count: int
    failed_count: int
    created_at: datetime


class SegmentPreviewOut(BaseModel):
    count: int


class BroadcastTestIn(BaseModel):
    tg_id: int
