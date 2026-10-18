from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Barista, GatewayDep, Manager, RedisDep, SessionDep, check_location
from app.models.enums import OrderStatus, StaffRole
from app.schemas.common import Page
from app.schemas.order import AdminOrderFilter, AdminOrderRead, OrderRejectIn, OrderStatusUpdate, QueueOut
from app.schemas.payment import RefundCreate
from app.services import OrderService
from app.services.errors import ServiceError
router=APIRouter(prefix="/admin", tags=["admin: заказы"])
@router.get("/queue", response_model=QueueOut)
async def queue(location_id: int, session: SessionDep, ctx: Barista):
    check_location(ctx, location_id)
    groups = await OrderService(session).queue(location_id)
    return QueueOut(new=groups[OrderStatus.NEW], accepted=groups[OrderStatus.ACCEPTED], preparing=groups[OrderStatus.PREPARING], ready=groups[OrderStatus.READY], server_time=datetime.now(timezone.utc))
@router.get("/orders", response_model=Page[AdminOrderRead])
async def list_orders(f: Annotated[AdminOrderFilter, Query()], session: SessionDep, ctx: Barista):
    if ctx.staff.role != StaffRole.OWNER and ctx.staff.location_id:
        f.location_id = ctx.staff.location_id
    items, total = await OrderService(session).admin_list(f)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.get("/orders/{order_id}", response_model=AdminOrderRead)
async def get_order(order_id: int, session: SessionDep, ctx: Barista):
    order = await OrderService(session).get(order_id)
    check_location(ctx, order.location_id)
    return order
@router.patch("/orders/{order_id}/status", response_model=AdminOrderRead)
async def change_status(order_id: int, data: OrderStatusUpdate, session: SessionDep, redis: RedisDep, ctx: Barista):
    service = OrderService(session, redis)
    order = await service.get(order_id)
    check_location(ctx, order.location_id)
    return await service.change_status(order_id, data.status, ctx.staff.id, ctx.user.id, data.comment, data.estimated_ready_at)
@router.post("/orders/{order_id}/reject", response_model=AdminOrderRead)
async def reject_order(order_id: int, data: OrderRejectIn, session: SessionDep, redis: RedisDep, gateway: GatewayDep, ctx: Barista):
    service = OrderService(session, redis, gateway)
    order = await service.get(order_id)
    check_location(ctx, order.location_id)
    return await service.reject(order_id, ctx.user.id, data.reason)
@router.post("/orders/{order_id}/refund", response_model=AdminOrderRead)
async def refund_order(order_id: int, data: RefundCreate, session: SessionDep, gateway: GatewayDep, ctx: Manager):
    service = OrderService(session, gateway=gateway)
    order = await service.get(order_id)
    check_location(ctx, order.location_id)
    refund = await service.payments().refund(order, data.amount, data.reason, ctx.user.id)
    if refund is None:
        raise ServiceError("Этот заказ не оплачен онлайн — возвращать нечего")
    session.expire(order)
    return await service.get(order_id)
