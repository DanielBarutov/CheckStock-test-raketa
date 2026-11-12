import dataclasses

import sqlalchemy

import domain.movements
import domain.stock
import infrastructure.balances


class PostgresMovements(infrastructure.balances.PostgresBalances):
    def active_stock(self, product_id: int) -> dict[int, tuple[str, domain.stock.Balance]]:
        query = sqlalchemy.text("""
            SELECT w.id, w.name, coalesce(b.on_hand, 0), coalesce(b.reserved, 0)
            FROM warehouses w CROSS JOIN products p LEFT JOIN stock_balances b
              ON b.product_id = p.id AND b.warehouse_id = w.id
            WHERE w.archived_at IS NULL AND p.id = :product_id ORDER BY w.name, w.id
        """)
        return {
            identifier: (name, domain.stock.Balance(on_hand, reserved))
            for identifier, name, on_hand, reserved in self.connection.execute(
                query, {"product_id": product_id}
            )
        }

    def add_movement(self, movement: domain.movements.Movement) -> int:
        query = sqlalchemy.text("""
            INSERT INTO stock_operations
                (kind, state, product_id, quantity, source_warehouse_id, destination_warehouse_id)
            VALUES (:kind, :state, :product_id, :quantity, :source, :destination) RETURNING id
        """)
        return int(self.connection.execute(query, dataclasses.asdict(movement)).scalar_one())

    def find_movement(
        self, kind: domain.movements.Kind, operation_id: int
    ) -> domain.movements.Movement | None:
        query = sqlalchemy.text("""
            SELECT kind, state, product_id, quantity, source_warehouse_id, destination_warehouse_id
            FROM stock_operations WHERE id = :id AND kind = :kind
        """)
        row = self.connection.execute(query, {"id": operation_id, "kind": kind}).one_or_none()
        return domain.movements.Movement(*row) if row is not None else None

    def save_state(self, operation_id: int, state: domain.movements.State) -> None:
        query = sqlalchemy.text("""
            UPDATE stock_operations SET state = :state, updated_at = now() WHERE id = :id
        """)
        self.connection.execute(query, {"id": operation_id, "state": state})

    def record_movement(
        self, action: str, operation_id: int, external_destination: str | None = None
    ) -> None:
        query = sqlalchemy.text("""
            INSERT INTO audit_entries (action, operation_id, product_id, quantity, source_warehouse_id,
                                       destination_warehouse_id, source_name, destination_name)
            SELECT :action, o.id, o.product_id, o.quantity, s.id, d.id, s.name,
                   coalesce(d.name, :external_destination)
            FROM stock_operations o JOIN warehouses s ON s.id = o.source_warehouse_id
            LEFT JOIN warehouses d ON d.id = o.destination_warehouse_id WHERE o.id = :id
        """)
        self.connection.execute(
            query,
            {"action": action, "id": operation_id, "external_destination": external_destination},
        )
