import psycopg.errors
import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.exc

import application.warehouses
import domain.warehouses

_STATEMENTS = {
    "create": "INSERT INTO warehouses (name) VALUES (:name) RETURNING id",
    "rename": """
        UPDATE warehouses SET name = :name WHERE id = :id
        RETURNING id
    """,
    "archive": """
        UPDATE warehouses SET archived_at = now() WHERE id = :id
        RETURNING id
    """,
}


class PostgresWarehouseWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def find(self, warehouse_id: int | None) -> domain.warehouses.Warehouse | None:
        query = sqlalchemy.text(
            "SELECT id, name, archived_at IS NOT NULL FROM warehouses WHERE id = :id"
        )
        row = self.connection.execute(query, {"id": warehouse_id}).one_or_none()
        return domain.warehouses.Warehouse(*row) if row is not None else None

    def save_change(self, change: application.warehouses.Change) -> int:
        try:
            result = self.connection.execute(
                sqlalchemy.text(_STATEMENTS[change.action]),
                {"id": change.warehouse_id, "name": change.name},
            ).scalar_one()
        except sqlalchemy.exc.IntegrityError as error:
            if isinstance(error.orig, psycopg.errors.UniqueViolation):
                raise domain.warehouses.NameConflict("Warehouse name is already in use") from error
            raise
        return int(result)

    def record_change(
        self, action: str, warehouse_id: int, old_name: str | None, new_name: str | None
    ) -> None:
        self.connection.execute(
            sqlalchemy.text("""
            INSERT INTO audit_entries
                (action, source_warehouse_id, destination_warehouse_id, source_name, destination_name)
            VALUES (:action, :source_id, :destination_id, :source, :destination)
        """),
            {
                "action": action,
                "source_id": warehouse_id if old_name is not None else None,
                "destination_id": warehouse_id if new_name is not None else None,
                "source": old_name,
                "destination": new_name,
            },
        )
