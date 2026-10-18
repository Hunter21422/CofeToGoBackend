from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin, enum_type
from .enums import PaymentProvider, PaymentStatus, RefundStatus

if TYPE_CHECKING:
    from .order import Order
    from .user import User


class Payment(IdMixin, TimestampMixin, Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("refunded_amount >= 0 AND refunded_amount <= amount", name="refund_le_amount"),
    )

    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    provider: Mapped[PaymentProvider] = mapped_column(enum_type(PaymentProvider))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # id в ЮKassa
    amount: Mapped[int]  # копейки
    currency: Mapped[str] = mapped_column(String(3), default="RUB")
    status: Mapped[PaymentStatus] = mapped_column(
        enum_type(PaymentStatus), default=PaymentStatus.PENDING
    )
    confirmation_url: Mapped[str | None] = mapped_column(String(1024))
    paid_at: Mapped[datetime | None]
    refunded_amount: Mapped[int] = mapped_column(default=0)
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    order: Mapped[Order] = relationship(back_populates="payments")
    refunds: Mapped[list[Refund]] = relationship(
        back_populates="payment", cascade="all, delete-orphan"
    )


class Refund(IdMixin, TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"), index=True
    )
    amount: Mapped[int]
    reason: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[RefundStatus] = mapped_column(enum_type(RefundStatus), default=RefundStatus.PENDING)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    payment: Mapped[Payment] = relationship(back_populates="refunds")
    created_by: Mapped[User | None] = relationship()
