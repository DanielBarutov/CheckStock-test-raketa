import typing

import fastapi

import application.inventory
import application.receipts
import application.transactions
import application.transfers
import application.warehouses
import infrastructure.database.db
import infrastructure.repositories.inventory
import infrastructure.repositories.movements
import infrastructure.repositories.receipts
import infrastructure.repositories.transactions
import infrastructure.repositories.warehouses


def get_database(request: fastapi.Request) -> infrastructure.database.db.Database:
    return typing.cast(infrastructure.database.db.Database, request.app.state.database)


Database = typing.Annotated[infrastructure.database.db.Database, fastapi.Depends(get_database)]
type WarehousePort = application.transactions.Transaction[application.warehouses.WarehouseWriter]
type ReceiptPort = application.transactions.Transaction[application.receipts.ReceiptWriter]


def check_database(database: Database) -> None:
    try:
        database.check()
    except ConnectionError as error:
        raise fastapi.HTTPException(503, "Database unavailable") from error


def inventory_reader(database: Database) -> application.inventory.InventoryReader:
    return infrastructure.repositories.inventory.PostgresInventoryReader(database.read_sessions)


def warehouse_transaction(database: Database) -> WarehousePort:
    return infrastructure.repositories.transactions.PostgresTransaction(
        database.sessions, infrastructure.repositories.warehouses.PostgresWarehouseWriter
    )


def receipt_transaction(database: Database) -> ReceiptPort:
    return infrastructure.repositories.transactions.PostgresTransaction(
        database.sessions, infrastructure.repositories.receipts.PostgresReceiptWriter
    )


def movement_transaction(database: Database) -> application.transfers.Transaction:
    return infrastructure.repositories.transactions.PostgresTransaction(
        database.sessions, infrastructure.repositories.movements.PostgresMovements
    )


InventoryReader = typing.Annotated[
    application.inventory.InventoryReader, fastapi.Depends(inventory_reader)
]
WarehouseTransaction = typing.Annotated[WarehousePort, fastapi.Depends(warehouse_transaction)]
ReceiptTransaction = typing.Annotated[ReceiptPort, fastapi.Depends(receipt_transaction)]
MovementTransaction = typing.Annotated[
    application.transfers.Transaction, fastapi.Depends(movement_transaction)
]
