from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.models import Favorite, Product, Review
from app.schemas.profile import ReviewFilter

from .base import BaseRepository


class FavoriteRepository(BaseRepository[Favorite]):
    model = Favorite

    async def for_user(self, user_id: int) -> list[Favorite]:
        stmt = (
            select(Favorite)
            .where(Favorite.user_id == user_id)
            .options(selectinload(Favorite.product).selectinload(Product.variants), selectinload(Favorite.variant))
            .order_by(Favorite.sort_order, Favorite.id)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def for_user_one(self, favorite_id: int, user_id: int) -> Favorite | None:
        stmt = select(Favorite).where(Favorite.id == favorite_id, Favorite.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def product_ids(self, user_id: int) -> set[int]:
        stmt = select(Favorite.product_id).where(Favorite.user_id == user_id)
        result = await self.session.execute(stmt)
        return set(result.scalars().all())

    async def count_for_user(self, user_id: int) -> int:
        stmt = select(func.count(Favorite.id)).where(Favorite.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one()


class ReviewRepository(BaseRepository[Review]):
    model = Review

    async def full(self, review_id: int) -> Review | None:
        stmt = (
            select(Review)
            .where(Review.id == review_id)
            .options(selectinload(Review.user), selectinload(Review.order), selectinload(Review.location))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def by_order(self, order_id: int) -> Review | None:
        stmt = select(Review).where(Review.order_id == order_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def admin_page(self, f: ReviewFilter) -> tuple[list[Review], int]:
        stmt = (
            select(Review)
            .options(selectinload(Review.user), selectinload(Review.order), selectinload(Review.location))
            .order_by(Review.created_at.desc())
        )
        if f.location_id:
            stmt = stmt.where(Review.location_id == f.location_id)
        if f.rating:
            stmt = stmt.where(Review.rating.in_(f.rating))
        if f.has_comment is not None:
            stmt = stmt.where(Review.comment.is_not(None) if f.has_comment else Review.comment.is_(None))
        if f.has_reply is not None:
            stmt = stmt.where(Review.reply.is_not(None) if f.has_reply else Review.reply.is_(None))
        if f.date_from:
            stmt = stmt.where(func.date(Review.created_at) >= f.date_from)
        if f.date_to:
            stmt = stmt.where(func.date(Review.created_at) <= f.date_to)
        return await self.paginate_stmt(stmt, limit=f.limit, offset=f.offset)

    async def public_page(self, limit: int, offset: int) -> tuple[list[Review], int]:
        stmt = (
            select(Review)
            .where(Review.comment.is_not(None), Review.comment != "")
            .options(selectinload(Review.user), selectinload(Review.location))
            .order_by(Review.created_at.desc())
        )
        return await self.paginate_stmt(stmt, limit=limit, offset=offset)

    async def summary(self) -> tuple[float | None, int]:
        result = await self.session.execute(select(func.avg(Review.rating), func.count(Review.id)))
        avg, count = result.one()
        return (float(avg) if avg is not None else None), int(count)

    async def avg_rating(self, location_id: int | None = None) -> float | None:
        stmt = select(func.avg(Review.rating))
        if location_id:
            stmt = stmt.where(Review.location_id == location_id)
        result = await self.session.execute(stmt)
        value = result.scalar_one()
        return float(value) if value is not None else None
