from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Location, PromoCode, ProductVariant
from app.models.enums import PromoType
from app.repositories import LocationRepository, LoyaltyRepository, ProductRepository, SettingRepository, StockRepository, UserRepository
from app.schemas.cart import CartItemIn, CartItemQuote, CartQuoteIn, CartQuoteOut

from .errors import NotFound, ServiceError
from .promo import PromoService


@dataclass
class PricedLine:
    index: int
    product_id: int
    variant_id: int
    product_name: str
    variant_name: str | None
    modifiers: list[dict]
    unit_price: int
    quantity: int
    line_total: int
    counts_for_loyalty: bool
    comment: str | None = None
    is_gift: bool = False
    error: str | None = None


@dataclass
class PricedCart:
    location: Location
    lines: list[PricedLine]
    out: CartQuoteOut
    promo: PromoCode | None = None
    gift_used: bool = False
    warnings: list[str] = field(default_factory=list)


class CartService:
    def __init__(self, session: AsyncSession):
        self.locations = LocationRepository(session)
        self.products = ProductRepository(session)
        self.stock = StockRepository(session)
        self.loyalty = LoyaltyRepository(session)
        self.users = UserRepository(session)
        self.promo = PromoService(session)
        self.settings = SettingRepository(session)

    async def quote(self, user_id: int, data: CartQuoteIn) -> PricedCart:
        location = await self.locations.with_hours(data.location_id)
        if location is None or not location.is_active:
            raise NotFound("Кофейня не найдена")

        stop_products, stop_variants, stop_modifiers = await self.stock.stopped_ids(location.id)
        variants = {v.id: v for v in await self.products.variants_by_ids([i.variant_id for i in data.items])}

        lines = [self._price_line(i, item, variants.get(item.variant_id), stop_products, stop_variants, stop_modifiers) for i, item in enumerate(data.items)]
        ok_lines = [l for l in lines if l.error is None]
        subtotal = sum(l.unit_price * l.quantity for l in ok_lines)

        account = await self.loyalty.by_user(user_id)
        gift_available = bool(account and account.gifts_available > 0)
        gift_candidates = [l for l in ok_lines if variants[l.variant_id].product.can_be_gift]
        gift_applicable = gift_available and bool(gift_candidates)
        gift_discount = 0
        with_mods = bool(await self.settings.get_value("loyalty.gift_with_modifiers", default=True))
        if data.use_gift and gift_applicable:
            best = max(gift_candidates, key=lambda l: l.unit_price if with_mods else variants[l.variant_id].price)
            gift_discount = best.unit_price if with_mods else variants[best.variant_id].price
            if best.quantity > 1:
                best.quantity -= 1
                best.line_total = best.unit_price * best.quantity
                gift_line = PricedLine(**{**best.__dict__, "quantity": 1, "line_total": best.unit_price - gift_discount, "is_gift": True})
                lines.insert(lines.index(best) + 1, gift_line)
            else:
                best.is_gift = True
                best.line_total = best.unit_price - gift_discount

        promo: PromoCode | None = None
        promo_discount = 0
        promo_error: str | None = None
        if data.promo_code:
            try:
                promo, promo_discount = await self.promo.validate(data.promo_code, user_id, location.id, subtotal - gift_discount)
            except ServiceError as e:
                promo_error = e.detail
            else:
                if promo.type == PromoType.FREE_PRODUCT:
                    product = await self.products.full(promo.product_id)
                    variant = next((v for v in product.variants if v.is_default and v.is_active), None) or next(v for v in product.variants if v.is_active)
                    lines.append(PricedLine(
                        index=len(data.items), product_id=product.id, variant_id=variant.id, product_name=product.name,
                        variant_name=variant.name, modifiers=[], unit_price=variant.price, quantity=1, line_total=0,
                        counts_for_loyalty=False, is_gift=True,
                    ))
                    subtotal += variant.price
                else:
                    promo_discount = min(promo_discount, subtotal - gift_discount)

        discount_total = gift_discount + promo_discount
        total = max(subtotal - discount_total, 0)
        discount_total = subtotal - total

        warnings: list[str] = []
        now = datetime.now(timezone.utc)
        ready_at = now + timedelta(minutes=location.avg_prep_minutes)
        if data.pickup_at is not None:
            earliest = now + timedelta(minutes=location.min_pickup_minutes)
            if data.pickup_at < earliest:
                warnings.append(f"Ко времени можно заказать не раньше чем через {location.min_pickup_minutes} мин")
            ready_at = max(data.pickup_at, ready_at)
        if not location.accepts_orders:
            warnings.append("Кофейня сейчас не принимает онлайн-заказы")

        user = await self.users.get(user_id)
        if user is not None and user.is_blocked:
            warnings.append("Онлайн-заказы для вашего аккаунта недоступны")

        stamps = sum(l.quantity for l in lines if l.error is None and l.counts_for_loyalty and not l.is_gift)
        can_checkout = bool(ok_lines) and len(ok_lines) == len(data.items) and not warnings

        out = CartQuoteOut(
            items=[
                CartItemQuote(
                    index=l.index, product_name=l.product_name, variant_name=l.variant_name,
                    modifiers=[m["name"] for m in l.modifiers], unit_price=l.unit_price, quantity=l.quantity,
                    line_total=l.line_total, is_gift=l.is_gift, is_available=l.error is None, error=l.error,
                )
                for l in lines
            ],
            subtotal=subtotal,
            promo_discount=promo_discount if promo else 0,
            gift_discount=gift_discount,
            discount_total=discount_total,
            total=total,
            promo_error=promo_error,
            gift_available=gift_available,
            gift_applicable=gift_applicable,
            gift_with_modifiers=with_mods,
            stamps_to_earn=stamps,
            estimated_ready_at=ready_at,
            warnings=warnings,
            can_checkout=can_checkout,
        )
        return PricedCart(location=location, lines=[l for l in lines if l.error is None], out=out, promo=promo, gift_used=gift_discount > 0, warnings=warnings)

    def _price_line(
        self,
        index: int,
        item: CartItemIn,
        variant: ProductVariant | None,
        stop_products: set[int],
        stop_variants: set[int],
        stop_modifiers: set[int],
    ) -> PricedLine:
        def broken(name: str, error: str) -> PricedLine:
            return PricedLine(
                index=index, product_id=item.product_id, variant_id=item.variant_id, product_name=name, variant_name=None,
                modifiers=[], unit_price=0, quantity=item.quantity, line_total=0, counts_for_loyalty=False, error=error,
            )

        if variant is None or variant.product_id != item.product_id:
            return broken("Товар", "Этой позиции больше нет в меню")
        product = variant.product
        if not product.is_active or not variant.is_active:
            return broken(product.name, "Этой позиции больше нет в меню")
        if product.id in stop_products or variant.id in stop_variants:
            return broken(product.name, "Сейчас закончилось")

        allowed: dict[int, tuple] = {}
        for link in product.modifier_links:
            group = link.group
            if not group.is_active:
                continue
            for m in group.modifiers:
                if m.is_active and (link.modifier_ids is None or m.id in link.modifier_ids):
                    allowed[m.id] = (group, m)

        picked: list[dict] = []
        per_group: dict[int, int] = {}
        for modifier_id in dict.fromkeys(item.modifier_ids):
            if modifier_id not in allowed:
                return broken(product.name, "Такую добавку к этому напитку выбрать нельзя")
            group, m = allowed[modifier_id]
            if m.id in stop_modifiers:
                return broken(product.name, f"Закончилось: {m.name}")
            per_group[group.id] = per_group.get(group.id, 0) + 1
            picked.append({"id": m.id, "group": group.name, "name": m.name, "price_delta": m.price_delta})

        for link in product.modifier_links:
            group = link.group
            if not group.is_active:
                continue
            count = per_group.get(group.id, 0)
            if count < group.min_select:
                return broken(product.name, f"Выберите: {group.name.lower()}")
            if count > group.max_select:
                return broken(product.name, f"{group.name}: можно выбрать не больше {group.max_select}")

        unit = variant.price + sum(m["price_delta"] for m in picked)
        return PricedLine(
            index=index, product_id=product.id, variant_id=variant.id, product_name=product.name,
            variant_name=variant.name, modifiers=picked, unit_price=unit, quantity=item.quantity,
            line_total=unit * item.quantity, counts_for_loyalty=product.counts_for_loyalty, comment=item.comment,
        )
