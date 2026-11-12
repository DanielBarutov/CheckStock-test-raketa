import typing
import uuid

import fastapi
import pydantic

import application.receipts
import application.stock
import application.transactions
import domain.receipts
import domain.stock
import presentation.deps

PositiveId = typing.Annotated[int, pydantic.Field(strict=True, gt=0, le=2**63 - 1)]


class ReceiptInput(pydantic.BaseModel):
    warehouse_id: PositiveId
    product_id: PositiveId
    quantity: pydantic.StrictInt


router = fastapi.APIRouter()


@router.post("/receipts", status_code=201)
def receive(
    body: ReceiptInput,
    transaction: presentation.deps.ReceiptTransaction,
    key: typing.Annotated[uuid.UUID, fastapi.Header(alias="Idempotency-Key")],
) -> dict[str, int]:
    receipt = application.stock.StockRequest(body.warehouse_id, body.product_id, body.quantity)
    try:
        return {"id": application.receipts.receive(transaction, key, receipt)}
    except domain.stock.InvalidQuantity as error:
        raise fastapi.HTTPException(422, str(error)) from error
    except domain.receipts.ReceiptTargetNotFound as error:
        raise fastapi.HTTPException(404, str(error)) from error
    except (domain.stock.StockLimit, application.transactions.KeyConflict) as error:
        raise fastapi.HTTPException(409, str(error)) from error
