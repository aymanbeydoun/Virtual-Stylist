from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_openapi() -> None:
    with TestClient(app) as client:
        resp = client.get("/api/v1/openapi.json")
        assert resp.status_code == 200
        spec = resp.json()
        paths = spec["paths"]
        assert "/api/v1/wardrobe/items" in paths
        assert "/api/v1/stylist/generate" in paths
        assert "/api/v1/family/members" in paths
