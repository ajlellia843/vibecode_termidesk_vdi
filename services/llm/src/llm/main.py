"""LLM service entrypoint - gateway to local inference or mock."""
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from prometheus_client import make_asgi_app

from shared.logging import configure_logging
from shared.middleware import RequestIdMiddleware
from shared.schemas import HealthResponse

from llm.api.schemas import GenerateRequest, GenerateResponse
from llm.client import HTTPLLMClient, MockLLMClient
from llm.config import LLMSettings

_settings: LLMSettings | None = None
_app: FastAPI | None = None


def get_settings() -> LLMSettings:
    global _settings
    if _settings is None:
        _settings = LLMSettings()
    return _settings


def get_app() -> FastAPI:
    global _app
    return _app  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.mock:
        app.state.llm_client = MockLLMClient()
    else:
        app.state.llm_client = HTTPLLMClient(settings.base_url)
    yield


def create_app() -> FastAPI:
    configure_logging(json_logs=True)
    app = FastAPI(title="LLM Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service="llm")

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz() -> HealthResponse:
        return HealthResponse(status="ok", service="llm")

    @app.post("/generate", response_model=GenerateResponse)
    async def generate(body: GenerateRequest, request: Request) -> GenerateResponse:
        settings = get_settings()
        client = request.app.state.llm_client
        try:
            text = await asyncio.wait_for(
                client.generate(body.prompt, max_tokens=body.max_tokens),
                timeout=settings.generate_timeout_seconds,
            )
        except asyncio.TimeoutError:
            return GenerateResponse(
                text="[LLM timeout] Ответ не получен в отведённое время. Попробуйте короче запрос или повторите позже."
            )
        return GenerateResponse(text=text)

    @app.post("/generate/stream")
    async def generate_stream(body: GenerateRequest, request: Request):
        """Streaming endpoint (stub: returns single SSE chunk until real LLM supports stream)."""
        settings = get_settings()
        client = request.app.state.llm_client
        async def event_stream():
            try:
                text = await asyncio.wait_for(
                    client.generate(body.prompt, max_tokens=body.max_tokens),
                    timeout=settings.generate_timeout_seconds,
                )
                yield f"data: {json.dumps(text)}\n\n"
            except asyncio.TimeoutError:
                yield "data: [LLM timeout]\n\n"
        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    global _app
    _app = app
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "llm.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
