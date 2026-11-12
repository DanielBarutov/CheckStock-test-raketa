import dataclasses

import domain.receipts


@dataclasses.dataclass(frozen=True)
class Balance:
    on_hand: int = 0
    reserved: int = 0

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved

    def add(self, quantity: int) -> "Balance":
        on_hand = self.on_hand + quantity
        if on_hand > domain.receipts.MAX_QUANTITY:
            raise domain.receipts.StockLimit("Physical stock exceeds the supported quantity")
        return Balance(on_hand, self.reserved)
