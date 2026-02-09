"""Request context for tracing."""
from pydantic import BaseModel


class RequestContext(BaseModel):
    """Request and trace identifiers."""

    request_id: str = ""
    trace_id: str = ""
