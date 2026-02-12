import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pysequence_api.config import get_server_config
from pysequence_api.routes import health_router, router
from pysequence_api.safeguards import AuditLog, DailyLimitTracker
from pysequence_sdk import SequenceClient, get_access_token


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = get_server_config()

    app.state.server_config = config
    app.state.api_key = config.api_key

    access_token = await asyncio.to_thread(get_access_token)

    app.state.client = SequenceClient(
        access_token=access_token,
        token_provider=get_access_token,
    )

    app.state.daily_limits = DailyLimitTracker(
        max_daily_cents=config.max_daily_transfer_cents,
    )

    app.state.audit = AuditLog()

    try:
        yield

    finally:
        app.state.client.close()


def create_app() -> FastAPI:
    app = FastAPI(title="GetSequence API", lifespan=lifespan)

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(
        request: Request, exc: RuntimeError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=502,
            content={"detail": str(exc)},
        )

    app.include_router(health_router)
    app.include_router(router)

    return app
