import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    r = client.post("/api/auth/register", json={"username": "test", "password": "test123"})
    if r.status_code == 200:
        return r.json().get("access_token")
    r = client.post("/api/auth/login", json={"username": "test", "password": "test123"})
    return r.json().get("access_token")


@pytest.fixture(autouse=True)
def _anyio_backend():
    return "asyncio"
