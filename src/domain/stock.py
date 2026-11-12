import dataclasses

import domain.receipts
import domain.transfers

MAX_QUANTITY = 2**31 - 1  # PostgreSQL integer upper bound.


class InvalidQuantity(ValueError):
    pass


class StockLimit(ValueError):
    pass


def validate_quantity(quantity: int) -> None:
    if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
        raise InvalidQuantity("Quantity must be a positive PostgreSQL integer")


@dataclasses.dataclass(frozen=True)
class Balance:
    on_hand: int = 0
    reserved: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.reserved <= self.on_hand <= MAX_QUANTITY:
            raise ValueError("Invalid stock balance")

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    def add(self, quantity: int) -> "Balance":
        on_hand = self.on_hand + quantity
        if on_hand > MAX_QUANTITY:
            raise StockLimit("Physical stock exceeds the supported quantity")
        return Balance(on_hand, self.reserved)

    def remove(self, quantity: int) -> "Balance":
        return Balance(self.on_hand - quantity, self.reserved)

    def reserve(self, quantity: int) -> "Balance":
        return Balance(self.on_hand, self.reserved + quantity)

    def release(self, quantity: int, *, shipped: bool) -> "Balance":
        on_hand = self.on_hand - quantity if shipped else self.on_hand
        return Balance(on_hand, self.reserved - quantity)


def require_active(stock: dict[int, tuple[str, Balance]], warehouse_id: int) -> Balance:
    if warehouse_id not in stock:
        raise domain.receipts.ReceiptTargetNotFound("Active warehouse or product not found")
    return stock[warehouse_id][1]


def require_available(
    stock: dict[int, tuple[str, Balance]], warehouse_id: int, quantity: int
) -> Balance:
    balance = require_active(stock, warehouse_id)
    if balance.available < quantity:
        alternatives = [
            (name, other.available)
            for identifier, (name, other) in stock.items()
            if identifier != warehouse_id and other.available > 0
        ]
        raise domain.transfers.InsufficientStock(balance.available, alternatives)
    return balance
