import dataclasses

import sqlalchemy
import sqlalchemy.engine

import application.fbo
import application.receipts
import infrastructure.balances


class PostgresWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def dispatch(self, shipment: application.receipts.Receipt) -> int:
        stock = infrastructure.balances.active_stock(self.connection, shipment.product_id)
        infrastructure.balances.require_available(stock, shipment.warehouse_id, shipment.quantity)
        params = dataclasses.asdict(shipment)
        balance = sqlalchemy.text("""
            UPDATE stock_balances SET on_hand = on_hand - :quantity
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
        """)
        self.connection.execute(balance, params)
        insert = sqlalchemy.text("""
            INSERT INTO stock_operations (kind, state, product_id, quantity, source_warehouse_id)
            VALUES ('fbo', 'in_transit', :product_id, :quantity, :warehouse_id) RETURNING id
        """)
        operation_id = int(self.connection.execute(insert, params).scalar_one())
        self._audit(operation_id, "fbo.dispatch")
        return operation_id

    def accept(self, operation_id: int) -> int:
        query = sqlalchemy.text("""
            SELECT state FROM stock_operations WHERE id = :id AND kind = 'fbo'
        """)
        params = {"id": operation_id}
        state = self.connection.execute(query, params).scalar_one_or_none()
        if state is None:
            raise application.fbo.ShipmentNotFound("Shipment not found")
        if state == "in_transit":
            update = sqlalchemy.text("""
                UPDATE stock_operations SET state = 'received', updated_at = now() WHERE id = :id
            """)
            self.connection.execute(update, params)
            self._audit(operation_id, "fbo.accept")
        return operation_id

    def _audit(self, operation_id: int, action: str) -> None:
        insert = sqlalchemy.text("""
            INSERT INTO audit_entries (action, operation_id, product_id, quantity, source_warehouse_id,
                                       source_name, destination_name)
            SELECT :action, o.id, o.product_id, o.quantity, w.id, w.name, 'Маркетплейс FBO'
            FROM stock_operations o JOIN warehouses w ON w.id = o.source_warehouse_id
            WHERE o.id = :id
        """)
        self.connection.execute(insert, {"id": operation_id, "action": action})
