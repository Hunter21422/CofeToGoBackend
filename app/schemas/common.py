import re
from typing import Annotated, Any, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints


class BaseSchema(BaseModel):
    """База для всех схем ответа: можно собирать прямо из SQLAlchemy-объекта."""

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


def _normalize_phone(v: Any) -> Any:
    """'8 (999) 123-45-67' → '+79991234567'"""
    if not isinstance(v, str):
        return v
    digits = re.sub(r"\D", "", v)
    if len(digits) == 11 and digits[0] in "78":
        return "+7" + digits[1:]
    if len(digits) == 10:
        return "+7" + digits
    return v


Money = Annotated[int, Field(ge=0, description="Сумма в копейках")]
Quantity = Annotated[int, Field(ge=1, le=20)]
Rating = Annotated[int, Field(ge=1, le=5)]
Phone = Annotated[str, BeforeValidator(_normalize_phone), Field(pattern=r"^\+7\d{10}$")]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9-]+$", min_length=1, max_length=64)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
PromoCodeStr = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, min_length=1, max_length=32)
]

T = TypeVar("T")


class PaginationParams(BaseModel):
    limit: int = Field(20, ge=1, le=500)
    offset: int = Field(0, ge=0)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class MessageOut(BaseModel):
    detail: str
