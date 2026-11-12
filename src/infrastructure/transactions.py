import collections.abc
import uuid

import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.orm

import application.transactions
import infrastructure.models as orm_models


class PostgresTransaction[Writer]:
    def __init__(
        self,
        engine: sqlalchemy.engine.Engine,
        writer: collections.abc.Callable[[sqlalchemy.orm.Session], Writer],
    ) -> None:
        self.engine = engine
        self.writer = writer

    def run(
        self,
        key: uuid.UUID,
        command: str,
        fingerprint: str,
        write: collections.abc.Callable[[Writer], int],
    ) -> int:
        with sqlalchemy.orm.Session(self.engine) as session, session.begin():
            lock = sqlalchemy.select(orm_models.Store.id).where(orm_models.Store.id == 1)
            session.execute(lock.with_for_update()).scalar_one()
            receipt = session.get(orm_models.CommandReceipt, key)
            if receipt is not None:
                if (receipt.command, receipt.fingerprint) != (command, fingerprint):
                    raise application.transactions.KeyConflict("Idempotency key is already in use")
                return receipt.result
            result = write(self.writer(session))
            session.add(
                orm_models.CommandReceipt(
                    idempotency_key=key, command=command, fingerprint=fingerprint, result=result
                )
            )
            return result
