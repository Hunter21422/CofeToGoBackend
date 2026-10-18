from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    CancelledBy,
    OrderPaymentStatus,
    OrderSource,
    OrderStatus,
    OrderType,
    PaymentMethod,
)

from .cart import CartQuoteIn
from .common import BaseSchema, Money, PaginationParams
from .location import LocationShort
from .staff import StaffShort
from .user import UserShort


class OrderModifierSnapshot(BaseModel):
    """Схема JSONB-поля order_items.modifiers"""

    id: int
    group: str
    name: str
    price_delta: Money


# ---------- Клиент ----------
class OrderCreate(CartQuoteIn):
    type: OrderType = OrderType.PICKUP
    payment_method: PaymentMethod
    comment: str | None = Field(None, max_length=500)
    # Idempotency-Key приходит заголовком, не в теле


class OrderItemRead(BaseSchema):
    id: int
    product_id: int | None
    product_name: str
    variant_name: str | None
    modifiers: list[OrderModifierSnapshot]
    unit_price: Money
    quantity: int
    line_total: Money
    is_gift: bool


class OrderStatusHistoryRead(BaseSchema):
    from_status: OrderStatus | None
    to_status: OrderStatus
    comment: str | None
    created_at: datetime


class OrderShort(BaseSchema):
    id: int
    display_number: str
    status: OrderStatus
    total: Money
    items_count: int
    location: LocationShort
    created_at: datetime


class OrderRead(BaseSchema):
    id: int
    display_number: str
    status: OrderStatus
    type: OrderType
    location: LocationShort
    pickup_at: datetime | None
    estimated_ready_at: datetime | None
    comment: str | None
    items: list[OrderItemRead]
    subtotal: Money
    discount_total: Money
    total: Money
    gift_used: bool
    payment_method: PaymentMethod
    payment_status: OrderPaymentStatus
    payment_url: str | None = None
    status_history: list[OrderStatusHistoryRead]
    can_cancel: bool = False   # заполняется в сервисе
    can_review: bool = False
    created_at: datetime


class OrderCreateOut(BaseModel):
    order: OrderRead
    payment_url: str | None = None


class OrderCancelIn(BaseModel):
    reason: str | None = Field(None, max_length=255)


class OrderFilter(PaginationParams):
    status: list[OrderStatus] = []
    active_only: bool = False


# ---------- Админка ----------
class AdminOrderFilter(PaginationParams):
    location_id: int | None = None
    status: list[OrderStatus] = []
    payment_status: OrderPaymentStatus | None = None
    source: OrderSource | None = None
    date_from: date | None = None
    date_to: date | None = None
    q: str | None = None  # номер, телефон, имя
    user_id: int | None = None


class AdminOrderRead(OrderRead):
    user: UserShort
    source: OrderSource
    accepted_by: StaffShort | None
    accepted_at: datetime | None
    ready_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    cancelled_by: CancelledBy | None


class QueueOut(BaseModel):
    new: list[AdminOrderRead]
    accepted: list[AdminOrderRead]
    preparing: list[AdminOrderRead]
    ready: list[AdminOrderRead]
    server_time: datetime


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
    comment: str | None = Field(None, max_length=255)
    estimated_ready_at: datetime | None = None


class OrderRejectIn(BaseModel):
    reason: str = Field(min_length=3, max_length=255)
