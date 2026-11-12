import typing
import uuid

import application.receipts
import application.transactions
import domain.receipts

type Action = typing.Literal["cancel", "dispatch"]


class Writer(typing.Protocol):
    def reserve(self, reservation: application.receipts.Receipt) -> int: ...
    def finish(self, operation_id: int, action: Action) -> int: ...


type Transaction = application.transactions.Transaction[Writer]


def reserve(
    transaction: Transaction, key: uuid.UUID, reservation: application.receipts.Receipt
) -> int:
    domain.receipts.validate_quantity(reservation.quantity)
    fingerprint = application.transactions.fingerprint(
        reservation.warehouse_id, reservation.product_id, reservation.quantity
    )
    return transaction.run(
        key, "fbs.reserve", fingerprint, lambda writer: writer.reserve(reservation)
    )


def finish(transaction: Transaction, key: uuid.UUID, operation_id: int, action: Action) -> int:
    return transaction.run(
        key,
        f"fbs.{action}",
        application.transactions.fingerprint(operation_id),
        lambda writer: writer.finish(operation_id, action),
    )
