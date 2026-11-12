import typing

import domain.stock


class Balances(typing.Protocol):
    def get_balance(self, warehouse_id: int, product_id: int) -> domain.stock.Balance: ...
    def save_balance(
        self, warehouse_id: int, product_id: int, balance: domain.stock.Balance
    ) -> None: ...
