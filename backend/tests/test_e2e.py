def test_status_endpoint(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "online"
    assert "version" in d


def test_batch_endpoint(client):
    r = client.post("/api/batch", json={"steps": [{"type": "wait", "wait_seconds": 0.01}]})
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "ok"


def test_rag_threshold(client):
    r = client.get("/api/rag/threshold")
    assert r.status_code == 200
    old = r.json()["threshold"]
    r2 = client.put("/api/rag/threshold", json={"threshold": old + 0.5})
    assert r2.status_code == 200
    r3 = client.get("/api/rag/threshold")
    assert r3.json()["threshold"] == old + 0.5


def test_voice_settings(client):
    r = client.get("/api/voice/settings")
    assert r.status_code == 200
    assert "stt_model" in r.json()


def test_chat_crud(client):
    # create
    r = client.post("/api/chats", json={"title": "test e2e"})
    assert r.status_code == 200
    sid = r.json()["session"]["id"]
    assert sid > 0

    # list
    r2 = client.get("/api/chats")
    assert r2.status_code == 200
    assert "sessions" in r2.json()

    # rename
    r3 = client.patch(f"/api/chats/{sid}", json={"title": "renamed"})
    assert r3.status_code == 200

    # delete
    r4 = client.delete(f"/api/chats/{sid}")
    assert r4.status_code == 200
