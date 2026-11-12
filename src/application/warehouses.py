import dataclasses
import typing
import uuid

import application.transactions
import domain.warehouses

type Action = typing.Literal["create", "rename", "archive"]


@dataclasses.dataclass(frozen=True)
class Change:
    action: Action
    warehouse_id: int | None
    name: str | None


class WarehouseWriter(typing.Protocol):
    def apply(self, change: Change) -> int: ...


def change_warehouse(
    transaction: application.transactions.Transaction[WarehouseWriter],
    key: uuid.UUID,
    change: Change,
) -> int:
    if change.name is not None:
        change = dataclasses.replace(change, name=domain.warehouses.normalize_name(change.name))
    command = f"warehouse.{change.action}"
    fingerprint = application.transactions.fingerprint(change.warehouse_id, change.name)
    return transaction.run(key, command, fingerprint, lambda writer: writer.apply(change))
