from pydantic import BaseModel, Field, field_validator


class LoyaltySettings(BaseModel):
    stamps_per_gift: int = Field(5, ge=2, le=20)
    stamps_expire_days: int | None = Field(None, ge=1)  # None = не сгорают
    gift_expire_days: int | None = Field(None, ge=1)
    gift_with_modifiers: bool = True
    birthday_gift: bool = True
    referral_stamps: int = Field(1, ge=0, le=10)


class OrderSettings(BaseModel):
    payment_timeout_min: int = Field(15, ge=1, le=120)
    accept_timeout_min: int = Field(5, ge=1, le=60)
    max_items_per_order: int = Field(30, ge=1, le=100)


class NotificationTexts(BaseModel):
    order_accepted: str = "Заказ {number} принят, готовим ☕"
    order_ready: str = "Заказ {number} готов, забирайте!"
    order_cancelled: str = "Заказ {number} отменён"
    gift_unlocked: str = "🎉 Следующий напиток — в подарок!"

    @field_validator("order_accepted", "order_ready", "order_cancelled")
    @classmethod
    def has_number(cls, v: str) -> str:
        if "{number}" not in v:
            raise ValueError("В тексте нужен плейсхолдер {number}")
        return v


class SettingsOut(BaseModel):
    loyalty: LoyaltySettings
    orders: OrderSettings
    texts: NotificationTexts


class SettingsUpdate(BaseModel):
    loyalty: LoyaltySettings | None = None
    orders: OrderSettings | None = None
    texts: NotificationTexts | None = None
