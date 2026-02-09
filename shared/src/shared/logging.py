"""Structured logging with request_id/trace_id correlation."""
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="")
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


def get_request_id() -> str:
    return request_id_var.get() or ""


def get_trace_id() -> str:
    return trace_id_var.get() or ""


def set_request_context(request_id: str | None = None, trace_id: str | None = None) -> None:
    request_id_var.set(request_id or str(uuid.uuid4()))
    trace_id_var.set(trace_id or request_id_var.get() or str(uuid.uuid4()))


def clear_request_context() -> None:
    request_id_var.set("")
    trace_id_var.set("")


def add_request_context(
    logger: Any,
    method: str,
    event: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """Processor to inject request_id and trace_id into log events."""
    out: dict[str, Any] = dict(kwargs)
    rid = get_request_id()
    tid = get_trace_id()
    if rid:
        out["request_id"] = rid
    if tid:
        out["trace_id"] = tid
    return out


def configure_logging(json_logs: bool = True) -> None:
    """Configure structlog for JSON output and request correlation."""
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        add_request_context,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        shared_processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=shared_processors,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )
