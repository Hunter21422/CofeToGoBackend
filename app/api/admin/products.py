from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Barista, Manager, SessionDep
from app.schemas.common import Page
from app.schemas.menu import ProductAdminFilter, ProductAdminRead, ProductCreate, ProductUpdate, ReorderIn
from app.services import MenuService
router=APIRouter(prefix="/admin/products", tags=["admin: меню"])
@router.get("", response_model=Page[ProductAdminRead])
async def list_products(f: Annotated[ProductAdminFilter, Query()], session: SessionDep, ctx: Barista):
    items, total = await MenuService(session).admin_products(f)
    return Page(items=items, total=total, limit=f.limit, offset=f.offset)
@router.get("/{product_id}", response_model=ProductAdminRead)
async def get_product(product_id: int, session: SessionDep, ctx: Barista):
    return await MenuService(session).get_product(product_id)
@router.post("", response_model=ProductAdminRead, status_code=201)
async def create_product(data:ProductCreate,session:SessionDep,ctx:Manager):
    return await MenuService(session).create_product(data)
@router.patch("/{product_id}", response_model=ProductAdminRead)
async def update_product(product_id: int, data: ProductUpdate, session: SessionDep, ctx: Manager):
    return await MenuService(session).update_product(product_id,data)
@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: int, session: SessionDep, ctx: Manager):
     await MenuService(session).delete_product(product_id)
@router.post("/reorder", status_code=204)
async def reorder_product(data:ReorderIn,session:SessionDep,ctx:Manager):
    await MenuService(session).reorder_product(data.ids)
