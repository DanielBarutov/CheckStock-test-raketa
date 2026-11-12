import dataclasses
import enum

import domain.stock
import domain.transfers


class Kind(enum.StrEnum):
    TRANSFER = "transfer"
    FBS = "fbs"
    FBO = "fbo"


class State(enum.StrEnum):
    RESERVED = "reserved"
    CANCELLED = "cancelled"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"


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
        domain.stock.validate_quantity(quantity)
        if kind is Kind.TRANSFER and source == destination:
            raise domain.transfers.InvalidRoute("Source and destination must differ")
        return cls(
            kind,
            State.RESERVED if kind is Kind.FBS else State.IN_TRANSIT,
            product_id,
            quantity,
            source,
            destination,
        )

    def receive(self) -> State | None:
        return State.RECEIVED if self.state is State.IN_TRANSIT else None
