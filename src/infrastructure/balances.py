import sqlalchemy.orm

import domain.stock
import infrastructure.models as orm_models


class PostgresBalances:
    def __init__(self, session: sqlalchemy.orm.Session) -> None:
        self.session = session

    def get_balance(self, warehouse_id: int, product_id: int) -> domain.stock.Balance:
        row = self.session.get(orm_models.StockBalance, (warehouse_id, product_id))
        return domain.stock.Balance(row.on_hand, row.reserved) if row else domain.stock.Balance()

    def save_balance(
        self, warehouse_id: int, product_id: int, balance: domain.stock.Balance
    ) -> None:
        row = self.session.get(orm_models.StockBalance, (warehouse_id, product_id))
        if row is None:
            row = orm_models.StockBalance(warehouse_id=warehouse_id, product_id=product_id)
            self.session.add(row)
        row.on_hand = balance.on_hand
        row.reserved = balance.reserved
