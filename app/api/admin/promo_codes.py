from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Manager, SessionDep
from app.schemas.common import Page
from app.schemas.promo import PromoCodeCreate, PromoCodeRead, PromoCodeUpdate, PromoFilter
from app.services import PromoService
router=APIRouter(prefix="/admin/promo-codes", tags=["admin: промокоды"])
@router.get("", response_model=Page[PromoCodeRead])
async def list_promos(f: Annotated[PromoFilter, Query()], session: SessionDep, ctx: Manager):
    items, total = await PromoService(session).admin_list(f)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.post("", response_model=PromoCodeRead, status_code=201)
async def create_promo(data: PromoCodeCreate, session: SessionDep, ctx: Manager):
    return await PromoService(session).create_promo(data)
@router.patch("/{promo_id}", response_model=PromoCodeRead)
async def update_promo(promo_id: int, data: PromoCodeUpdate, session: SessionDep, ctx: Manager):
    return await PromoService(session).update_promo(promo_id, data)
