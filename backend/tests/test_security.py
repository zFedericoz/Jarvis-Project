import uuid


def _unique():
    return f"sec{uuid.uuid4().hex[:8]}"


def test_sql_injection_auth(client):
    """Tentativo di SQL injection nel login."""
    r = client.post("/api/auth/login", json={"username": "' OR 1=1--", "password": "' OR 1=1--"})
    assert r.status_code == 401


def test_path_traversal_upload(client):
    """Tentativo di path traversal nel filename."""
    r = client.post("/api/upload", files={"file": ("../../etc/passwd", b"test", "text/plain")})
    assert r.status_code in (200, 413, 400)
    if r.status_code == 200:
        fname = r.json()["filename"]
        assert ".." not in fname
        assert fname != "passwd"


def test_invalid_json(client):
    """Payload malformato."""
    r = client.post("/api/auth/login", data="not-json-at-all", headers={"Content-Type": "application/json"})
    assert r.status_code in (400, 422)


def test_auth_missing_fields(client):
    """Campi obbligatori mancanti."""
    r = client.post("/api/auth/register", json={"username": _unique()})
    assert r.status_code in (400, 422)
    r2 = client.post("/api/auth/login", json={"password": "x"})
    assert r2.status_code in (400, 422)


def test_auth_empty_password(client):
    """Password vuota."""
    r = client.post("/api/auth/register", json={"username": _unique(), "password": ""})
    assert r.status_code in (200, 400, 422)


def test_nonexistent_route(client):
    """Route inesistente."""
    r = client.get("/api/nonexistent12345")
    assert r.status_code == 404
