import collections.abc
import uuid

import sqlalchemy
import sqlalchemy.orm

import application.transactions
import infrastructure.database.db
import infrastructure.database.models as orm_models


class PostgresTransaction[Writer]:
    def __init__(
        self,
        sessions: infrastructure.database.db.SessionFactory,
        writer: collections.abc.Callable[[sqlalchemy.orm.Session], Writer],
    ) -> None:
        self.sessions = sessions
        self.writer = writer

    def run(
        self,
        key: uuid.UUID,
        command: str,
        fingerprint: str,
        write: collections.abc.Callable[[Writer], int],
    ) -> int:
        with self.sessions() as session, session.begin():
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
