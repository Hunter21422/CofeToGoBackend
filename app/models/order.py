from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin, enum_type
from .enums import (
    ACTIVE_ORDER_STATUSES,
    CancelledBy,
    OrderPaymentStatus,
    OrderSource,
    OrderStatus,
    OrderType,
    PaymentMethod,
)

if TYPE_CHECKING:
    from .location import Location
    from .menu import Product, ProductVariant
    from .payment import Payment
    from .profile import Review
    from .promo import PromoCode
    from .staff import Staff
    from .user import User


class Order(IdMixin, TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        # #042 уникален в рамках точки и дня
        UniqueConstraint("location_id", "business_date", "number"),
        UniqueConstraint("user_id", "idempotency_key"),
        Index("ix_orders_location_status", "location_id", "status"),
        Index("ix_orders_user_created", "user_id", "created_at"),
        CheckConstraint("subtotal >= 0 AND discount_total >= 0 AND total >= 0", name="money_non_negative"),
        CheckConstraint("total = subtotal - discount_total", name="total_consistent"),
    )

    number: Mapped[int]
    business_date: Mapped[date]  # дата в TZ точки, для сброса нумерации

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))

    status: Mapped[OrderStatus] = mapped_column(enum_type(OrderStatus), default=OrderStatus.NEW)
    type: Mapped[OrderType] = mapped_column(enum_type(OrderType), default=OrderType.PICKUP)
    source: Mapped[OrderSource] = mapped_column(enum_type(OrderSource), default=OrderSource.MINIAPP)

    pickup_at: Mapped[datetime | None]  # NULL = как можно скорее
    estimated_ready_at: Mapped[datetime | None]
    comment: Mapped[str | None] = mapped_column(String(500))

    # Деньги в копейках
    subtotal: Mapped[int] = mapped_column(default=0)
    discount_total: Mapped[int] = mapped_column(default=0)
    total: Mapped[int] = mapped_column(default=0)

    promo_code_id: Mapped[int | None] = mapped_column(
        ForeignKey("promo_codes.id", ondelete="SET NULL")
    )
    gift_used: Mapped[bool] = mapped_column(default=False)
    loyalty_processed: Mapped[bool] = mapped_column(default=False)  # штампы уже начислены

    payment_method: Mapped[PaymentMethod] = mapped_column(enum_type(PaymentMethod))
    payment_status: Mapped[OrderPaymentStatus] = mapped_column(
        enum_type(OrderPaymentStatus), default=OrderPaymentStatus.UNPAID
    )

    idempotency_key: Mapped[str | None] = mapped_column(String(64))

    accepted_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    accepted_at: Mapped[datetime | None]
    ready_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
    cancelled_at: Mapped[datetime | None]
    cancelled_by: Mapped[CancelledBy | None] = mapped_column(enum_type(CancelledBy))
    cancel_reason: Mapped[str | None] = mapped_column(String(255))

    user: Mapped[User] = relationship(back_populates="orders", lazy="selectin")
    location: Mapped[Location] = relationship(lazy="selectin")
    promo_code: Mapped[PromoCode | None] = relationship()
    accepted_by: Mapped[Staff | None] = relationship(lazy="selectin")
    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderItem.id", lazy="selectin"
    )
    status_history: Mapped[list[OrderStatusHistory]] = relationship(
        back_populates="order", cascade="all, delete-orphan", order_by="OrderStatusHistory.id", lazy="selectin"
    )
    payments: Mapped[list[Payment]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )
    review: Mapped[Review | None] = relationship(back_populates="order", uselist=False, lazy="selectin")

    @property
    def display_number(self) -> str:
        return f"#{self.number:03d}"

    @property
    def items_count(self) -> int:
        return sum(i.quantity for i in self.items)

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_ORDER_STATUSES

    @property
    def loyalty_items_count(self) -> int:
        return sum(i.quantity for i in self.items if i.counts_for_loyalty and not i.is_gift)

    @property
    def loyalty_stamps(self) -> int:
        return 1 if self.loyalty_items_count > 0 else 0


class OrderItem(IdMixin, Base):
    """Всё хранится снапшотом — изменение меню не ломает старые заказы."""

    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price >= 0 AND line_total >= 0", name="money_non_negative"),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), index=True
    )
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="SET NULL")
    )

    product_name: Mapped[str] = mapped_column(String(128))
    variant_name: Mapped[str | None] = mapped_column(String(32))
    # [{"id": 3, "group": "Молоко", "name": "Овсяное", "price_delta": 6000}]
    modifiers: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    unit_price: Mapped[int]   # вариант + модификаторы, копейки
    quantity: Mapped[int] = mapped_column(default=1)
    line_total: Mapped[int]   # unit_price * quantity (подарок → 0)
    is_gift: Mapped[bool] = mapped_column(default=False)
    counts_for_loyalty: Mapped[bool] = mapped_column(default=False)
    comment: Mapped[str | None] = mapped_column(String(255))

    order: Mapped[Order] = relationship(back_populates="items")
    product: Mapped[Product | None] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()


class OrderStatusHistory(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "order_status_history"

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    from_status: Mapped[OrderStatus | None] = mapped_column(enum_type(OrderStatus))
    to_status: Mapped[OrderStatus] = mapped_column(enum_type(OrderStatus))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    comment: Mapped[str | None] = mapped_column(String(255))

    order: Mapped[Order] = relationship(back_populates="status_history")
    changed_by: Mapped[User | None] = relationship()
