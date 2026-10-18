from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Review
from app.models.enums import OrderStatus
from app.repositories import OrderRepository, ReviewRepository
from app.schemas.profile import ReviewCreate, ReviewFilter

from .errors import Conflict, NotFound


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.reviews = ReviewRepository(session)
        self.orders = OrderRepository(session)

    async def create(self, user_id: int, order_id: int, data: ReviewCreate) -> Review:
        order = await self.orders.for_user_one(order_id, user_id)
        if order is None:
            raise NotFound("Заказ не найден")
        if order.status != OrderStatus.COMPLETED:
            raise Conflict("Отзыв можно оставить после получения заказа")
        if await self.reviews.by_order(order_id) is not None:
            raise Conflict("Отзыв на этот заказ уже есть")
        return await self.reviews.create(
            order_id=order_id, user_id=user_id, location_id=order.location_id,
            rating=data.rating, comment=data.comment, tags=list(data.tags),
        )

    async def admin_list(self, f: ReviewFilter) -> tuple[list[Review], int]:
        return await self.reviews.admin_page(f)

    async def reply(self, review_id: int, staff_user_id: int, text: str) -> Review:
        review = await self.reviews.full(review_id)
        if review is None:
            raise NotFound("Отзыв не найден")
        await self.reviews.update(review, reply=text, replied_by_id=staff_user_id, replied_at=datetime.now(timezone.utc))
        return review
