from __future__ import annotations

from datetime import date, datetime, time
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from sqlalchemy import CheckConstraint, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin
from .enums import PaymentMethod

if TYPE_CHECKING:
    from .staff import Staff
    from .stock import StockItem


class Location(IdMixin, TimestampMixin, Base):
    __tablename__ = "locations"

    name: Mapped[str] = mapped_column(String(128))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    address: Mapped[str] = mapped_column(String(255))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    phone: Mapped[str | None] = mapped_column(String(20))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")

    is_active: Mapped[bool] = mapped_column(default=True)
    accepts_orders: Mapped[bool] = mapped_column(default=True)  # быстрый стоп онлайн-заказов
    payment_methods: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        default=lambda: [PaymentMethod.CARD_ONLINE.value, PaymentMethod.SBP.value],
    )

    avg_prep_minutes: Mapped[int] = mapped_column(default=7)
    min_pickup_minutes: Mapped[int] = mapped_column(default=5)
    max_orders_per_slot: Mapped[int | None]  # лимит заказов на 15-минутный слот
    sort_order: Mapped[int] = mapped_column(default=0)

    hours: Mapped[list[LocationHours]] = relationship(
        back_populates="location", cascade="all, delete-orphan", order_by="LocationHours.weekday"
    )
    special_days: Mapped[list[LocationSpecialDay]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    staff: Mapped[list[Staff]] = relationship(back_populates="location")
    stock_items: Mapped[list[StockItem]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    @property
    def is_open_now(self) -> bool:
        now = datetime.now(ZoneInfo(self.timezone))
        day = next((d for d in self.special_days if d.date == now.date()), None)
        if day is None:
            day = next((h for h in self.hours if h.weekday == now.weekday()), None)
        if day is None or day.is_closed or day.opens_at is None or day.closes_at is None:
            return False
        t = now.time()
        if day.opens_at <= day.closes_at:
            return day.opens_at <= t < day.closes_at
        return t >= day.opens_at or t < day.closes_at


class LocationHours(IdMixin, Base):
    __tablename__ = "location_hours"
    __table_args__ = (
        UniqueConstraint("location_id", "weekday"),
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_range"),
    )

    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    weekday: Mapped[int] = mapped_column(SmallInteger)  # 0 = понедельник
    opens_at: Mapped[time | None]
    closes_at: Mapped[time | None]  # может быть < opens_at, если работают после полуночи
    is_closed: Mapped[bool] = mapped_column(default=False)

    location: Mapped[Location] = relationship(back_populates="hours")


class LocationSpecialDay(IdMixin, Base):
    """Праздники, санитарные дни, сокращённые смены."""

    __tablename__ = "location_special_days"
    __table_args__ = (UniqueConstraint("location_id", "date"),)

    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    date: Mapped[date]
    opens_at: Mapped[time | None]
    closes_at: Mapped[time | None]
    is_closed: Mapped[bool] = mapped_column(default=False)
    comment: Mapped[str | None] = mapped_column(String(255))

    location: Mapped[Location] = relationship(back_populates="special_days")
