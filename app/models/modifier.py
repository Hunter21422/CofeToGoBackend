from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IdMixin, TimestampMixin

if TYPE_CHECKING:
    from .menu import Product


class ModifierGroup(IdMixin, TimestampMixin, Base):
    """«Молоко», «Сироп», «Доп. шот». min_select=1 → обязательный выбор."""

    __tablename__ = "modifier_groups"
    __table_args__ = (
        CheckConstraint("min_select >= 0", name="min_non_negative"),
        CheckConstraint("max_select >= min_select AND max_select >= 1", name="max_gte_min"),
    )

    name: Mapped[str] = mapped_column(String(128))
    min_select: Mapped[int] = mapped_column(default=0)
    max_select: Mapped[int] = mapped_column(default=1)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    modifiers: Mapped[list[Modifier]] = relationship(
        back_populates="group", cascade="all, delete-orphan", order_by="Modifier.sort_order"
    )
    product_links: Mapped[list[ProductModifierGroup]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )

    @property
    def is_required(self) -> bool:
        return self.min_select > 0

    @property
    def is_multiple(self) -> bool:
        return self.max_select > 1


class Modifier(IdMixin, TimestampMixin, Base):
    __tablename__ = "modifiers"
    __table_args__ = (CheckConstraint("price_delta >= 0", name="price_delta_non_negative"),)

    group_id: Mapped[int] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))  # «Овсяное», «Карамель»
    price_delta: Mapped[int] = mapped_column(default=0)  # копейки
    is_default: Mapped[bool] = mapped_column(default=False)
    sort_order: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)

    group: Mapped[ModifierGroup] = relationship(back_populates="modifiers")


class ProductModifierGroup(Base):
    """M2M: какие группы модификаторов доступны у товара и какие добавки из них отмечены."""

    __tablename__ = "product_modifier_groups"

    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[int] = mapped_column(
        ForeignKey("modifier_groups.id", ondelete="CASCADE"), primary_key=True
    )
    sort_order: Mapped[int] = mapped_column(default=0)
    # id отмеченных добавок группы; NULL = все добавки группы
    modifier_ids: Mapped[list[int] | None] = mapped_column(JSONB)

    product: Mapped[Product] = relationship(back_populates="modifier_links")
    group: Mapped[ModifierGroup] = relationship(back_populates="product_links")
