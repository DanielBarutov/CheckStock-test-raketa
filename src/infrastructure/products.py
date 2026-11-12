import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.engine
import sqlalchemy.orm

import infrastructure.models as orm_models


class PostgresProductCatalog:
    def __init__(self, engine: sqlalchemy.engine.Engine) -> None:
        self.engine = engine

    def ensure_product(self, sku: str, name: str) -> int:
        insert = sqlalchemy.dialects.postgresql.insert(orm_models.Product).values(
            sku=sku, name=name
        )
        with sqlalchemy.orm.Session(self.engine) as session, session.begin():
            session.execute(insert.on_conflict_do_nothing(index_elements=[orm_models.Product.sku]))
            return session.execute(
                sqlalchemy.select(orm_models.Product.id).where(orm_models.Product.sku == sku)
            ).scalar_one()
