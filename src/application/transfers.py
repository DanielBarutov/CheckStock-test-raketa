import dataclasses
import typing
import uuid

import application.transactions
import domain.receipts
import domain.transfers


@dataclasses.dataclass(frozen=True)
class Transfer:
    source: int
    destination: int
    product_id: int
    quantity: int


class TransferWriter(typing.Protocol):
    def send(self, transfer: Transfer) -> int: ...
    def accept(self, operation_id: int) -> int: ...


type Transaction = application.transactions.Transaction[TransferWriter]


def send(transaction: Transaction, key: uuid.UUID, transfer: Transfer) -> int:
    domain.receipts.validate_quantity(transfer.quantity)
    if transfer.source == transfer.destination:
        raise domain.transfers.InvalidRoute("Source and destination must differ")
    fingerprint = application.transactions.fingerprint(
        transfer.source, transfer.destination, transfer.product_id, transfer.quantity
    )
    return transaction.run(key, "transfer.send", fingerprint, lambda writer: writer.send(transfer))


def accept(transaction: Transaction, key: uuid.UUID, operation_id: int) -> int:
    fingerprint = application.transactions.fingerprint(operation_id)
    return transaction.run(
        key, "transfer.accept", fingerprint, lambda writer: writer.accept(operation_id)
    )
