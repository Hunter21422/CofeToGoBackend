from fastapi import APIRouter

from app.api.deps import Owner, SessionDep
from app.schemas.staff import StaffCreate, StaffRead, StaffUpdate
from app.services import StaffService
router=APIRouter(prefix="/admin/staff", tags=["admin: команда"])
@router.get("", response_model=list[StaffRead])
async def list_team(session: SessionDep, ctx: Owner):
    return await StaffService(session).list_team()
@router.post("", response_model=StaffRead, status_code=201)
async def add_staff(data: StaffCreate, session: SessionDep, ctx: Owner):
    return await StaffService(session).add_staff(ctx.staff, data)
@router.patch("/{staff_id}", response_model=StaffRead)
async def update_staff(staff_id: int, data: StaffUpdate, session: SessionDep, ctx: Owner):
    return await StaffService(session).update_staff(ctx.staff, staff_id, data)
@router.post("/{staff_id}/reset-pin", response_model=StaffRead)
async def reset_pin(staff_id: int, session: SessionDep, ctx: Owner):
    return await StaffService(session).reset_pin(staff_id)
@router.post("/{staff_id}/revoke", response_model=StaffRead)
async def revoke_sessions(staff_id: int, session: SessionDep, ctx: Owner):
    service = StaffService(session)
    await service.revoke_sessions(staff_id)
    return await service.get_staff(staff_id)
