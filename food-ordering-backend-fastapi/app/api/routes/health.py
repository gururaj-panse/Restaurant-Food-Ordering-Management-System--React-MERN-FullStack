"""
Health-check endpoints — the one route group implemented for real in this
skeleton (no business logic involved, and required to verify the app boots).

Reproduces the confirmed contract exactly (CURRENT_STATE.md §2, PRD.md
BM-09): GET /, GET /health, GET /api/health, uptime computed from an
in-process start time.

NOTE: this preserves the SAME known limitation as the current Node backend
— uptime resets per-process and is meaningless under multiple instances.
Whether to fix this is Open Question #20 and is NOT decided here; this
skeleton reproduces current behavior, it does not improve on it.
"""

import time
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["health"])

_server_start_time = time.time()


@router.get("/", response_class=HTMLResponse)
async def root() -> str:
    return (
        "<h1>BigHungers Food Ordering Backend (FastAPI skeleton) is running</h1>"
        "<p>Module 3 structure-only skeleton — business logic not yet migrated.</p>"
    )


def _health_payload() -> dict:
    uptime_seconds = int(time.time() - _server_start_time)
    return {
        "message": "health OK!",
        "uptime": uptime_seconds,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "serverStartTime": datetime.fromtimestamp(
            _server_start_time, tz=timezone.utc
        ).isoformat(),
    }


@router.get("/health")
async def health() -> dict:
    return _health_payload()


@router.get("/api/health")
async def api_health() -> dict:
    return _health_payload()
