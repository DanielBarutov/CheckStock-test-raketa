import collections.abc
import contextlib
import os

import fastapi

import infrastructure.database.db
import presentation.health
import presentation.inventory
import presentation.receipts
import presentation.warehouses


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI) -> collections.abc.AsyncGenerator[None]:
    database = infrastructure.database.db.Database(os.environ["DATABASE_URL"])
    app.state.database = database
    try:
        yield
    finally:
        database.close()


def create_app() -> fastapi.FastAPI:
    app = fastapi.FastAPI(title="CheckStock", lifespan=lifespan)
    app.include_router(presentation.health.router)
    app.include_router(presentation.warehouses.router)
    app.include_router(presentation.receipts.router)
    app.include_router(presentation.inventory.router)
    return app
