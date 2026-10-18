from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Favorite
from app.repositories import FavoriteRepository, ModifierGroupRepository, ProductRepository
from app.schemas.profile import FavoriteCreate

from .errors import Conflict, NotFound, ServiceError


class FavoriteService:
    def __init__(self, session: AsyncSession):
        self.favorites = FavoriteRepository(session)
        self.products = ProductRepository(session)
        self.modifiers = ModifierGroupRepository(session)

    async def list(self, user_id: int) -> list[Favorite]:
        return await self.favorites.for_user(user_id)

    async def add(self, user_id: int, data: FavoriteCreate) -> Favorite:
        if await self.favorites.count_for_user(user_id) >= 30:
            raise Conflict("В избранном уже 30 напитков")
        product = await self.products.full(data.product_id)
        if product is None:
            raise NotFound("Товар не найден")
        if data.variant_id and data.variant_id not in {v.id for v in product.variants}:
            raise ServiceError("Такого размера у товара нет")
        favorite = await self.favorites.create(
            user_id=user_id, product_id=data.product_id, variant_id=data.variant_id,
            modifier_ids=list(data.modifier_ids), custom_name=data.custom_name,
        )
        return (await self.favorites.for_user(user_id))[-1] if favorite else favorite

    async def remove(self, user_id: int, favorite_id: int) -> None:
        favorite = await self.favorites.for_user_one(favorite_id, user_id)
        if favorite is None:
            raise NotFound("Нет в избранном")
        await self.favorites.delete(favorite)
