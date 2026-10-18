from fastapi import APIRouter
from app.api.deps import Owner, SessionDep
from app.schemas.location import LocationCreate, LocationHoursUpdate, LocationRead, LocationUpdate
from app.services import LocationService
router=APIRouter(prefix="/admin/locations",tags=["admin: точки"])
@router.get("",response_model=list[LocationRead])
async def list_for_admin(session:SessionDep,ctx:Owner):
    return await LocationService(session).list_for_admin()
@router.post("",response_model=LocationRead,status_code=201)
async def create_location(data:LocationCreate,session:SessionDep,ctx:Owner):
    return await LocationService(session).create_location(data)
@router.patch("/{location_id}",response_model=LocationRead)
async def update_location(location_id:int,data:LocationUpdate,session:SessionDep,ctx:Owner):
    return await LocationService(session).update_location(location_id,data)
@router.put("/{location_id}/hours",response_model=LocationRead)
async def set_hours(location_id:int,data:LocationHoursUpdate,session:SessionDep,ctx:Owner):
    return await LocationService(session).set_hours(location_id,data)
