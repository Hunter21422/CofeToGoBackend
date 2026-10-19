from functools import lru_cache

from pydantic import Field, field_validator
from typing import Annotated

from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Кофе с тобой"
    debug: bool = False
    dev_mode: bool = False  # принимать initData вида "dev=<tg_id>" — только для локальной разработки

    database_url: str = "postgresql+asyncpg://coffee:coffee@localhost:5432/coffee"
    db_echo: bool = False
    redis_url: str = "redis://localhost:6379/0"

    bot_token: str = ""
    bot_username: str = "kofe_s_toboy_bot"
    bot_proxy: str = ""
    bot_api_url: str = ""
    webapp_url: str = "https://localhost"
    # Секретный путь админки, должен совпадать с VITE_ADMIN_PATH во фронте. Ссылки из бота: {webapp_url}/{admin_path}/
    admin_path: str = "staff-change-me"

    @property
    def admin_url(self) -> str:
        return f"{self.webapp_url.rstrip('/')}/{self.admin_path.strip('/')}/"
    # Первые владельцы — создаются в staff при старте. Дальше сотрудников добавляет только owner
    owner_tg_ids: Annotated[list[int], NoDecode] = Field(default_factory=list)

    # Вход на сайте по SMS (sms.ru). Пусто + dev_mode → код пишется в лог вместо отправки
    sms_ru_api_id: str = ""
    sms_ru_mode: str = "call"
    sms_code_ttl_sec: int = 300
    sms_resend_sec: int = 60
    sms_max_attempts: int = 5
    sms_daily_limit_per_phone: int = 10

    jwt_secret: str = "change-me"
    access_ttl_min: int = 15
    refresh_ttl_days: int = 30
    init_data_ttl_hours: int = 24

    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=list)

    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""

    @field_validator("owner_tg_ids", mode="before")
    @classmethod
    def split_ids(cls, v: object) -> object:
        if isinstance(v, str):
            return [int(x) for x in v.replace(" ", "").split(",") if x]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
