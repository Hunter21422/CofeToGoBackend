from fastapi import APIRouter
from app.api.deps import Barista, Manager, SessionDep
from app.schemas.modifier import ModifierGroupAdminRead, ModifierGroupCreate, ModifierGroupUpdate
from app.services import ModifierService
router=APIRouter(prefix="/admin/modifier-groups",tags=["admin: меню"])
@router.get("",response_model=list[ModifierGroupAdminRead])
async def list_group(session:SessionDep,ctx:Barista):
    return await ModifierService(session).list_groups()
@router.post("",response_model=ModifierGroupAdminRead, status_code=201)
async def create_group(data:ModifierGroupCreate,session:SessionDep,ctx:Manager):
    return await ModifierService(session).create_group(data)
@router.patch("/{group_id}",response_model=ModifierGroupAdminRead)
async def update_group(group_id: int, data: ModifierGroupUpdate,session:SessionDep,ctx:Manager):
    return await ModifierService(session).update_group(group_id,data)
@router.delete("/{group_id}",status_code=204)
async def delete_group(group_id:int,session:SessionDep,ctx:Manager):
    await ModifierService(session).delete_group(group_id)
