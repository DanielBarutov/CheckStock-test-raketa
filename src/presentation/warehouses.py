import typing
import uuid

import fastapi
import pydantic

import application.transactions
import application.warehouses
import domain.warehouses
import presentation.deps

Key = typing.Annotated[uuid.UUID, fastapi.Header(alias="Idempotency-Key")]
WarehouseId = typing.Annotated[int, fastapi.Path(gt=0, le=2**63 - 1)]


class WarehouseName(pydantic.BaseModel):
    name: str


router = fastapi.APIRouter(prefix="/warehouses")


def _run(
    transaction: presentation.deps.WarehousePort,
    key: uuid.UUID,
    change: application.warehouses.Change,
) -> dict[str, int]:
    try:
        return {"id": application.warehouses.change_warehouse(transaction, key, change)}
    except domain.warehouses.InvalidName as error:
        raise fastapi.HTTPException(422, str(error)) from error
    except domain.warehouses.WarehouseNotFound as error:
        raise fastapi.HTTPException(404, str(error)) from error
    except (domain.warehouses.NameConflict, application.transactions.KeyConflict) as error:
        raise fastapi.HTTPException(409, str(error)) from error


@router.post("", status_code=201)
def create(
    body: WarehouseName, key: Key, transaction: presentation.deps.WarehouseTransaction
) -> dict[str, int]:
    return _run(transaction, key, application.warehouses.Change("create", None, body.name))


@router.patch("/{warehouse_id}")
def rename(
    warehouse_id: WarehouseId,
    body: WarehouseName,
    key: Key,
    transaction: presentation.deps.WarehouseTransaction,
) -> dict[str, int]:
    return _run(transaction, key, application.warehouses.Change("rename", warehouse_id, body.name))


@router.delete("/{warehouse_id}")
def archive(
    warehouse_id: WarehouseId, key: Key, transaction: presentation.deps.WarehouseTransaction
) -> dict[str, int]:
    return _run(transaction, key, application.warehouses.Change("archive", warehouse_id, None))
