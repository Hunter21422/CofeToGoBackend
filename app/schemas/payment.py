from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentProvider, PaymentStatus, RefundStatus

from .common import BaseSchema, Money


class PaymentRead(BaseSchema):
    id: int
    provider: PaymentProvider
    amount: Money
    status: PaymentStatus
    paid_at: datetime | None
    refunded_amount: Money
    confirmation_url: str | None


class RefundCreate(BaseModel):
    amount: Money | None = None  # None = полный возврат
    reason: str = Field(min_length=3, max_length=255)


class RefundRead(BaseSchema):
    id: int
    amount: Money
    status: RefundStatus
    reason: str | None
    created_at: datetime


# ---------- Вебхук ЮKassa ----------
class YooKassaAmount(BaseModel):
    value: Decimal
    currency: str


class YooKassaPaymentObject(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    status: str
    paid: bool = False
    amount: YooKassaAmount
    metadata: dict[str, str] = {}  # сюда кладём order_id


class YooKassaWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str
    event: str  # payment.succeeded / payment.canceled / refund.succeeded
    object: YooKassaPaymentObject
