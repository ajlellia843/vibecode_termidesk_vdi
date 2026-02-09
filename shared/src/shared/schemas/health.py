"""Health check response schema."""
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response for /healthz and /readyz."""

    status: str  # "ok" | "degraded" | "unhealthy"
    service: str = ""
