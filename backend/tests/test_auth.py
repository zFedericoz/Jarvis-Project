import uuid


def _unique(prefix="u"):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def test_register(client):
    r = client.post("/api/auth/register", json={"username": _unique(), "password": "pass123"})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_register_duplicate(client):
    name = _unique("dup")
    r = client.post("/api/auth/register", json={"username": name, "password": "pass123"})
    assert r.status_code == 200
    r2 = client.post("/api/auth/register", json={"username": name, "password": "pass123"})
    assert r2.status_code == 409


def test_login(client):
    name = _unique("lg")
    client.post("/api/auth/register", json={"username": name, "password": "pass123"})
    r = client.post("/api/auth/login", json={"username": name, "password": "pass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_login_wrong_password(client):
    r = client.post("/api/auth/login", json={"username": "nonexistent", "password": "wrong"})
    assert r.status_code == 401
