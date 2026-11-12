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
    def find(self, warehouse_id: int | None) -> domain.warehouses.Warehouse | None: ...
    def save_change(self, change: Change) -> int: ...
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
        previous = None
        if change.action != "create":
            previous = domain.warehouses.require_active(store.find(change.warehouse_id))
        warehouse_id = store.save_change(change)
        new_name = None if change.action == "archive" else change.name
        store.record_change(command, warehouse_id, previous.name if previous else None, new_name)
        return warehouse_id

    return transaction.run(key, command, fingerprint, write)
