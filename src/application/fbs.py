import uuid

import application.stock
import application.transactions
import domain.fbs
import domain.movements
import domain.stock

type Transaction = application.transactions.Transaction[application.stock.Movements]


def reserve(
    transaction: Transaction, key: uuid.UUID, reservation: application.stock.StockRequest
) -> int:
    warehouse_id, product_id, quantity = (
        reservation.warehouse_id,
        reservation.product_id,
        reservation.quantity,
    )
    movement = domain.movements.Movement.start("fbs", product_id, quantity, warehouse_id)
    fingerprint = application.transactions.fingerprint(warehouse_id, product_id, quantity)

    def write(store: application.stock.Movements) -> int:
        stock = store.active_stock(product_id)
        balance = domain.stock.require_available(stock, warehouse_id, quantity)
        store.save_balance(warehouse_id, product_id, balance.reserve(quantity))
        operation_id = store.add_movement(movement)
        store.record_movement("fbs.reserve", operation_id)
        return operation_id

    return transaction.run(key, "fbs.reserve", fingerprint, write)


def finish(
    transaction: Transaction, key: uuid.UUID, operation_id: int, action: domain.fbs.Action
) -> int:
    command = f"fbs.{action}"

    def write(store: application.stock.Movements) -> int:
        reservation = store.find_movement("fbs", operation_id)
        if reservation is None:
            raise domain.fbs.ReservationNotFound("Reservation not found")
        state = domain.fbs.finish_reservation(reservation.state, action)
        if state is not None:
            warehouse_id, product_id = reservation.source, reservation.product_id
            shipped = state == "in_transit"
            balance = store.get_balance(warehouse_id, product_id)
            store.save_balance(
                warehouse_id, product_id, balance.release(reservation.quantity, shipped=shipped)
            )
            store.save_state(operation_id, state)
            store.record_movement(command, operation_id, "Клиент FBS" if shipped else None)
        return operation_id

    return transaction.run(key, command, application.transactions.fingerprint(operation_id), write)
