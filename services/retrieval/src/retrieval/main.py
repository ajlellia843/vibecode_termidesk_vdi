"""Retrieval service entrypoint."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from prometheus_client import make_asgi_app
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from shared.logging import configure_logging
from shared.middleware import RequestIdMiddleware
from shared.schemas import HealthResponse

from retrieval.api.routes import router
from retrieval.config import RetrievalSettings
from retrieval.service import SearchService
from retrieval.storage.pgvector_storage import PgVectorStorage

_settings: RetrievalSettings | None = None
_app: FastAPI | None = None


def get_settings() -> RetrievalSettings:
    global _settings
    if _settings is None:
        _settings = RetrievalSettings()
    return _settings


def get_app() -> FastAPI:
    global _app
    return _app  # type: ignore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        echo=False,
    )
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1 FROM retrieval.chunks LIMIT 1"))
    except ProgrammingError as e:
        if "does not exist" in str(e):
            structlog.get_logger().warning(
                "retrieval_schema_missing",
                msg="Schema retrieval or table chunks not found. RAG will return empty. Apply migrations: docker compose run --rm retrieval python -m alembic -c alembic.ini upgrade head",
            )
    except Exception:
        pass
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    storage = PgVectorStorage(session_factory)
    app.state.search_service = SearchService(storage)
    app.state.engine = engine
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    configure_logging(json_logs=True)
    settings = get_settings()
    app = FastAPI(title="Retrieval Service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(RequestIdMiddleware)

    app.include_router(router)

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service="retrieval")

    @app.get("/readyz", response_model=HealthResponse)
    async def readyz() -> HealthResponse:
        try:
            engine = app.state.engine
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return HealthResponse(status="unhealthy", service="retrieval")
        return HealthResponse(status="ok", service="retrieval")

    global _app
    _app = app
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "retrieval.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
