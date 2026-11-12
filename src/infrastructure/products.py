import sqlalchemy
import sqlalchemy.engine


class PostgresProductCatalog:
    def __init__(self, engine: sqlalchemy.engine.Engine) -> None:
        self.engine = engine

    def ensure_product(self, sku: str, name: str) -> int:
        insert = sqlalchemy.text("""
            INSERT INTO products (sku, name) VALUES (:sku, :name) ON CONFLICT (sku) DO NOTHING
        """)
        lookup = sqlalchemy.text("SELECT id FROM products WHERE sku = :sku")
        with self.engine.begin() as connection:
            connection.execute(insert, {"sku": sku, "name": name})
            return int(connection.execute(lookup, {"sku": sku}).scalar_one())
