"""Orchestrator service entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import make_asgi_app
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.logging import configure_logging
from shared.middleware import RequestIdMiddleware
from shared.schemas import HealthResponse

from orchestrator.api.routes import router
from orchestrator.clients import LLMClient, RetrievalClient
from orchestrator.config import OrchestratorSettings
from orchestrator.service import DialogService

_settings: OrchestratorSettings | None = None
_app: FastAPI | None = None


def get_settings() -> OrchestratorSettings:
    global _settings
    if _settings is None:
        _settings = OrchestratorSettings()
    return _settings


def get_app() -> FastAPI:
    global _app
    return _app  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    retrieval_client = RetrievalClient(settings.retrieval_url)
    llm_client = LLMClient(settings.llm_url)
    dialog_service = DialogService(
        session_factory=session_factory,
        retrieval_client=retrieval_client,
        llm_client=llm_client,
        retrieval_top_k=settings.retrieval_top_k,
        max_history_messages=settings.max_history_messages,
    )
    app.state.dialog_service = dialog_service
    app.state.session_factory = session_factory
    app.state.engine = engine
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    configure_logging(json_logs=True)
    app = FastAPI(title="Orchestrator Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)

    # #region agent log
    import json
    import os
    import traceback
    from fastapi import Request
    from fastapi.responses import JSONResponse
    @app.exception_handler(Exception)
    async def _log_exception(request: Request, exc: Exception):
        path = os.environ.get("DEBUG_LOG_PATH", ".cursor/debug.log")
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": "orchestrator", "message": "exception", "data": {"type": type(exc).__name__, "message": str(exc), "path": str(request.url.path), "traceback": traceback.format_exc()}, "hypothesisId": "H2", "timestamp": __import__("time").time() * 1000}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})
    # #endregion

    app.include_router(router)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service="orchestrator")

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz() -> HealthResponse:
        from sqlalchemy import text
        try:
            async with app.state.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return HealthResponse(status="unhealthy", service="orchestrator")
        return HealthResponse(status="ok", service="orchestrator")

    global _app
    _app = app
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "orchestrator.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
