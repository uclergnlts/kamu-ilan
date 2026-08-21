from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_daily_job_requires_cron_secret() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs/daily")
    assert response.status_code == 401
