"""Ingest service configuration."""
from pydantic_settings import SettingsConfigDict

from shared.config import BaseAppSettings


class IngestSettings(BaseAppSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_")

    knowledge_path: str = "knowledge"
    database_url: str = "postgresql+asyncpg://app:changeme@localhost:5432/termidesk_bot"
    chunk_size: int = 900
    chunk_overlap: int = 180
    embedding_dim: int = 384
    embedder_backend: str = "sentence_transformers"  # sentence_transformers | mock
    embedder_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    kb_default_version: str = "6.1 (latest)"
