import os
import sys

import pydantic
import sqlalchemy

import application.demo
import infrastructure.products
import infrastructure.receipts
import infrastructure.transactions
import infrastructure.warehouses


class ProductInput(pydantic.BaseModel):
    sku: str
    name: str
    initial_receipts: dict[str, pydantic.NonNegativeInt]


class DemoInput(pydantic.BaseModel):
    warehouses: list[str]
    products: list[ProductInput]


def main() -> None:
    data = DemoInput.model_validate_json(sys.stdin.read())
    engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"])
    try:
        application.demo.load(
            infrastructure.transactions.PostgresTransaction(
                engine, infrastructure.warehouses.PostgresWarehouseWriter
            ),
            infrastructure.transactions.PostgresTransaction(
                engine, infrastructure.receipts.PostgresReceiptWriter
            ),
            infrastructure.products.PostgresProductCatalog(engine),
            data.warehouses,
            [
                application.demo.Product(product.sku, product.name, product.initial_receipts)
                for product in data.products
            ],
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
