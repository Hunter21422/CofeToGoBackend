from fastapi import APIRouter

from app.api.deps import Owner, SessionDep
from app.schemas.setting import SettingsOut, SettingsUpdate
from app.services import SettingsService
router=APIRouter(prefix="/admin/settings", tags=["admin: настройки"])
@router.get("", response_model=SettingsOut)
async def get_settings(session: SessionDep, ctx: Owner):
    return await SettingsService(session).get_all()
@router.patch("", response_model=SettingsOut)
async def update_settings(data: SettingsUpdate, session: SessionDep, ctx: Owner):
    return await SettingsService(session).update(data)
