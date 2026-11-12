import typing
import uuid

import application.stock
import application.transactions
import domain.receipts


class ReceiptWriter(application.stock.Balances, typing.Protocol):
    def active_target_name(self, warehouse_id: int, product_id: int) -> str | None: ...
    def record_receipt(
        self, receipt: application.stock.StockRequest, destination_name: str
    ) -> int: ...


def receive(
    transaction: application.transactions.Transaction[ReceiptWriter],
    key: uuid.UUID,
    receipt: application.stock.StockRequest,
) -> int:
    domain.receipts.validate_quantity(receipt.quantity)
    fingerprint = application.transactions.fingerprint(
        receipt.warehouse_id, receipt.product_id, receipt.quantity
    )

    def write(store: ReceiptWriter) -> int:
        warehouse_id, product_id = receipt.warehouse_id, receipt.product_id
        name = store.active_target_name(warehouse_id, product_id)
        if name is None:
            raise domain.receipts.ReceiptTargetNotFound("Active warehouse or product not found")
        balance = store.get_balance(warehouse_id, product_id)
        store.save_balance(warehouse_id, product_id, balance.add(receipt.quantity))
        return store.record_receipt(receipt, name)

    return transaction.run(key, "stock.receipt", fingerprint, write)
