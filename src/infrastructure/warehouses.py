import collections.abc
import uuid

import psycopg.errors
import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.exc

import application.warehouses
import domain.warehouses

_STATEMENTS = {
    "create": "INSERT INTO warehouses (name) VALUES (:name) RETURNING id, NULL, name",
    "rename": """
        UPDATE warehouses SET name = :name WHERE id = :id AND archived_at IS NULL
        RETURNING id, old.name, new.name
    """,
    "archive": """
        UPDATE warehouses SET archived_at = now() WHERE id = :id AND archived_at IS NULL
        RETURNING id, name, NULL
    """,
}


class PostgresWarehouseWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def apply(self, change: application.warehouses.Change) -> int:
        try:
            row = self.connection.execute(
                sqlalchemy.text(_STATEMENTS[change.action]),
                {"id": change.warehouse_id, "name": change.name},
            ).one_or_none()
        except sqlalchemy.exc.IntegrityError as error:
            if isinstance(error.orig, psycopg.errors.UniqueViolation):
                raise domain.warehouses.NameConflict("Warehouse name is already in use") from error
            raise
        if row is None:
            raise domain.warehouses.WarehouseNotFound("Active warehouse not found")

        warehouse_id, old_name, new_name = row
        self.connection.execute(
            sqlalchemy.text("""
            INSERT INTO audit_entries
                (action, source_warehouse_id, destination_warehouse_id, source_name, destination_name)
            VALUES (:action, :source_id, :destination_id, :source, :destination)
        """),
            {
                "action": f"warehouse.{change.action}",
                "source_id": warehouse_id if old_name is not None else None,
                "destination_id": warehouse_id if new_name is not None else None,
                "source": old_name,
                "destination": new_name,
            },
        )
        return int(warehouse_id)


class PostgresTransaction:
    def __init__(self, engine: sqlalchemy.engine.Engine) -> None:
        self.engine = engine

    def run(
        self,
        key: uuid.UUID,
        command: str,
        fingerprint: str,
        write: collections.abc.Callable[[application.warehouses.WarehouseWriter], int],
    ) -> int:
        with self.engine.begin() as connection:
            connection.execute(
                sqlalchemy.text("SELECT id FROM stores WHERE id = 1 FOR UPDATE")
            ).one()
            receipt = connection.execute(
                sqlalchemy.text("""
                SELECT command, fingerprint, result FROM command_receipts
                WHERE idempotency_key = :key
            """),
                {"key": key},
            ).one_or_none()
            if receipt is not None:
                if (receipt.command, receipt.fingerprint) != (command, fingerprint):
                    raise application.warehouses.KeyConflict("Idempotency key is already in use")
                return int(receipt.result)
            result = write(PostgresWarehouseWriter(connection))
            connection.execute(
                sqlalchemy.text("""
                INSERT INTO command_receipts (idempotency_key, command, fingerprint, result)
                VALUES (:key, :command, :fingerprint, to_jsonb(CAST(:result AS bigint)))
            """),
                {"key": key, "command": command, "fingerprint": fingerprint, "result": result},
            )
            return result
