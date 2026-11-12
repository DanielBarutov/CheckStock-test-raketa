import collections.abc

import fastapi.testclient
import sqlalchemy as sa

type Key = collections.abc.Callable[[], dict[str, str]]


def test_fbo_receipt_moves_shipment_out_of_transit_without_respending_stock(
    api: fastapi.testclient.TestClient,
    postgres: sa.engine.Engine,
    warehouse_id: int,
    product_id: int,
    command_key: Key,
) -> None:
    """Проверяет учёт FBO в пути и однократную приёмку без повторного списания со склада."""
    stock = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 5}
    assert api.post("/receipts", json=stock, headers=command_key()).status_code == 201
    data = {**stock, "quantity": 3, "key": command_key()["Idempotency-Key"]}
    sent = api.post("/inventory/fbo-dispatch", data=data)
    assert "В пути на маркетплейс" in sent.text
    assert 'action="/inventory/fbo-accept"' in sent.text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 2
        operation_id = connection.exec_driver_sql("SELECT id FROM stock_operations").scalar_one()

    for _ in range(2):
        confirmation = {"operation_id": operation_id, "key": command_key()["Idempotency-Key"]}
        accepted = api.post("/inventory/fbo-accept", data=confirmation)
        assert "Принято на маркетплейсе" in accepted.text
        assert 'action="/inventory/fbo-accept"' not in accepted.text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 2
        assert connection.exec_driver_sql("SELECT quantity FROM stock_operations").scalar_one() == 3
        assert (
            connection.exec_driver_sql("""
            SELECT count(*) FROM audit_entries WHERE action = 'fbo.accept'
        """).scalar_one()
            == 1
        )


def test_fbo_rejects_shortage_and_acceptance_of_unknown_shipment(
    api: fastapi.testclient.TestClient,
    warehouse_id: int,
    product_id: int,
    command_key: Key,
) -> None:
    """Проверяет отказ при нехватке товара и попытке принять неизвестную поставку."""
    key = command_key()["Idempotency-Key"]
    data = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 1, "key": key}

    assert api.post("/inventory/fbo-dispatch", data=data).status_code == 409
    assert (
        api.post("/inventory/fbo-accept", data={"operation_id": 999, "key": key}).status_code == 404
    )
