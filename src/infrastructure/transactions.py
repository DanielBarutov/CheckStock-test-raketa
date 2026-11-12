import collections.abc
import uuid

import sqlalchemy
import sqlalchemy.engine

import application.transactions


class PostgresTransaction[Writer]:
    def __init__(
        self,
        engine: sqlalchemy.engine.Engine,
        writer: collections.abc.Callable[[sqlalchemy.engine.Connection], Writer],
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
        with self.engine.begin() as connection:
            connection.execute(
                sqlalchemy.text("SELECT id FROM stores WHERE id = 1 FOR UPDATE")
            ).one()
            receipt = connection.execute(
                sqlalchemy.text("""
                SELECT command, fingerprint, result FROM command_receipts
                WHERE idempotency_key = :key
            """),
                {"key": key},
            ).one_or_none()
            if receipt is not None:
                if (receipt.command, receipt.fingerprint) != (command, fingerprint):
                    raise application.transactions.KeyConflict("Idempotency key is already in use")
                return int(receipt.result)
            result = write(self.writer(connection))
            connection.execute(
                sqlalchemy.text("""
                INSERT INTO command_receipts (idempotency_key, command, fingerprint, result)
                VALUES (:key, :command, :fingerprint, to_jsonb(CAST(:result AS bigint)))
            """),
                {"key": key, "command": command, "fingerprint": fingerprint, "result": result},
            )
            return result
