import collections.abc
import concurrent.futures

import fastapi.testclient
import sqlalchemy as sa

type Key = collections.abc.Callable[[], dict[str, str]]


def test_concurrent_fbs_reservations_and_repeated_dispatch(
    api: fastapi.testclient.TestClient,
    postgres: sa.engine.Engine,
    warehouse_id: int,
    product_id: int,
    command_key: Key,
) -> None:
    """Проверяет защиту от двойного резерва и повторного списания после архивации склада."""
    stock = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 5}
    assert api.post("/receipts", json=stock, headers=command_key()).status_code == 201

    def reserve(key: str) -> int:
        data = {**stock, "quantity": 4, "key": key}
        return api.post("/inventory/fbs-reserve", data=data, follow_redirects=False).status_code

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        keys = [command_key()["Idempotency-Key"] for _ in range(2)]
        assert sorted(pool.map(reserve, keys)) == [303, 409]
    assert "В резерве" in api.get("/inventory/fbs").text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand, reserved FROM stock_balances").one() == (
            5,
            4,
        )
        operation_id = connection.exec_driver_sql("SELECT id FROM stock_operations").scalar_one()
    assert api.delete(f"/warehouses/{warehouse_id}", headers=command_key()).status_code == 200
    for _ in range(2):
        data = {"operation_id": operation_id, "key": command_key()["Idempotency-Key"]}
        assert (
            api.post("/inventory/fbs-dispatch", data=data, follow_redirects=False).status_code
            == 303
        )
    assert "В пути к клиенту" in api.get("/inventory/fbs").text
    data["key"] = command_key()["Idempotency-Key"]
    assert api.post("/inventory/fbs-cancel", data=data).status_code == 409
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand, reserved FROM stock_balances").one() == (
            1,
            0,
        )


def test_cancelling_fbs_reservation_releases_stock(
    api: fastapi.testclient.TestClient,
    postgres: sa.engine.Engine,
    warehouse_id: int,
    product_id: int,
    command_key: Key,
) -> None:
    """Проверяет, что отмена снимает резерв на архивном складе и сохраняет остаток."""
    stock = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 2}
    assert api.post("/receipts", json=stock, headers=command_key()).status_code == 201
    request = {**stock, "key": command_key()["Idempotency-Key"]}
    assert (
        api.post("/inventory/fbs-reserve", data=request, follow_redirects=False).status_code == 303
    )
    with postgres.connect() as connection:
        operation_id = connection.exec_driver_sql("SELECT id FROM stock_operations").scalar_one()
    assert api.delete(f"/warehouses/{warehouse_id}", headers=command_key()).status_code == 200
    data = {"operation_id": operation_id, "key": command_key()["Idempotency-Key"]}
    assert api.post("/inventory/fbs-cancel", data=data, follow_redirects=False).status_code == 303
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand, reserved FROM stock_balances").one() == (
            2,
            0,
        )
    data["operation_id"] = 999
    data["key"] = command_key()["Idempotency-Key"]
    assert api.post("/inventory/fbs-dispatch", data=data).status_code == 404
    request["key"] = command_key()["Idempotency-Key"]
    assert api.post("/inventory/fbs-reserve", data=request).status_code == 404
