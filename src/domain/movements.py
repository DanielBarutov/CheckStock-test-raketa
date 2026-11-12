import dataclasses
import typing

import domain.receipts
import domain.transfers

type Kind = typing.Literal["transfer", "fbs", "fbo"]
type State = typing.Literal["reserved", "cancelled", "in_transit", "received"]


@dataclasses.dataclass(frozen=True)
class Movement:
    kind: Kind
    state: State
    product_id: int
    quantity: int
    source: int
    destination: int | None = None

    @classmethod
    def start(
        cls, kind: Kind, product_id: int, quantity: int, source: int, destination: int | None = None
    ) -> "Movement":
        domain.receipts.validate_quantity(quantity)
        if kind == "transfer" and source == destination:
            raise domain.transfers.InvalidRoute("Source and destination must differ")
        return cls(
            kind,
            "reserved" if kind == "fbs" else "in_transit",
            product_id,
            quantity,
            source,
            destination,
        )

    def receive(self) -> State | None:
        return "received" if self.state == "in_transit" else None
