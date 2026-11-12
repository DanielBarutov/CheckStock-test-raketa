import psycopg.errors
import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm

import application.warehouses
import domain.warehouses
import infrastructure.database.models as orm_models


class PostgresWarehouseWriter:
    def __init__(self, session: sqlalchemy.orm.Session) -> None:
        self.session = session

    def find(self, warehouse_id: int | None) -> domain.warehouses.Warehouse | None:
        if warehouse_id is None:
            return None
        row = self.session.get(orm_models.Warehouse, warehouse_id)
        return (
            domain.warehouses.Warehouse(row.id, row.name, row.archived_at is not None)
            if row
            else None
        )

    def save_change(self, change: application.warehouses.Change) -> int:
        if change.action == "create":
            warehouse = orm_models.Warehouse(name=change.name)
            self.session.add(warehouse)
        else:
            warehouse = self.session.get_one(orm_models.Warehouse, change.warehouse_id)
            if change.action == "rename":
                assert change.name is not None
                warehouse.name = change.name
            else:
                self.session.execute(
                    sqlalchemy.update(orm_models.Warehouse)
                    .where(orm_models.Warehouse.id == warehouse.id)
                    .values(archived_at=sqlalchemy.func.now())
                )
        try:
            self.session.flush()
        except sqlalchemy.exc.IntegrityError as error:
            if isinstance(error.orig, psycopg.errors.UniqueViolation):
                raise domain.warehouses.NameConflict("Warehouse name is already in use") from error
            raise
        return warehouse.id

    def record_change(
        self, action: str, warehouse_id: int, old_name: str | None, new_name: str | None
    ) -> None:
        self.session.add(
            orm_models.AuditEntry(
                action=action,
                source_warehouse_id=warehouse_id if old_name is not None else None,
                destination_warehouse_id=warehouse_id if new_name is not None else None,
                source_name=old_name,
                destination_name=new_name,
            )
        )
