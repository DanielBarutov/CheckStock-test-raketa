import collections.abc
import itertools
import subprocess
import time
import uuid

import fastapi.testclient
import pytest
import sqlalchemy as sa

import main


@pytest.fixture(scope="session")
def postgres_url() -> collections.abc.Iterator[sa.engine.URL]:
    run = ["docker", "run", "--rm", "-d", "-p", "127.0.0.1::5432", "-e"]
    container = subprocess.check_output(
        [*run, "POSTGRES_PASSWORD=checkstock", "postgres:18"], text=True
    ).strip()
    try:
        port = ["docker", "port", container, "5432/tcp"]
        address = subprocess.check_output(port, text=True).strip()
        url = sa.engine.make_url(f"postgresql+psycopg://postgres:checkstock@{address}/postgres")
        ready = ["docker", "exec", container, "pg_isready", "-h", "127.0.0.1"]
        for _ in range(30):
            if subprocess.run(ready, check=False, capture_output=True).returncode == 0:
                break
            time.sleep(0.5)
        else:
            pytest.fail("PostgreSQL did not become ready")
        yield url
    finally:
        subprocess.run(["docker", "rm", "-f", container], check=True, capture_output=True)


@pytest.fixture
def postgres(
    postgres_url: sa.engine.URL, monkeypatch: pytest.MonkeyPatch
) -> collections.abc.Iterator[sa.engine.Engine]:
    admin = sa.create_engine(postgres_url, isolation_level="AUTOCOMMIT")
    engine = sa.create_engine(postgres_url.set(database="checkstock_test"))
    try:
        with admin.connect() as connection:
            connection.exec_driver_sql("CREATE DATABASE checkstock_test")
        monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
        subprocess.run(["alembic", "upgrade", "head"], check=True, capture_output=True)
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.exec_driver_sql("DROP DATABASE IF EXISTS checkstock_test")
        admin.dispose()


@pytest.fixture
def api(
    postgres: sa.engine.Engine,
) -> collections.abc.Iterator[fastapi.testclient.TestClient]:
    with fastapi.testclient.TestClient(main.create_app(), raise_server_exceptions=False) as client:
        yield client


@pytest.fixture
def command_key() -> collections.abc.Callable[[], dict[str, str]]:
    keys = itertools.count(1)
    return lambda: {"Idempotency-Key": str(uuid.UUID(int=next(keys)))}


@pytest.fixture
def warehouse_id(
    api: fastapi.testclient.TestClient, command_key: collections.abc.Callable[[], dict[str, str]]
) -> int:
    response = api.post("/warehouses", json={"name": " Север "}, headers=command_key())
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


@pytest.fixture
def product_id(postgres: sa.engine.Engine) -> int:
    with postgres.begin() as connection:
        result = connection.exec_driver_sql(
            "INSERT INTO products (sku, name) VALUES ('SKU', 'Test') RETURNING id"
        )
        return int(result.scalar_one())
