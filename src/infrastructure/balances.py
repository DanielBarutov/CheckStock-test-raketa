import sqlalchemy
import sqlalchemy.engine

import domain.stock


class PostgresBalances:
    def __init__(self, connection: sqlalchemy.engine.Connection) -> None:
        self.connection = connection

    def get_balance(self, warehouse_id: int, product_id: int) -> domain.stock.Balance:
        query = sqlalchemy.text("""
            SELECT on_hand, reserved FROM stock_balances
            WHERE warehouse_id = :warehouse_id AND product_id = :product_id
        """)
        row = self.connection.execute(
            query, {"warehouse_id": warehouse_id, "product_id": product_id}
        ).one_or_none()
        return domain.stock.Balance(*row) if row is not None else domain.stock.Balance()

    def save_balance(
        self, warehouse_id: int, product_id: int, balance: domain.stock.Balance
    ) -> None:
        query = sqlalchemy.text("""
            INSERT INTO stock_balances (warehouse_id, product_id, on_hand, reserved)
            VALUES (:warehouse_id, :product_id, :on_hand, :reserved)
            ON CONFLICT (warehouse_id, product_id) DO UPDATE
            SET on_hand = EXCLUDED.on_hand, reserved = EXCLUDED.reserved
        """)
        self.connection.execute(
            query,
            {
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "on_hand": balance.on_hand,
                "reserved": balance.reserved,
            },
        )
