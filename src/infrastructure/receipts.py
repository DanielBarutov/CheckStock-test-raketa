import dataclasses

import sqlalchemy
import sqlalchemy.engine

import application.receipts
import domain.receipts


class PostgresReceiptWriter:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def receive(self, receipt: application.receipts.Receipt) -> int:
        params = dataclasses.asdict(receipt)
        target = sqlalchemy.text("""
            SELECT w.name FROM warehouses AS w CROSS JOIN products AS p
            WHERE w.id = :warehouse_id AND w.archived_at IS NULL AND p.id = :product_id
        """)
        name = self.connection.execute(target, params).scalar_one_or_none()
        if name is None:
            raise domain.receipts.ReceiptTargetNotFound("Active warehouse or product not found")
        balance = sqlalchemy.text("""
            INSERT INTO stock_balances (warehouse_id, product_id, on_hand, reserved)
            VALUES (:warehouse_id, :product_id, :quantity, 0)
            ON CONFLICT (warehouse_id, product_id) DO UPDATE
            SET on_hand = stock_balances.on_hand + EXCLUDED.on_hand
            WHERE stock_balances.on_hand <= 2147483647 - EXCLUDED.on_hand
            RETURNING on_hand
        """)
        if self.connection.execute(balance, params).scalar_one_or_none() is None:
            raise domain.receipts.StockLimit("Physical stock exceeds the supported quantity")
        audit = sqlalchemy.text("""
            INSERT INTO audit_entries (action, product_id, quantity, destination_warehouse_id,
                                       source_name, destination_name)
            VALUES ('stock.receipt', :product_id, :quantity, :warehouse_id,
                    'External receipt', :name)
            RETURNING id
        """)
        return int(self.connection.execute(audit, {**params, "name": name}).scalar_one())
