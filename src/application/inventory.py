import dataclasses
import datetime
import typing

import domain.stock


@dataclasses.dataclass(frozen=True)
class BalanceRow:
    sku: str
    product: str
    warehouse: str
    archived: bool
    stock: domain.stock.Balance

    @property
    def available(self) -> int:
        return 0 if self.archived else self.stock.available


@dataclasses.dataclass(frozen=True)
class HistoryEntry:
    occurred_at: datetime.datetime
    action: str
    sku: str | None
    quantity: int | None
    source: str | None
    destination: str | None


@dataclasses.dataclass(frozen=True)
class Option:
    id: int
    label: str


@dataclasses.dataclass(frozen=True)
class InTransit:
    id: int
    sku: str
    quantity: int
    source: str
    destination: str


@dataclasses.dataclass(frozen=True)
class Inventory:
    balances: list[BalanceRow]
    history: list[HistoryEntry]
    warehouses: list[Option]
    products: list[Option]
    transfers: list[InTransit]
    fbs_reserved: list[InTransit]
    fbs_in_transit: list[InTransit]
    fbo_in_transit: list[InTransit]
    fbo_received: list[InTransit]


class InventoryReader(typing.Protocol):
    def read(self) -> Inventory: ...
