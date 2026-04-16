from __future__ import annotations

from functools import lru_cache
from typing import Annotated
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram
    bot_token: str = Field(alias="BOT_TOKEN")
    webhook_base_url: str = Field(alias="WEBHOOK_BASE_URL")
    webhook_path: str = Field("/telegram/webhook", alias="WEBHOOK_PATH")
    webhook_secret: str = Field(alias="WEBHOOK_SECRET")

    doctor_bootstrap_ids: str = Field("", alias="DOCTOR_BOOTSTRAP_IDS")

    # App
    app_env: str = Field("production", alias="APP_ENV")
    app_host: str = Field("0.0.0.0", alias="APP_HOST")
    app_port: int = Field(8080, alias="APP_PORT")
    app_timezone: str = Field("Europe/Moscow", alias="APP_TIMEZONE")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # PostgreSQL
    postgres_host: str = Field("db", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(..., alias="POSTGRES_DB")
    postgres_user: str = Field(..., alias="POSTGRES_USER")
    postgres_password: str = Field(..., alias="POSTGRES_PASSWORD")

    # Redis (FSM storage)
    redis_url: str = Field("redis://redis:6379/0", alias="REDIS_URL")

    # Alert thresholds (defaults; per-user overrides in DB)
    alert_bp_sys_high: int = Field(160, alias="ALERT_BP_SYS_HIGH")
    alert_bp_dia_high: int = Field(100, alias="ALERT_BP_DIA_HIGH")
    alert_bp_sys_low: int = Field(90, alias="ALERT_BP_SYS_LOW")
    alert_bp_dia_low: int = Field(60, alias="ALERT_BP_DIA_LOW")
    alert_glucose_low: float = Field(3.9, alias="ALERT_GLUCOSE_LOW")
    alert_glucose_high: float = Field(11.1, alias="ALERT_GLUCOSE_HIGH")
    alert_no_data_days: int = Field(3, alias="ALERT_NO_DATA_DAYS")
    alert_missed_med_hours: int = Field(2, alias="ALERT_MISSED_MED_HOURS")

    @field_validator("webhook_base_url")
    @classmethod
    def _strip_slash(cls, v: str) -> str:
        return v.rstrip("/")

    # ----- Derived properties -----

    @property
    def database_url_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def database_url_sync(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url}{self.webhook_path}"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.app_timezone)

    @property
    def doctor_ids(self) -> set[int]:
        out: set[int] = set()
        for chunk in (self.doctor_bootstrap_ids or "").split(","):
            chunk = chunk.strip()
            if chunk.isdigit():
                out.add(int(chunk))
        return out


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


SettingsDep = Annotated[Settings, "settings"]
