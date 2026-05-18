from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import Settings
from .db import Database
from .dependencies import build_services
from .legacy import LegacyAPIError, legacy_error
from .middleware import request_logging_middleware
from .routers import router
from .settings_provider import SettingsProvider


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db.bootstrap()
    app.state.visit_worker_task = asyncio.create_task(app.state.visit_service.run())
    try:
        yield
    finally:
        app.state.visit_worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await app.state.visit_worker_task
        pending_geo_tasks = list(app.state.geo_service.background_tasks)
        for task in pending_geo_tasks:
            task.cancel()
        if pending_geo_tasks:
            await asyncio.gather(*pending_geo_tasks, return_exceptions=True)


def create_app(*, config_path: str | None = None, settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    provider = SettingsProvider(config_path=config_path, settings=settings)
    current_settings = provider.current()
    db = db or Database(
        current_settings.db_path,
        geo_enabled=current_settings.geo_enabled,
        moderation_schema=bool(current_settings.llm_filter),
    )
    app = FastAPI(title="Anonymous Question Box API", version="0.1.0", lifespan=lifespan)
    app.state.settings_provider = provider
    app.state.settings = current_settings
    app.state.db = db
    app.state.visit_worker_task = None
    for name, service in build_services(db, provider).items():
        setattr(app.state, name, service)

    @app.exception_handler(LegacyAPIError)
    async def legacy_exception_handler(_: Request, exc: LegacyAPIError) -> JSONResponse:
        return legacy_error(exc.status_code, exc.message)

    app.middleware("http")(request_logging_middleware)
    app.include_router(router)
    return app
