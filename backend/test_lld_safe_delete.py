from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.site_planning import (
    _build_lld_cell_delete_scope,
    _collect_lld_check_item_fact_reasons,
    _prepare_lld_unbound_cell_delete,
)
from app.core.database import Base
from app.models.inspection import (
    CheckItemStatusEnum,
    InspectionCheckItem,
    InspectionStatusEnum,
    SiteInspection,
)
from app.models.work_order import WorkOrder, WorkOrderStatusEnum, WorkOrderTypeEnum


def _cell(local_cell_id, band_code, frequency):
    return SimpleNamespace(
        local_cell_id=local_cell_id,
        band_code=band_code,
        frequency=frequency,
    )


def _check_item(**overrides):
    values = {
        "equipment_sn": None,
        "status": CheckItemStatusEnum.PENDING,
        "data_value": None,
        "notes": None,
        "validation_result": None,
        "checked_by": None,
        "checked_at": None,
        "review_status": None,
        "review_comments": None,
        "review_comments_manual": None,
        "field_issue_comments": None,
        "field_review_results": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "ai_status": None,
        "ai_result": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_delete_scope_removes_carrier_slot_and_sector_for_last_sector_cell():
    target = _cell(3, "N50", None)
    remaining = [_cell(1, "N50", None), _cell(2, "N50", None)]

    scope = _build_lld_cell_delete_scope(target, remaining)

    assert scope["carrier_cell_id"] == "3_N50_NA"
    assert scope["remove_carrier_cell"] is True
    assert scope["remove_device_slot"] is True
    assert scope["remove_sector"] is True


def test_delete_scope_keeps_device_and_sector_when_another_carrier_remains():
    target = _cell(1, "N50", 503000)
    remaining = [_cell(1, "N50", 504000), _cell(2, "N50", 503000)]

    scope = _build_lld_cell_delete_scope(target, remaining)

    assert scope["remove_carrier_cell"] is True
    assert scope["remove_device_slot"] is False
    assert scope["remove_sector"] is False


def test_delete_scope_keeps_generated_items_for_duplicate_carrier_row():
    target = _cell(1, "N50", 503000)
    remaining = [_cell(1, "n50", 503000)]

    scope = _build_lld_cell_delete_scope(target, remaining)

    assert scope["remove_carrier_cell"] is False
    assert scope["remove_device_slot"] is False
    assert scope["remove_sector"] is False


def test_pending_empty_check_item_has_no_operation_facts():
    assert _collect_lld_check_item_fact_reasons(_check_item()) == []


def test_bound_or_completed_check_item_blocks_safe_delete():
    reasons = _collect_lld_check_item_fact_reasons(
        _check_item(
            equipment_sn="12020008972619B0003",
            status=CheckItemStatusEnum.COMPLETED,
            data_value={"value": "done"},
        ),
        photo_count=2,
        binding_history_count=1,
    )

    assert "已绑定 SN 12020008972619B0003" in reasons
    assert "检查项状态为 completed" in reasons
    assert "已有填写数据" in reasons
    assert "已有 2 张照片" in reasons
    assert "已有 1 条设备绑定历史" in reasons


def _build_safe_delete_session(*, equipment_sn=None):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    work_order = WorkOrder(
        id="work-order-safe-delete",
        site_id=84,
        title="Safe delete opening work order",
        type=WorkOrderTypeEnum.OPENING_INSPECTION,
        status=WorkOrderStatusEnum.ACTIVE,
        assigned_by=1,
        assigned_to=1,
    )
    inspection = SiteInspection(
        id="inspection-safe-delete",
        site_id=84,
        work_order_id=work_order.id,
        template_id="template-safe-delete",
        inspector_id=1,
        status=InspectionStatusEnum.DRAFT,
        total_items=2,
    )
    work_order.inspection_id = inspection.id
    session.add_all(
        [
            work_order,
            inspection,
            InspectionCheckItem(
                id="sector-item-safe-delete",
                inspection_id=inspection.id,
                item_id="planning_sector_3",
                item_name="Planning - 扇区 3",
                sector_id="3",
                status=CheckItemStatusEnum.PENDING,
                is_active=True,
                removed_by_template=False,
            ),
            InspectionCheckItem(
                id="device-item-safe-delete",
                inspection_id=inspection.id,
                item_id="device_3_N50",
                item_name="Which sector? - 设备 3_N50",
                sector_id="3",
                band="N50",
                cell_id="3_N50",
                equipment_sn=equipment_sn,
                status=CheckItemStatusEnum.PENDING,
                is_active=True,
                removed_by_template=False,
            ),
        ]
    )
    session.commit()
    return session


def test_prepare_safe_delete_deactivates_only_empty_matching_items():
    session = _build_safe_delete_session()
    try:
        result = _prepare_lld_unbound_cell_delete(
            session,
            84,
            {
                "sector_id": "3",
                "band": "N50",
                "device_cell_id": "3_N50",
                "carrier_cell_id": "3_N50_NA",
                "remove_carrier_cell": True,
                "remove_device_slot": True,
                "remove_sector": True,
            },
        )

        assert result == {"removed_check_items": 2, "synchronized_inspections": 1}
        active_count = (
            session.query(InspectionCheckItem)
            .filter(InspectionCheckItem.is_active.is_(True))
            .count()
        )
        assert active_count == 0
        inspection = session.query(SiteInspection).one()
        assert inspection.total_items == 0
    finally:
        session.close()


def test_prepare_safe_delete_rejects_bound_matching_item_without_partial_change():
    session = _build_safe_delete_session(equipment_sn="12020008972619B0003")
    try:
        try:
            _prepare_lld_unbound_cell_delete(
                session,
                84,
                {
                    "sector_id": "3",
                    "band": "N50",
                    "device_cell_id": "3_N50",
                    "carrier_cell_id": "3_N50_NA",
                    "remove_carrier_cell": True,
                    "remove_device_slot": True,
                    "remove_sector": True,
                },
            )
            raise AssertionError("bound planning item should block safe delete")
        except HTTPException as error:
            assert error.status_code == 409
            assert error.detail["code"] == "LLD_CELL_HAS_OPERATION_FACTS"

        assert session.query(InspectionCheckItem).filter(
            InspectionCheckItem.is_active.is_(True)
        ).count() == 2
    finally:
        session.close()


if __name__ == "__main__":
    test_delete_scope_removes_carrier_slot_and_sector_for_last_sector_cell()
    test_delete_scope_keeps_device_and_sector_when_another_carrier_remains()
    test_delete_scope_keeps_generated_items_for_duplicate_carrier_row()
    test_pending_empty_check_item_has_no_operation_facts()
    test_bound_or_completed_check_item_blocks_safe_delete()
    test_prepare_safe_delete_deactivates_only_empty_matching_items()
    test_prepare_safe_delete_rejects_bound_matching_item_without_partial_change()
    print("LLD safe delete tests passed")
