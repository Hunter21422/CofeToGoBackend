from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .location import Location
    from .menu import Product, ProductVariant
    from .order import Order
    from .user import User


class Favorite(IdMixin, TimestampMixin, Base):
    """Сохранённая сборка: «Мой капучино» — L, овсяное, карамель. Заказ в один тап."""

    __tablename__ = "favorites"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE")
    )
    modifier_ids: Mapped[list[int]] = mapped_column(JSONB, default=list)
    custom_name: Mapped[str | None] = mapped_column(String(64))
    sort_order: Mapped[int] = mapped_column(default=0)

    user: Mapped[User] = relationship(back_populates="favorites")
    product: Mapped[Product] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()


class Review(IdMixin, TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),)

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    rating: Mapped[int] = mapped_column(SmallInteger)
    comment: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)  # fast, tasty, cold…

    reply: Mapped[str | None] = mapped_column(Text)
    replied_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    replied_at: Mapped[datetime | None]

    order: Mapped[Order] = relationship(back_populates="review")
    user: Mapped[User] = relationship(foreign_keys=[user_id])
    location: Mapped[Location | None] = relationship()
    replied_by: Mapped[User | None] = relationship(foreign_keys=[replied_by_id])

    @property
    def order_number(self) -> str:
        return self.order.display_number if self.order is not None else ""
