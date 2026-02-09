"""Retrieval service configuration."""
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class RetrievalSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_")

    host: str = "0.0.0.0"
    port: int = 8001
    database_url: str = "postgresql+asyncpg://app:changeme@localhost:5432/termidesk_bot"
    embedding_dim: int = 384
