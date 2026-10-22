# tests/conftest.py — pytest loads this BEFORE any test module.
#
# app/db.py reads DATABASE_URL at import time and crashes if it is missing.
# The CI runner has no database, so we give it a harmless dummy value and
# replace the repository with an in-memory fake (tests/fake_repo.py).
import os

os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost/none")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.routes import get_repo  # noqa: E402
from tests.fake_repo import FakeWordRepository  # noqa: E402


@pytest.fixture
def repo():
    return FakeWordRepository()


@pytest.fixture
def client(repo):
    app.dependency_overrides[get_repo] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()
