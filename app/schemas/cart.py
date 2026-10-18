from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from .common import Money, PromoCodeStr, Quantity


class CartItemIn(BaseModel):
    product_id: int
    variant_id: int
    modifier_ids: list[int] = []
    quantity: Quantity = 1
    comment: str | None = Field(None, max_length=255)

    @field_validator("modifier_ids")
    @classmethod
    def unique_modifiers(cls, v: list[int]) -> list[int]:
        if len(v) != len(set(v)):
            raise ValueError("Модификаторы повторяются")
        return v


class CartQuoteIn(BaseModel):
    location_id: int
    items: list[CartItemIn] = Field(min_length=1, max_length=30)
    promo_code: PromoCodeStr | None = None
    use_gift: bool = False
    pickup_at: datetime | None = None  # None = как можно скорее


class CartItemQuote(BaseModel):
    index: int
    product_name: str
    variant_name: str | None
    modifiers: list[str]
    unit_price: Money
    quantity: int
    line_total: Money
    is_gift: bool = False
    is_available: bool = True
    error: str | None = None


class CartQuoteOut(BaseModel):
    items: list[CartItemQuote]
    subtotal: Money
    promo_discount: Money = 0
    gift_discount: Money = 0
    discount_total: Money
    total: Money
    promo_error: str | None = None
    gift_available: bool = False
    gift_applicable: bool = False
    stamps_to_earn: int = 0
    estimated_ready_at: datetime | None = None
    warnings: list[str] = []
    can_checkout: bool
