import os
import sys
import uuid

import pydantic
import sqlalchemy
import sqlalchemy.engine

import application.receipts
import application.warehouses
import infrastructure.receipts
import infrastructure.transactions
import infrastructure.warehouses


class Product(pydantic.BaseModel):
    sku: str
    name: str
    initial_receipts: dict[str, pydantic.NonNegativeInt]


class Demo(pydantic.BaseModel):
    warehouses: list[str]
    products: list[Product]


def load(engine: sqlalchemy.engine.Engine, data: Demo) -> None:
    warehouses = infrastructure.transactions.PostgresTransaction(
        engine, infrastructure.warehouses.PostgresWarehouseWriter
    )
    receipts = infrastructure.transactions.PostgresTransaction(
        engine, infrastructure.receipts.PostgresReceiptWriter
    )
    ids = {
        name: application.warehouses.change_warehouse(
            warehouses,
            uuid.uuid5(uuid.NAMESPACE_URL, f"checkstock/demo/warehouse/{name}"),
            application.warehouses.Change("create", None, name),
        )
        for name in data.warehouses
    }
    insert = sqlalchemy.text("""
        INSERT INTO products (sku, name) VALUES (:sku, :name) ON CONFLICT (sku) DO NOTHING
    """)
    lookup = sqlalchemy.text("SELECT id FROM products WHERE sku = :sku")
    for product in data.products:
        with engine.begin() as connection:
            connection.execute(insert, {"sku": product.sku, "name": product.name})
            product_id = int(connection.execute(lookup, {"sku": product.sku}).scalar_one())
        for name, quantity in product.initial_receipts.items():
            if quantity:
                key = uuid.uuid5(
                    uuid.NAMESPACE_URL, f"checkstock/demo/receipt/{product.sku}/{name}"
                )
                application.receipts.receive(
                    receipts, key, application.receipts.Receipt(ids[name], product_id, quantity)
                )


def main() -> None:
    engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
    try:
        load(engine, Demo.model_validate_json(sys.stdin.read()))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
