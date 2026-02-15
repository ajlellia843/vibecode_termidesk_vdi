"""LLM service configuration."""
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class LLMSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="LLM_")

    host: str = "0.0.0.0"
    port: int = 8002
    base_url: str = "http://localhost:8000"
    mock: bool = True
    generate_timeout_seconds: float = 120.0
