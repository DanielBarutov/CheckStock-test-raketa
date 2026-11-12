import sqlalchemy
import sqlalchemy.orm

import application.inventory
import domain.stock
import infrastructure.database.db
import infrastructure.database.models as orm_models


class PostgresInventoryReader:
    def __init__(self, sessions: infrastructure.database.db.SessionFactory) -> None:
        self.sessions = sessions

    def read(self) -> application.inventory.Inventory:
        product = orm_models.Product
        warehouse = orm_models.Warehouse
        balance = orm_models.StockBalance
        audit = orm_models.AuditEntry
        operation = orm_models.StockOperation
        destination = sqlalchemy.orm.aliased(warehouse)

        with self.sessions() as session:
            balances_query = (
                sqlalchemy.select(
                    product.sku,
                    product.name,
                    warehouse.name,
                    warehouse.archived_at.is_not(None),
                    sqlalchemy.func.coalesce(balance.on_hand, 0),
                    sqlalchemy.func.coalesce(balance.reserved, 0),
                )
                .select_from(product)
                .join(warehouse, sqlalchemy.true())
                .outerjoin(
                    balance,
                    (balance.product_id == product.id) & (balance.warehouse_id == warehouse.id),
                )
                .order_by(
                    product.sku, warehouse.archived_at.is_not(None), warehouse.name, warehouse.id
                )
            )
            balances = [
                application.inventory.Balance(
                    sku, name, site, archived, domain.stock.Balance(on_hand, reserved)
                )
                for sku, name, site, archived, on_hand, reserved in session.execute(balances_query)
            ]
            history_query = (
                sqlalchemy.select(
                    audit.created_at,
                    audit.action,
                    product.sku,
                    audit.quantity,
                    audit.source_name,
                    audit.destination_name,
                )
                .outerjoin(product, product.id == audit.product_id)
                .order_by(audit.created_at.desc(), audit.id.desc())
            )
            history = [
                application.inventory.HistoryEntry(*row) for row in session.execute(history_query)
            ]
            active = (
                sqlalchemy.select(warehouse.id, warehouse.name)
                .where(warehouse.archived_at.is_(None))
                .order_by(warehouse.name, warehouse.id)
            )
            catalog = sqlalchemy.select(product.id, product.sku + " · " + product.name).order_by(
                product.sku
            )
            warehouses = [application.inventory.Option(*row) for row in session.execute(active)]
            products = [application.inventory.Option(*row) for row in session.execute(catalog)]

            movement_query = (
                sqlalchemy.select(
                    operation.kind,
                    operation.state,
                    operation.id,
                    product.sku,
                    operation.quantity,
                    warehouse.name,
                    destination.name,
                )
                .select_from(operation)
                .join(product, product.id == operation.product_id)
                .join(warehouse, warehouse.id == operation.source_warehouse_id)
                .outerjoin(destination, destination.id == operation.destination_warehouse_id)
                .where(
                    sqlalchemy.tuple_(operation.kind, operation.state).in_(
                        [
                            ("transfer", "in_transit"),
                            ("fbs", "reserved"),
                            ("fbs", "in_transit"),
                            ("fbo", "in_transit"),
                            ("fbo", "received"),
                        ]
                    )
                )
                .order_by(operation.id)
            )
            movements = session.execute(movement_query).all()

        external = {"fbs": "Клиент FBS", "fbo": "Маркетплейс FBO"}
        by_status: dict[tuple[str, str], list[application.inventory.InTransit]] = {}
        for kind, state, identifier, sku, quantity, source, target in movements:
            label = target if target is not None else external[kind]
            by_status.setdefault((kind, state), []).append(
                application.inventory.InTransit(identifier, sku, quantity, source, label)
            )
        return application.inventory.Inventory(
            balances,
            history,
            warehouses,
            products,
            by_status.get(("transfer", "in_transit"), []),
            by_status.get(("fbs", "reserved"), []),
            by_status.get(("fbs", "in_transit"), []),
            by_status.get(("fbo", "in_transit"), []),
            by_status.get(("fbo", "received"), []),
        )
