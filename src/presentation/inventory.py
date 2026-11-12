import datetime
import pathlib
import typing
import uuid

import fastapi
import fastapi.responses
import fastapi.templating

import application.fbo
import application.fbs
import application.inventory
import application.receipts
import application.transactions
import application.transfers
import application.warehouses
import domain.fbs
import domain.receipts
import domain.transfers
import domain.warehouses

_ACTIONS = {
    "warehouse.create": "Создание склада",
    "warehouse.rename": "Переименование склада",
    "warehouse.archive": "Архивирование склада",
    "stock.receipt": "Приход",
    "fbo.dispatch": "Отправка на маркетплейс FBO",
    "fbo.accept": "Приёмка на маркетплейсе FBO",
    "fbs.reserve": "Резерв FBS",
    "fbs.cancel": "Отмена резерва FBS",
    "fbs.dispatch": "Отправка клиенту FBS",
    "transfer.send": "Отправка между складами",
    "transfer.accept": "Приёмка перемещения",
}
_FORM_ERRORS: dict[type[Exception], tuple[int, str]] = {
    domain.transfers.InvalidRoute: (422, "Выберите разные склады."),
    domain.transfers.TransferNotFound: (404, "Перемещение не найдено."),
    domain.fbs.ReservationNotFound: (404, "Резерв не найден."),
    domain.fbs.ReservationClosed: (409, "Резерв уже закрыт."),
    application.fbo.ShipmentNotFound: (404, "Отправка FBO не найдена."),
    ValueError: (422, "Проверьте введённые данные."),
    domain.warehouses.InvalidName: (422, "Укажите название склада длиной от 1 до 120 символов."),
    domain.warehouses.NameConflict: (409, "Склад с таким названием уже существует."),
    domain.warehouses.WarehouseNotFound: (404, "Активный склад не найден."),
    domain.receipts.InvalidQuantity: (422, "Укажите положительное целое количество."),
    domain.receipts.ReceiptTargetNotFound: (404, "Активный склад или товар не найден."),
    domain.receipts.StockLimit: (409, "Операция превысит допустимый остаток."),
    application.transactions.KeyConflict: (409, "Форма уже отправлена с другими данными."),
}
type FormAction = typing.Literal[
    "receive",
    "create",
    "rename",
    "archive",
    "transfer-send",
    "transfer-accept",
    "fbs-reserve",
    "fbs-cancel",
    "fbs-dispatch",
    "fbo-dispatch",
    "fbo-accept",
]
FormText = typing.Annotated[str, fastapi.Form()]


def _identifier(value: str) -> int:
    identifier = int(value)
    if not 0 < identifier < 2**63:
        raise ValueError("Invalid identifier")
    return identifier


def router(
    reader: application.inventory.InventoryReader,
    warehouses: application.transactions.Transaction[application.warehouses.WarehouseWriter],
    receipts: application.transactions.Transaction[application.receipts.ReceiptWriter],
    transfers: application.transfers.Transaction,
    fbs: application.fbs.Transaction,
    fbo: application.fbo.Transaction,
) -> fastapi.APIRouter:
    routes = fastapi.APIRouter()
    templates = fastapi.templating.Jinja2Templates(
        directory=pathlib.Path(__file__).with_name("templates")
    )

    def render(
        request: fastapi.Request, error: str | None = None, status: int = 200
    ) -> fastapi.responses.Response:
        return templates.TemplateResponse(
            request,
            "inventory.html",
            {
                "inventory": reader.read(),
                "actions": _ACTIONS,
                "utc": datetime.UTC,
                "new_key": uuid.uuid4,
                "max_quantity": domain.receipts.MAX_QUANTITY,
                "error": error,
            },
            status_code=status,
            headers={"Cache-Control": "no-store"},
        )

    @routes.get("/", response_class=fastapi.responses.HTMLResponse, include_in_schema=False)
    def inventory(request: fastapi.Request) -> fastapi.responses.Response:
        return render(request)

    @routes.post("/inventory/{action}", include_in_schema=False)
    def submit(
        request: fastapi.Request,
        action: FormAction,
        key: FormText = "",
        warehouse_id: FormText = "",
        product_id: FormText = "",
        quantity: FormText = "",
        name: FormText = "",
        destination_id: FormText = "",
        operation_id: FormText = "",
    ) -> fastapi.responses.Response:
        origin = request.headers.get("origin")
        if origin is not None and origin != str(request.base_url).rstrip("/"):
            raise fastapi.HTTPException(403, "Cross-origin form submission")
        try:
            command_key = uuid.UUID(key)
            if action == "receive" or action == "fbs-reserve" or action == "fbo-dispatch":
                receipt = application.receipts.Receipt(
                    _identifier(warehouse_id), _identifier(product_id), int(quantity)
                )
                if action == "receive":
                    application.receipts.receive(receipts, command_key, receipt)
                elif action == "fbo-dispatch":
                    application.fbo.dispatch(fbo, command_key, receipt)
                else:
                    application.fbs.reserve(fbs, command_key, receipt)
            elif action == "transfer-send":
                transfer = application.transfers.Transfer(
                    _identifier(warehouse_id),
                    _identifier(destination_id),
                    _identifier(product_id),
                    int(quantity),
                )
                application.transfers.send(transfers, command_key, transfer)
            elif action == "transfer-accept":
                application.transfers.accept(transfers, command_key, _identifier(operation_id))
            elif action == "fbo-accept":
                application.fbo.accept(fbo, command_key, _identifier(operation_id))
            elif action == "fbs-cancel" or action == "fbs-dispatch":
                finish: application.fbs.Action = "cancel" if action == "fbs-cancel" else "dispatch"
                application.fbs.finish(fbs, command_key, _identifier(operation_id), finish)
            else:
                change = application.warehouses.Change(
                    action,
                    None if action == "create" else _identifier(warehouse_id),
                    None if action == "archive" else name,
                )
                application.warehouses.change_warehouse(warehouses, command_key, change)
        except domain.transfers.InsufficientStock as error:
            alternatives = ", ".join(f"{name}: {amount}" for name, amount in error.alternatives)
            message = f"На выбранном складе доступно: {error.available}."
            if alternatives:
                message += f" На других складах: {alternatives}."
            return render(request, message, 409)
        except tuple(_FORM_ERRORS) as error:
            status, message = _FORM_ERRORS[type(error)]
            return render(request, message, status)
        return fastapi.responses.RedirectResponse("/#balances", status_code=303)

    return routes
