import dataclasses

import sqlalchemy
import sqlalchemy.engine

import application.fbs
import application.receipts
import domain.fbs
import infrastructure.balances


class PostgresWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def reserve(self, reservation: application.receipts.Receipt) -> int:
        stock = infrastructure.balances.active_stock(self.connection, reservation.product_id)
        infrastructure.balances.require_available(
            stock, reservation.warehouse_id, reservation.quantity
        )
        params = dataclasses.asdict(reservation)
        balance = sqlalchemy.text("""
            UPDATE stock_balances SET reserved = reserved + :quantity
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
        """)
        self.connection.execute(balance, params)
        insert = sqlalchemy.text("""
            INSERT INTO stock_operations (kind, state, product_id, quantity, source_warehouse_id)
            VALUES ('fbs', 'reserved', :product_id, :quantity, :warehouse_id) RETURNING id
        """)
        operation_id = int(self.connection.execute(insert, params).scalar_one())
        self._audit(operation_id, "fbs.reserve")
        return operation_id

    def finish(self, operation_id: int, action: application.fbs.Action) -> int:
        query = sqlalchemy.text("""
            SELECT state, quantity, product_id, source_warehouse_id FROM stock_operations
            WHERE id = :id AND kind = 'fbs'
        """)
        reservation = self.connection.execute(query, {"id": operation_id}).one_or_none()
        if reservation is None:
            raise domain.fbs.ReservationNotFound("Reservation not found")
        state = "in_transit" if action == "dispatch" else "cancelled"
        if reservation.state == state:
            return operation_id
        if reservation.state != "reserved":
            raise domain.fbs.ReservationClosed("Reservation already closed")
        balance = sqlalchemy.text("""
            UPDATE stock_balances SET reserved = reserved - :quantity, on_hand = on_hand - :shipped
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
        """)
        self.connection.execute(
            balance,
            {
                "quantity": reservation.quantity,
                "shipped": reservation.quantity if action == "dispatch" else 0,
                "warehouse_id": reservation.source_warehouse_id,
                "product_id": reservation.product_id,
            },
        )
        update = sqlalchemy.text("""
            UPDATE stock_operations SET state = :state, updated_at = now() WHERE id = :id
        """)
        self.connection.execute(update, {"id": operation_id, "state": state})
        self._audit(operation_id, f"fbs.{action}")
        return operation_id

    def _audit(self, operation_id: int, action: str) -> None:
        insert = sqlalchemy.text("""
            INSERT INTO audit_entries (action, operation_id, product_id, quantity, source_warehouse_id,
                                       source_name, destination_name)
            SELECT :action, o.id, o.product_id, o.quantity, w.id, w.name, :destination
            FROM stock_operations o JOIN warehouses w ON w.id = o.source_warehouse_id
            WHERE o.id = :id
        """)
        destination = "Клиент FBS" if action == "fbs.dispatch" else None
        self.connection.execute(
            insert,
            {
                "id": operation_id,
                "action": action,
                "destination": destination,
            },
        )
