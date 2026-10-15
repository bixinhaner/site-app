from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.equipment import (
    Equipment,
    EquipmentCategoryEnum,
    EquipmentInstance,
    InventoryStatusEnum,
)
from app.models.equipment_binding_history import BindingActionEnum, EquipmentBindingHistory
from app.models.inspection import (
    CheckItemStatusEnum,
    InspectionCheckItem,
    InspectionStatusEnum,
    SiteInspection,
)
from app.models.site import Site
from app.models.user import User
from app.services.equipment_dismantle_service import (
    execute_dismantle,
    normalize_sns,
    preview_dismantle,
)
from app.services.inventory_overview_service import _latest_binding_map

SN = "1202000879259KD0371"
BOUND_AT = datetime(2026, 9, 9, 11, 5, 55)


def _session(*, inspection_status=InspectionStatusEnum.APPROVED, instance_status=InventoryStatusEnum.INSPECTED):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()

    session.add_all(
        [
            User(id=1, username="admin", email="admin@example.com", hashed_password="x", full_name="Admin"),
            User(id=69, username="moses", email="moses@example.com", hashed_password="x", full_name="Moses"),
            Site(id=503, site_code="NAB-TDD", site_name="Nabweru-TDD"),
            Equipment(id=1, equipment_code="RRU", equipment_name="RRU B38", category=EquipmentCategoryEnum.MAIN_DEVICE),
            EquipmentInstance(
                id="inst-1",
                equipment_id=1,
                barcode=SN,
                serial_number=SN,
                status=instance_status,
                issued_to=69,
            ),
            SiteInspection(
                id="insp-1",
                site_id=503,
                template_id="tpl-1",
                inspector_id=69,
                status=inspection_status,
            ),
        ]
    )
    for idx in range(3):
        item_id = f"item-{idx}"
        session.add(
            InspectionCheckItem(
                id=item_id,
                inspection_id="insp-1",
                item_id=f"device_1_B38_{idx}",
                item_name="设备 1_B38",
                sector_id="1",
                band="B38",
                cell_id="1_B38",
                equipment_sn=SN,
                status=CheckItemStatusEnum.COMPLETED,
                is_active=True,
                removed_by_template=False,
                checked_at=BOUND_AT,
            )
        )
        session.add(
            EquipmentBindingHistory(
                inspection_id="insp-1",
                check_item_id=item_id,
                site_id=503,
                sector_id="1",
                band="B38",
                cell_id="1_B38",
                equipment_sn=SN,
                action=BindingActionEnum.BIND,
                operator_id=69,
                operated_at=BOUND_AT,
            )
        )
    session.commit()
    return session


def test_normalize_sns_accepts_text_and_dedupes():
    assert normalize_sns(f" {SN}\n{SN}, ABC，DEF ") == [SN, "ABC", "DEF"]
    assert normalize_sns([SN, "", None, SN]) == [SN]


def test_preview_reports_binding_and_eligibility():
    session = _session()
    try:
        result = preview_dismantle(session, [SN, "NOT-EXIST"])
        assert result["total"] == 2
        assert result["eligible_count"] == 1
        bound, missing = result["items"]
        assert bound["eligible"] is True
        assert bound["site_name"] == "Nabweru-TDD"
        assert bound["cell_id"] == "1_B38"
        assert bound["issued_to_name"] == "Moses"
        assert missing["eligible"] is False
        assert missing["reason"] == "设备SN不存在"
    finally:
        session.close()


def test_execute_unbinds_every_check_item_and_keeps_archive():
    session = _session()
    try:
        assert SN in _latest_binding_map(session, [SN])

        result = execute_dismantle(session, raw_sns=[SN], reason="装错站", operator_id=1)
        session.commit()

        assert result["dismantled_count"] == 1
        assert result["unbind_record_count"] == 3
        assert result["reverted_equipment_count"] == 1

        unbinds = session.query(EquipmentBindingHistory).filter(
            EquipmentBindingHistory.action == BindingActionEnum.UNBIND
        ).all()
        assert sorted(u.check_item_id for u in unbinds) == ["item-0", "item-1", "item-2"]
        assert all(u.operator_id == 1 and u.notes == "拆除/移机：装错站" for u in unbinds)

        instance = session.query(EquipmentInstance).one()
        assert instance.status == InventoryStatusEnum.ISSUED
        assert instance.issued_to == 69  # 领料人不变

        # 原检查与检查项保留作档案
        assert session.query(SiteInspection).one().status == InspectionStatusEnum.APPROVED
        assert session.query(InspectionCheckItem).filter(InspectionCheckItem.equipment_sn == SN).count() == 3

        # 库存台账不再显示旧站点
        assert _latest_binding_map(session, [SN]) == {}

        # 再次拆除：已无绑定
        again = preview_dismantle(session, [SN])["items"][0]
        assert again["eligible"] is False
        assert again["reason"] == "设备当前未绑定站点，无需拆除"
    finally:
        session.close()


