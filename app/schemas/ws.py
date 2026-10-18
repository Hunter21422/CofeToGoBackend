from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

WsEventType = Literal[
    "order.created",
    "order.updated",
    "order.cancelled",
    "stock.changed",
    "loyalty.updated",
    "ping",
]


class WsEvent(BaseModel):
    type: WsEventType
    data: dict[str, Any] = {}
    ts: Annotated[datetime, Field(default_factory=lambda: datetime.now(UTC))]
