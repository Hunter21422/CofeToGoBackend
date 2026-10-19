from __future__ import annotations

import json
import logging

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.webpush import encrypt, endpoint_allowed, generate_vapid, vapid_headers
from app.models import PushSubscription
from app.repositories import SettingRepository
from app.schemas.push import PushSubscriptionIn

from .errors import ServiceError

log = logging.getLogger(__name__)


class PushService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.settings = SettingRepository(session)

    async def keys(self) -> tuple[str, str]:
        private = await self.settings.get_value("push.vapid_private")
        public = await self.settings.get_value("push.vapid_public")
        if not private or not public:
            private, public = generate_vapid()
            await self.settings.set_value("push.vapid_private", private)
            await self.settings.set_value("push.vapid_public", public)
        return private, public

    async def subscribe(self, user_id: int, data: PushSubscriptionIn, user_agent: str | None = None) -> None:
        if not endpoint_allowed(data.endpoint):
            raise ServiceError("Этот браузер не поддерживает уведомления")
        row = (await self.session.execute(select(PushSubscription).where(PushSubscription.endpoint == data.endpoint))).scalar_one_or_none()
        if row is None:
            self.session.add(PushSubscription(user_id=user_id, endpoint=data.endpoint, p256dh=data.keys.p256dh, auth=data.keys.auth, user_agent=(user_agent or "")[:255]))
        else:
            row.user_id, row.p256dh, row.auth = user_id, data.keys.p256dh, data.keys.auth
        await self.session.flush()

    async def unsubscribe(self, user_id: int, endpoint: str) -> None:
        await self.session.execute(delete(PushSubscription).where(PushSubscription.user_id == user_id, PushSubscription.endpoint == endpoint))

    async def has_subscription(self, user_id: int) -> bool:
        stmt = select(PushSubscription.id).where(PushSubscription.user_id == user_id).limit(1)
        return (await self.session.execute(stmt)).first() is not None

    async def send(self, user_id: int, title: str, body: str, url: str | None = None) -> int:
        subs = (await self.session.execute(select(PushSubscription).where(PushSubscription.user_id == user_id))).scalars().all()
        if not subs:
            return 0
        private, public = await self.keys()
        config = get_settings()
        payload = json.dumps({"title": title, "body": body, "url": url or config.webapp_url}).encode()
        delivered = 0
        async with httpx.AsyncClient(timeout=10) as client:
            for sub in subs:
                headers = {"Content-Encoding": "aes128gcm", "TTL": "86400", "Urgency": "high", **vapid_headers(sub.endpoint, private, public, config.webapp_url)}
                try:
                    r = await client.post(sub.endpoint, content=encrypt(payload, sub.p256dh, sub.auth), headers=headers)
                except httpx.HTTPError as e:
                    log.warning("push %s: %s", sub.id, e)
                    continue
                if r.status_code in (404, 410):
                    await self.session.delete(sub)
                elif r.status_code < 300:
                    delivered += 1
                else:
                    log.warning("push %s: %s %s", sub.id, r.status_code, r.text[:200])
        await self.session.flush()
        return delivered
