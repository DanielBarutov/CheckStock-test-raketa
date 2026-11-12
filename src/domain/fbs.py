class ReservationNotFound(LookupError):
    pass


class ReservationClosed(ValueError):
    pass
