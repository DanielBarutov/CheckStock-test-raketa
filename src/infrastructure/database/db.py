import sqlalchemy as sa
import sqlalchemy.orm as sa_orm

type SessionFactory = sa_orm.sessionmaker[sa_orm.Session]


class Database:
    def __init__(self, url: str) -> None:
        self._engine = sa.create_engine(url, pool_pre_ping=True)
        self.sessions = sa_orm.sessionmaker(self._engine)
        read_engine = self._engine.execution_options(
            isolation_level="REPEATABLE READ", postgresql_readonly=True
        )
        self.read_sessions = sa_orm.sessionmaker(read_engine)

    def check(self) -> None:
        try:
            with self.sessions() as session:
                session.execute(sa.select(1))
        except sa.exc.OperationalError as error:
            raise ConnectionError("Database unavailable") from error

    def close(self) -> None:
        self._engine.dispose()
