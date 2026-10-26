# tests/conftest.py — pytest loads this BEFORE any test module.
#
# app/db.py reads DATABASE_URL at import time and crashes if it is missing.
# The CI runner has no database, so we give it a harmless dummy value and
# replace the repositories with in-memory fakes (tests/fake_repo.py).
# The real login code (app/auth.py) still runs: only the storage is fake.
import os

os.environ.setdefault("DATABASE_URL", "postgresql://unused@localhost/none")
os.environ.setdefault("APP_ENV", "test")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.auth import CurrentUser, get_conn, get_users  # noqa: E402
from app.main import app  # noqa: E402
from app.routes import get_repo  # noqa: E402
from tests.fake_repo import FakeStore, FakeUserRepository, FakeWordRepository  # noqa: E402

PASSWORD = "correct-horse-1"


@pytest.fixture
def repo():
    # Named "repo" for the word tests: it holds every user's words and reviews.
    return FakeStore()


@pytest.fixture
def users(repo):
    return FakeUserRepository(repo)


@pytest.fixture
def anon(repo, users):
    """A browser that has not logged in yet."""

    def fake_get_repo(user: CurrentUser):
        return FakeWordRepository(repo, user["id"])

    app.dependency_overrides[get_conn] = lambda: None
    app.dependency_overrides[get_users] = lambda: users
    app.dependency_overrides[get_repo] = fake_get_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def register(client, email="an@example.com", name="An"):
    r = client.post(
        "/api/auth/register", json={"email": email, "display_name": name, "password": PASSWORD}
    )
    assert r.status_code == 201, r.text
    return r


@pytest.fixture
def client(anon):
    """A browser logged in as a freshly registered user."""
    register(anon)
    return anon
