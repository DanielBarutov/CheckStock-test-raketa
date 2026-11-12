import sqlalchemy
import sqlalchemy.engine

import domain.receipts


def add(
    connection: sqlalchemy.engine.Connection, warehouse_id: int, product_id: int, quantity: int
) -> None:
    balance = sqlalchemy.text("""
        INSERT INTO stock_balances (warehouse_id, product_id, on_hand, reserved)
        VALUES (:warehouse_id, :product_id, :quantity, 0)
        ON CONFLICT (warehouse_id, product_id) DO UPDATE
        SET on_hand = stock_balances.on_hand + EXCLUDED.on_hand
        WHERE stock_balances.on_hand <= 2147483647 - EXCLUDED.on_hand
        RETURNING on_hand
    """)
    if (
        connection.execute(
            balance, {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": quantity}
        ).scalar_one_or_none()
        is None
    ):
        raise domain.receipts.StockLimit("Physical stock exceeds the supported quantity")
