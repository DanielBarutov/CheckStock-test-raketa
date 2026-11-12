MAX_QUANTITY = 2**31 - 1


class InvalidQuantity(ValueError):
    pass


class StockLimit(ValueError):
    pass


class ReceiptTargetNotFound(LookupError):
    pass


def validate_quantity(quantity: int) -> None:
    if type(quantity) is not int or not 1 <= quantity <= MAX_QUANTITY:
        raise InvalidQuantity("Quantity must be a positive PostgreSQL integer")