def test_instance_list_binding_info_follows_dismantle():
    from app.api.stock import _serialize_equipment_instances

    session = _session()
    try:
        before = _serialize_equipment_instances(session, session.query(EquipmentInstance).all())[0]
        assert before["binding_info"]["site_name"] == "Nabweru-TDD"
        assert before["binding_info"]["cell_id"] == "1_B38"

        execute_dismantle(session, raw_sns=[SN], reason="装错站", operator_id=1)
        session.commit()

        after = _serialize_equipment_instances(session, session.query(EquipmentInstance).all())[0]
        assert after["binding_info"] is None
    finally:
        session.close()


def test_rebind_after_dismantle_shows_new_site_in_ledger():
    session = _session()
    try:
        execute_dismantle(session, raw_sns=[SN], reason="装错站", operator_id=1)
        session.commit()

        new_bound_at = datetime.utcnow() + timedelta(minutes=5)
        session.add_all(
            [
                Site(id=900, site_code="NEW", site_name="New-Site"),
                SiteInspection(id="insp-new", site_id=900, template_id="tpl-1", inspector_id=69,
                               status=InspectionStatusEnum.IN_PROGRESS),
                InspectionCheckItem(
                    id="item-new", inspection_id="insp-new", item_id="device_2_B38", item_name="设备 2_B38",
                    sector_id="2", band="B38", cell_id="2_B38", equipment_sn=SN,
                    status=CheckItemStatusEnum.COMPLETED, is_active=True, removed_by_template=False,
                    checked_at=new_bound_at, updated_at=new_bound_at,
                ),
                EquipmentBindingHistory(
                    inspection_id="insp-new", check_item_id="item-new", site_id=900, sector_id="2",
                    band="B38", cell_id="2_B38", equipment_sn=SN, action=BindingActionEnum.BIND,
                    operator_id=69, operated_at=new_bound_at,
                ),
            ]
        )
        session.commit()

        assert _latest_binding_map(session, [SN])[SN]["site_name"] == "New-Site"
    finally:
        session.close()


@pytest.mark.parametrize(
    "inspection_status, reason",
    [
        (InspectionStatusEnum.IN_PROGRESS, "检查尚未提交，请由执行人在检查中直接解绑"),
        (InspectionStatusEnum.UNDER_REVIEW, "检查审核中，请审核通过或驳回后再处理"),
    ],
)
def test_unfinished_inspection_is_not_dismantled(inspection_status, reason):
    session = _session(inspection_status=inspection_status)
    try:
        item = preview_dismantle(session, [SN])["items"][0]
        assert item["eligible"] is False
        assert item["reason"] == reason
    finally:
        session.close()


def test_execute_is_all_or_nothing():
    session = _session()
    try:
        with pytest.raises(ValueError, match="设备 NOT-EXIST 无法拆除：设备SN不存在"):
            execute_dismantle(session, raw_sns=[SN, "NOT-EXIST"], reason="装错站", operator_id=1)
        session.rollback()
        assert session.query(EquipmentBindingHistory).filter(
            EquipmentBindingHistory.action == BindingActionEnum.UNBIND
        ).count() == 0
        assert session.query(EquipmentInstance).one().status == InventoryStatusEnum.INSPECTED
    finally:
        session.close()


def test_endpoint_rejection_keeps_current_user_usable():
    """校验失败返回 400 时不能让 current_user 过期，否则操作日志中间件读取 user.id 会变成 500。"""
    import asyncio

    from fastapi import HTTPException

    from app.api.equipment_dismantle import dismantle_execute

    session = _session()
    try:
        user = session.query(User).filter(User.id == 1).one()
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(dismantle_execute({"sns": ["NOT-EXIST"], "reason": "x"}, db=session, current_user=user))
        assert exc_info.value.status_code == 400
        session.close()
        assert user.id == 1  # 会话关闭后仍可读取（未被 rollback 过期）
    finally:
        session.close()


def test_execute_requires_reason():
    session = _session()
    try:
        with pytest.raises(ValueError, match="请填写拆除原因"):
            execute_dismantle(session, raw_sns=[SN], reason="  ", operator_id=1)
    finally:
        session.close()


def test_dismantle_messages_are_localized():
    from app.i18n.error_localization import localize_text

    text = "设备 X1 无法拆除：检查审核中，请审核通过或驳回后再处理"
    assert localize_text(text, "en-US") == (
        "Device X1 cannot be dismantled: Inspection is under review; approve or reject it first"
    )
    assert localize_text("拆除成功", "id-ID") == "Berhasil dibongkar"
