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
