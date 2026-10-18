from typing import Annotated

from fastapi import APIRouter, Header, Query

from app.api.deps import CurrentUser, GatewayDep, RedisDep, SessionDep
from app.models.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from app.schemas.common import Page
from app.schemas.order import OrderCancelIn, OrderCreate, OrderCreateOut, OrderFilter, OrderRead, OrderShort
from app.schemas.profile import ReviewCreate, ReviewRead
from app.services import OrderService, ReviewService
router=APIRouter(prefix="/orders", tags=["клиент: заказы"])
async def to_read(service: OrderService, order, url: str | None = None) -> OrderRead:
    out = OrderRead.model_validate(order)
    out.can_cancel = service.can_cancel(order)
    out.can_review = service.can_review(order)
    if url is None and order.status == OrderStatus.PENDING_PAYMENT:
        url = (await service.payments().get_order_payment(order.id)).confirmation_url
    out.payment_url = url
    return out
@router.post("", response_model=OrderCreateOut, status_code=201)
async def create_order(data: OrderCreate, session: SessionDep, redis: RedisDep, gateway: GatewayDep, user: CurrentUser, idempotency_key: Annotated[str | None, Header()] = None):
    service = OrderService(session, redis, gateway)
    order, url = await service.create(user.id, data, idempotency_key)
    return OrderCreateOut(order=await to_read(service, order, url), payment_url=url)
@router.get("", response_model=Page[OrderShort])
async def list_orders(f: Annotated[OrderFilter, Query()], session: SessionDep, user: CurrentUser):
    if f.active_only:
        statuses = [OrderStatus.PENDING_PAYMENT, *ACTIVE_ORDER_STATUSES]
    else:
        statuses = f.status
    items, total = await OrderService(session).list_for_user(user.id, statuses, f.limit, f.offset)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.get("/{order_id}", response_model=OrderRead)
async def get_order(order_id: int, session: SessionDep, gateway: GatewayDep, user: CurrentUser):
    service = OrderService(session, gateway=gateway)
    order = await service.get_for_user(order_id, user.id)
    return await to_read(service, order)
@router.post("/{order_id}/cancel", response_model=OrderRead)
async def cancel_order(order_id: int, data: OrderCancelIn, session: SessionDep, redis: RedisDep, gateway: GatewayDep, user: CurrentUser):
    service = OrderService(session, redis, gateway)
    order = await service.cancel_by_user(order_id, user.id, data.reason)
    return await to_read(service, order)
@router.post("/{order_id}/review", response_model=ReviewRead, status_code=201)
async def review_order(order_id: int, data: ReviewCreate, session: SessionDep, user: CurrentUser):
    return await ReviewService(session).create(user.id, order_id, data)
