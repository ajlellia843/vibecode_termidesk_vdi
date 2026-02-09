"""LLM service entrypoint - gateway to local inference or mock."""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
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
        client = request.app.state.llm_client
        text = await client.generate(body.prompt, max_tokens=body.max_tokens)
        return GenerateResponse(text=text)

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
