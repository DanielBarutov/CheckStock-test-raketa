import datetime
import uuid

import sqlalchemy
import sqlalchemy.dialects.postgresql
import sqlalchemy.orm

import domain.movements


class Base(sqlalchemy.orm.DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "stores"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(primary_key=True)
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)


class Product(Base):
    __tablename__ = "products"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.Identity(always=True), primary_key=True
    )
    sku: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text, unique=True)
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.Identity(always=True), primary_key=True
    )
    name: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)
    archived_at: sqlalchemy.orm.Mapped[datetime.datetime | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.DateTime(timezone=True)
    )


class StockBalance(Base):
    __tablename__ = "stock_balances"

    warehouse_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("warehouses.id"), primary_key=True
    )
    product_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("products.id"), primary_key=True
    )
    on_hand: sqlalchemy.orm.Mapped[int]
    reserved: sqlalchemy.orm.Mapped[int]


class StockOperation(Base):
    __tablename__ = "stock_operations"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.Identity(always=True), primary_key=True
    )
    kind: sqlalchemy.orm.Mapped[domain.movements.Kind] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text
    )
    state: sqlalchemy.orm.Mapped[domain.movements.State] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text
    )
    product_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("products.id")
    )
    quantity: sqlalchemy.orm.Mapped[int]
    source_warehouse_id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("warehouses.id")
    )
    destination_warehouse_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("warehouses.id")
    )
    created_at: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.func.now()
    )
    updated_at: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        sqlalchemy.DateTime(timezone=True),
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.Identity(always=True), primary_key=True
    )
    created_at: sqlalchemy.orm.Mapped[datetime.datetime] = sqlalchemy.orm.mapped_column(
        sqlalchemy.DateTime(timezone=True), server_default=sqlalchemy.func.now()
    )
    action: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)
    operation_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("stock_operations.id")
    )
    product_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("products.id")
    )
    quantity: sqlalchemy.orm.Mapped[int | None]
    source_warehouse_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("warehouses.id")
    )
    destination_warehouse_id: sqlalchemy.orm.Mapped[int | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.BigInteger, sqlalchemy.ForeignKey("warehouses.id")
    )
    source_name: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)
    destination_name: sqlalchemy.orm.Mapped[str | None] = sqlalchemy.orm.mapped_column(
        sqlalchemy.Text
    )


class CommandReceipt(Base):
    __tablename__ = "command_receipts"

    idempotency_key: sqlalchemy.orm.Mapped[uuid.UUID] = sqlalchemy.orm.mapped_column(
        primary_key=True
    )
    command: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)
    fingerprint: sqlalchemy.orm.Mapped[str] = sqlalchemy.orm.mapped_column(sqlalchemy.Text)
    result: sqlalchemy.orm.Mapped[int] = sqlalchemy.orm.mapped_column(
        sqlalchemy.dialects.postgresql.JSONB
    )
