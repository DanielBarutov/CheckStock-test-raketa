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
    def save_change(self, change: Change) -> tuple[int, str | None, str | None] | None: ...
    def record_change(
        self, action: str, warehouse_id: int, old_name: str | None, new_name: str | None
    ) -> None: ...


def change_warehouse(
    transaction: application.transactions.Transaction[WarehouseWriter],
    key: uuid.UUID,
    change: Change,
) -> int:
    if change.name is not None:
        change = dataclasses.replace(change, name=domain.warehouses.normalize_name(change.name))
    command = f"warehouse.{change.action}"
    fingerprint = application.transactions.fingerprint(change.warehouse_id, change.name)

    def write(store: WarehouseWriter) -> int:
        result = store.save_change(change)
        if result is None:
            raise domain.warehouses.WarehouseNotFound("Active warehouse not found")
        warehouse_id, old_name, new_name = result
        store.record_change(command, warehouse_id, old_name, new_name)
        return warehouse_id

    return transaction.run(key, command, fingerprint, write)
