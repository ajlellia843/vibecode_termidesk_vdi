"""Orchestrator service configuration."""
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class OrchestratorSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="ORCHESTRATOR_")

    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://app:changeme@localhost:5432/termidesk_bot"
    retrieval_url: str = "http://retrieval:8001"
    llm_url: str = "http://llm:8002"
    retrieval_top_k: int = 5
    max_history_messages: int = 10
