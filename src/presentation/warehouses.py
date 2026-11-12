import typing
import uuid

import fastapi
import pydantic

import application.warehouses
import domain.warehouses

Key = typing.Annotated[uuid.UUID, fastapi.Header(alias="Idempotency-Key")]
WarehouseId = typing.Annotated[int, fastapi.Path(gt=0, le=2**63 - 1)]


class WarehouseName(pydantic.BaseModel):
    name: str


def router(transaction: application.warehouses.Transaction) -> fastapi.APIRouter:
    routes = fastapi.APIRouter(prefix="/warehouses")

    def run(key: uuid.UUID, change: application.warehouses.Change) -> dict[str, int]:
        try:
            return {"id": application.warehouses.change_warehouse(transaction, key, change)}
        except domain.warehouses.InvalidName as error:
            raise fastapi.HTTPException(422, str(error)) from error
        except domain.warehouses.WarehouseNotFound as error:
            raise fastapi.HTTPException(404, str(error)) from error
        except (domain.warehouses.NameConflict, application.warehouses.KeyConflict) as error:
            raise fastapi.HTTPException(409, str(error)) from error

    @routes.post("", status_code=201)
    def create(body: WarehouseName, key: Key) -> dict[str, int]:
        return run(key, application.warehouses.Change("create", None, body.name))

    @routes.patch("/{warehouse_id}")
    def rename(warehouse_id: WarehouseId, body: WarehouseName, key: Key) -> dict[str, int]:
        return run(key, application.warehouses.Change("rename", warehouse_id, body.name))

    @routes.delete("/{warehouse_id}")
    def archive(warehouse_id: WarehouseId, key: Key) -> dict[str, int]:
        return run(key, application.warehouses.Change("archive", warehouse_id, None))

    return routes
