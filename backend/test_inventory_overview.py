import asyncio
import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 - register model relationships
from app.core.database import Base
from app.api.stock import get_inventory_dashboard, get_inventory_list
from app.models.equipment import (
    Equipment,
    EquipmentCategoryEnum,
    EquipmentInstance,
    EquipmentStatusEnum,
    Inventory,
    InventoryStatusEnum,
    StockTransaction,
    StockTransactionItem,
    TransactionTypeEnum,
    Warehouse,
)
from app.models.inspection import (
    InspectionCheckItem,
    InspectionTemplate,
    SiteInspection,
)
from app.models.site import Site
from app.models.user import User
from app.services.inventory_overview_service import (
    get_auxiliary_inventory_details,
    get_auxiliary_inventory_overview,
    get_main_inventory_instances,
    get_main_inventory_overview,
)


class InventoryOverviewTestCase(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(bind=self.engine)
        self.db = sessionmaker(bind=self.engine)()
        self._seed()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _seed(self):
        now = datetime(2026, 8, 10, 8, 0, 0)
        user = User(
            id=1,
            username="installer",
            email="installer@example.com",
            hashed_password="test",
            full_name="Installer One",
            is_active=True,
        )
        warehouses = [
            Warehouse(
                id=1,
                warehouse_code="WH-A",
                warehouse_name="Warehouse A",
                status=EquipmentStatusEnum.ACTIVE,
            ),
            Warehouse(
                id=2,
                warehouse_code="WH-B",
                warehouse_name="Warehouse B",
                status=EquipmentStatusEnum.ACTIVE,
            ),
        ]
        equipment = [
            Equipment(
                id=1,
                equipment_code="MAIN-1",
                equipment_name="Aurora",
                category=EquipmentCategoryEnum.MAIN_DEVICE,
                unit="台",
            ),
            Equipment(
                id=2,
                equipment_code="MAIN-ZERO",
                equipment_name="Zero Device",
                category=EquipmentCategoryEnum.MAIN_DEVICE,
                unit="台",
            ),
            Equipment(
                id=3,
                equipment_code="AUX-CABLE",
                equipment_name="DC Cable",
                category=EquipmentCategoryEnum.AUXILIARY,
                unit="米",
            ),
            Equipment(
                id=4,
                equipment_code="AUX-BOLT",
                equipment_name="Bolt",
                category=EquipmentCategoryEnum.AUXILIARY,
                unit="个",
            ),
        ]
        self.db.add(user)
        self.db.add_all(warehouses + equipment)
        self.db.flush()

        instances = [
            EquipmentInstance(
                id="main-in-stock",
                equipment_id=1,
                barcode="BC-1",
                serial_number="SN-IN-STOCK",
                status=InventoryStatusEnum.IN_STOCK,
                warehouse_id=1,
                updated_at=now,
            ),
            EquipmentInstance(
                id="main-issued",
                equipment_id=1,
                barcode="BC-2",
                serial_number="SN-ISSUED",
                status=InventoryStatusEnum.ISSUED,
                warehouse_id=None,
                issued_to=1,
                issued_date=now + timedelta(minutes=1),
            ),
            EquipmentInstance(
                id="main-pending",
                equipment_id=1,
                barcode="BC-3",
                serial_number="SN-PENDING",
                status=InventoryStatusEnum.PENDING_INSPECTION,
                warehouse_id=None,
                issued_to=1,
                updated_at=now + timedelta(minutes=2),
            ),
            EquipmentInstance(
                id="main-inspected",
                equipment_id=1,
                barcode="BC-4",
                serial_number="SN-INSPECTED",
                status=InventoryStatusEnum.INSPECTED,
                warehouse_id=None,
                issued_to=1,
                updated_at=now + timedelta(minutes=3),
            ),
            EquipmentInstance(
                id="main-damaged",
                equipment_id=1,
                barcode="BC-5",
                serial_number="SN-DAMAGED",
                status=InventoryStatusEnum.DAMAGED,
                warehouse_id=2,
                updated_at=now + timedelta(minutes=4),
            ),
            EquipmentInstance(
                id="main-voided",
                equipment_id=1,
                barcode="BC-VOID",
                serial_number="SN-VOIDED",
                status=InventoryStatusEnum.IN_STOCK,
                warehouse_id=1,
                is_voided=True,
            ),
        ]
        self.db.add_all(instances)
        self.db.add_all(
            [
                Inventory(
                    warehouse_id=1,
                    equipment_id=1,
                    current_stock=1,
                    allocated_stock=2,
                ),
                Inventory(
                    warehouse_id=1,
                    equipment_id=2,
                    current_stock=0,
                    allocated_stock=0,
                ),
                Inventory(
                    warehouse_id=1,
                    equipment_id=3,
                    current_stock=100,
                    allocated_stock=20,
                    min_stock=0,
                ),
                Inventory(
                    warehouse_id=2,
                    equipment_id=3,
                    current_stock=0,
                    allocated_stock=10,
                    min_stock=50,
                ),
                Inventory(
                    warehouse_id=1,
                    equipment_id=4,
                    current_stock=0,
                    allocated_stock=0,
                    min_stock=0,
                ),
            ]
        )

        transactions = [
            StockTransaction(
                id="out-a",
                transaction_type=TransactionTypeEnum.STOCK_OUT,
                warehouse_id=1,
                operator_id=1,
                issued_to=1,
                document_number="OUT-A",
                operation_time=now,
            ),
            StockTransaction(
                id="out-b",
                transaction_type=TransactionTypeEnum.STOCK_OUT,
                warehouse_id=2,
                operator_id=1,
                issued_to=1,
                document_number="OUT-B",
                operation_time=now + timedelta(minutes=1),
            ),
            StockTransaction(
                id="out-aux",
                transaction_type=TransactionTypeEnum.STOCK_OUT,
                warehouse_id=1,
                operator_id=1,
                issued_to=1,
                document_number="OUT-AUX",
                operation_time=now + timedelta(minutes=2),
            ),
            StockTransaction(
                id="return-aux",
                transaction_type=TransactionTypeEnum.RETURN,
                warehouse_id=1,
                operator_id=1,
                document_number="RET-AUX",
                operation_time=now + timedelta(minutes=3),
                related_transaction_id="out-aux",
                approval_status="received",
            ),
        ]
        self.db.add_all(transactions)
        self.db.flush()
        self.db.add_all(
            [
                StockTransactionItem(
                    transaction_id="out-a",
                    equipment_instance_id="main-issued",
                    equipment_id=1,
                    quantity=1,
                ),
                StockTransactionItem(
                    transaction_id="out-a",
                    equipment_instance_id="main-pending",
                    equipment_id=1,
                    quantity=1,
                ),
                StockTransactionItem(
                    transaction_id="out-b",
                    equipment_instance_id="main-inspected",
                    equipment_id=1,
                    quantity=1,
                ),
                StockTransactionItem(
                    transaction_id="out-aux",
                    equipment_id=3,
                    quantity=30,
                    received_qty=0,
                ),
                StockTransactionItem(
                    transaction_id="return-aux",
                    equipment_id=3,
                    quantity=10,
                    received_qty=10,
                ),
            ]
        )

        site = Site(id=1, site_code="SITE-001", site_name="Bound Site")
        template = InspectionTemplate(
            id="template-1",
            template_name="Opening",
            template_data={},
            created_by=1,
        )
        inspection = SiteInspection(
            id="inspection-1",
            site_id=1,
            template_id="template-1",
            inspector_id=1,
        )
        check_item = InspectionCheckItem(
            id="check-1",
            inspection_id="inspection-1",
            item_id="device",
            item_name="Device",
            equipment_sn="SN-PENDING",
            sector_id="2",
            band="N50",
            cell_id="2_N50",
            is_active=True,
            updated_at=now + timedelta(minutes=3),
        )
        self.db.add_all([site, template, inspection, check_item])
        self.db.commit()
        self.user = user

    def test_main_summary_excludes_voided_and_attributes_outbound_warehouse(self):
        result = get_main_inventory_overview(
            self.db,
            view_mode="warehouse",
        )
        self.assertEqual(result["summary"]["device_total"], 5)
        self.assertEqual(result["summary"]["in_stock"], 1)
        self.assertEqual(result["summary"]["issued"], 1)
        self.assertEqual(result["summary"]["pending_inspection"], 1)
        self.assertEqual(result["summary"]["inspected"], 1)
        self.assertEqual(result["summary"]["abnormal"], 1)

        by_warehouse = {item["warehouse_id"]: item for item in result["items"]}
        self.assertEqual(by_warehouse[1]["device_total"], 3)
        self.assertEqual(by_warehouse[1]["issued"], 1)
        self.assertEqual(by_warehouse[1]["pending_inspection"], 1)
        self.assertEqual(by_warehouse[2]["device_total"], 2)
        self.assertEqual(by_warehouse[2]["inspected"], 1)

    def test_main_zero_records_are_progressively_disclosed(self):
        hidden = get_main_inventory_overview(self.db, view_mode="equipment")
        visible = get_main_inventory_overview(
            self.db,
            view_mode="equipment",
            include_zero=True,
        )
        self.assertEqual(hidden["meta"]["hidden_zero_record_count"], 1)
        self.assertEqual(len(hidden["items"]), 1)
        self.assertEqual(len(visible["items"]), 2)
        self.assertEqual(visible["items"][1]["equipment_code"], "MAIN-ZERO")

    def test_main_instance_drilldown_returns_site_binding(self):
        result = get_main_inventory_instances(
            self.db,
            equipment_id=1,
            status_filter="pending_inspection",
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["serial_number"], "SN-PENDING")
        self.assertEqual(result["items"][0]["site_code"], "SITE-001")
        self.assertEqual(result["items"][0]["warehouse_name"], "Warehouse A")

    def test_auxiliary_summary_preserves_units_and_min_zero_is_unconfigured(self):
        result = get_auxiliary_inventory_overview(
            self.db,
            view_mode="equipment",
        )
        self.assertEqual(result["summary"]["equipment_type_count"], 2)
        self.assertEqual(result["summary"]["inventory_record_count"], 3)
        self.assertEqual(result["summary"]["stocked_record_count"], 1)
        self.assertEqual(result["summary"]["zero_stock_record_count"], 2)
        self.assertEqual(result["summary"]["needs_restock_count"], 1)
        self.assertEqual(result["summary"]["unconfigured_reorder_type_count"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["current_stock"], 100)
        self.assertEqual(result["items"][0]["allocated_stock"], 20)
        self.assertEqual(result["items"][0]["unit"], "米")

    def test_auxiliary_outbound_drilldown_uses_unreturned_quantity(self):
        result = get_auxiliary_inventory_details(
            self.db,
            equipment_id=3,
            mode="outbound",
        )
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["quantity"], 30)
        self.assertEqual(result["items"][0]["returned_quantity"], 10)
        self.assertEqual(result["items"][0]["pending_quantity"], 20)

    def test_zero_reorder_point_is_not_reported_as_low_stock(self):
        low_stock = asyncio.run(
            get_inventory_list(
                warehouse_id=None,
                equipment_id=None,
                low_stock_only=True,
                db=self.db,
                current_user=self.user,
            )
        )
        self.assertEqual(len(low_stock["inventory"]), 1)
        self.assertEqual(low_stock["inventory"][0]["equipment_code"], "AUX-CABLE")
        self.assertEqual(low_stock["inventory"][0]["warehouse_id"], 2)

        dashboard = asyncio.run(
            get_inventory_dashboard(db=self.db, current_user=self.user)
        )
        self.assertEqual(dashboard["summary"]["low_stock_items"], 1)


if __name__ == "__main__":
    unittest.main()
