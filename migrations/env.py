import os

import alembic.context
import sqlalchemy as sa

url = os.environ["DATABASE_URL"]

if alembic.context.is_offline_mode():
    alembic.context.configure(url=url, literal_binds=True)
    with alembic.context.begin_transaction():
        alembic.context.run_migrations()
else:
    engine = sa.create_engine(url, poolclass=sa.NullPool)
    with engine.connect() as connection:
        alembic.context.configure(connection=connection)
        with alembic.context.begin_transaction():
            alembic.context.run_migrations()
