"""Create CheckStock inventory schema."""

import alembic.op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    alembic.op.execute("""
        CREATE TABLE stores (
            id integer PRIMARY KEY CHECK (id = 1),
            name text NOT NULL
        );
        INSERT INTO stores (id, name) VALUES (1, 'Демо-магазин');

        CREATE TABLE products (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            sku text NOT NULL UNIQUE,
            name text NOT NULL
        );
        CREATE TABLE warehouses (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            name text NOT NULL CHECK (btrim(name) <> ''),
            archived_at timestamptz
        );
        CREATE UNIQUE INDEX active_warehouse_name
            ON warehouses (lower(btrim(name))) WHERE archived_at IS NULL;

        CREATE TABLE stock_balances (
            warehouse_id bigint REFERENCES warehouses,
            product_id bigint REFERENCES products,
            on_hand integer NOT NULL CHECK (on_hand >= 0),
            reserved integer NOT NULL CHECK (reserved BETWEEN 0 AND on_hand),
            PRIMARY KEY (warehouse_id, product_id)
        );
        CREATE TABLE stock_operations (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            product_id bigint NOT NULL REFERENCES products,
            kind text NOT NULL,
            state text NOT NULL,
            quantity integer NOT NULL CHECK (quantity > 0),
            source_warehouse_id bigint NOT NULL REFERENCES warehouses,
            destination_warehouse_id bigint REFERENCES warehouses,
            created_at timestamptz NOT NULL DEFAULT now(),
            updated_at timestamptz NOT NULL DEFAULT now(),
            CHECK (
                (kind IN ('transfer', 'fbo') AND state IN ('in_transit', 'received'))
                OR (kind = 'fbs' AND state IN ('reserved', 'cancelled', 'in_transit'))
            ),
            CHECK ((kind = 'transfer') = (destination_warehouse_id IS NOT NULL)),
            CHECK (source_warehouse_id <> destination_warehouse_id)
        );
        CREATE INDEX stock_operations_by_state ON stock_operations (kind, state, product_id);

        CREATE TABLE audit_entries (
            id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            created_at timestamptz NOT NULL DEFAULT now(),
            action text NOT NULL,
            operation_id bigint REFERENCES stock_operations,
            product_id bigint REFERENCES products,
            quantity integer CHECK (quantity > 0),
            source_warehouse_id bigint REFERENCES warehouses,
            destination_warehouse_id bigint REFERENCES warehouses,
            source_name text,
            destination_name text,
            CHECK ((product_id IS NULL) = (quantity IS NULL))
        );
        CREATE INDEX audit_entries_by_time ON audit_entries (created_at, id);

        CREATE TABLE command_receipts (
            idempotency_key uuid PRIMARY KEY,
            command text NOT NULL,
            fingerprint text NOT NULL,
            result jsonb NOT NULL
        );
    """)


def downgrade() -> None:
    alembic.op.execute("""
        DROP TABLE command_receipts, audit_entries, stock_operations,
            stock_balances, warehouses, products, stores;
    """)
