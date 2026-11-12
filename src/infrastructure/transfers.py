import dataclasses

import sqlalchemy
import sqlalchemy.engine

import application.transfers
import domain.receipts
import domain.transfers
import infrastructure.balances


class PostgresTransferWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def send(self, transfer: application.transfers.Transfer) -> int:
        params = dataclasses.asdict(transfer)
        stock = infrastructure.balances.active_stock(self.connection, transfer.product_id)
        if transfer.destination not in stock:
            raise domain.receipts.ReceiptTargetNotFound("Active warehouse or product not found")
        infrastructure.balances.require_available(stock, transfer.source, transfer.quantity)
        self.connection.execute(
            sqlalchemy.text("""
            UPDATE stock_balances SET on_hand = on_hand - :quantity
            WHERE warehouse_id = :source AND product_id = :product_id
        """),
            params,
        )
        insert = sqlalchemy.text("""
            INSERT INTO stock_operations
                (kind, state, product_id, quantity, source_warehouse_id, destination_warehouse_id)
            VALUES ('transfer', 'in_transit', :product_id, :quantity, :source, :destination)
            RETURNING id
        """)
        operation_id = int(self.connection.execute(insert, params).scalar_one())
        self._audit(operation_id, "transfer.send")
        return operation_id

    def accept(self, operation_id: int) -> int:
        query = sqlalchemy.text("""
            SELECT state, destination_warehouse_id, product_id, quantity FROM stock_operations
            WHERE id = :id AND kind = 'transfer'
        """)
        params = {"id": operation_id}
        transfer = self.connection.execute(query, params).one_or_none()
        if transfer is None:
            raise domain.transfers.TransferNotFound("Transfer not found")
        if transfer.state == "received":
            return operation_id
        infrastructure.balances.add(
            self.connection,
            transfer.destination_warehouse_id,
            transfer.product_id,
            transfer.quantity,
        )
        self.connection.execute(
            sqlalchemy.text("""
            UPDATE stock_operations SET state = 'received', updated_at = now() WHERE id = :id
        """),
            params,
        )
        self._audit(operation_id, "transfer.accept")
        return operation_id

    def _audit(self, operation_id: int, action: str) -> None:
        insert = sqlalchemy.text("""
            INSERT INTO audit_entries (action, operation_id, product_id, quantity, source_warehouse_id,
                                       destination_warehouse_id, source_name, destination_name)
            SELECT :action, o.id, o.product_id, o.quantity, s.id, d.id, s.name, d.name
            FROM stock_operations o JOIN warehouses s ON s.id = o.source_warehouse_id
            JOIN warehouses d ON d.id = o.destination_warehouse_id WHERE o.id = :id
        """)
        self.connection.execute(insert, {"id": operation_id, "action": action})
