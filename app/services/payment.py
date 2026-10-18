from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Protocol

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Order, Payment, Refund
from app.models.enums import OrderPaymentStatus, OrderStatus, PaymentProvider, PaymentStatus, RefundStatus
from app.repositories import OrderRepository, PaymentRepository, RefundRepository

from .notify import NotifyService
from .errors import NotFound, ServiceError


class PaymentGateway(Protocol):
    async def create_payment(self, amount: int, description: str, return_url: str, metadata: dict[str, str], key: str) -> dict[str, Any]: ...
    async def get_payment(self, payment_id: str) -> dict[str, Any]: ...
    async def create_refund(self, payment_id: str, amount: int, key: str) -> dict[str, Any]: ...


def rub(kopecks: int) -> str:
    return str((Decimal(kopecks) / 100).quantize(Decimal("0.01")))


class YooKassaGateway:
    url = "https://api.yookassa.ru/v3"

    def __init__(self, shop_id: str, secret_key: str):
        self.auth = (shop_id, secret_key)

    async def _request(self, method: str, path: str, key: str | None = None, json: dict | None = None) -> dict[str, Any]:
        headers = {"Idempotence-Key": key} if key else {}
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.request(method, f"{self.url}{path}", auth=self.auth, headers=headers, json=json)
        if r.status_code >= 400:
            raise ServiceError("Платёжная система не ответила, попробуйте ещё раз", code="payment_failed")
        return r.json()

    async def create_payment(self, amount: int, description: str, return_url: str, metadata: dict[str, str], key: str) -> dict[str, Any]:
        body = {
            "amount": {"value": rub(amount), "currency": "RUB"},
            "capture": True,
            "confirmation": {"type": "redirect", "return_url": return_url},
            "description": description[:128],
            "metadata": metadata,
        }
        return await self._request("POST", "/payments", key, body)

    async def get_payment(self, payment_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/payments/{payment_id}")

    async def create_refund(self, payment_id: str, amount: int, key: str) -> dict[str, Any]:
        body = {"payment_id": payment_id, "amount": {"value": rub(amount), "currency": "RUB"}}
        return await self._request("POST", "/refunds", key, body)


def default_gateway() -> YooKassaGateway:
    s = get_settings()
    return YooKassaGateway(s.yookassa_shop_id, s.yookassa_secret_key)


class PaymentService:
    def __init__(self, session: AsyncSession, gateway: PaymentGateway | None = None):
        self.payments = PaymentRepository(session)
        self.refunds = RefundRepository(session)
        self.orders = OrderRepository(session)
        self.gateway = gateway or default_gateway()

    async def create_for_order(self, order: Order) -> str:
        settings = get_settings()
        return_url = f"{settings.webapp_url.rstrip('/')}/#/orders/{order.id}"
        data = await self.gateway.create_payment(
            amount=order.total,
            description=f"Заказ {order.display_number} — {settings.app_name}",
            return_url=return_url,
            metadata={"order_id": str(order.id)},
            key=f"order-{order.id}",
        )
        url = data.get("confirmation", {}).get("confirmation_url")
        await self.payments.create(
            order_id=order.id,
            provider=PaymentProvider.YOOKASSA,
            external_id=data["id"],
            amount=order.total,
            status=PaymentStatus.PENDING,
            confirmation_url=url,
            raw_payload=data,
        )
        return url

    async def handle_webhook(self, external_id: str) -> Order | None:
        payment = await self.payments.by_external_id(external_id, for_update=True)
        if payment is None:
            return None
        data = await self.gateway.get_payment(external_id)
        status = data.get("status")
        order = await self.orders.full(payment.order_id, for_update=True)
        payment.raw_payload = data

        if status == "succeeded" and payment.status != PaymentStatus.SUCCEEDED:
            payment.status = PaymentStatus.SUCCEEDED
            payment.paid_at = datetime.now(timezone.utc)
            order.payment_status = OrderPaymentStatus.PAID
            if order.status == OrderStatus.PENDING_PAYMENT:
                await self.orders.add_status(order, OrderStatus.NEW, comment="Оплачен")
                await NotifyService(self.payments.session).new_order(order)
        elif status == "canceled" and payment.status != PaymentStatus.CANCELED:
            payment.status = PaymentStatus.CANCELED
            if order.payment_status != OrderPaymentStatus.PAID:
                order.payment_status = OrderPaymentStatus.UNPAID
        await self.payments.session.flush()
        return order

    async def refund(self, order: Order, amount: int | None = None, reason: str | None = None, by_user_id: int | None = None) -> Refund | None:
        paid = [p for p in await self.payments.for_order(order.id) if p.status == PaymentStatus.SUCCEEDED]
        if not paid:
            return None
        payment = paid[-1]
        left = payment.amount - payment.refunded_amount
        amount = left if amount is None else amount
        if amount <= 0 or amount > left:
            raise ServiceError("Нельзя вернуть больше, чем оплачено")
        key = f"refund-{payment.id}-{payment.refunded_amount}-{amount}"
        data = await self.gateway.create_refund(payment.external_id, amount, key)
        refund = await self.refunds.create(
            payment_id=payment.id,
            amount=amount,
            reason=reason,
            external_id=data.get("id"),
            status=RefundStatus.SUCCEEDED if data.get("status") == "succeeded" else RefundStatus.PENDING,
            created_by_id=by_user_id,
        )
        payment.refunded_amount += amount
        order.payment_status = OrderPaymentStatus.REFUNDED if payment.refunded_amount >= payment.amount else OrderPaymentStatus.PARTIALLY_REFUNDED
        await self.payments.session.flush()
        return refund

    async def get_order_payment(self, order_id: int) -> Payment:
        payments = await self.payments.for_order(order_id)
        if not payments:
            raise NotFound("Платёж не найден")
        return payments[-1]
