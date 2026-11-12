import collections.abc
import dataclasses
import hashlib
import json
import typing
import uuid

import domain.warehouses


class KeyConflict(ValueError):
    pass


type Action = typing.Literal["create", "rename", "archive"]


@dataclasses.dataclass(frozen=True)
class Change:
    action: Action
    warehouse_id: int | None
    name: str | None


class WarehouseWriter(typing.Protocol):
    def apply(self, change: Change) -> int: ...


class Transaction(typing.Protocol):
    def run(
        self,
        key: uuid.UUID,
        command: str,
        fingerprint: str,
        write: collections.abc.Callable[[WarehouseWriter], int],
    ) -> int: ...


def change_warehouse(
    transaction: Transaction,
    key: uuid.UUID,
    change: Change,
) -> int:
    if change.name is not None:
        change = dataclasses.replace(change, name=domain.warehouses.normalize_name(change.name))
    command = f"warehouse.{change.action}"
    payload = json.dumps([change.warehouse_id, change.name], ensure_ascii=False)
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    return transaction.run(key, command, fingerprint, lambda writer: writer.apply(change))
