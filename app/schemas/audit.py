from datetime import date, datetime
from typing import Any

from .common import BaseSchema, PaginationParams
from .user import UserShort


class AuditLogRead(BaseSchema):
    id: int
    actor: UserShort | None
    action: str
    entity_type: str
    entity_id: str | None
    before: dict[str, Any] | None
    after: dict[str, Any] | None
    ip: str | None
    created_at: datetime


class AuditFilter(PaginationParams):
    actor_user_id: int | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    action: str | None = None
    date_from: date | None = None
    date_to: date | None = None
