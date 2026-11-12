import collections.abc
import contextlib
import functools
import os

import fastapi
import sqlalchemy

import infrastructure.database
import infrastructure.warehouses
import presentation.health
import presentation.warehouses


def create_app() -> fastapi.FastAPI:
    engine = sqlalchemy.create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)

    @contextlib.asynccontextmanager
    async def lifespan(app: fastapi.FastAPI) -> collections.abc.AsyncGenerator[None]:
        try:
            yield
        finally:
            engine.dispose()

    app = fastapi.FastAPI(title="CheckStock", lifespan=lifespan)
    app.include_router(
        presentation.health.router(
            functools.partial(infrastructure.database.check_connection, engine)
        )
    )
    app.include_router(
        presentation.warehouses.router(infrastructure.warehouses.PostgresTransaction(engine))
    )
    return app
