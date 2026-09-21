"""
Middleware registration.

CORS: reproduces the current Node backend's fixed allow-list exactly
(app.config.Settings.cors_allow_origins) — confirmed requirement, not a new
decision (docs/module-3-development-plan.md §7).

Request logging: new, minimal, standard-library only. Not present in the
current Node backend (which has no request logging middleware at all —
CURRENT_STATE.md §9) but does not change any preserved behavior; it only
logs.
"""

import logging
import time

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from app.config import Settings

logger = logging.getLogger("app.request")


def register_middleware(app: FastAPI, settings: Settings) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Cookie", "X-Requested-With"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        return response
