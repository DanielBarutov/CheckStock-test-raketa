import sqlalchemy
import sqlalchemy.engine
import sqlalchemy.exc


def check_connection(engine: sqlalchemy.engine.Engine) -> None:
    try:
        with engine.connect() as connection:
            connection.execute(sqlalchemy.select(1))
    except sqlalchemy.exc.OperationalError as error:
        raise ConnectionError("Database unavailable") from error
