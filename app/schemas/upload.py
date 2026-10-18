from typing import Literal

from pydantic import BaseModel, Field


class UploadRequestIn(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size: int = Field(gt=0, le=5_000_000)  # до 5 МБ


class UploadUrlOut(BaseModel):
    upload_url: str
    public_url: str
    fields: dict[str, str] = {}  # для presigned POST
    expires_in: int
