def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready(client):
    r = client.get("/api/ready")
    assert r.status_code == 200
    assert r.json()["status"] in ("ok", "degraded")


def test_plugins(client):
    r = client.get("/api/plugins")
    assert r.status_code == 200
    data = r.json()
    assert "plugins" in data
    names = [p["name"] for p in data["plugins"]]
    assert "hello" in names
    assert "echo" in names


def test_plugin_exec(client):
    r = client.post("/api/plugins/echo/exec", json={"action": "execute", "params": {"message": "test"}})
    assert r.status_code == 200
    data = r.json()
    assert data["plugin"] == "echo"
    assert "Echo: test" in data["result"]["response"]


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "python_info" in r.text


def test_cors(client):
    r = client.options("/api/health", headers={"Origin": "http://localhost"})
    headers = {k.lower(): v for k, v in r.headers.items()}
    assert "access-control-allow-origin" in headers
