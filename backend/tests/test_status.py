from fastapi.testclient import TestClient


def test_status_endpoint(client: TestClient) -> None:
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "redis" in data
    assert "openai" in data
    assert "doc_repo_enabled" in data
