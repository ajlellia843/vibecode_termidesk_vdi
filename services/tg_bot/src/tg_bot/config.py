"""Telegram bot configuration."""
from pydantic import Field
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class TgBotSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="TG_BOT_")

    telegram_bot_token: str = Field("", validation_alias="TELEGRAM_BOT_TOKEN")
    orchestrator_url: str = "http://orchestrator:8000"
