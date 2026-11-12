import dataclasses
import typing
import uuid

import application.transactions
import domain.receipts


@dataclasses.dataclass(frozen=True)
class Receipt:
    warehouse_id: int
    product_id: int
    quantity: int


class ReceiptWriter(typing.Protocol):
    def receive(self, receipt: Receipt) -> int: ...


def receive(
    transaction: application.transactions.Transaction[ReceiptWriter],
    key: uuid.UUID,
    receipt: Receipt,
) -> int:
    domain.receipts.validate_quantity(receipt.quantity)
    fingerprint = application.transactions.fingerprint(
        receipt.warehouse_id, receipt.product_id, receipt.quantity
    )
    return transaction.run(
        key, "stock.receipt", fingerprint, lambda writer: writer.receive(receipt)
    )
