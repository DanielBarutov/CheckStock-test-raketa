import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as sa_pg

import infrastructure.database.db
import infrastructure.database.models as orm_models


class PostgresProductCatalog:
    def __init__(self, sessions: infrastructure.database.db.SessionFactory) -> None:
        self.sessions = sessions

    def ensure_product(self, sku: str, name: str) -> int:
        insert = sa_pg.insert(orm_models.Product).values(sku=sku, name=name)
        with self.sessions() as session, session.begin():
            session.execute(insert.on_conflict_do_nothing(index_elements=[orm_models.Product.sku]))
            return session.execute(
                sa.select(orm_models.Product.id).where(orm_models.Product.sku == sku)
            ).scalar_one()
