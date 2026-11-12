class InvalidRoute(ValueError):
    pass


class TransferNotFound(LookupError):
    pass


class InsufficientStock(ValueError):
    def __init__(self, available: int, alternatives: list[tuple[str, int]]) -> None:
        self.available = available
        self.alternatives = alternatives
