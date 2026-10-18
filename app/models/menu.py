from __future__ import annotations

from datetime import time
from decimal import Decimal
from types import SimpleNamespace
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .modifier import ProductModifierGroup


class Category(IdMixin, TimestampMixin, Base):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    icon: Mapped[str | None] = mapped_column(String(64))  # эмодзи или имя иконки
    image_url: Mapped[str | None] = mapped_column(String(512))
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    # Например «Завтраки» только до 12:00. NULL = весь день
    available_from: Mapped[time | None]
    available_to: Mapped[time | None]

    products: Mapped[list[Product]] = relationship(
        back_populates="category", order_by="Product.sort_order"
    )


class Product(IdMixin, TimestampMixin, Base):
    __tablename__ = "products"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    composition: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)  # new, hit, vegan…

    counts_for_loyalty: Mapped[bool] = mapped_column(default=True)  # идёт в счётчик 6-го кофе
    can_be_gift: Mapped[bool] = mapped_column(default=True)         # = counts_for_loyalty, ставит сервис: подарком может быть любой напиток

    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    category: Mapped[Category] = relationship(back_populates="products")
    variants: Mapped[list[ProductVariant]] = relationship(
        back_populates="product", cascade="all, delete-orphan", order_by="ProductVariant.sort_order"
    )
    modifier_links: Mapped[list[ProductModifierGroup]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductModifierGroup.sort_order",
    )

    @property
    def modifier_groups(self):
        groups = []
        for link in self.modifier_links:
            g = link.group
            mods = [m for m in g.modifiers if m.is_active and (link.modifier_ids is None or m.id in link.modifier_ids)]
            if g.is_active and mods:
                groups.append(SimpleNamespace(id=g.id, name=g.name, min_select=g.min_select, max_select=min(g.max_select, len(mods)), modifiers=mods))
        return groups

    @property
    def min_price(self) -> int | None:
        prices = [v.price for v in self.variants if v.is_active]
        return min(prices) if prices else None


class ProductVariant(IdMixin, TimestampMixin, Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("price >= 0", name="price_non_negative"),
        CheckConstraint("old_price IS NULL OR old_price > price", name="old_price_gt_price"),
    )

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(32))  # S / M / L / «0,3 л»
    volume_ml: Mapped[int | None]
    price: Mapped[int]                  # копейки
    old_price: Mapped[int | None]       # зачёркнутая цена
    sku: Mapped[str | None] = mapped_column(String(64), unique=True)  # для интеграции с кассой

    calories: Mapped[Decimal | None] = mapped_column(Numeric(6, 1))
    proteins: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    fats: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    carbs: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))

    is_default: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    product: Mapped[Product] = relationship(back_populates="variants")
