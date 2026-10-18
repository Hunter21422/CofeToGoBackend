from datetime import datetime

from pydantic import BaseModel, Field, computed_field, model_validator

from app.models.enums import LoyaltyTier, LoyaltyTxType

from .common import BaseSchema, PaginationParams
from .order import OrderShort
from .user import UserShort


class LoyaltyRead(BaseSchema):
    stamps: int
    stamps_per_gift: int = 5  # из настроек, подставляется в сервисе
    gifts_available: int
    lifetime_stamps: int
    lifetime_gifts: int
    tier: LoyaltyTier

    @computed_field
    @property
    def stamps_left(self) -> int:
        return max(self.stamps_per_gift - self.stamps, 0)


class LoyaltyTransactionRead(BaseSchema):
    id: int
    type: LoyaltyTxType
    stamps_delta: int
    gifts_delta: int
    stamps_after: int
    gifts_after: int
    order_id: int | None
    reason: str | None
    created_at: datetime


class LoyaltyHistoryFilter(PaginationParams):
    type: list[LoyaltyTxType] = []


class LoyaltyQrOut(BaseModel):
    token: str        # содержимое QR (подписанный, одноразовый)
    code: str         # 6 цифр — гость называет бариста; живёт 5 минут, сгорает после проверки
    expires_at: datetime
    refresh_in: int  # через сколько секунд обновить QR


# ---------- Админка / касса ----------
class QrScanIn(BaseModel):
    token: str
    location_id: int


class GuestCodeIn(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")
    location_id: int


class CustomerSearchItem(BaseModel):
    """Результат поиска гостя на кассе по @username / телефону / имени"""

    user: UserShort
    phone: str | None
    loyalty: LoyaltyRead


class ScanResultOut(BaseModel):
    user: UserShort
    phone: str | None
    loyalty: LoyaltyRead
    last_orders: list[OrderShort]


class StampAddIn(BaseModel):
    user_id: int
    location_id: int
    count: int = Field(1, ge=1, le=10)


class GiftRedeemIn(BaseModel):
    user_id: int
    location_id: int


class LoyaltyAdjustIn(BaseModel):
    user_id: int
    stamps_delta: int = Field(0, ge=-50, le=50)
    gifts_delta: int = Field(0, ge=-10, le=10)
    reason: str = Field(min_length=5, max_length=255)

    @model_validator(mode="after")
    def not_empty(self):
        if self.stamps_delta == 0 and self.gifts_delta == 0:
            raise ValueError("Нужно изменить штампы или подарки")
        return self


class LoyaltyOperationOut(BaseModel):
    loyalty: LoyaltyRead
    transaction: LoyaltyTransactionRead
    gift_unlocked: bool = False
