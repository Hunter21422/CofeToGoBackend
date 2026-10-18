from fastapi import APIRouter
from app.api.deps import CurrentUser, SessionDep
from app.schemas.cart import CartQuoteIn, CartQuoteOut
from app.services import CartService
router=APIRouter(prefix="/cart",tags=["клиент: корзина"])
@router.post("/quote",response_model=CartQuoteOut)
async def quote_cart(data: CartQuoteIn, session: SessionDep, user: CurrentUser):
    priced=await CartService(session).quote(user.id,data)
    return priced.out
