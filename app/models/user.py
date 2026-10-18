from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .location import Location
    from .loyalty import LoyaltyAccount
    from .order import Order
    from .profile import Favorite
    from .staff import Staff


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # NULL — гость пришёл с сайта по SMS и Telegram ещё не привязал
    tg_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    last_name: Mapped[str | None] = mapped_column(String(128))
    photo_url: Mapped[str | None] = mapped_column(String(512))
    language_code: Mapped[str] = mapped_column(String(8), default="ru")

    # Профиль
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    birth_date: Mapped[date | None]
    favorite_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL")
    )

    # Рефералка
    referral_code: Mapped[str] = mapped_column(String(16), unique=True)
    referred_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )

    # Настройки
    marketing_consent: Mapped[bool] = mapped_column(default=False)
    notifications_enabled: Mapped[bool] = mapped_column(default=True)

    # Модерация / активность
    is_blocked: Mapped[bool] = mapped_column(default=False)
    blocked_reason: Mapped[str | None] = mapped_column(String(255))
    last_seen_at: Mapped[datetime | None]

    loyalty_account: Mapped[LoyaltyAccount | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    staff: Mapped[Staff | None] = relationship(
        back_populates="user", uselist=False, foreign_keys="Staff.user_id", lazy="selectin"
    )
    orders: Mapped[list[Order]] = relationship(back_populates="user")
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list[RefreshToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorite_location: Mapped[Location | None] = relationship()
    referred_by: Mapped[User | None] = relationship(remote_side="User.id")

    @property
    def role(self):
        return self.staff.role if self.staff and self.staff.is_active else None

    @property
    def full_name(self) -> str:
        return " ".join(p for p in (self.first_name, self.last_name) if p)


class RefreshToken(IdMixin, TimestampMixin, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)  # sha256, сам токен не храним
    user_agent: Mapped[str | None] = mapped_column(String(512))
    ip: Mapped[str | None] = mapped_column(String(45))
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="refresh_tokens")
