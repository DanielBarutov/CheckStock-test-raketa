import collections.abc
import subprocess
import time
import uuid

import fastapi.testclient
import pytest
import sqlalchemy
import sqlalchemy.engine

import main


@pytest.fixture
def postgres(monkeypatch: pytest.MonkeyPatch) -> collections.abc.Iterator[sqlalchemy.engine.Engine]:
    run = ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::5432", "-e"]
    container = subprocess.check_output(
        [*run, "POSTGRES_PASSWORD=checkstock", "postgres:18"], text=True
    ).strip()
    try:
        port = ["docker", "port", container, "5432/tcp"]
        address = subprocess.check_output(port, text=True).strip()
        url = f"postgresql+psycopg://postgres:checkstock@{address}/postgres"
        monkeypatch.setenv("DATABASE_URL", url)
        ready = ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1"]
        for _ in range(30):
            if subprocess.run(ready, check=False, capture_output=True).returncode == 0:
                break
            time.sleep(0.5)
        subprocess.run(["alembic", "upgrade", "head"], check=True)
        engine = sqlalchemy.create_engine(url)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=True, capture_output=True)


def test_warehouse_lifecycle_and_idempotency(postgres: sqlalchemy.engine.Engine) -> None:
    def key() -> dict[str, str]:
        return {"Idempotency-Key": str(uuid.uuid4())}

    with fastapi.testclient.TestClient(main.create_app(), raise_server_exceptions=False) as client:
        original = key()
        created = client.post("/warehouses", json={"name": " Север "}, headers=original)
        assert created.status_code == 201, created.text
        warehouse_id = created.json()["id"]
        path = f"/warehouses/{warehouse_id}"
        replay = client.post("/warehouses", json={"name": "Север"}, headers=original)
        assert replay.status_code == 201 and replay.json() == created.json()
        assert client.post("/warehouses", json={"name": "Юг"}, headers=original).status_code == 409
        assert client.post("/warehouses", json={"name": "север"}, headers=key()).status_code == 409
        assert client.post("/warehouses", json={"name": " "}, headers=key()).status_code == 422
        missing = client.patch("/warehouses/999", json={"name": "Юг"}, headers=key())
        assert missing.status_code == 404

        with postgres.begin() as connection:
            connection.exec_driver_sql("INSERT INTO products (sku, name) VALUES ('SKU', 'Test')")
            insert_balance = sqlalchemy.text("INSERT INTO stock_balances VALUES (:id, 1, 10, 2)")
            connection.execute(insert_balance, {"id": warehouse_id})
            connection.exec_driver_sql("""
                ALTER TABLE audit_entries ADD CHECK (action <> 'warehouse.archive')
            """)
        renamed = client.patch(path, json={"name": "Новый Север"}, headers=key())
        assert renamed.status_code == 200 and renamed.json() == created.json()
        archive = key()
        assert client.delete(path, headers=archive).status_code == 500
        with postgres.begin() as connection:
            archived = connection.exec_driver_sql("SELECT archived_at FROM warehouses")
            assert archived.scalar_one() is None
            connection.exec_driver_sql(
                "ALTER TABLE audit_entries DROP CONSTRAINT audit_entries_action_check"
            )
        assert client.delete(path, headers=archive).json() == created.json()
        assert client.delete(path, headers=archive).json() == created.json()
        assert client.patch(path, json={"name": "Юг"}, headers=key()).status_code == 404

    with postgres.connect() as connection:
        archived = connection.exec_driver_sql("SELECT archived_at FROM warehouses")
        assert archived.scalar_one() is not None
        balance = connection.exec_driver_sql("SELECT * FROM stock_balances").one()
        assert balance == (warehouse_id, 1, 10, 2)
        assert connection.exec_driver_sql("""
            SELECT source_name, destination_name FROM audit_entries ORDER BY id
        """).all() == [(None, "Север"), ("Север", "Новый Север"), ("Новый Север", None)]
        assert connection.exec_driver_sql("SELECT count(*) FROM command_receipts").scalar_one() == 3
