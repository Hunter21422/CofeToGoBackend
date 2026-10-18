from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.models import Favorite
from app.repositories import ModifierGroupRepository
from app.schemas.menu import ModifierRead, ProductShort, VariantRead
from app.schemas.profile import FavoriteCreate, FavoriteRead
from app.services import FavoriteService
router=APIRouter(prefix="/favorites", tags=["клиент: избранное"])
async def to_read(session, favorites: list[Favorite]) -> list[FavoriteRead]:
    ids = {i for f in favorites for i in f.modifier_ids}
    mods = {m.id: m for m in await ModifierGroupRepository(session).modifiers_by_ids(list(ids))}
    result = []
    for f in favorites:
        p = f.product
        active = [v for v in p.variants if v.is_active]
        variant = f.variant or next((v for v in active if v.is_default), None) or (active[0] if active else None)
        picked = [mods[i] for i in f.modifier_ids if i in mods]
        ok = p.is_active and variant is not None and variant.is_active and all(m.is_active for m in picked)
        price = (variant.price if variant else 0) + sum(m.price_delta for m in picked)
        short = ProductShort(id=p.id, name=p.name, slug=p.slug, description=p.description, image_url=p.image_url, min_price=min((v.price for v in active), default=0), tags=list(p.tags), is_available=ok)
        result.append(FavoriteRead(id=f.id, product=short, variant=VariantRead.model_validate(variant) if variant else None, modifiers=[ModifierRead.model_validate(m) for m in picked], custom_name=f.custom_name, price=price, is_available=ok))
    return result
@router.get("", response_model=list[FavoriteRead])
async def list_favorites(session: SessionDep, user: CurrentUser):
    return await to_read(session, await FavoriteService(session).list(user.id))
@router.post("", response_model=FavoriteRead, status_code=201)
async def add_favorite(data: FavoriteCreate, session: SessionDep, user: CurrentUser):
    favorite = await FavoriteService(session).add(user.id, data)
    return (await to_read(session, [favorite]))[0]
@router.delete("/{favorite_id}", status_code=204)
async def remove_favorite(favorite_id: int, session: SessionDep, user: CurrentUser):
    await FavoriteService(session).remove(user.id, favorite_id)
