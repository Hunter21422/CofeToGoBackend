from fastapi import APIRouter

from app.api.deps import Barista, Manager, SessionDep
from app.schemas.menu import CategoryAdminRead, CategoryCreate, CategoryUpdate, ReorderIn
from app.services import MenuService
router=APIRouter(prefix="/admin/categories", tags=["admin: меню"])
@router.get("", response_model=list[CategoryAdminRead])
async def list_categories(session: SessionDep, ctx: Barista):
    return await MenuService(session).list_categories()
@router.post("", response_model=CategoryAdminRead, status_code=201)
async def create_category(data: CategoryCreate, session: SessionDep, ctx: Manager):
    return await MenuService(session).create_category(data)
@router.patch("/{category_id}", response_model=CategoryAdminRead)
async def update_category(category_id: int, data: CategoryUpdate, session: SessionDep, ctx: Manager):
    return await MenuService(session).update_category(category_id, data)
@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: int, session: SessionDep, ctx: Manager):
    await MenuService(session).delete_category(category_id)
@router.post("/reorder", status_code=204)
async def reorder_categories(data: ReorderIn, session: SessionDep, ctx: Manager):
    await MenuService(session).reorder_categories(data.ids)
