import datetime
import pathlib

import fastapi
import fastapi.responses
import fastapi.templating

import application.inventory

_ACTIONS = {
    "warehouse.create": "Создание склада",
    "warehouse.rename": "Переименование склада",
    "warehouse.archive": "Архивирование склада",
    "stock.receipt": "Приход",
}


def router(reader: application.inventory.InventoryReader) -> fastapi.APIRouter:
    routes = fastapi.APIRouter()
    templates = fastapi.templating.Jinja2Templates(
        directory=pathlib.Path(__file__).with_name("templates")
    )

    @routes.get("/", response_class=fastapi.responses.HTMLResponse, include_in_schema=False)
    def inventory(request: fastapi.Request) -> fastapi.responses.Response:
        return templates.TemplateResponse(
            request,
            "inventory.html",
            {"inventory": reader.read(), "actions": _ACTIONS, "utc": datetime.UTC},
        )

    return routes
