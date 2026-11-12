import dataclasses
import typing
import uuid

import application.receipts
import application.stock
import application.transactions
import application.warehouses


@dataclasses.dataclass(frozen=True)
class DemoProduct:
    sku: str
    name: str
    initial_receipts: dict[str, int]


class ProductCatalog(typing.Protocol):
    def ensure_product(self, sku: str, name: str) -> int: ...


def load(
    warehouses: application.transactions.Transaction[application.warehouses.WarehouseWriter],
    receipts: application.transactions.Transaction[application.receipts.ReceiptWriter],
    catalog: ProductCatalog,
    names: list[str],
    products: list[DemoProduct],
) -> None:
    ids = {
        name: application.warehouses.change_warehouse(
            warehouses,
            uuid.uuid5(uuid.NAMESPACE_URL, f"checkstock/demo/warehouse/{name}"),
            application.warehouses.Change("create", None, name),
        )
        for name in names
    }
    for product in products:
        product_id = catalog.ensure_product(product.sku, product.name)
        for name, quantity in product.initial_receipts.items():
            if quantity:
                key = uuid.uuid5(
                    uuid.NAMESPACE_URL, f"checkstock/demo/receipt/{product.sku}/{name}"
                )
                application.receipts.receive(
                    receipts, key, application.stock.StockRequest(ids[name], product_id, quantity)
                )
