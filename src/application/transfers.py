import dataclasses
import uuid

import application.stock
import application.transactions
import domain.movements
import domain.stock
import domain.transfers


@dataclasses.dataclass(frozen=True)
class Transfer:
    source: int
    destination: int
    product_id: int
    quantity: int


type Transaction = application.transactions.Transaction[application.stock.Movements]


def send(transaction: Transaction, key: uuid.UUID, transfer: Transfer) -> int:
    movement = domain.movements.Movement.start(
        "transfer", transfer.product_id, transfer.quantity, transfer.source, transfer.destination
    )
    fingerprint = application.transactions.fingerprint(
        transfer.source, transfer.destination, transfer.product_id, transfer.quantity
    )

    def write(store: application.stock.Movements) -> int:
        stock = store.active_stock(transfer.product_id)
        domain.stock.require_active(stock, transfer.destination)
        balance = domain.stock.require_available(stock, transfer.source, transfer.quantity)
        store.save_balance(transfer.source, transfer.product_id, balance.remove(transfer.quantity))
        operation_id = store.add_movement(movement)
        store.record_movement("transfer.send", operation_id)
        return operation_id

    return transaction.run(key, "transfer.send", fingerprint, write)


def accept(transaction: Transaction, key: uuid.UUID, operation_id: int) -> int:
    def write(store: application.stock.Movements) -> int:
        movement = store.find_movement("transfer", operation_id)
        if movement is None or movement.destination is None:
            raise domain.transfers.TransferNotFound("Transfer not found")
        state = movement.receive()
        if state is not None:
            balance = store.get_balance(movement.destination, movement.product_id)
            store.save_balance(
                movement.destination, movement.product_id, balance.add(movement.quantity)
            )
            store.save_state(operation_id, state)
            store.record_movement("transfer.accept", operation_id)
        return operation_id

    return transaction.run(
        key, "transfer.accept", application.transactions.fingerprint(operation_id), write
    )
