import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register model relationships
from app.api.dashboard import _build_site_device_progress_metrics
from app.core.database import Base
from app.models.equipment_binding_history import (
    BindingActionEnum,
    EquipmentBindingHistory,
)
from app.models.inspection import (
    InspectionCheckItem,
    InspectionTemplate,
    SiteInspection,
)
from app.models.omc_state import OmcDeviceState
from app.models.planning import SitePlanning, SitePlanningCell
from app.models.site import Site
from app.models.user import User
from app.models.work_order import (
    WorkOrder,
    WorkOrderPriorityEnum,
    WorkOrderStatusEnum,
    WorkOrderTypeEnum,
)
from app.services.omc_state import summarize_site_binding_slots_for_sites
from app.services.omc_state import get_opening_expected_device_slots_for_sites


class DashboardBatchProgressTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.query_count = 0

        def count_query(*_args, **_kwargs):
            self.query_count += 1

        self._count_query = count_query
        event.listen(self.engine, "before_cursor_execute", self._count_query)
        self._seed_data()

    def tearDown(self):
        event.remove(self.engine, "before_cursor_execute", self._count_query)
        self.db.close()
        self.engine.dispose()

    def _seed_data(self):
        user = User(
            id=1,
            username="admin",
            email="admin@example.com",
            hashed_password="test",
            full_name="Admin",
            is_active=True,
        )
        sites = [
            Site(id=1, site_code="SITE-1", site_name="Site 1"),
            Site(id=2, site_code="SITE-2", site_name="Site 2"),
            Site(id=3, site_code="SITE-3", site_name="Site 3"),
        ]
        template = InspectionTemplate(
            id="template-1",
            template_name="Opening",
            template_data={},
            created_by=1,
        )
        opening_order = WorkOrder(
            id="opening-order-1",
            site_id=1,
            title="Opening Site 1",
            type=WorkOrderTypeEnum.OPENING_INSPECTION,
            priority=WorkOrderPriorityEnum.NORMAL,
            status=WorkOrderStatusEnum.ACTIVE,
            assigned_by=1,
            assigned_to=1,
        )
        expansion_order = WorkOrder(
            id="expansion-order-1",
            site_id=1,
            title="Expansion Site 1",
            type=WorkOrderTypeEnum.CELL_EXPANSION,
            priority=WorkOrderPriorityEnum.NORMAL,
            status=WorkOrderStatusEnum.ACTIVE,
            assigned_by=1,
            assigned_to=1,
        )
        opening_inspection = SiteInspection(
            id="opening-inspection-1",
            site_id=1,
            work_order_id=opening_order.id,
            template_id=template.id,
            inspector_id=1,
        )
        expansion_inspection = SiteInspection(
            id="expansion-inspect-1",
            site_id=1,
            work_order_id=expansion_order.id,
            template_id=template.id,
            inspector_id=1,
        )
        opening_items = [
            InspectionCheckItem(
                id="opening-item-1",
                inspection_id=opening_inspection.id,
                item_id="slot-1",
                item_name="Slot 1",
                sector_id="1",
                band="N41",
                is_active=True,
            ),
            InspectionCheckItem(
                id="opening-item-2",
                inspection_id=opening_inspection.id,
                item_id="slot-2",
                item_name="Slot 2",
                sector_id="2",
                band="N41",
                is_active=True,
            ),
            InspectionCheckItem(
                id="opening-item-inactive",
                inspection_id=opening_inspection.id,
                item_id="slot-3",
                item_name="Inactive slot",
                sector_id="3",
                band="N41",
                is_active=False,
            ),
        ]
        expansion_item = InspectionCheckItem(
            id="expansion-item-1",
            inspection_id=expansion_inspection.id,
            item_id="slot-1-expansion",
            item_name="Expansion Slot 1",
            sector_id="1",
            band="N41",
            is_active=True,
        )

        planning_1 = SitePlanning(
            id=1,
            site_id=1,
            version=1,
            bands=["N41"],
            is_current=True,
        )
        planning_2 = SitePlanning(
            id=2,
            site_id=2,
            version=1,
            bands=["N41"],
            is_current=True,
        )
        planning_cells = [
            SitePlanningCell(
                planning_id=planning_1.id,
                site_id=1,
                local_cell_id=slot,
                band_code="N41",
                frequency=500000 + slot,
            )
            for slot in (1, 2, 11, 12)
        ]
        planning_cells.append(
            SitePlanningCell(
                planning_id=planning_2.id,
                site_id=2,
                local_cell_id=1,
                band_code="N41",
                frequency=500001,
            )
        )

        self.db.add(user)
        self.db.add_all(sites)
        self.db.add(template)
        self.db.add_all([opening_order, expansion_order])
        self.db.add_all([opening_inspection, expansion_inspection])
        self.db.add_all(opening_items + [expansion_item])
        self.db.add_all([planning_1, planning_2] + planning_cells)
        self.db.flush()

        started = datetime(2026, 1, 1, 0, 0, 0)
        bindings = [
            EquipmentBindingHistory(
                id=1,
                inspection_id=opening_inspection.id,
                check_item_id="opening-item-1",
                site_id=1,
                sector_id="1",
                band="N41",
                cell_id="1_N41",
                equipment_sn="SN-OLD",
                action=BindingActionEnum.BIND,
                operator_id=1,
                operated_at=started,
            ),
            EquipmentBindingHistory(
                id=2,
                inspection_id=opening_inspection.id,
                check_item_id="opening-item-1",
                site_id=1,
                sector_id="1",
                band="N41",
                cell_id="1_N41",
                equipment_sn="SN-1",
                action=BindingActionEnum.REBIND,
                operator_id=1,
                operated_at=started + timedelta(minutes=1),
            ),
            EquipmentBindingHistory(
                id=3,
                inspection_id=opening_inspection.id,
                check_item_id="opening-item-2",
                site_id=1,
                sector_id="2",
                band="N41",
                cell_id="2_N41",
                equipment_sn="SN-2",
                action=BindingActionEnum.BIND,
                operator_id=1,
                operated_at=started + timedelta(minutes=2),
            ),
            EquipmentBindingHistory(
                id=4,
                inspection_id=expansion_inspection.id,
                check_item_id="expansion-item-1",
                site_id=1,
                sector_id="1",
                band="N41",
                cell_id="1_N41",
                equipment_sn="SN-EXPANSION",
                action=BindingActionEnum.REBIND,
                operator_id=1,
                operated_at=started + timedelta(minutes=3),
            ),
        ]
        self.db.add_all(bindings)
        self.db.add_all(
            [
                OmcDeviceState(sn="SN-1", ever_online=True, ever_activated=False),
                OmcDeviceState(sn="SN-2", ever_online=True, ever_activated=True),
                OmcDeviceState(
                    sn="SN-EXPANSION",
                    ever_online=True,
                    ever_activated=True,
                ),
            ]
        )
        self.db.commit()

    def test_bulk_summary_preserves_opening_baseline_and_latest_binding(self):
        self.query_count = 0
        opening_slots = get_opening_expected_device_slots_for_sites(self.db, [1, 2])
        self.assertEqual(opening_slots[2], [])

        self.query_count = 0
        summaries = summarize_site_binding_slots_for_sites(
            self.db,
            [1, 2, 3],
            opening_only=True,
        )

        site_1 = summaries[1]
        self.assertEqual(site_1["expected_slot_count"], 2)
        self.assertEqual(site_1["bound_slot_count"], 2)
        self.assertEqual(
            [row.equipment_sn for row in site_1["rows"]],
            ["SN-1", "SN-2"],
        )
        self.assertNotIn("SN-EXPANSION", [row.equipment_sn for row in site_1["all_rows"]])

        self.assertEqual(summaries[2]["expected_slot_count"], 1)
        self.assertEqual(summaries[2]["bound_slot_count"], 0)
        self.assertEqual(summaries[3]["expected_slot_count"], 0)
        self.assertLessEqual(self.query_count, 6)

    def test_dashboard_device_metrics_use_constant_query_count(self):
        self.query_count = 0
        metrics = _build_site_device_progress_metrics(self.db)

        self.assertEqual(metrics[1]["denominator"], 2)
        self.assertEqual(metrics[1]["slot_sns"], ["SN-1", "SN-2"])
        self.assertEqual(metrics[1]["online_devices"], 2)
        self.assertEqual(metrics[1]["activated_devices"], 1)
        self.assertEqual(metrics[2]["denominator"], 1)
        self.assertEqual(metrics[3]["denominator"], 0)
        self.assertLessEqual(self.query_count, 8)

    def test_bulk_summary_does_not_add_one_query_per_site(self):
        extra_sites = [
            Site(id=site_id, site_code=f"SITE-{site_id}", site_name=f"Site {site_id}")
            for site_id in range(4, 104)
        ]
        self.db.add_all(extra_sites)
        self.db.commit()

        self.query_count = 0
        summaries = summarize_site_binding_slots_for_sites(
            self.db,
            range(1, 104),
            opening_only=True,
        )

        self.assertEqual(len(summaries), 103)
        self.assertEqual(summaries[103]["expected_slot_count"], 0)
        self.assertLessEqual(self.query_count, 6)


if __name__ == "__main__":
    unittest.main()
