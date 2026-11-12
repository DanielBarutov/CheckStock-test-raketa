import sqlalchemy
import sqlalchemy.engine

import domain.receipts
import domain.transfers


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


def active_stock(
    connection: sqlalchemy.engine.Connection, product_id: int
) -> dict[int, tuple[str, int]]:
    query = sqlalchemy.text("""
        SELECT w.id, w.name, coalesce(b.on_hand - b.reserved, 0)
        FROM warehouses w CROSS JOIN products p LEFT JOIN stock_balances b
          ON b.product_id = p.id AND b.warehouse_id = w.id
        WHERE w.archived_at IS NULL AND p.id = :product_id ORDER BY w.name, w.id
    """)
    return {
        identifier: (name, available)
        for identifier, name, available in connection.execute(query, {"product_id": product_id})
    }


def require_available(stock: dict[int, tuple[str, int]], warehouse_id: int, quantity: int) -> None:
    if warehouse_id not in stock:
        raise domain.receipts.ReceiptTargetNotFound("Active warehouse or product not found")
    available = stock[warehouse_id][1]
    if available < quantity:
        raise domain.transfers.InsufficientStock(
            available, [row for other, row in stock.items() if other != warehouse_id and row[1] > 0]
        )
