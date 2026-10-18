from __future__ import annotations

from sqlalchemy import or_, select, update
from sqlalchemy.orm import selectinload

from app.models import Category, Modifier, ModifierGroup, Product, ProductModifierGroup, ProductVariant
from app.schemas.menu import ProductAdminFilter

from .base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    model = Category

    async def list_all(self) -> list[Category]:
        stmt = select(Category).order_by(Category.sort_order, Category.id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def by_slug(self, slug: str) -> Category | None:
        stmt = select(Category).where(Category.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def menu_tree(self) -> list[Category]:
        stmt = (
            select(Category)
            .where(Category.is_active.is_(True))
            .options(selectinload(Category.products).selectinload(Product.variants))
            .order_by(Category.sort_order, Category.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def reorder(self, ids: list[int]) -> None:
        for i, category_id in enumerate(ids):
            await self.session.execute(update(Category).where(Category.id == category_id).values(sort_order=i))


class ProductRepository(BaseRepository[Product]):
    model = Product

    def _full_options(self):
        return (
            selectinload(Product.variants),
            selectinload(Product.category),
            selectinload(Product.modifier_links)
            .selectinload(ProductModifierGroup.group)
            .selectinload(ModifierGroup.modifiers),
        )

    async def full(self, product_id: int) -> Product | None:
        stmt = select(Product).where(Product.id == product_id).options(*self._full_options())
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_slug(self, slug: str) -> Product | None:
        stmt = select(Product).where(Product.slug == slug)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def slug_taken(self, slug: str, exclude_id: int | None = None) -> bool:
        stmt = select(Product.id).where(Product.slug == slug)
        if exclude_id is not None:
            stmt = stmt.where(Product.id != exclude_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalar_one_or_none() is not None

    async def admin_page(self, f: ProductAdminFilter) -> tuple[list[Product], int]:
        stmt = select(Product).options(*self._full_options()).order_by(Product.sort_order, Product.id)
        if f.category_id:
            stmt = stmt.where(Product.category_id == f.category_id)
        if f.is_active is not None:
            stmt = stmt.where(Product.is_active.is_(f.is_active))
        if f.q:
            stmt = stmt.where(or_(Product.name.ilike(f"%{f.q}%"), Product.slug.ilike(f"%{f.q}%")))
        return await self.paginate_stmt(stmt, limit=f.limit, offset=f.offset)

    async def variants_by_ids(self, ids: list[int]) -> list[ProductVariant]:
        if not ids:
            return []
        stmt = (
            select(ProductVariant)
            .where(ProductVariant.id.in_(ids))
            .options(
                selectinload(ProductVariant.product)
                .selectinload(Product.modifier_links)
                .selectinload(ProductModifierGroup.group)
                .selectinload(ModifierGroup.modifiers)
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def set_modifiers(self, product: Product, modifier_ids: list[int]) -> None:
        groups: list[ModifierGroup] = []
        if modifier_ids:
            stmt = (
                select(ModifierGroup)
                .where(ModifierGroup.id.in_(select(Modifier.group_id).where(Modifier.id.in_(modifier_ids))))
                .options(selectinload(ModifierGroup.modifiers))
                .order_by(ModifierGroup.sort_order, ModifierGroup.id)
            )
            groups = list((await self.session.execute(stmt)).scalars().all())
        product.modifier_links.clear()
        await self.session.flush()
        for i, g in enumerate(groups):
            all_ids = [m.id for m in g.modifiers]
            picked = [m_id for m_id in all_ids if m_id in modifier_ids]
            link = ProductModifierGroup(group_id=g.id, sort_order=i, modifier_ids=None if picked == all_ids else picked)
            product.modifier_links.append(link)
        await self.session.flush()

    async def reorder(self, ids: list[int]) -> None:
        for i, product_id in enumerate(ids):
            await self.session.execute(update(Product).where(Product.id == product_id).values(sort_order=i))
