from pydantic import BaseModel, Field, model_validator

from .common import BaseSchema, Money, Name
from .menu import ModifierRead


class ModifierIn(BaseModel):
    id: int | None = None  # None = новый
    name: Name
    price_delta: Money = 0
    is_default: bool = False
    sort_order: int = 0
    is_active: bool = True


class ModifierGroupCreate(BaseModel):
    name: Name
    min_select: int = Field(0, ge=0)
    max_select: int = Field(1, ge=1)
    sort_order: int = 0
    modifiers: list[ModifierIn] = Field(min_length=1)

    @model_validator(mode="after")
    def check(self):
        if self.max_select < self.min_select:
            raise ValueError("max_select должен быть >= min_select")
        if sum(m.is_default for m in self.modifiers) > self.max_select:
            raise ValueError("Модификаторов по умолчанию больше, чем max_select")
        return self


class ModifierGroupUpdate(BaseModel):
    name: Name | None = None
    min_select: int | None = Field(None, ge=0)
    max_select: int | None = Field(None, ge=1)
    sort_order: int | None = None
    modifiers: list[ModifierIn] | None = Field(None, min_length=1)
    is_active: bool | None = None


class ModifierAdminRead(ModifierRead):
    sort_order: int
    is_active: bool


class ModifierGroupAdminRead(BaseSchema):
    id: int
    name: str
    min_select: int
    max_select: int
    sort_order: int
    is_active: bool
    modifiers: list[ModifierAdminRead]


class GroupProductsIn(BaseModel):
    product_ids: list[int] = Field(default_factory=list, max_length=500)
