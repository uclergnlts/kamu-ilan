from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import UserFilter


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_daily_job_requires_cron_secret() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/jobs/daily")
    assert response.status_code == 401


def test_unsubscribe_form_disables_matching_email() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    filters = UserFilter(
        email="user@example.com",
        cities=[],
        include_keywords=[],
        exclude_keywords=[],
        education_levels=[],
        kpss_types=[],
        institutions=[],
    )
    session.add(filters)
    session.commit()

    def override_db():
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            form = client.get("/unsubscribe")
            response = client.post(
                "/unsubscribe",
                content="email=USER%40example.com",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert form.status_code == 200
        assert "Abonelikten çık" in form.text
        assert response.status_code == 200
        assert "Talebiniz alındı" in response.text
        session.refresh(filters)
        assert filters.subscribed is False
    finally:
        app.dependency_overrides.clear()
        session.close()
