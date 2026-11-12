import dataclasses


class InvalidName(ValueError):
    pass


class NameConflict(ValueError):
    pass


class WarehouseNotFound(LookupError):
    pass


def normalize_name(name: str) -> str:
    normalized = name.strip()
    if not normalized or len(normalized) > 120 or "\0" in normalized:
        raise InvalidName("Warehouse name must contain 1 to 120 characters without null bytes")
    return normalized


@dataclasses.dataclass(frozen=True)
class Warehouse:
    id: int
    name: str
    archived: bool


def require_active(warehouse: Warehouse | None) -> Warehouse:
    if warehouse is None or warehouse.archived:
        raise WarehouseNotFound("Active warehouse not found")
    return warehouse
