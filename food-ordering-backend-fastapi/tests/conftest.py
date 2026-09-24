from collections import defaultdict
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

from app.config import get_settings
from app.db.mongodb import mongodb
from app.main import app


@pytest.fixture()
def client() -> TestClient:
    """
    No real MongoDB is required to test this skeleton's structure: the
    stub service methods raise NotImplementedFeatureError before ever
    touching a repository's collection handle. We only need
    `mongodb.database` to be non-None so dependency injection can construct
    repositories at all — a defaultdict stands in for "some database",
    never queried.
    """
    mongodb.database = defaultdict(lambda: None)
    with TestClient(app) as test_client:
        yield test_client
    mongodb.database = None


@pytest.fixture()
def api_client(monkeypatch) -> TestClient:
    """
    Real end-to-end client for the API/integration test suite
    (docs/testing/api-integration-test-plan.md). Unlike `client` above
    (a structure-only smoke-test fixture for the 501-stub routes), this
    wires a genuine in-memory mongomock-motor database into the app's DI
    chain so the 3 real Order Management endpoints can be exercised with
    actual reads/writes.

    `mongodb.connect` is monkeypatched to a no-op: this project's `.env`
    points at a live MongoDB Atlas cluster with real credentials. Tests
    must never attempt that connection — it is network-dependent and would
    risk touching non-test data. Swapping `mongodb.database` to an
    in-memory mongomock database instead keeps every test hermetic, with
    no real network access.
    """
    monkeypatch.setattr(mongodb, "connect", AsyncMock())
    with TestClient(app) as test_client:
        mongodb.database = AsyncMongoMockClient().get_database("test_food_ordering_api")
        yield test_client
    mongodb.database = None


@pytest.fixture()
def api_client_no_raise(monkeypatch) -> TestClient:
    """
    Same wiring as `api_client`, but with `raise_server_exceptions=False`.

    Starlette's TestClient re-raises an exception in the TEST PROCESS
    (for debugger-friendly tracebacks) whenever it escapes all the way to
    FastAPI's generic `@app.exception_handler(Exception)` catch-all —
    even though that handler DID run and DID produce a normal 500 JSON
    response for what a real client over HTTP would actually receive.
    This fixture is for the small set of security tests that deliberately
    trigger an unhandled/unexpected exception (e.g. an unhashable status
    value) and need to assert on the actual client-facing response body,
    not pytest's re-raised traceback.
    """
    monkeypatch.setattr(mongodb, "connect", AsyncMock())
    with TestClient(app, raise_server_exceptions=False) as test_client:
        mongodb.database = AsyncMongoMockClient().get_database("test_food_ordering_security")
        yield test_client
    mongodb.database = None


@pytest.fixture()
def make_token():
    """
    Factory fixture: signs a JWT using the exact same secret-resolution
    order and algorithm as app.api.deps.get_current_user_id, so tests
    exercise the real verification path rather than a stand-in.
    """

    def _make_token(
        user_id: str | None = "000000000000000000000001",
        secret: str | None = None,
        expired: bool = False,
        omit_user_id: bool = False,
    ) -> str:
        resolved_secret = (
            secret if secret is not None else (get_settings().JWT_SECRET_KEY or "fallback_secret_key_12345")
        )
        now = datetime.now(timezone.utc)
        payload: dict = {"exp": now - timedelta(days=1) if expired else now + timedelta(days=1)}
        if not omit_user_id:
            payload["userId"] = user_id
        return jwt.encode(payload, resolved_secret, algorithm="HS256")

    return _make_token
