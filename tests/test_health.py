from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)


def test_root():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["name"] == "GenAI Enterprise Lab API"


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    payload = response.json()

    assert payload["api"] == "healthy"
    assert payload["database"] == "healthy"
    assert payload["postgresql"].startswith("18.")
    assert payload["pgvector"] == "0.8.6"
