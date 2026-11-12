import dataclasses
import typing

import sqlalchemy

import application.receipts
import infrastructure.balances


class PostgresReceiptWriter(infrastructure.balances.PostgresBalances):
    def active_target_name(self, warehouse_id: int, product_id: int) -> str | None:
        query = sqlalchemy.text("""
            SELECT w.name FROM warehouses AS w CROSS JOIN products AS p
            WHERE w.id = :warehouse_id AND w.archived_at IS NULL AND p.id = :product_id
        """)
        return typing.cast(
            str | None,
            self.connection.execute(
                query, {"warehouse_id": warehouse_id, "product_id": product_id}
            ).scalar_one_or_none(),
        )

    def record_receipt(self, receipt: application.receipts.Receipt, destination_name: str) -> int:
        audit = sqlalchemy.text("""
            INSERT INTO audit_entries (action, product_id, quantity, destination_warehouse_id,
                                       source_name, destination_name)
            VALUES ('stock.receipt', :product_id, :quantity, :warehouse_id,
                    'External receipt', :name)
            RETURNING id
        """)
        params = {**dataclasses.asdict(receipt), "name": destination_name}
        return int(self.connection.execute(audit, params).scalar_one())
