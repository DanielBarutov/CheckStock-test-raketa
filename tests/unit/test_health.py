import pathlib

import fastapi.testclient
import pytest

import main


@pytest.mark.parametrize(
    ("database_file", "status", "body"),
    [
        ("db.sqlite", 200, {"status": "ok"}),
        ("missing/db.sqlite", 503, {"detail": "Database unavailable"}),
    ],
)
def test_health(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    database_file: str,
    status: int,
    body: dict[str, str],
) -> None:
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / database_file}")
    with fastapi.testclient.TestClient(main.create_app()) as client:
        response = client.get("/health")
    assert (response.status_code, response.json()) == (status, body)
