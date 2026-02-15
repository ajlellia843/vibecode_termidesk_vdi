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
    rag_min_confidence: float = 0.30
    diagnostic_questions_max: int = 2
    rag_max_chunks: int = 3
    rag_max_context_chars: int = 2000
    rag_strict_mode: bool = False
    rag_join_neighbors: bool = True
    rag_dedup_lines: bool = True
    rag_section_extraction: bool = True
    rag_normalize_text: bool = True
