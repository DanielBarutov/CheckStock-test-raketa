import sqlalchemy as sa

import application.stock
import infrastructure.database.models as orm_models
import infrastructure.repositories.balances


class PostgresReceiptWriter(infrastructure.repositories.balances.PostgresBalances):
    def active_target_name(self, warehouse_id: int, product_id: int) -> str | None:
        query = (
            sa.select(orm_models.Warehouse.name)
            .join(orm_models.Product, orm_models.Product.id == product_id)
            .where(
                orm_models.Warehouse.id == warehouse_id, orm_models.Warehouse.archived_at.is_(None)
            )
        )
        return self.session.execute(query).scalar_one_or_none()

    def record_receipt(self, receipt: application.stock.StockRequest, destination_name: str) -> int:
        entry = orm_models.AuditEntry(
            action="stock.receipt",
            product_id=receipt.product_id,
            quantity=receipt.quantity,
            destination_warehouse_id=receipt.warehouse_id,
            source_name="External receipt",
            destination_name=destination_name,
        )
        self.session.add(entry)
        self.session.flush()
        return entry.id
