from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str = Field(max_length=255)
    auth: str = Field(max_length=64)


class PushSubscriptionIn(BaseModel):
    endpoint: str = Field(max_length=2048)
    keys: PushKeys


class PushUnsubscribeIn(BaseModel):
    endpoint: str = Field(max_length=2048)


class PushKeyOut(BaseModel):
    public_key: str
    subscribed: bool
