from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from .common import BaseSchema


class StockItemRead(BaseSchema):
    id: int
    location_id: int
    product_id: int | None
    variant_id: int | None
    modifier_id: int | None
    title: str = ""  # название позиции, заполняется в сервисе
    until: datetime | None
    reason: str | None
    created_at: datetime


class StockItemCreate(BaseModel):
    product_id: int | None = None
    variant_id: int | None = None
    modifier_id: int | None = None
    until: datetime | None = None  # None = пока вручную не вернут
    until_end_of_day: bool = False
    reason: str | None = Field(None, max_length=255)

    @model_validator(mode="after")
    def exactly_one_target(self):
        filled = sum(x is not None for x in (self.product_id, self.variant_id, self.modifier_id))
        if filled != 1:
            raise ValueError("Укажи ровно одно: product_id, variant_id или modifier_id")
        return self
