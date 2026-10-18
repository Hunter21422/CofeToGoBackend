from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin, enum_type
from .enums import PromoType

if TYPE_CHECKING:
    from .menu import Product
    from .order import Order
    from .user import User


class PromoCode(IdMixin, TimestampMixin, Base):
    __tablename__ = "promo_codes"
    __table_args__ = (
        CheckConstraint("value >= 0", name="value_non_negative"),
        CheckConstraint("type <> 'percent' OR value <= 100", name="percent_le_100"),
        CheckConstraint("type <> 'free_product' OR product_id IS NOT NULL", name="free_product_has_product"),
    )

    code: Mapped[str] = mapped_column(String(32), unique=True)  # храним в UPPER
    description: Mapped[str | None] = mapped_column(String(255))
    type: Mapped[PromoType] = mapped_column(enum_type(PromoType))
    value: Mapped[int] = mapped_column(default=0)  # % или копейки
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))

    min_order_total: Mapped[int | None]
    max_discount: Mapped[int | None]
    starts_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]
    usage_limit_total: Mapped[int | None]
    usage_limit_per_user: Mapped[int | None] = mapped_column(default=1)
    used_count: Mapped[int] = mapped_column(default=0)
    first_order_only: Mapped[bool] = mapped_column(default=False)
    location_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))  # NULL = все точки
    is_active: Mapped[bool] = mapped_column(default=True)

    product: Mapped[Product | None] = relationship()
    redemptions: Mapped[list[PromoRedemption]] = relationship(back_populates="promo_code")


class PromoRedemption(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (Index("ix_promo_redemptions_promo_user", "promo_code_id", "user_id"),)

    promo_code_id: Mapped[int] = mapped_column(ForeignKey("promo_codes.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)
    discount_amount: Mapped[int]

    promo_code: Mapped[PromoCode] = relationship(back_populates="redemptions")
    user: Mapped[User] = relationship()
    order: Mapped[Order] = relationship()
