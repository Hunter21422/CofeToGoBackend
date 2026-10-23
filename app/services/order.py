from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Order, OrderItem, OrderStatusHistory
from app.models.enums import (
    ACTIVE_ORDER_STATUSES,
    ENABLED_PAYMENT_METHODS,
    ONLINE_PAYMENT_METHODS,
    CancelledBy,
    OrderPaymentStatus,
    OrderStatus,
)
from app.repositories import OrderRepository, SettingRepository, UserRepository
from app.schemas.order import AdminOrderFilter, OrderCreate

from .cart import CartService
from .errors import Conflict, Forbidden, NotFound, ServiceError
from .loyalty import LoyaltyService
from .notify import NotifyService
from .payment import PaymentGateway, PaymentService
from .promo import PromoService

NEXT_STATUS = {
    OrderStatus.NEW: {OrderStatus.ACCEPTED},
    OrderStatus.ACCEPTED: {OrderStatus.PREPARING, OrderStatus.READY},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.COMPLETED},
}
USER_CAN_CANCEL = {OrderStatus.PENDING_PAYMENT, OrderStatus.NEW}


class OrderService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None, gateway: PaymentGateway | None = None):
        self.session = session
        self.orders = OrderRepository(session)
        self.users = UserRepository(session)
        self.settings = SettingRepository(session)
        self.cart = CartService(session)
        self.loyalty = LoyaltyService(session, redis)
        self.promo = PromoService(session)
        self.gateway = gateway
        self.notify = NotifyService(session)

    def payments(self) -> PaymentService:
        return PaymentService(self.session, self.gateway)

    async def create(self, user_id: int, data: OrderCreate, idempotency_key: str | None = None) -> tuple[Order, str | None]:
        if idempotency_key:
            existing = await self.orders.by_idempotency_key(user_id, idempotency_key)
            if existing is not None:
                order = await self.orders.full(existing.id)
                url = None
                if order.status == OrderStatus.PENDING_PAYMENT:
                    url = (await self.payments().get_order_payment(order.id)).confirmation_url
                return order, url

        user = await self.users.get(user_id)
        if user is None:
            raise NotFound("Гость не найден")
        if user.is_blocked:
            raise Forbidden("Онлайн-заказы для вашего аккаунта недоступны")

        priced = await self.cart.quote(user_id, data)
        if data.payment_method not in priced.location.payment_methods or data.payment_method not in ENABLED_PAYMENT_METHODS:
            raise ServiceError("Этот способ оплаты недоступен. Оплатить можно наличными или картой при получении")
        if data.promo_code and priced.out.promo_error:
            raise ServiceError(priced.out.promo_error, code="promo_invalid")
        if not priced.out.can_checkout:
            errors = [i.error for i in priced.out.items if i.error] + priced.out.warnings
            raise ServiceError(errors[0] if errors else "Корзину нельзя оформить", code="cart_invalid")

        online = data.payment_method in ONLINE_PAYMENT_METHODS
        today = datetime.now(ZoneInfo(priced.location.timezone)).date()
        number = await self.orders.next_number(priced.location.id, today)
        status = OrderStatus.PENDING_PAYMENT if online else OrderStatus.NEW

        order = Order(
            number=number,
            business_date=today,
            user_id=user_id,
            location_id=priced.location.id,
            status=status,
            type=data.type,
            pickup_at=data.pickup_at,
            estimated_ready_at=priced.out.estimated_ready_at,
            comment=data.comment,
            subtotal=priced.out.subtotal,
            discount_total=priced.out.discount_total,
            total=priced.out.total,
            promo_code_id=priced.promo.id if priced.promo else None,
            gift_used=priced.gift_used,
            payment_method=data.payment_method,
            payment_status=OrderPaymentStatus.PENDING if online else OrderPaymentStatus.UNPAID,
            idempotency_key=idempotency_key,
            items=[
                OrderItem(
                    product_id=l.product_id,
                    variant_id=l.variant_id,
                    product_name=l.product_name,
                    variant_name=l.variant_name,
                    modifiers=l.modifiers,
                    unit_price=l.unit_price,
                    quantity=l.quantity,
                    line_total=l.line_total,
                    is_gift=l.is_gift,
                    counts_for_loyalty=l.counts_for_loyalty,
                    comment=l.comment,
                )
                for l in priced.lines
            ],
            status_history=[OrderStatusHistory(from_status=None, to_status=status, changed_by_id=user_id)],
        )
        await self.orders.add(order)

        if priced.gift_used:
            await self.loyalty.redeem_gift(user_id, order.id)
        if priced.promo:
            await self.promo.redeem(priced.promo, user_id, order.id, priced.out.promo_discount)

        url = None
        if online and order.total > 0:
            url = await self.payments().create_for_order(order)
        elif online:
            order.payment_status = OrderPaymentStatus.PAID
            await self.orders.add_status(order, OrderStatus.NEW, comment="Оплачено подарком")

        order_id = order.id
        self.session.expire(order)
        order = await self.orders.full(order_id)
        if order.status == OrderStatus.NEW:
            await self.notify.new_order(order)
        return order, url

    async def get_for_user(self, order_id: int, user_id: int) -> Order:
        order = await self.orders.for_user_one(order_id, user_id)
        if order is None:
            raise NotFound("Заказ не найден")
        return order

    async def get(self, order_id: int) -> Order:
        order = await self.orders.full(order_id)
        if order is None:
            raise NotFound("Заказ не найден")
        return order

    def can_cancel(self, order: Order) -> bool:
        return order.status in USER_CAN_CANCEL

    def can_review(self, order: Order) -> bool:
        return order.status == OrderStatus.COMPLETED and order.review is None

    async def list_for_user(self, user_id: int, statuses: list[OrderStatus], limit: int, offset: int) -> tuple[list[Order], int]:
        return await self.orders.page_for_user(user_id, statuses, limit, offset)

    async def admin_list(self, f: AdminOrderFilter) -> tuple[list[Order], int]:
        return await self.orders.admin_page(f)

    async def queue(self, location_id: int) -> dict[OrderStatus, list[Order]]:
        result: dict[OrderStatus, list[Order]] = {s: [] for s in ACTIVE_ORDER_STATUSES}
        for order in await self.orders.queue(location_id):
            result[order.status].append(order)
        return result

    async def _undo(self, order: Order, reason: str | None, by_user_id: int | None) -> None:
        if order.gift_used:
            await self.loyalty.return_gift(order.user_id, order.id)
        if order.promo_code_id:
            await self.promo.release(order.id)
        if order.payment_status in (OrderPaymentStatus.PAID, OrderPaymentStatus.PARTIALLY_REFUNDED) and order.payment_method in ONLINE_PAYMENT_METHODS:
            await self.payments().refund(order, reason=reason or "Заказ отменён", by_user_id=by_user_id)

    async def cancel_by_user(self, order_id: int, user_id: int, reason: str | None = None) -> Order:
        order = await self.orders.full(order_id, for_update=True)
        if order is None or order.user_id != user_id:
            raise NotFound("Заказ не найден")
        if not self.can_cancel(order):
            raise Conflict("Заказ уже готовят — отменить его можно только у бариста")
        await self.orders.add_status(order, OrderStatus.CANCELLED, changed_by_id=user_id, comment=reason)
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancelled_by = CancelledBy.USER
        order.cancel_reason = reason
        await self._undo(order, reason, user_id)
        await self.notify.order_cancelled_by_guest(order)
        return order

    async def reject(self, order_id: int, staff_user_id: int, reason: str) -> Order:
        order = await self.orders.full(order_id, for_update=True)
        if order is None:
            raise NotFound("Заказ не найден")
        if order.status not in ACTIVE_ORDER_STATUSES:
            raise Conflict("Заказ уже закрыт")
        await self.orders.add_status(order, OrderStatus.REJECTED, changed_by_id=staff_user_id, comment=reason)
        order.cancelled_at = datetime.now(timezone.utc)
        order.cancelled_by = CancelledBy.STAFF
        order.cancel_reason = reason
        await self._undo(order, reason, staff_user_id)
        await self.notify.order_status(order, "cancelled", reason)
        return order

    async def change_status(
        self,
        order_id: int,
        to: OrderStatus,
        staff_id: int,
        staff_user_id: int,
        comment: str | None = None,
        estimated_ready_at: datetime | None = None,
    ) -> Order:
        order = await self.orders.full(order_id, for_update=True)
        if order is None:
            raise NotFound("Заказ не найден")
        if to not in NEXT_STATUS.get(order.status, set()):
            raise Conflict(f"Нельзя перевести заказ из «{order.status.value}» в «{to.value}»")

        now = datetime.now(timezone.utc)
        await self.orders.add_status(order, to, changed_by_id=staff_user_id, comment=comment)
        if to == OrderStatus.ACCEPTED:
            order.accepted_at = now
            order.accepted_by_id = staff_id
            if estimated_ready_at:
                order.estimated_ready_at = estimated_ready_at
        elif to == OrderStatus.READY:
            order.ready_at = now
        elif to == OrderStatus.COMPLETED:
            order.completed_at = now
            if order.payment_status == OrderPaymentStatus.UNPAID:
                order.payment_status = OrderPaymentStatus.PAID
            if not order.loyalty_processed:
                stamps = order.loyalty_stamps
                if stamps > 0:
                    await self.loyalty.add_stamps(order.user_id, stamps, order_id=order.id, staff_id=staff_id, location_id=order.location_id)
                order.loyalty_processed = True
        if to == OrderStatus.ACCEPTED:
            await self.notify.order_status(order, "accepted")
        elif to == OrderStatus.READY:
            await self.notify.order_status(order, "ready")
        await self.session.flush()
        return order

    async def expire_unpaid(self) -> int:
        minutes = int(await self.settings.get_value("orders.payment_timeout_min", default=15))
        border = datetime.now(timezone.utc) - timedelta(minutes=minutes)
        count = 0
        for order in await self.orders.unpaid_before(border):
            full = await self.orders.full(order.id)
            await self.orders.add_status(full, OrderStatus.EXPIRED, comment="Не оплачен вовремя")
            full.cancelled_at = datetime.now(timezone.utc)
            full.cancelled_by = CancelledBy.SYSTEM
            full.payment_status = OrderPaymentStatus.UNPAID
            if full.gift_used:
                await self.loyalty.return_gift(full.user_id, full.id)
            if full.promo_code_id:
                await self.promo.release(full.id)
            count += 1
        return count
