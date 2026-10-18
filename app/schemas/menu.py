from datetime import datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from .common import BaseSchema, Money, Name, PaginationParams, Slug
from .location import LocationShort
from .marketing import BannerRead


# ---------- Клиент ----------
class ModifierRead(BaseSchema):
    id: int
    name: str
    price_delta: Money
    is_default: bool
    is_available: bool = True


class ModifierGroupRead(BaseSchema):
    id: int
    name: str
    min_select: int
    max_select: int
    modifiers: list[ModifierRead]


class VariantRead(BaseSchema):
    id: int
    name: str
    volume_ml: int | None
    price: Money
    old_price: Money | None
    is_default: bool
    is_available: bool = True
    calories: Decimal | None
    proteins: Decimal | None
    fats: Decimal | None
    carbs: Decimal | None


class ProductShort(BaseSchema):
    id: int
    name: str
    slug: str
    description: str | None
    image_url: str | None
    min_price: Money | None
    tags: list[str]
    is_available: bool = True


class ProductRead(ProductShort):
    composition: str | None
    counts_for_loyalty: bool
    can_be_gift: bool
    variants: list[VariantRead]
    modifier_groups: list[ModifierGroupRead]
    is_favorite: bool = False


class CategoryRead(BaseSchema):
    id: int
    name: str
    slug: str
    icon: str | None
    image_url: str | None
    products: list[ProductShort]


class MenuOut(BaseModel):
    location: LocationShort
    categories: list[CategoryRead]
    banners: list[BannerRead]


class MenuSearchParams(BaseModel):
    q: str = Field(min_length=2, max_length=64)
    category_id: int | None = None
    tags: list[str] = []


# ---------- Админка: категории ----------
class CategoryCreate(BaseModel):
    name: Name
    slug: Slug
    icon: str | None = Field(None, max_length=64)
    image_url: str | None = Field(None, max_length=512)
    sort_order: int = 0
    available_from: time | None = None
    available_to: time | None = None


class CategoryUpdate(BaseModel):
    name: Name | None = None
    slug: Slug | None = None
    icon: str | None = Field(None, max_length=64)
    image_url: str | None = Field(None, max_length=512)
    sort_order: int | None = None
    available_from: time | None = None
    available_to: time | None = None
    is_active: bool | None = None


class CategoryAdminRead(BaseSchema):
    id: int
    name: str
    slug: str
    icon: str | None
    image_url: str | None
    sort_order: int
    available_from: time | None
    available_to: time | None
    is_active: bool


# ---------- Админка: товары ----------
class VariantIn(BaseModel):
    id: int | None = None  # None = новый вариант
    name: str = Field(min_length=1, max_length=32)
    volume_ml: int | None = Field(None, ge=1)
    price: Money
    old_price: Money | None = None
    sku: str | None = Field(None, max_length=64)
    calories: Decimal | None = Field(None, ge=0)
    proteins: Decimal | None = Field(None, ge=0)
    fats: Decimal | None = Field(None, ge=0)
    carbs: Decimal | None = Field(None, ge=0)
    is_default: bool = False
    sort_order: int = 0
    is_active: bool = True

    @model_validator(mode="after")
    def old_price_gt_price(self):
        if self.old_price is not None and self.old_price <= self.price:
            raise ValueError("old_price должна быть больше price")
        return self


def _check_variants(v: list[VariantIn] | None) -> list[VariantIn] | None:
    if v is None:
        return v
    defaults = sum(1 for x in v if x.is_default)
    if defaults > 1:
        raise ValueError("Вариант по умолчанию может быть только один")
    if defaults == 0 and v:
        v[0].is_default = True
    return v


class ProductCreate(BaseModel):
    category_id: int
    name: Name
    slug: Slug
    description: str | None = Field(None, max_length=2000)
    composition: str | None = Field(None, max_length=2000)
    image_url: str | None = Field(None, max_length=512)
    tags: list[str] = []
    counts_for_loyalty: bool = True  # напиток: даёт штамп и может быть подарком (can_be_gift = это же значение)
    sort_order: int = 0
    variants: list[VariantIn] = Field(min_length=1)
    modifier_ids: list[int] = []  # отмеченные добавки; группы сервис выводит из них сам

    @field_validator("variants")
    @classmethod
    def check_variants(cls, v: list[VariantIn] | None) -> list[VariantIn] | None:
        return _check_variants(v)


class ProductUpdate(BaseModel):
    category_id: int | None = None
    name: Name | None = None
    slug: Slug | None = None
    description: str | None = Field(None, max_length=2000)
    composition: str | None = Field(None, max_length=2000)
    image_url: str | None = Field(None, max_length=512)
    tags: list[str] | None = None
    counts_for_loyalty: bool | None = None
    sort_order: int | None = None
    variants: list[VariantIn] | None = Field(None, min_length=1)
    modifier_ids: list[int] | None = None
    is_active: bool | None = None

    @field_validator("variants")
    @classmethod
    def check_variants(cls, v: list[VariantIn] | None) -> list[VariantIn] | None:
        return _check_variants(v)


class VariantAdminRead(VariantRead):
    sku: str | None
    sort_order: int
    is_active: bool


class ProductAdminRead(BaseSchema):
    id: int
    category_id: int
    name: str
    slug: str
    description: str | None
    composition: str | None
    image_url: str | None
    tags: list[str]
    counts_for_loyalty: bool
    can_be_gift: bool
    sort_order: int
    is_active: bool
    variants: list[VariantAdminRead]
    modifier_groups: list[ModifierGroupRead]
    created_at: datetime


class ProductAdminFilter(PaginationParams):
    category_id: int | None = None
    is_active: bool | None = None
    q: str | None = None


class ReorderIn(BaseModel):
    ids: list[int] = Field(min_length=1)
