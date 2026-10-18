from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models.enums import ACTIVE_ORDER_STATUSES, OrderStatus
from app.repositories import FavoriteRepository, OrderRepository, UserRepository
from app.schemas.profile import ProfileOut
from app.schemas.user import PhoneIn, UserRead, UserUpdate
from app.services import LoyaltyService, UserService
router=APIRouter(prefix="/me", tags=["клиент: профиль"])
@router.get("", response_model=UserRead)
async def get_me(user: CurrentUser):
    return user
@router.patch("", response_model=UserRead)
async def update_me(data: UserUpdate, session: SessionDep, user: CurrentUser):
    return await UserService(session).update_me(user.id, data)
@router.post("/phone", response_model=UserRead)
async def set_phone(data: PhoneIn, session: SessionDep, user: CurrentUser):
    return await UserService(session).set_phone(user.id, data.phone)
@router.get("/profile", response_model=ProfileOut)
async def get_profile(session: SessionDep, user: CurrentUser):
    loyalty = await LoyaltyService(session).read(user.id)
    orders_count, _ = await UserRepository(session).customer_stats(user.id)
    active, _ = await OrderRepository(session).page_for_user(user.id, [OrderStatus.PENDING_PAYMENT, *ACTIVE_ORDER_STATUSES], 10, 0)
    favorites_count = await FavoriteRepository(session).count_for_user(user.id)
    return ProfileOut(user=user, loyalty=loyalty, orders_count=orders_count, active_orders=active, favorites_count=favorites_count)
