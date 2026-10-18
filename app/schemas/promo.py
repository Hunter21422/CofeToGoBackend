from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import PromoType

from .common import BaseSchema, Money, PaginationParams, PromoCodeStr


class PromoCheckIn(BaseModel):
    code: PromoCodeStr
    location_id: int


class PromoCheckOut(BaseModel):
    valid: bool
    discount_preview: Money | None = None
    message: str


class _PromoFields(BaseModel):
    description: str | None = Field(None, max_length=255)
    min_order_total: Money | None = None
    max_discount: Money | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit_total: int | None = Field(None, ge=1)
    usage_limit_per_user: int | None = Field(1, ge=1)
    first_order_only: bool = False
    location_ids: list[int] | None = None


class PromoCodeCreate(_PromoFields):
    code: PromoCodeStr
    type: PromoType
    value: int = Field(0, ge=0)  # % или копейки
    product_id: int | None = None

    @model_validator(mode="after")
    def check(self):
        if self.type == PromoType.PERCENT and not 1 <= self.value <= 100:
            raise ValueError("Процент должен быть от 1 до 100")
        if self.type == PromoType.FIXED and self.value <= 0:
            raise ValueError("Сумма скидки должна быть больше 0")
        if self.type == PromoType.FREE_PRODUCT and not self.product_id:
            raise ValueError("Для free_product нужен product_id")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at должен быть позже starts_at")
        return self


class PromoCodeUpdate(BaseModel):
    description: str | None = Field(None, max_length=255)
    value: int | None = Field(None, ge=0)
    product_id: int | None = None
    min_order_total: Money | None = None
    max_discount: Money | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    usage_limit_total: int | None = Field(None, ge=1)
    usage_limit_per_user: int | None = Field(None, ge=1)
    first_order_only: bool | None = None
    location_ids: list[int] | None = None
    is_active: bool | None = None


class PromoCodeRead(BaseSchema):
    id: int
    code: str
    description: str | None
    type: PromoType
    value: int
    product_id: int | None
    min_order_total: Money | None
    max_discount: Money | None
    starts_at: datetime | None
    ends_at: datetime | None
    usage_limit_total: int | None
    usage_limit_per_user: int | None
    used_count: int
    first_order_only: bool
    location_ids: list[int] | None
    is_active: bool
    created_at: datetime


class PromoFilter(PaginationParams):
    q: str | None = None
    is_active: bool | None = None
    type: PromoType | None = None
    expired: bool | None = None


class PromoGenerateIn(_PromoFields):
    """Массовая генерация одноразовых кодов: PREFIX-XXXXXX"""

    prefix: str = Field(min_length=2, max_length=10, pattern=r"^[A-Z0-9]+$")
    count: int = Field(ge=1, le=1000)
    type: PromoType
    value: int = Field(0, ge=0)
    product_id: int | None = None
