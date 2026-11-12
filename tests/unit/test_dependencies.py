import fastapi.testclient
import pytest

import application.inventory
import main
import presentation.deps


class EmptyInventory:
    def read(self) -> application.inventory.Inventory:
        return application.inventory.Inventory(
            balances=[],
            history=[],
            warehouses=[],
            products=[],
            transfers=[],
            fbs_reserved=[],
            fbs_in_transit=[],
            fbo_in_transit=[],
            fbo_received=[],
        )


def test_inventory_route_can_override_reader_without_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Проверяет, что страница остатков использует подставленный порт без подключения к БД."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://unused:unused@127.0.0.1:1/unused")
    app = main.create_app()
    app.dependency_overrides[presentation.deps.inventory_reader] = EmptyInventory

    with fastapi.testclient.TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Пока нет остатков" in response.text
