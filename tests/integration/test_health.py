import fastapi.testclient
import pytest
import sqlalchemy as sa

import main


@pytest.mark.parametrize(
    ("available", "status"), [(True, 200), (False, 503)], ids=["ready", "unavailable"]
)
def test_health_reports_database_readiness(
    postgres: sa.engine.Engine,
    monkeypatch: pytest.MonkeyPatch,
    available: bool,
    status: int,
) -> None:
    """Проверяет, что статус готовности отражает возможность подключения к PostgreSQL."""
    if not available:
        url = postgres.url.set(database="missing_database")
        monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))

    with fastapi.testclient.TestClient(main.create_app()) as client:
        response = client.get("/health")

    assert response.status_code == status
    if available:
        assert response.json()["status"] == "ok"
