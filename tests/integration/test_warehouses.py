import collections.abc

import fastapi.testclient
import pytest
import sqlalchemy as sa

type CommandKey = collections.abc.Callable[[], dict[str, str]]


def test_creation_replays_normalized_name_without_creating_another_warehouse(
    api: fastapi.testclient.TestClient, command_key: CommandKey, postgres: sa.engine.Engine
) -> None:
    """Проверяет, что повтор создания с тем же ключом возвращает тот же склад."""
    key = command_key()
    created = api.post("/warehouses", json={"name": " Север "}, headers=key)
    replay = api.post("/warehouses", json={"name": "Север"}, headers=key)

    assert created.status_code == replay.status_code == 201
    assert replay.json()["id"] == created.json()["id"]
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT name FROM warehouses").scalar_one() == "Север"
        assert connection.exec_driver_sql("SELECT count(*) FROM audit_entries").scalar_one() == 1


@pytest.mark.parametrize(
    ("name", "reuse_key", "status"),
    [("Юг", True, 409), ("север", False, 409), (" ", False, 422)],
    ids=["changed-payload", "duplicate-name", "blank-name"],
)
def test_rejected_creation_preserves_catalog(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    postgres: sa.engine.Engine,
    name: str,
    reuse_key: bool,
    status: int,
) -> None:
    """Проверяет, что конфликт ключа, дубликат имени или пустое имя не меняют справочник."""
    key = command_key()
    assert api.post("/warehouses", json={"name": "Север"}, headers=key).status_code == 201

    response = api.post(
        "/warehouses", json={"name": name}, headers=key if reuse_key else command_key()
    )

    assert response.status_code == status
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT name FROM warehouses").scalar_one() == "Север"


def test_rename_preserves_warehouse_id_and_previous_name_in_history(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    warehouse_id: int,
    postgres: sa.engine.Engine,
) -> None:
    """Проверяет, что переименование сохраняет ID и прежнее название в журнале."""
    response = api.patch(
        f"/warehouses/{warehouse_id}", json={"name": "Новый Север"}, headers=command_key()
    )

    assert response.status_code == 200
    assert response.json()["id"] == warehouse_id
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT id, name FROM warehouses").one() == (
            warehouse_id,
            "Новый Север",
        )
        assert connection.exec_driver_sql("""
            SELECT source_name, destination_name FROM audit_entries ORDER BY id
        """).all() == [(None, "Север"), ("Север", "Новый Север")]


def test_archiving_preserves_balance_and_replay_does_not_duplicate_history(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    warehouse_id: int,
    product_id: int,
    postgres: sa.engine.Engine,
) -> None:
    """Проверяет, что архивирование сохраняет остаток и повтор не добавляет запись в журнал."""
    with postgres.begin() as connection:
        connection.exec_driver_sql(
            "INSERT INTO stock_balances VALUES (%s, %s, 10, 2)", (warehouse_id, product_id)
        )
    key = command_key()
    path = f"/warehouses/{warehouse_id}"

    assert api.delete(path, headers=key).status_code == 200
    assert api.delete(path, headers=key).json()["id"] == warehouse_id
    assert api.patch(path, json={"name": "Юг"}, headers=command_key()).status_code == 404
    with postgres.connect() as connection:
        assert (
            connection.exec_driver_sql("SELECT archived_at FROM warehouses").scalar_one()
            is not None
        )
        assert connection.exec_driver_sql("SELECT on_hand, reserved FROM stock_balances").one() == (
            10,
            2,
        )
        assert (
            connection.exec_driver_sql("""
            SELECT source_name FROM audit_entries WHERE action = 'warehouse.archive'
        """).scalar_one()
            == "Север"
        )


def test_archive_can_be_retried_after_history_write_fails(
    api: fastapi.testclient.TestClient,
    command_key: CommandKey,
    warehouse_id: int,
    postgres: sa.engine.Engine,
) -> None:
    """Проверяет, что сбой записи истории отменяет архивирование и позволяет повторить запрос."""
    with postgres.begin() as connection:
        connection.exec_driver_sql("""
            ALTER TABLE audit_entries ADD CONSTRAINT reject_archive CHECK (action <> 'warehouse.archive')
        """)
    key = command_key()
    path = f"/warehouses/{warehouse_id}"

    assert api.delete(path, headers=key).status_code == 500
    with postgres.begin() as connection:
        assert connection.exec_driver_sql("SELECT archived_at FROM warehouses").scalar_one() is None
        connection.exec_driver_sql("ALTER TABLE audit_entries DROP CONSTRAINT reject_archive")
    assert api.delete(path, headers=key).status_code == 200
