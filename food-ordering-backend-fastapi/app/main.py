"""
FastAPI application entry point — Module 3 structure-only skeleton.

Boot sequence mirrors food-ordering-backend/src/index.ts's shape (connect DB
-> configure app -> register middleware -> mount routes -> health checks),
adapted to FastAPI's lifespan/dependency model. No business logic has been
migrated — every non-health route currently returns 501 via
NotImplementedFeatureError. See docs/module-3-development-plan.md.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import analytics, auth, health, my_restaurant, order, restaurant, user
from app.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.middleware import register_middleware
from app.db.mongodb import mongodb
from app.logging_config import configure_logging

settings = get_settings()
configure_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.mongodb_uri:
        await mongodb.connect(settings.mongodb_uri)
    else:
        # Allow the app to boot without a DB for structure verification
        # (e.g. `uvicorn app.main:app` with no .env yet) — every DB-backed
        # route is a 501 stub at this stage anyway.
        import logging

        logging.getLogger(__name__).warning(
            "MONGODB_URI/MONGODB_CONNECTION_STRING not set — starting without a database connection."
        )
    yield
    await mongodb.close()


app = FastAPI(
    title="BigHungers Food Ordering Backend (FastAPI)",
    version="0.1.0-module3-skeleton",
    lifespan=lifespan,
)

register_middleware(app, settings)
register_exception_handlers(app)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(user.router)
app.include_router(my_restaurant.router)
app.include_router(restaurant.router)
app.include_router(order.router)
app.include_router(analytics.router)
