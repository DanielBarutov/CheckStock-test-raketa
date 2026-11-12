import typing
import uuid

import application.receipts
import application.transactions
import domain.receipts


class ShipmentNotFound(LookupError):
    pass


class Writer(typing.Protocol):
    def dispatch(self, shipment: application.receipts.Receipt) -> int: ...
    def accept(self, operation_id: int) -> int: ...


type Transaction = application.transactions.Transaction[Writer]


def dispatch(
    transaction: Transaction, key: uuid.UUID, shipment: application.receipts.Receipt
) -> int:
    domain.receipts.validate_quantity(shipment.quantity)
    fingerprint = application.transactions.fingerprint(
        shipment.warehouse_id, shipment.product_id, shipment.quantity
    )
    return transaction.run(
        key, "fbo.dispatch", fingerprint, lambda writer: writer.dispatch(shipment)
    )


def accept(transaction: Transaction, key: uuid.UUID, operation_id: int) -> int:
    return transaction.run(
        key,
        "fbo.accept",
        application.transactions.fingerprint(operation_id),
        lambda writer: writer.accept(operation_id),
    )
