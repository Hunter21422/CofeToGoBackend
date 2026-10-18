from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import SettingRepository
from app.schemas.setting import LoyaltySettings, NotificationTexts, OrderSettings, SettingsOut, SettingsUpdate

SECTIONS = {"loyalty": LoyaltySettings, "orders": OrderSettings, "texts": NotificationTexts}


class SettingsService:
    def __init__(self, session: AsyncSession):
        self.settings = SettingRepository(session)

    async def get_all(self) -> SettingsOut:
        saved = await self.settings.all_global()
        data = {}
        for section, model in SECTIONS.items():
            values = {f: saved[f"{section}.{f}"] for f in model.model_fields if f"{section}.{f}" in saved}
            data[section] = model(**values)
        return SettingsOut(**data)

    async def update(self, data: SettingsUpdate) -> SettingsOut:
        for section in SECTIONS:
            part = getattr(data, section)
            if part is None:
                continue
            for key, value in part.model_dump(mode="json").items():
                await self.settings.set_value(f"{section}.{key}", value)
        return await self.get_all()
