from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin, enum_type
from .enums import NotificationStatus, NotificationType

if TYPE_CHECKING:
    from .user import User


class NotificationLog(IdMixin, CreatedAtMixin, Base):
    """Каждое сообщение бота — чтобы понимать, что дошло, а что нет (бот заблокирован и т.п.)."""

    __tablename__ = "notification_logs"
    __table_args__ = (Index("ix_notification_logs_user_created", "user_id", "created_at"),)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(enum_type(NotificationType))
    status: Mapped[NotificationStatus] = mapped_column(
        enum_type(NotificationStatus), default=NotificationStatus.PENDING
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id", ondelete="SET NULL"))
    broadcast_id: Mapped[int | None] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="SET NULL"), index=True
    )
    tg_message_id: Mapped[int | None]
    error: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None]

    user: Mapped[User] = relationship()
