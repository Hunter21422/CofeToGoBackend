from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Manager, SessionDep
from app.models.enums import StaffRole
from app.repositories import OrderRepository
from app.schemas.common import Page
from app.schemas.profile import CustomerDetail
from app.schemas.user import CustomerFilter, CustomerListItem, UserBlockIn
from app.services import LoyaltyService, UserService
router=APIRouter(prefix="/admin/customers", tags=["admin: гости"])
async def build_detail(session, user_id: int) -> CustomerDetail:
    user, orders_count, total_spent = await UserService(session).customer_card(user_id)
    loyalty = await LoyaltyService(session).read(user_id)
    last_orders, _ = await OrderRepository(session).page_for_user(user_id, [], 5, 0)
    return CustomerDetail(user=user, loyalty=loyalty, last_orders=last_orders, orders_count=orders_count, total_spent=total_spent, is_blocked=user.is_blocked)
@router.get("", response_model=Page[CustomerListItem])
async def list_customers(f: Annotated[CustomerFilter, Query()], session: SessionDep, ctx: Manager):
    if ctx.staff.role != StaffRole.OWNER and ctx.staff.location_id:
        f.location_id = ctx.staff.location_id
    rows, total = await UserService(session).list_customers(f)
    items = [CustomerListItem(id=u.id, first_name=u.first_name, username=u.username, phone=u.phone, orders_count=orders_count, total_spent=total_spent, stamps=stamps, last_order_at=last_order_at) for u, orders_count, total_spent, stamps, last_order_at in rows]
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.get("/{user_id}", response_model=CustomerDetail)
async def get_customer(user_id: int, session: SessionDep, ctx: Manager):
    return await build_detail(session, user_id)
@router.post("/{user_id}/block", response_model=CustomerDetail)
async def block_customer(user_id: int, data: UserBlockIn, session: SessionDep, ctx: Manager):
    await UserService(session).block(user_id, data.is_blocked, data.reason)
    return await build_detail(session, user_id)
