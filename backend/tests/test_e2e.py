def test_status_endpoint(client):
    r = client.get("/api/status")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "online"
    assert "version" in d


def test_batch_endpoint(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = client.post("/api/batch", json={"steps": [{"type": "wait", "wait_seconds": 0.01}]}, headers=headers)
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) == 1
    assert results[0]["status"] == "ok"


def test_rag_threshold(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = client.get("/api/rag/threshold", headers=headers)
    assert r.status_code == 200
    old = r.json()["threshold"]
    r2 = client.put("/api/rag/threshold", json={"threshold": old + 0.5}, headers=headers)
    assert r2.status_code == 200
    r3 = client.get("/api/rag/threshold", headers=headers)
    assert r3.json()["threshold"] == old + 0.5


def test_voice_settings(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = client.get("/api/voice/settings", headers=headers)
    assert r.status_code == 200
    assert "stt_model" in r.json()


def test_chat_crud(client, auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    # create
    r = client.post("/api/chats", json={"title": "test e2e"}, headers=headers)
    assert r.status_code == 200
    sid = r.json()["session"]["id"]
    assert sid > 0

    # list
    r2 = client.get("/api/chats", headers=headers)
    assert r2.status_code == 200
    assert "sessions" in r2.json()

    # rename
    r3 = client.patch(f"/api/chats/{sid}", json={"title": "renamed"}, headers=headers)
    assert r3.status_code == 200

    # delete
    r4 = client.delete(f"/api/chats/{sid}", headers=headers)
    assert r4.status_code == 200
