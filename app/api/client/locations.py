from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.location import LocationFilter, LocationRead, LocationShort
from app.schemas.menu import MenuOut, ProductRead
from app.services import LocationService, MarketingService, MenuService
router=APIRouter(prefix="/locations", tags=["клиент: меню"])
@router.get("", response_model=list[LocationRead])
async def list_locations(f: Annotated[LocationFilter, Query()], session: SessionDep, user: CurrentUser):
    locations = await LocationService(session).list_for_guest()
    if f.only_open:
        locations = [l for l in locations if l.is_open_now]
    if f.lat is not None and f.lng is not None:
        locations.sort(key=lambda l: (l.lat - f.lat) ** 2 + (l.lng - f.lng) ** 2 if l.lat is not None and l.lng is not None else 10**9)
    return locations
@router.get("/{location_id}/menu", response_model=MenuOut)
async def get_menu(location_id: int, session: SessionDep, user: CurrentUser):
    location = await LocationService(session).get_location(location_id)
    categories = await MenuService(session).menu_for_location(location_id)
    banners = await MarketingService(session).active_banners(location_id)
    return MenuOut(location=LocationShort.model_validate(location), categories=categories, banners=banners)
@router.get("/{location_id}/products/{product_id}", response_model=ProductRead)
async def get_product(location_id: int, product_id: int, session: SessionDep, user: CurrentUser):
    return await MenuService(session).product_for_guest(location_id, product_id, user.id)
