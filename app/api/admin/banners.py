from fastapi import APIRouter

from app.api.deps import Owner, SessionDep
from app.schemas.marketing import BannerAdminRead, BannerCreate, BannerUpdate
from app.services import MarketingService
router=APIRouter(prefix="/admin/banners", tags=["admin: маркетинг"])
@router.get("", response_model=list[BannerAdminRead])
async def list_banners(session: SessionDep, ctx: Owner):
    return await MarketingService(session).list_banners()
@router.post("", response_model=BannerAdminRead, status_code=201)
async def create_banner(data: BannerCreate, session: SessionDep, ctx: Owner):
    return await MarketingService(session).create_banner(data)
@router.patch("/{banner_id}", response_model=BannerAdminRead)
async def update_banner(banner_id: int, data: BannerUpdate, session: SessionDep, ctx: Owner):
    return await MarketingService(session).update_banner(banner_id, data)
@router.delete("/{banner_id}", status_code=204)
async def delete_banner(banner_id: int, session: SessionDep, ctx: Owner):
    await MarketingService(session).delete_banner(banner_id)
