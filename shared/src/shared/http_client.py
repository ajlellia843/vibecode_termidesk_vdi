"""HTTP client with retries, timeout and simple circuit breaker."""
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """Simple in-memory circuit breaker: opens after failure_threshold failures."""

    def __init__(self, failure_threshold: int = 5, reset_after_seconds: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_after_seconds = reset_after_seconds
        self._failures = 0
        self._last_failure_time: float | None = None

    def record_success(self) -> None:
        self._failures = 0
        self._last_failure_time = None

    def record_failure(self) -> None:
        self._last_failure_time = time.time()
        self._failures += 1

    def is_open(self) -> bool:
        if self._failures < self.failure_threshold:
            return False
        if self._last_failure_time is None:
            return True
        if time.time() - self._last_failure_time >= self.reset_after_seconds:
            self._failures = 0
            self._last_failure_time = None
            return False
        return True


def create_http_client(
    timeout: float = 30.0,
    max_retries: int = 3,
    retry_wait_base: float = 1.0,
) -> httpx.AsyncClient:
    """Create async HTTP client with retries and timeout."""
    transport = httpx.AsyncHTTPTransport(retries=0)
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout),
        transport=transport,
    )


async def request_with_retries(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    json: Any = None,
    retries: int = 3,
    circuit_breaker: CircuitBreaker | None = None,
) -> httpx.Response:
    """Perform request with tenacity retries and optional circuit breaker."""
    if circuit_breaker and circuit_breaker.is_open():
        raise CircuitBreakerOpenError("Circuit breaker is open")

    @retry(
        retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
        stop=stop_after_attempt(retries),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def _do() -> httpx.Response:
        resp = await client.request(method, url, json=json)
        resp.raise_for_status()
        return resp

    try:
        resp = await _do()
        if circuit_breaker:
            circuit_breaker.record_success()
        return resp
    except Exception as e:
        if circuit_breaker:
            circuit_breaker.record_failure()
        raise e
