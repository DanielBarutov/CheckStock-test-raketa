import sqlalchemy
import sqlalchemy.dialects.postgresql

import infrastructure.database.db
import infrastructure.database.models as orm_models


class PostgresProductCatalog:
    def __init__(self, sessions: infrastructure.database.db.SessionFactory) -> None:
        self.sessions = sessions

    def ensure_product(self, sku: str, name: str) -> int:
        insert = sqlalchemy.dialects.postgresql.insert(orm_models.Product).values(
            sku=sku, name=name
        )
        with self.sessions() as session, session.begin():
            session.execute(insert.on_conflict_do_nothing(index_elements=[orm_models.Product.sku]))
            return session.execute(
                sqlalchemy.select(orm_models.Product.id).where(orm_models.Product.sku == sku)
            ).scalar_one()
