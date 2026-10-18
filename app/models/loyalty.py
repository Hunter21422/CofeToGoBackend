from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin, TimestampMixin, enum_type
from .enums import LoyaltyTier, LoyaltyTxType

if TYPE_CHECKING:
    from .location import Location
    from .order import Order
    from .staff import Staff
    from .user import User


class LoyaltyAccount(TimestampMixin, Base):
    """Карта «6-й напиток в подарок». Один аккаунт на юзера."""

    __tablename__ = "loyalty_accounts"
    __table_args__ = (
        CheckConstraint("stamps >= 0", name="stamps_non_negative"),
        CheckConstraint("gifts_available >= 0", name="gifts_non_negative"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stamps: Mapped[int] = mapped_column(default=0)           # текущие, 0..stamps_per_gift-1
    gifts_available: Mapped[int] = mapped_column(default=0)  # накоплено, не потрачено
    lifetime_stamps: Mapped[int] = mapped_column(default=0)
    lifetime_gifts: Mapped[int] = mapped_column(default=0)
    tier: Mapped[LoyaltyTier] = mapped_column(enum_type(LoyaltyTier), default=LoyaltyTier.BASE)
    last_activity_at: Mapped[datetime | None]  # для сгорания штампов

    # Optimistic lock: параллельные апдейты одной карты упадут с StaleDataError, а не затрут друг друга
    version: Mapped[int] = mapped_column(default=1)
    __mapper_args__ = {"version_id_col": version}

    user: Mapped[User] = relationship(back_populates="loyalty_account")
    transactions: Mapped[list[LoyaltyTransaction]] = relationship(
        back_populates="account",
        primaryjoin="LoyaltyAccount.user_id == foreign(LoyaltyTransaction.user_id)",
        order_by="LoyaltyTransaction.id.desc()",
        viewonly=True,
    )


class LoyaltyTransaction(IdMixin, CreatedAtMixin, Base):
    __tablename__ = "loyalty_transactions"
    __table_args__ = (Index("ix_loyalty_tx_user_created", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[LoyaltyTxType] = mapped_column(enum_type(LoyaltyTxType))
    stamps_delta: Mapped[int] = mapped_column(default=0)
    gifts_delta: Mapped[int] = mapped_column(default=0)
    # Баланс после операции — удобно для истории и разборов
    stamps_after: Mapped[int]
    gifts_after: Mapped[int]

    order_id: Mapped[int | None] = mapped_column(
        ForeignKey("orders.id", ondelete="SET NULL"), index=True
    )
    staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"))
    reason: Mapped[str | None] = mapped_column(String(255))  # обязателен для manual_adjust

    account: Mapped[LoyaltyAccount] = relationship(
        back_populates="transactions",
        primaryjoin="LoyaltyAccount.user_id == foreign(LoyaltyTransaction.user_id)",
        viewonly=True,
    )
    order: Mapped[Order | None] = relationship()
    staff: Mapped[Staff | None] = relationship()
    location: Mapped[Location | None] = relationship()
