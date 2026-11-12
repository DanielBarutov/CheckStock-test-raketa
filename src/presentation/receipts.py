import typing
import uuid

import fastapi
import pydantic

import application.receipts
import application.stock
import application.transactions
import domain.receipts

PositiveId = typing.Annotated[int, pydantic.Field(strict=True, gt=0, le=2**63 - 1)]


class ReceiptInput(pydantic.BaseModel):
    warehouse_id: PositiveId
    product_id: PositiveId
    quantity: pydantic.StrictInt


def router(
    transaction: application.transactions.Transaction[application.receipts.ReceiptWriter],
) -> fastapi.APIRouter:
    routes = fastapi.APIRouter()

    @routes.post("/receipts", status_code=201)
    def receive(
        body: ReceiptInput,
        key: typing.Annotated[uuid.UUID, fastapi.Header(alias="Idempotency-Key")],
    ) -> dict[str, int]:
        receipt = application.stock.StockRequest(body.warehouse_id, body.product_id, body.quantity)
        try:
            return {"id": application.receipts.receive(transaction, key, receipt)}
        except domain.receipts.InvalidQuantity as error:
            raise fastapi.HTTPException(422, str(error)) from error
        except domain.receipts.ReceiptTargetNotFound as error:
            raise fastapi.HTTPException(404, str(error)) from error
        except (domain.receipts.StockLimit, application.transactions.KeyConflict) as error:
            raise fastapi.HTTPException(409, str(error)) from error

    return routes
