from concurrent.futures import ThreadPoolExecutor, as_completed


def _check(client, path, headers=None):
    r = client.get(path, headers=headers)
    return r.status_code == 200


def _check_plugins(client, headers=None):
    r = client.get("/api/plugins", headers=headers)
    return r.status_code == 200


def test_health_sequential(client):
    """10 richieste sequenziali a /api/health."""
    for _ in range(10):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_plugins_sequential(client, auth_token):
    """10 richieste sequenziali a /api/plugins."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    for _ in range(10):
        r = client.get("/api/plugins", headers=headers)
        assert r.status_code == 200
        assert len(r.json()["plugins"]) >= 2


def test_metrics_sequential(client):
    """10 richieste sequenziali a /metrics."""
    for _ in range(10):
        r = client.get("/metrics")
        assert r.status_code == 200


def test_mixed_sequential(client, auth_token):
    """Mix di richieste a diversi endpoint."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    for _ in range(5):
        assert client.get("/api/health").status_code == 200
        assert client.get("/api/plugins", headers=headers).status_code == 200
        assert client.get("/metrics").status_code == 200
