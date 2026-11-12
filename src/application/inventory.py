import dataclasses
import datetime
import typing


@dataclasses.dataclass(frozen=True)
class Balance:
    sku: str
    product: str
    warehouse: str
    archived: bool
    on_hand: int
    available: int
    reserved: int


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
    balances: list[Balance]
    history: list[HistoryEntry]
    warehouses: list[Option]
    products: list[Option]
    transfers: list[InTransit]
    fbs_reserved: list[InTransit]
    fbs_in_transit: list[InTransit]


class InventoryReader(typing.Protocol):
    def read(self) -> Inventory: ...
