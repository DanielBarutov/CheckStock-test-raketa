import collections.abc
import html.parser
import io
import pathlib
import re

import fastapi.testclient
import pytest
import sqlalchemy as sa

import seed


class TableRows(html.parser.HTMLParser):
    def __init__(self, document: str) -> None:
        super().__init__()
        self.tables: dict[str, list[list[str]]] = {}
        self.section = ""
        self.in_body = False
        self.cell: list[str] = []
        self.feed(document)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "section":
            self.section = dict(attrs).get("id") or ""
        if tag == "tbody":
            self.in_body = True
            self.tables[self.section] = []
        if self.in_body and tag == "tr":
            self.tables[self.section].append([])
        if self.in_body and tag in {"td", "th"}:
            self.cell = []

    def handle_data(self, data: str) -> None:
        self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_body and tag in {"td", "th"}:
            self.tables[self.section][-1].append(" ".join("".join(self.cell).split()))
        if tag == "tbody":
            self.in_body = False


@pytest.fixture
def demo(monkeypatch: pytest.MonkeyPatch, postgres: sa.engine.Engine) -> None:
    path = pathlib.Path(__file__).parents[1] / "fixtures" / "demo_inventory.json"
    monkeypatch.setattr("sys.stdin", io.StringIO(path.read_text(encoding="utf-8")))
    seed.main()


def test_inventory_renders_empty_state(api: fastapi.testclient.TestClient) -> None:
    """Проверяет, что на чистой базе страница показывает пустые остатки и историю."""
    response = api.get("/")

    assert response.status_code == 200
    assert "Пока нет остатков" in response.text
    assert "Операций пока нет" in api.get("/inventory/history").text


def test_inventory_lists_all_demo_pairs_and_receipt_history(
    api: fastapi.testclient.TestClient, demo: None
) -> None:
    """Проверяет шесть пар SKU и склада, включая нули, и четыре прихода с направлениями."""
    response = api.get("/")
    assert response.status_code == 200
    tables = TableRows(response.text).tables

    assert {tuple(row[:1] + row[2:]) for row in tables["balances"]} == {
        ("SKU-101", "Север", "10", "10", "0"),
        ("SKU-101", "Юг", "6", "6", "0"),
        ("SKU-102", "Север", "5", "5", "0"),
        ("SKU-102", "Юг", "0", "0", "0"),
        ("SKU-103", "Север", "0", "0", "0"),
        ("SKU-103", "Юг", "4", "4", "0"),
    }
    history = TableRows(api.get("/inventory/history").text).tables["history"]
    receipts = [row for row in history if row[1] == "Приход"]
    assert [tuple(row[2:]) for row in receipts] == [
        ("SKU-103", "4", "Внешний приход", "Юг"),
        ("SKU-102", "5", "Внешний приход", "Север"),
        ("SKU-101", "6", "Внешний приход", "Юг"),
        ("SKU-101", "10", "Внешний приход", "Север"),
    ]


def test_inventory_shows_archived_stock_and_keeps_historical_warehouse_name(
    api: fastapi.testclient.TestClient,
    demo: None,
    postgres: sa.engine.Engine,
    command_key: collections.abc.Callable[[], dict[str, str]],
) -> None:
    """Проверяет доступность до и после архивации и сохранение прежнего названия в истории."""
    with postgres.begin() as connection:
        warehouse_id = connection.exec_driver_sql(
            "SELECT id FROM warehouses WHERE name = 'Север'"
        ).scalar_one()
        connection.exec_driver_sql(
            "UPDATE stock_balances SET reserved = 2 WHERE warehouse_id = %s AND on_hand = 10",
            (warehouse_id,),
        )
    assert ["SKU-101", "Органайзер", "Север", "10", "8", "2"] in TableRows(
        api.get("/").text
    ).tables["balances"]
    path = f"/warehouses/{warehouse_id}"
    assert api.patch(path, json={"name": "Северный"}, headers=command_key()).status_code == 200
    assert api.delete(path, headers=command_key()).status_code == 200

    tables = TableRows(api.get("/").text).tables
    assert ["SKU-101", "Органайзер", "Северный Архив", "10", "0", "2"] in tables["balances"]
    assert ("SKU-101", "10", "Внешний приход", "Север") in {
        tuple(row[2:])
        for row in TableRows(api.get("/inventory/history").text).tables["history"]
        if row[1] == "Приход"
    }


def test_inventory_keeps_fbs_and_fbo_shipments_in_separate_sections(
    api: fastapi.testclient.TestClient,
    warehouse_id: int,
    product_id: int,
    command_key: collections.abc.Callable[[], dict[str, str]],
) -> None:
    """Проверяет раздельный показ FBS и FBO, когда обе отправки одновременно в пути."""
    stock = {"warehouse_id": warehouse_id, "product_id": product_id, "quantity": 5}
    assert api.post("/receipts", json=stock, headers=command_key()).status_code == 201
    reserve = {**stock, "quantity": 2, "key": command_key()["Idempotency-Key"]}
    assert (
        api.post("/inventory/fbs-reserve", data=reserve, follow_redirects=False).status_code == 303
    )
    page = api.get("/inventory/fbs")
    operation = re.search(r'name="operation_id" value="(\d+)"', page.text)
    assert operation is not None
    dispatch = {"operation_id": operation[1], "key": command_key()["Idempotency-Key"]}
    assert (
        api.post("/inventory/fbs-dispatch", data=dispatch, follow_redirects=False).status_code
        == 303
    )

    fbo = {**stock, "quantity": 3, "key": command_key()["Idempotency-Key"]}
    response = api.post("/inventory/fbo-dispatch", data=fbo)
    assert response.status_code == 200
    tables = TableRows(response.text).tables
    fbs = TableRows(api.get("/inventory/fbs").text).tables
    assert fbs["fbs"] == [["SKU", "Север", "2", "В пути к клиенту", "—"]]
    assert tables["fbo"][0][:4] == ["SKU", "Север", "3", "В пути на маркетплейс"]
    assert len(tables["fbo"]) == 1


def test_inventory_navigation_opens_one_section_per_page(
    api: fastapi.testclient.TestClient,
) -> None:
    """Проверяет отдельные страницы, ссылки меню и выделение текущего раздела."""
    pages = ("balances", "operations", "transfers", "fbs", "fbo", "history")
    for page in pages:
        path = "/" if page == "balances" else f"/inventory/{page}"
        response = api.get(path)
        assert response.status_code == 200
        assert response.text.count('aria-current="page"') == 1
        for section in pages:
            assert (f'<section id="{section}"' in response.text) == (section == page)
    assert api.get("/inventory/unknown").status_code == 404
