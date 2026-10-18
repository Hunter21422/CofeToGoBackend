from __future__ import annotations

from typing import Any

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, IdMixin, TimestampMixin


class Setting(IdMixin, TimestampMixin, Base):
    """Настройки key-value. location_id=NULL — глобальные, иначе переопределение для точки.

    Примеры ключей: loyalty.stamps_per_gift=5, loyalty.stamps_expire_days=90,
    orders.payment_timeout_min=15, texts.order_ready="Заказ {number} готов ☕"
    """

    __tablename__ = "settings"
    __table_args__ = (
        UniqueConstraint("key", "location_id", postgresql_nulls_not_distinct=True),
    )

    key: Mapped[str] = mapped_column(String(64), index=True)
    value: Mapped[Any] = mapped_column(JSONB)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    description: Mapped[str | None] = mapped_column(String(255))
