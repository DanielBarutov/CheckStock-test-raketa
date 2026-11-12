import datetime
import uuid

import sqlalchemy as sa
import sqlalchemy.dialects.postgresql as sa_pg
import sqlalchemy.orm as sa_orm


class Base(sa_orm.DeclarativeBase):
    pass


class Store(Base):
    __tablename__ = "stores"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(primary_key=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)


class Product(Base):
    __tablename__ = "products"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    sku: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text, unique=True)
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)


class Warehouse(Base):
    __tablename__ = "warehouses"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    name: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    archived_at: sa_orm.Mapped[datetime.datetime | None] = sa_orm.mapped_column(
        sa_pg.TIMESTAMP(timezone=True)
    )


class StockBalance(Base):
    __tablename__ = "stock_balances"

    warehouse_id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("warehouses.id"), primary_key=True
    )
    product_id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("products.id"), primary_key=True
    )
    on_hand: sa_orm.Mapped[int]
    reserved: sa_orm.Mapped[int]


class StockOperation(Base):
    __tablename__ = "stock_operations"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    kind: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    state: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    product_id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("products.id")
    )
    quantity: sa_orm.Mapped[int]
    source_warehouse_id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("warehouses.id")
    )
    destination_warehouse_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("warehouses.id")
    )
    created_at: sa_orm.Mapped[datetime.datetime] = sa_orm.mapped_column(
        sa_pg.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )
    updated_at: sa_orm.Mapped[datetime.datetime] = sa_orm.mapped_column(
        sa_pg.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )


class AuditEntry(Base):
    __tablename__ = "audit_entries"

    id: sa_orm.Mapped[int] = sa_orm.mapped_column(
        sa.BigInteger, sa.Identity(always=True), primary_key=True
    )
    created_at: sa_orm.Mapped[datetime.datetime] = sa_orm.mapped_column(
        sa_pg.TIMESTAMP(timezone=True),
        server_default=sa.func.now(),
    )
    action: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    operation_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("stock_operations.id")
    )
    product_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("products.id")
    )
    quantity: sa_orm.Mapped[int | None]
    source_warehouse_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("warehouses.id")
    )
    destination_warehouse_id: sa_orm.Mapped[int | None] = sa_orm.mapped_column(
        sa.BigInteger, sa.ForeignKey("warehouses.id")
    )
    source_name: sa_orm.Mapped[str | None] = sa_orm.mapped_column(sa.Text)
    destination_name: sa_orm.Mapped[str | None] = sa_orm.mapped_column(sa.Text)


class CommandReceipt(Base):
    __tablename__ = "command_receipts"

    idempotency_key: sa_orm.Mapped[uuid.UUID] = sa_orm.mapped_column(primary_key=True)
    command: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    fingerprint: sa_orm.Mapped[str] = sa_orm.mapped_column(sa.Text)
    result: sa_orm.Mapped[int] = sa_orm.mapped_column(sa_pg.JSONB)
