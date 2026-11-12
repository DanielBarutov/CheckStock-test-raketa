import collections.abc
import contextlib
import os

import fastapi

import infrastructure.database.db
import infrastructure.repositories.inventory
import infrastructure.repositories.movements
import infrastructure.repositories.receipts
import infrastructure.repositories.transactions
import infrastructure.repositories.warehouses
import presentation.health
import presentation.inventory
import presentation.receipts
import presentation.warehouses


def create_app() -> fastapi.FastAPI:
    database = infrastructure.database.db.Database(os.environ["DATABASE_URL"])

    @contextlib.asynccontextmanager
    async def lifespan(app: fastapi.FastAPI) -> collections.abc.AsyncGenerator[None]:
        try:
            yield
        finally:
            database.close()

    app = fastapi.FastAPI(title="CheckStock", lifespan=lifespan)
    app.include_router(presentation.health.router(database.check))
    warehouses = infrastructure.repositories.transactions.PostgresTransaction(
        database.sessions, infrastructure.repositories.warehouses.PostgresWarehouseWriter
    )
    receipts = infrastructure.repositories.transactions.PostgresTransaction(
        database.sessions, infrastructure.repositories.receipts.PostgresReceiptWriter
    )
    app.include_router(presentation.warehouses.router(warehouses))
    app.include_router(presentation.receipts.router(receipts))
    app.include_router(
        presentation.inventory.router(
            infrastructure.repositories.inventory.PostgresInventoryReader(database.read_sessions),
            warehouses,
            receipts,
            infrastructure.repositories.transactions.PostgresTransaction(
                database.sessions, infrastructure.repositories.movements.PostgresMovements
            ),
        )
    )
    return app
