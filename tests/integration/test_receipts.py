import collections.abc
import io
import pathlib

import fastapi.testclient
import pytest
import sqlalchemy.engine

import infrastructure.seed

type CommandKey = collections.abc.Callable[[], dict[str, str]]


@pytest.fixture
def receipt(warehouse_id: int, product_id: int) -> dict[str, int]:
    return {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 2}


def test_demo_can_be_loaded_twice_without_duplicating_stock(
    postgres: sqlalchemy.engine.Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Проверяет, что повторная загрузка демо сохраняет исходные остатки и четыре прихода."""
    data = pathlib.Path(__file__).parents[1] / "fixtures" / "demo_inventory.json"
    for _ in range(2):
        monkeypatch.setattr("sys.stdin", io.StringIO(data.read_text(encoding="utf-8")))
        infrastructure.seed.main()

    with postgres.connect() as connection:
        balances = connection.exec_driver_sql("""
            SELECT p.sku, w.name, b.on_hand FROM stock_balances b
            JOIN warehouses w ON w.id = b.warehouse_id JOIN products p ON p.id = b.product_id
        """).all()
        assert set(balances) == {
            ("SKU-101", "Север", 10),
            ("SKU-101", "Юг", 6),
            ("SKU-102", "Север", 5),
            ("SKU-103", "Юг", 4),
        }
        audit = "SELECT count(*) FROM audit_entries WHERE action = 'stock.receipt'"
        assert connection.exec_driver_sql(audit).scalar_one() == 4


def test_new_receipt_increases_stock_once_even_if_retried(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    receipt: dict[str, int],
    postgres: sqlalchemy.engine.Engine,
) -> None:
    """Проверяет, что два разных прихода складываются, а повтор второго не увеличивает остаток."""
    assert api.post("/receipts", json=receipt, headers=command_key()).status_code == 201
    key = command_key()
    created = api.post("/receipts", json=receipt, headers=key)
    replay = api.post("/receipts", json=receipt, headers=key)
    assert created.status_code == replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    changed = api.post("/receipts", json={**receipt, "quantity": 3}, headers=key)
    assert changed.status_code == 409

    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand, reserved FROM stock_balances").one() == (
            4,
            0,
        )
        audit = "SELECT quantity FROM audit_entries WHERE action = 'stock.receipt' ORDER BY id"
        assert connection.exec_driver_sql(audit).scalars().all() == [2, 2]


@pytest.mark.parametrize(
    "quantity",
    [0, -1, 1.5, True, 2**31],
    ids=["zero", "negative", "fraction", "boolean", "too-large"],
)
def test_receipt_rejects_invalid_quantity(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    receipt: dict[str, int],
    postgres: sqlalchemy.engine.Engine,
    quantity: float | bool,
) -> None:
    """Проверяет, что недопустимое количество отклоняется без создания остатка."""
    response = api.post("/receipts", json={**receipt, "quantity": quantity}, headers=command_key())

    assert response.status_code == 422
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").first() is None


def test_receipt_rejects_archived_warehouse(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    receipt: dict[str, int],
    postgres: sqlalchemy.engine.Engine,
) -> None:
    """Проверяет, что архивный склад отклоняет новый приход, сохраняя результат прежнего."""
    key = command_key()
    original = api.post("/receipts", json=receipt, headers=key)
    assert original.status_code == 201
    path = f"/warehouses/{receipt['warehouse_id']}"
    assert api.delete(path, headers=command_key()).status_code == 200

    assert api.post("/receipts", json=receipt, headers=command_key()).status_code == 404
    replay = api.post("/receipts", json=receipt, headers=key)
    assert replay.status_code == 201 and replay.json()["id"] == original.json()["id"]
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 2


def test_receipt_rejects_balance_overflow(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    receipt: dict[str, int],
    postgres: sqlalchemy.engine.Engine,
) -> None:
    """Проверяет, что приход сверх предельного остатка отклоняется и сохраняет прежнее число."""
    limit = 2**31 - 1
    full = api.post("/receipts", json={**receipt, "quantity": limit}, headers=command_key())
    assert full.status_code == 201

    assert api.post("/receipts", json=receipt, headers=command_key()).status_code == 409
    with postgres.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == limit
        )


def test_receipt_can_be_retried_after_history_write_fails(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    receipt: dict[str, int],
    postgres: sqlalchemy.engine.Engine,
) -> None:
    """Проверяет, что сбой журнала откатывает приход и тот же запрос можно провести повторно."""
    assert api.post("/receipts", json=receipt, headers=command_key()).status_code == 201
    with postgres.begin() as connection:
        connection.exec_driver_sql("""
            ALTER TABLE audit_entries ADD CONSTRAINT reject_receipt CHECK (quantity <> 3)
        """)
    key = command_key()
    body = {**receipt, "quantity": 3}
    stock = "SELECT on_hand FROM stock_balances"

    assert api.post("/receipts", json=body, headers=key).status_code == 500
    with postgres.begin() as connection:
        assert connection.exec_driver_sql(stock).scalar_one() == 2
        connection.exec_driver_sql("ALTER TABLE audit_entries DROP CONSTRAINT reject_receipt")
    assert api.post("/receipts", json=body, headers=key).status_code == 201
    with postgres.connect() as connection:
        assert connection.exec_driver_sql(stock).scalar_one() == 5
