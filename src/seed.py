import os
import sys

import pydantic

import application.demo
import infrastructure.database.db
import infrastructure.repositories.products
import infrastructure.repositories.receipts
import infrastructure.repositories.transactions
import infrastructure.repositories.warehouses


class ProductInput(pydantic.BaseModel):
    sku: str
    name: str
    initial_receipts: dict[str, pydantic.NonNegativeInt]


class DemoInput(pydantic.BaseModel):
    warehouses: list[str]
    products: list[ProductInput]


def main() -> None:
    data = DemoInput.model_validate_json(sys.stdin.read())
    database = infrastructure.database.db.Database(os.environ["DATABASE_URL"])
    try:
        application.demo.load(
            infrastructure.repositories.transactions.PostgresTransaction(
                database.sessions, infrastructure.repositories.warehouses.PostgresWarehouseWriter
            ),
            infrastructure.repositories.transactions.PostgresTransaction(
                database.sessions, infrastructure.repositories.receipts.PostgresReceiptWriter
            ),
            infrastructure.repositories.products.PostgresProductCatalog(database.sessions),
            data.warehouses,
            [
                application.demo.DemoProduct(product.sku, product.name, product.initial_receipts)
                for product in data.products
            ],
        )
    finally:
        database.close()


if __name__ == "__main__":
    main()
