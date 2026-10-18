from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, CreatedAtMixin, IdMixin

if TYPE_CHECKING:
    from .location import Location
    from .menu import Product, ProductVariant
    from .modifier import Modifier
    from .staff import Staff


class StockItem(IdMixin, CreatedAtMixin, Base):
    """Стоп-лист: запись есть → позиция недоступна на точке (до until или до удаления)."""

    __tablename__ = "stock_items"
    __table_args__ = (
        CheckConstraint(
            "(product_id IS NOT NULL)::int + (variant_id IS NOT NULL)::int"
            " + (modifier_id IS NOT NULL)::int = 1",
            name="exactly_one_target",
        ),
        Index("ix_stock_items_location_product", "location_id", "product_id"),
    )

    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id", ondelete="CASCADE"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    variant_id: Mapped[int | None] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE")
    )
    modifier_id: Mapped[int | None] = mapped_column(
        ForeignKey("modifiers.id", ondelete="CASCADE")
    )
    until: Mapped[datetime | None]  # NULL = пока вручную не вернут
    reason: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("staff.id", ondelete="SET NULL"))

    location: Mapped[Location] = relationship(back_populates="stock_items")
    product: Mapped[Product | None] = relationship()
    variant: Mapped[ProductVariant | None] = relationship()
    modifier: Mapped[Modifier | None] = relationship()
    created_by: Mapped[Staff | None] = relationship()

    @property
    def title(self) -> str:
        if self.product is not None:
            return self.product.name
        if self.variant is not None:
            return f"{self.variant.product.name} {self.variant.name}"
        if self.modifier is not None:
            return self.modifier.name
        return ""
