from concurrent.futures import ThreadPoolExecutor, as_completed


def _check(client, path):
    r = client.get(path)
    return r.status_code == 200


def _check_plugins(client):
    r = client.get("/api/plugins")
    return r.status_code == 200


def test_health_sequential(client):
    """10 richieste sequenziali a /api/health."""
    for _ in range(10):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_plugins_sequential(client):
    """10 richieste sequenziali a /api/plugins."""
    for _ in range(10):
        r = client.get("/api/plugins")
        assert r.status_code == 200
        assert len(r.json()["plugins"]) >= 2


def test_metrics_sequential(client):
    """10 richieste sequenziali a /metrics."""
    for _ in range(10):
        r = client.get("/metrics")
        assert r.status_code == 200


def test_mixed_sequential(client):
    """Mix di richieste a diversi endpoint."""
    for _ in range(5):
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/plugins").status_code == 200
        assert client.get("/metrics").status_code == 200
