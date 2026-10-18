"""Экран профиля, избранное, отзывы, карточка клиента в админке."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from .common import BaseSchema, Money, PaginationParams, Rating
from .location import LocationShort
from .loyalty import LoyaltyRead
from .menu import ModifierRead, ProductShort, VariantRead
from .order import OrderShort
from .user import UserRead, UserShort

ReviewTag = Literal["fast", "tasty", "friendly", "slow", "cold", "wrong_order"]


# ---------- Профиль ----------
class ProfileOut(BaseModel):
    user: UserRead
    loyalty: LoyaltyRead
    orders_count: int
    active_orders: list[OrderShort]
    favorites_count: int = 0


class CustomerDetail(BaseModel):
    user: UserRead
    loyalty: LoyaltyRead
    last_orders: list[OrderShort]
    orders_count: int = 0
    total_spent: Money = 0
    is_blocked: bool = False


# ---------- Избранное ----------
class FavoriteCreate(BaseModel):
    product_id: int
    variant_id: int | None = None
    modifier_ids: list[int] = []
    custom_name: str | None = Field(None, max_length=64)


class FavoriteUpdate(BaseModel):
    custom_name: str | None = Field(None, max_length=64)
    sort_order: int | None = None


class FavoriteRead(BaseModel):
    id: int
    product: ProductShort
    variant: VariantRead | None
    modifiers: list[ModifierRead]
    custom_name: str | None
    price: Money          # актуальная цена сборки
    is_available: bool


# ---------- Отзывы ----------
class ReviewCreate(BaseModel):
    rating: Rating
    comment: str | None = Field(None, max_length=1000)
    tags: list[ReviewTag] = []


class ReviewRead(BaseSchema):
    id: int
    order_id: int
    rating: int
    comment: str | None
    tags: list[str]
    reply: str | None
    replied_at: datetime | None
    created_at: datetime


class ReviewAdminRead(ReviewRead):
    user: UserShort
    location: LocationShort | None
    order_number: str = ""


class ReviewReplyIn(BaseModel):
    reply: str = Field(min_length=1, max_length=1000)


class ReviewFilter(PaginationParams):
    location_id: int | None = None
    rating: list[int] = []
    has_comment: bool | None = None
    has_reply: bool | None = None
    date_from: date | None = None
    date_to: date | None = None
