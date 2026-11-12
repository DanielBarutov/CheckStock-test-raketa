import collections.abc
import html.parser
import io
import pathlib

import fastapi.testclient
import pytest
import sqlalchemy.engine

import infrastructure.seed


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
def demo(monkeypatch: pytest.MonkeyPatch, postgres: sqlalchemy.engine.Engine) -> None:
    path = pathlib.Path(__file__).parents[1] / "fixtures" / "demo_inventory.json"
    monkeypatch.setattr("sys.stdin", io.StringIO(path.read_text(encoding="utf-8")))
    infrastructure.seed.main()


def test_inventory_renders_empty_state(api: fastapi.testclient.TestClient) -> None:
    """Проверяет, что на чистой базе страница показывает пустые остатки и историю."""
    response = api.get("/")

    assert response.status_code == 200
    assert "Пока нет остатков" in response.text
    assert "Операций пока нет" in response.text


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
    receipts = [row for row in tables["history"] if row[1] == "Приход"]
    assert [tuple(row[2:]) for row in receipts] == [
        ("SKU-103", "4", "Внешний приход", "Юг"),
        ("SKU-102", "5", "Внешний приход", "Север"),
        ("SKU-101", "6", "Внешний приход", "Юг"),
        ("SKU-101", "10", "Внешний приход", "Север"),
    ]


def test_inventory_shows_archived_stock_and_keeps_historical_warehouse_name(
    api: fastapi.testclient.TestClient,
    demo: None,
    postgres: sqlalchemy.engine.Engine,
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
        tuple(row[2:]) for row in tables["history"] if row[1] == "Приход"
    }
