import uuid

import application.receipts
import application.stock
import application.transactions
import domain.movements
import domain.receipts
import domain.stock


class ShipmentNotFound(LookupError):
    pass


type Transaction = application.transactions.Transaction[application.stock.Movements]
_DESTINATION = "Маркетплейс FBO"


def dispatch(
    transaction: Transaction, key: uuid.UUID, shipment: application.receipts.Receipt
) -> int:
    domain.receipts.validate_quantity(shipment.quantity)
    fingerprint = application.transactions.fingerprint(
        shipment.warehouse_id, shipment.product_id, shipment.quantity
    )

    def write(store: application.stock.Movements) -> int:
        warehouse_id, product_id, quantity = (
            shipment.warehouse_id,
            shipment.product_id,
            shipment.quantity,
        )
        stock = store.active_stock(product_id)
        balance = domain.stock.require_available(stock, warehouse_id, quantity)
        store.save_balance(warehouse_id, product_id, balance.remove(quantity))
        operation_id = store.add_movement(
            domain.movements.Movement("fbo", "in_transit", product_id, quantity, warehouse_id)
        )
        store.record_movement("fbo.dispatch", operation_id, _DESTINATION)
        return operation_id

    return transaction.run(key, "fbo.dispatch", fingerprint, write)


def accept(transaction: Transaction, key: uuid.UUID, operation_id: int) -> int:
    def write(store: application.stock.Movements) -> int:
        movement = store.find_movement("fbo", operation_id)
        if movement is None:
            raise ShipmentNotFound("Shipment not found")
        if movement.is_in_transit():
            store.save_state(operation_id, "received")
            store.record_movement("fbo.accept", operation_id, _DESTINATION)
        return operation_id

    return transaction.run(
        key, "fbo.accept", application.transactions.fingerprint(operation_id), write
    )
