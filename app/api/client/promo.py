from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models.enums import PromoType
from app.schemas.promo import PromoCheckIn, PromoCheckOut
from app.services import PromoService
from app.services.errors import ServiceError
router=APIRouter(prefix="/promo", tags=["клиент: промокоды"])
@router.post("/check", response_model=PromoCheckOut)
async def check_promo(data: PromoCheckIn, session: SessionDep, user: CurrentUser):
    try:
        promo, discount = await PromoService(session).validate(data.code, user.id, data.location_id, 10**9)
    except ServiceError as e:
        return PromoCheckOut(valid=False, message=e.detail)
    if promo.type == PromoType.PERCENT:
        message = f"Скидка {promo.value}%"
        discount = None
    elif promo.type == PromoType.FIXED:
        message = f"Скидка {promo.value // 100} ₽"
    else:
        message = "Напиток в подарок"
    if promo.min_order_total:
        message += f" при заказе от {promo.min_order_total // 100} ₽"
    return PromoCheckOut(valid=True, discount_preview=discount, message=message)
