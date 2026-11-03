from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Review
from app.models.enums import OrderStatus
from app.repositories import OrderRepository, ReviewRepository
from app.schemas.profile import ReviewCreate, ReviewFilter

from .errors import Conflict, NotFound, ServiceError


class ReviewService:
    def __init__(self, session: AsyncSession):
        self.session = session
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
            rating=data.rating, comment=data.comment, tags=list(data.tags), publish_consent=data.publish_consent,
        )

    async def admin_list(self, f: ReviewFilter) -> tuple[list[Review], int]:
        return await self.reviews.admin_page(f)

    async def reply(self, review_id: int, staff_user_id: int, text: str) -> Review:
        review = await self.reviews.full(review_id)
        if review is None:
            raise NotFound("Отзыв не найден")
        await self.reviews.update(review, reply=text, replied_by_id=staff_user_id, replied_at=datetime.now(timezone.utc))
        return review

    async def publish(self, review_id: int, channel: str | None) -> Review:
        from app.bot.channel import post_to_channel
        from app.bot.reviews import channel_text

        review = await self.reviews.full(review_id)
        if review is None:
            raise NotFound("Отзыв не найден")
        if not channel:
            raise ServiceError("Укажите Telegram-канал в «Настройках» → «Отзывы»")
        if not review.publish_consent:
            raise Conflict("Гость не разрешил публиковать этот отзыв")
        if review.published_at is not None:
            raise Conflict("Отзыв уже опубликован в канале")
        if not (review.comment or review.tags):
            raise Conflict("В отзыве нет текста — публиковать нечего")
        review.channel_message_id = await post_to_channel(channel, channel_text(review))
        review.published_at = datetime.now(timezone.utc)
        await self.session.flush()
        return review
