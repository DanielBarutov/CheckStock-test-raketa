import enum

import domain.movements


class Action(enum.StrEnum):
    CANCEL = "cancel"
    DISPATCH = "dispatch"


class ReservationNotFound(LookupError):
    pass


class ReservationClosed(ValueError):
    pass


def finish_reservation(
    state: domain.movements.State, action: Action
) -> domain.movements.State | None:
    target = (
        domain.movements.State.IN_TRANSIT
        if action == "dispatch"
        else domain.movements.State.CANCELLED
    )
    if state is target:
        return None
    if state is not domain.movements.State.RESERVED:
        raise ReservationClosed("Reservation already closed")
    return target
