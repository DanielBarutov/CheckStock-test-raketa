import re

import fastapi.testclient
import pytest
import sqlalchemy.engine


def form(html: str, action: str) -> str:
    return html.split(f'<form action="/inventory/{action}"', 1)[1].split("</form>", 1)[0]


def key_for(api: fastapi.testclient.TestClient, action: str) -> str:
    match = re.search(
        r'name="key" value="([^"]+)"', form(api.get("/inventory/operations").text, action)
    )
    assert match is not None
    return match[1]


def test_receipt_form_redirects_and_retry_keeps_stock_unchanged(
    api: fastapi.testclient.TestClient,
    warehouse_id: int,
    product_id: int,
    postgres: sqlalchemy.engine.Engine,
) -> None:
    """Проверяет, что приход из формы обновляет остаток один раз и возвращает в раздел операций."""
    data = {
        "key": key_for(api, "receive"),
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "quantity": 4,
    }
    for _ in range(2):
        response = api.post("/inventory/receive", data=data, follow_redirects=False)
        assert (
            response.status_code == 303
            and response.headers["location"] == "/inventory/operations?saved=1"
        )
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 4


def test_warehouse_forms_create_rename_and_archive_without_losing_stock(
    api: fastapi.testclient.TestClient, product_id: int, postgres: sqlalchemy.engine.Engine
) -> None:
    """Проверяет управление складом из браузера и исключение архива из новых приходов."""
    created = api.post("/inventory/create", data={"key": key_for(api, "create"), "name": "Запад"})
    assert created.status_code == 200
    with postgres.connect() as connection:
        warehouse_id = connection.exec_driver_sql("SELECT id FROM warehouses").scalar_one()
    selection = {"warehouse_id": warehouse_id}
    renamed = api.post(
        "/inventory/rename",
        data={**selection, "key": key_for(api, "rename"), "name": "Новый Запад"},
    )
    assert "Новый Запад" in form(renamed.text, "receive")
    receipt = {**selection, "key": key_for(api, "receive"), "product_id": product_id, "quantity": 3}
    assert api.post("/inventory/receive", data=receipt, follow_redirects=False).status_code == 303
    archived = api.post("/inventory/archive", data={**selection, "key": key_for(api, "archive")})
    assert archived.status_code == 200
    assert "Новый Запад" not in form(archived.text, "receive")
    assert "Операция сохранена" in archived.text
    assert "Новый Запад" in api.get("/").text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").scalar_one() == 3


@pytest.mark.parametrize(
    ("field", "value"), [("quantity", "0"), ("warehouse_id", "0"), ("key", "invalid")]
)
def test_invalid_receipt_form_returns_readable_error_without_writing_stock(
    api: fastapi.testclient.TestClient,
    warehouse_id: int,
    product_id: int,
    postgres: sqlalchemy.engine.Engine,
    field: str,
    value: str,
) -> None:
    """Проверяет, что неверные данные возвращают ошибку в HTML и не создают приход."""
    data = {
        "key": key_for(api, "receive"),
        "warehouse_id": warehouse_id,
        "product_id": product_id,
        "quantity": 4,
        field: value,
    }

    response = api.post("/inventory/receive", data=data)

    assert response.status_code == 422 and 'role="alert"' in response.text
    with postgres.connect() as connection:
        assert connection.exec_driver_sql("SELECT on_hand FROM stock_balances").first() is None


def test_form_rejects_cross_origin_submission(api: fastapi.testclient.TestClient) -> None:
    """Проверяет, что форма с чужого сайта не может создать склад."""
    data = {"key": key_for(api, "create"), "name": "Запад"}

    response = api.post("/inventory/create", data=data, headers={"Origin": "https://other.example"})

    assert response.status_code == 403
    assert "Запад" not in api.get("/inventory/operations").text
