import typing

import domain.movements

type Action = typing.Literal["cancel", "dispatch"]


class ReservationNotFound(LookupError):
    pass


class ReservationClosed(ValueError):
    pass


def finish_reservation(
    state: domain.movements.State, action: Action
) -> domain.movements.State | None:
    target: domain.movements.State = "in_transit" if action == "dispatch" else "cancelled"
    if state == target:
        return None
    if state != "reserved":
        raise ReservationClosed("Reservation already closed")
    return target
