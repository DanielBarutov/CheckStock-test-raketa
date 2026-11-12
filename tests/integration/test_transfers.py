import collections.abc
import concurrent.futures
import threading

import fastapi.testclient
import pytest
import sqlalchemy.engine

type Key = collections.abc.Callable[[], dict[str, str]]


@pytest.fixture
def transfer_data(
    api: fastapi.testclient.TestClient,
    warehouse_id: int,
    product_id: int,
    command_key: Key,
) -> dict[str, int]:
    target = api.post("/warehouses", headers=command_key(), json={"name": "Юг"})
    assert target.status_code == 201
    receipt = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 5}
    assert api.post("/receipts", headers=command_key(), json=receipt).status_code == 201
    return {**receipt, "destination_id": int(target.json()["id"]), "quantity": 3}


def test_transfer_accepts_once_even_concurrently_after_destination_is_archived(
    api: fastapi.testclient.TestClient,
    postgres: sqlalchemy.engine.Engine,
    transfer_data: dict[str, int],
    command_key: Key,
) -> None:
    """Проверяет однократную приёмку параллельными запросами даже после архивации получателя."""
    sent = api.post(
        "/inventory/transfer-send", data={**transfer_data, "key": command_key()["Idempotency-Key"]}
    )
    assert 'action="/inventory/transfer-accept"' in sent.text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 2
        operation_id = connection.exec_driver_sql("SELECT id FROM stock_operations").scalar_one()
    destination = transfer_data["destination_id"]
    assert api.delete(f"/warehouses/{destination}", headers=command_key()).status_code == 200
    barrier = threading.Barrier(2)

    def accept(key: str) -> int:
        barrier.wait(timeout=5)
        data = {"key": key, "operation_id": operation_id}
        return api.post("/inventory/transfer-accept", data=data, follow_redirects=False).status_code

    keys = [command_key()["Idempotency-Key"] for _ in range(2)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(accept, keys)) == [303, 303]
    assert 'action="/inventory/transfer-accept"' not in api.get("/").text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("""
            SELECT on_hand FROM stock_balances ORDER BY warehouse_id
        """).scalars().all() == [2, 3]
        assert (
            connection.exec_driver_sql("""
            SELECT count(*) FROM audit_entries WHERE action = 'transfer.accept'
        """).scalar_one()
            == 1
        )


def test_transfer_shortage_shows_other_warehouse_stock(
    api: fastapi.testclient.TestClient,
    transfer_data: dict[str, int],
    command_key: Key,
) -> None:
    """Проверяет подсказку с доступным остатком на другом складе при локальной нехватке."""
    data = {
        **transfer_data,
        "warehouse_id": transfer_data["destination_id"],
        "destination_id": transfer_data["warehouse_id"],
        "key": command_key()["Idempotency-Key"],
    }
    response = api.post("/inventory/transfer-send", data=data)
    assert response.status_code == 409
    assert "доступно: 0" in response.text and "Север: 5" in response.text
    assert 'action="/inventory/transfer-accept"' not in response.text


def test_transfer_rejects_same_or_missing_warehouse_and_unknown_operation(
    api: fastapi.testclient.TestClient,
    transfer_data: dict[str, int],
    command_key: Key,
) -> None:
    """Проверяет отказ при недопустимом маршруте и приёмке неизвестной отправки."""
    data = {**transfer_data, "key": command_key()["Idempotency-Key"]}
    same = api.post(
        "/inventory/transfer-send", data={**data, "destination_id": data["warehouse_id"]}
    )
    missing = api.post("/inventory/transfer-send", data={**data, "destination_id": 999})
    unknown = api.post("/inventory/transfer-accept", data={**data, "operation_id": 999})
    assert (same.status_code, missing.status_code, unknown.status_code) == (422, 404, 404)
