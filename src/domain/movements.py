import dataclasses
import typing

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

    def is_in_transit(self) -> bool:
        return self.state == "in_transit"
