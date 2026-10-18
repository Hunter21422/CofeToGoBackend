from __future__ import annotations

import secrets
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, PromoCode, PromoRedemption
from app.models.enums import OrderStatus, PromoType
from app.repositories import OrderRepository, ProductRepository, PromoRepository
from app.schemas.promo import PromoCodeCreate, PromoCodeUpdate, PromoFilter, PromoGenerateIn

from .errors import Conflict, NotFound, ServiceError


class PromoService:
    def __init__(self, session: AsyncSession):
        self.promos = PromoRepository(session)
        self.orders = OrderRepository(session)
        self.products = ProductRepository(session)

    async def get_promo(self, promo_id: int) -> PromoCode:
        promo = await self.promos.get(promo_id)
        if promo is None:
            raise NotFound("Промокод не найден")
        return promo

    async def admin_list(self, f: PromoFilter) -> tuple[list[PromoCode], int]:
        return await self.promos.admin_page(f)

    async def create_promo(self, data: PromoCodeCreate) -> PromoCode:
        existing = await self.promos.by_code(data.code)
        if existing is not None:
            raise Conflict("Такой промокод уже есть")
        promo = await self.promos.create(**data.model_dump())
        return promo

    async def update_promo(self, promo_id: int, data: PromoCodeUpdate) -> PromoCode:
        promo = await self.get_promo(promo_id)
        await self.promos.update(promo, **data.model_dump(exclude_unset=True))
        return promo

    async def validate(self, code: str, user_id: int, location_id: int, subtotal: int) -> tuple[PromoCode, int]:
        promo = await self.promos.by_code(code)
        if promo is None or not promo.is_active:
            raise ServiceError("Такого промокода нет", code="promo_invalid")

        now = datetime.now(timezone.utc)
        if promo.starts_at and promo.starts_at > now:
            raise ServiceError("Промокод ещё не действует", code="promo_invalid")
        if promo.ends_at and promo.ends_at <= now:
            raise ServiceError("Промокод больше не действует", code="promo_invalid")
        if promo.location_ids and location_id not in promo.location_ids:
            raise ServiceError("На этой точке промокод не действует", code="promo_invalid")
        if promo.usage_limit_total and promo.used_count >= promo.usage_limit_total:
            raise ServiceError("Промокод закончился", code="promo_invalid")
        if promo.usage_limit_per_user:
            used = await self.promos.user_uses(promo.id, user_id)
            if used >= promo.usage_limit_per_user:
                raise ServiceError("Вы уже использовали этот промокод", code="promo_invalid")
        if promo.first_order_only:
            had_orders = await self.orders.exists(Order.user_id == user_id, Order.status == OrderStatus.COMPLETED)
            if had_orders:
                raise ServiceError("Промокод только для первого заказа", code="promo_invalid")
        if promo.min_order_total and subtotal < promo.min_order_total:
            raise ServiceError(f"Промокод работает от {promo.min_order_total // 100} ₽", code="promo_invalid")

        if promo.type == PromoType.PERCENT:
            discount = subtotal * promo.value // 100
            if promo.max_discount:
                discount = min(discount, promo.max_discount)
        elif promo.type == PromoType.FIXED:
            discount = min(promo.value, subtotal)
        else:
            product = await self.products.full(promo.product_id) if promo.product_id else None
            variants = [v for v in product.variants if v.is_active] if product else []
            if not product or not product.is_active or not variants:
                raise ServiceError("Подарочный товар сейчас недоступен", code="promo_invalid")
            default = next((v for v in variants if v.is_default), variants[0])
            discount = default.price

        return promo, discount

    async def redeem(self, promo: PromoCode, user_id: int, order_id: int, discount: int) -> None:
        await self.promos.use(promo.id)
        redemption = PromoRedemption(promo_code_id=promo.id, user_id=user_id, order_id=order_id, discount_amount=discount)
        self.promos.session.add(redemption)
        await self.promos.session.flush()

    async def release(self, order_id: int) -> None:
        redemption = await self.promos.redemption_by_order(order_id)
        if redemption is None:
            return
        await self.promos.unuse(redemption.promo_code_id)
        await self.promos.session.delete(redemption)

    async def generate(self, data: PromoGenerateIn) -> list[str]:
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        fields = data.model_dump(exclude={"prefix", "count"})
        fields["usage_limit_total"] = 1
        fields["usage_limit_per_user"] = 1

        codes: set[str] = set()
        while len(codes) < data.count:
            need = data.count - len(codes)
            batch = {f"{data.prefix}-" + "".join(secrets.choice(alphabet) for _ in range(6)) for _ in range(need)}
            taken = await self.promos.codes_exist(list(batch))
            codes |= batch - taken

        for code in codes:
            self.promos.session.add(PromoCode(code=code, **fields))
        await self.promos.session.flush()
        return sorted(codes)
