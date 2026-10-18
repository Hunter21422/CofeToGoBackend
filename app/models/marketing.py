from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin, enum_type
from .enums import BannerLinkType, BroadcastStatus

if TYPE_CHECKING:
    from .user import User


class Banner(IdMixin, TimestampMixin, Base):
    __tablename__ = "banners"

    title: Mapped[str] = mapped_column(String(128))
    subtitle: Mapped[str | None] = mapped_column(String(255))
    image_url: Mapped[str] = mapped_column(String(512))
    link_type: Mapped[BannerLinkType] = mapped_column(
        enum_type(BannerLinkType), default=BannerLinkType.NONE
    )
    link_value: Mapped[str | None] = mapped_column(String(512))  # id товара/категории или URL
    location_ids: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))  # NULL = везде
    starts_at: Mapped[datetime | None]
    ends_at: Mapped[datetime | None]
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class Broadcast(IdMixin, TimestampMixin, Base):
    """Рассылка через бота по сегменту клиентов."""

    __tablename__ = "broadcasts"

    title: Mapped[str] = mapped_column(String(128))  # внутреннее название
    text: Mapped[str] = mapped_column(Text)          # HTML-разметка Telegram
    image_url: Mapped[str | None] = mapped_column(String(512))
    button_text: Mapped[str | None] = mapped_column(String(64))
    button_url: Mapped[str | None] = mapped_column(String(512))
    # {"location_ids": [1], "inactive_days": 30, "stamps_gte": 4, "birthday_month": 10}
    segment: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    status: Mapped[BroadcastStatus] = mapped_column(
        enum_type(BroadcastStatus), default=BroadcastStatus.DRAFT
    )
    scheduled_at: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    total_count: Mapped[int] = mapped_column(default=0)
    sent_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_by: Mapped[User | None] = relationship()
