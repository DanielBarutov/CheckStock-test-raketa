import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

import domain.movements
import domain.stock
import infrastructure.database.models as orm_models
import infrastructure.repositories.balances


class PostgresMovements(infrastructure.repositories.balances.PostgresBalances):
    def active_stock(self, product_id: int) -> dict[int, tuple[str, domain.stock.Balance]]:
        warehouse = orm_models.Warehouse
        balance = orm_models.StockBalance
        query = (
            sa.select(
                warehouse.id,
                warehouse.name,
                sa.func.coalesce(balance.on_hand, 0),
                sa.func.coalesce(balance.reserved, 0),
            )
            .select_from(warehouse)
            .join(orm_models.Product, orm_models.Product.id == product_id)
            .outerjoin(
                balance, (balance.product_id == product_id) & (balance.warehouse_id == warehouse.id)
            )
            .where(warehouse.archived_at.is_(None))
            .order_by(warehouse.name, warehouse.id)
        )
        return {
            identifier: (name, domain.stock.Balance(on_hand, reserved))
            for identifier, name, on_hand, reserved in self.session.execute(query)
        }

    def add_movement(self, movement: domain.movements.Movement) -> int:
        row = orm_models.StockOperation(
            kind=movement.kind.value,
            state=movement.state.value,
            product_id=movement.product_id,
            quantity=movement.quantity,
            source_warehouse_id=movement.source,
            destination_warehouse_id=movement.destination,
        )
        self.session.add(row)
        self.session.flush()
        return row.id

    def find_movement(
        self, kind: domain.movements.Kind, operation_id: int
    ) -> domain.movements.Movement | None:
        operation = orm_models.StockOperation
        query = sa.select(operation).where(
            operation.id == operation_id, operation.kind == kind.value
        )
        row = self.session.scalars(query).one_or_none()
        if row is None:
            return None
        return domain.movements.Movement(
            domain.movements.Kind(row.kind),
            domain.movements.State(row.state),
            row.product_id,
            row.quantity,
            row.source_warehouse_id,
            row.destination_warehouse_id,
        )

    def save_state(self, operation_id: int, state: domain.movements.State) -> None:
        self.session.get_one(orm_models.StockOperation, operation_id).state = state.value

    def record_movement(
        self, action: str, operation_id: int, external_destination: str | None = None
    ) -> None:
        operation = orm_models.StockOperation
        source = sa_orm.aliased(orm_models.Warehouse)
        destination = sa_orm.aliased(orm_models.Warehouse)
        query = (
            sa.select(operation, source.name, destination.name)
            .join(source, source.id == operation.source_warehouse_id)
            .outerjoin(destination, destination.id == operation.destination_warehouse_id)
            .where(operation.id == operation_id)
        )
        row, source_name, destination_name = self.session.execute(query).one()
        self.session.add(
            orm_models.AuditEntry(
                action=action,
                operation_id=operation_id,
                product_id=row.product_id,
                quantity=row.quantity,
                source_warehouse_id=row.source_warehouse_id,
                destination_warehouse_id=row.destination_warehouse_id,
                source_name=source_name,
                destination_name=destination_name
                if destination_name is not None
                else external_destination,
            )
        )
