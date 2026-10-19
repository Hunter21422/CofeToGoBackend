from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin, enum_type
from .enums import StaffRole

if TYPE_CHECKING:
    from .location import Location
    from .user import User


class Staff(IdMixin, TimestampMixin, Base):
    __tablename__ = "staff"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    role: Mapped[StaffRole] = mapped_column(enum_type(StaffRole), default=StaffRole.BARISTA)
    # NULL = доступ ко всем точкам (owner)
    location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id", ondelete="SET NULL"), index=True
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    # Кто добавил — сотрудника может создать только owner
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    # ---- второй фактор: личный PIN ----
    # Хранится только хеш (argon2/bcrypt). Сотрудник задаёт PIN сам при первом входе — владелец его не знает.
    pin_hash: Mapped[str | None] = mapped_column(String(255))
    pin_set_at: Mapped[datetime | None]
    pin_failed_attempts: Mapped[int] = mapped_column(SmallInteger, default=0)
    pin_locked_until: Mapped[datetime | None]
    # Все токены, выданные раньше этого момента, недействительны («завершить все сеансы», сброс PIN)
    tokens_valid_after: Mapped[datetime | None]
    last_login_at: Mapped[datetime | None]

    user: Mapped[User] = relationship(back_populates="staff", foreign_keys=[user_id], lazy="selectin")
    location: Mapped[Location | None] = relationship(back_populates="staff")

    @property
    def phone_linked(self) -> bool:
        return bool(self.user and self.user.phone)

    @property
    def phone(self) -> str | None:
        return self.user.phone if self.user else None

    @property
    def pin_set(self) -> bool:
        return self.pin_hash is not None

    def pin_locked(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.pin_locked_until is not None and self.pin_locked_until > now

    def can_access_location(self, location_id: int) -> bool:
        return self.is_active and (self.location_id is None or self.location_id == location_id)
