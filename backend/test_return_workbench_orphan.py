"""退库工作台：关联出库单已被物理删除时不应 500。"""
import asyncio
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.stock as stock
from app.core.database import Base
from app.models.equipment import StockTransaction, TransactionTypeEnum, Warehouse
from app.models.user import User

ADMIN = SimpleNamespace(id=1, role="admin", is_admin=True)


def test_workbench_tolerates_missing_out_transaction(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            User(id=1, username="admin", email="a@example.com", hashed_password="x"),
            Warehouse(id=1, warehouse_code="WH1", warehouse_name="Main"),
            StockTransaction(
                id="ret1",
                transaction_type=TransactionTypeEnum.RETURN,
                warehouse_id=1,
                operator_id=1,
                document_number="RET-1",
                related_transaction_id="deleted-out-id",
                approval_status="pending",
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(stock, "_ensure_inventory_workbench_scope", lambda *a, **k: None)
    monkeypatch.setattr(stock, "_get_managed_warehouse_ids", lambda db, user: None)

    res = asyncio.run(stock.list_return_workbench_batches(status_filter="all", db=db, current_user=ADMIN))
    docs = [d for b in res["records"] for d in b["documents"]]
    assert docs and docs[0]["out_document_number"] is None
