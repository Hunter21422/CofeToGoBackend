from fastapi import APIRouter, Request

from app.api.deps import GatewayDep, SessionDep
from app.services import PaymentService
router=APIRouter(prefix="/webhooks", tags=["вебхуки"])
@router.post("/yookassa")
async def yookassa(request: Request, session: SessionDep, gateway: GatewayDep):
    body = await request.json()
    payment_id = (body.get("object") or {}).get("id")
    if payment_id:
        await PaymentService(session, gateway).handle_webhook(payment_id)
    return {"ok": True}
