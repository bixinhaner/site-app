import asyncio
import unittest

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register all model relationships
from app.api.work_orders import list_work_orders
from app.core.database import Base
from app.models.site import Site
from app.models.user import User
from app.models.work_order import (
    WorkOrder,
    WorkOrderPriorityEnum,
    WorkOrderStatusEnum,
    WorkOrderTypeEnum,
)


class WorkOrderListFilterTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self.user = User(
            id=1,
            username="manager",
            email="manager@example.com",
            hashed_password="test",
            full_name="Manager",
            is_active=True,
        )
        self.db.add_all(
            [
                self.user,
                Site(id=1, site_code="SITE-1", site_name="Site 1"),
                WorkOrder(
                    id="pending-order",
                    site_id=1,
                    title="Pending",
                    type=WorkOrderTypeEnum.OPENING_INSPECTION,
                    priority=WorkOrderPriorityEnum.NORMAL,
                    status=WorkOrderStatusEnum.PENDING,
                    assigned_by=1,
                    assigned_to=1,
                ),
                WorkOrder(
                    id="active-order",
                    site_id=1,
                    title="Active",
                    type=WorkOrderTypeEnum.MAINTENANCE,
                    priority=WorkOrderPriorityEnum.NORMAL,
                    status=WorkOrderStatusEnum.ACTIVE,
                    assigned_by=1,
                    assigned_to=1,
                ),
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _list(self, **overrides):
        params = {
            "status_filter": None,
            "status": None,
            "assigned_to": None,
            "type_filter": None,
            "type": None,
            "skip": 0,
            "limit": 100,
            "db": self.db,
            "current_user": self.user,
        }
        params.update(overrides)
        return asyncio.run(list_work_orders(**params))

    def test_legacy_status_alias_filters_instead_of_returning_all_rows(self):
        rows = self._list(status=WorkOrderStatusEnum.ACTIVE)
        self.assertEqual([row["id"] for row in rows], ["active-order"])

    def test_canonical_type_filter_is_preserved(self):
        rows = self._list(type_filter=WorkOrderTypeEnum.OPENING_INSPECTION)
        self.assertEqual([row["id"] for row in rows], ["pending-order"])

    def test_conflicting_aliases_are_rejected(self):
        with self.assertRaises(HTTPException) as context:
            self._list(
                status_filter=WorkOrderStatusEnum.PENDING,
                status=WorkOrderStatusEnum.ACTIVE,
            )
        self.assertEqual(context.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
