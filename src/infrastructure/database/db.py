import sqlalchemy
import sqlalchemy.exc
import sqlalchemy.orm

type SessionFactory = sqlalchemy.orm.sessionmaker[sqlalchemy.orm.Session]


class Database:
    def __init__(self, url: str) -> None:
        self._engine = sqlalchemy.create_engine(url, pool_pre_ping=True)
        self.sessions = sqlalchemy.orm.sessionmaker(self._engine)
        read_engine = self._engine.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        self.read_sessions = sqlalchemy.orm.sessionmaker(read_engine)

    def check(self) -> None:
        try:
            with self.sessions() as session:
                session.execute(sqlalchemy.select(1))
        except sqlalchemy.exc.OperationalError as error:
            raise ConnectionError("Database unavailable") from error

    def close(self) -> None:
        self._engine.dispose()
