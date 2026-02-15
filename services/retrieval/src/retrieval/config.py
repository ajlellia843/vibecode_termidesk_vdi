"""Retrieval service configuration."""
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class RetrievalSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="RETRIEVAL_")

    host: str = "0.0.0.0"
    port: int = 8001
    database_url: str = "postgresql+asyncpg://app:changeme@localhost:5432/termidesk_bot"
    embedding_dim: int = 384
    retrieval_mode: str = "vector"  # vector | text | hybrid
    embedder_backend: str = "mock"  # sentence_transformers | mock
    embedder_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    min_score: float = 0.35
    kb_latest_version: str = "6.1 (latest)"
