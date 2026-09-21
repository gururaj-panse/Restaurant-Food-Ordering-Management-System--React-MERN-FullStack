from collections import defaultdict

import pytest
from fastapi.testclient import TestClient

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
