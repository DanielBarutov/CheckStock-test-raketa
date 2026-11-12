import sqlalchemy
import sqlalchemy.engine

import application.inventory

_BALANCES = sqlalchemy.text("""
    SELECT p.sku, p.name, w.name, w.archived_at IS NOT NULL,
           coalesce(b.on_hand, 0),
           CASE WHEN w.archived_at IS NULL THEN coalesce(b.on_hand - b.reserved, 0) ELSE 0 END,
           coalesce(b.reserved, 0)
    FROM products p CROSS JOIN warehouses w
    LEFT JOIN stock_balances b ON b.product_id = p.id AND b.warehouse_id = w.id
    ORDER BY p.sku, w.archived_at IS NOT NULL, w.name, w.id
""")

_HISTORY = sqlalchemy.text("""
    SELECT a.created_at, a.action, p.sku, a.quantity, a.source_name, a.destination_name
    FROM audit_entries a LEFT JOIN products p ON p.id = a.product_id
    ORDER BY a.created_at DESC, a.id DESC
""")


class PostgresInventoryReader:
    def __init__(self, engine: sqlalchemy.engine.Engine) -> None:
        self.engine = engine

    def read(self) -> application.inventory.Inventory:
        with self.engine.connect().execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        ) as connection:
            balances = [
                application.inventory.Balance(*row) for row in connection.execute(_BALANCES)
            ]
            history = [
                application.inventory.HistoryEntry(*row) for row in connection.execute(_HISTORY)
            ]
        return application.inventory.Inventory(balances, history)
