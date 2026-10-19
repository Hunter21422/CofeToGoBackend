from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, SessionDep, user_agent
from app.schemas.push import PushKeyOut, PushSubscriptionIn, PushUnsubscribeIn
from app.services import PushService
router=APIRouter(prefix="/push", tags=["клиент: уведомления"])
@router.get("/key", response_model=PushKeyOut)
async def push_key(session: SessionDep, user: CurrentUser):
    service = PushService(session)
    _, public = await service.keys()
    return PushKeyOut(public_key=public, subscribed=await service.has_subscription(user.id))
@router.post("/subscribe", status_code=204)
async def subscribe(data: PushSubscriptionIn, request: Request, session: SessionDep, user: CurrentUser):
    await PushService(session).subscribe(user.id, data, user_agent(request))
@router.post("/unsubscribe", status_code=204)
async def unsubscribe(data: PushUnsubscribeIn, session: SessionDep, user: CurrentUser):
    await PushService(session).unsubscribe(user.id, data.endpoint)
