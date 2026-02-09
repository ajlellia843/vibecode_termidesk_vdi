"""FastAPI middleware for request_id and trace_id."""
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from shared.logging import clear_request_context, set_request_context


def get_request_id_from_headers(request: Request) -> str | None:
    """Extract X-Request-ID from request headers."""
    return request.headers.get("X-Request-ID") or request.headers.get("x-request-id")


def get_trace_id_from_headers(request: Request) -> str | None:
    """Extract X-Trace-ID from request headers."""
    return request.headers.get("X-Trace-ID") or request.headers.get("x-trace-id")


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Add request_id and trace_id to context and response headers."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = get_request_id_from_headers(request) or str(uuid.uuid4())
        trace_id = get_trace_id_from_headers(request) or request_id
        set_request_context(request_id=request_id, trace_id=trace_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            clear_request_context()
