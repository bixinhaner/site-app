"""设备拆除/移机：解绑已验收站点上的设备，供新站点重新派单绑定。

规则：
- 仅处理“当前仍绑定”（绑定历史最新动作为 bind/rebind）的设备；
- 仅允许原检查已审核通过/已完成；未提交的检查由执行人在检查中直接解绑，审核中的检查需先审核；
- 每个仍绑定该 SN 的检查项写一条 UNBIND 历史，设备状态回退为“已出库”，领料人不变；
- 原检查、检查项、照片与审核记录保留不动，作为原站点的历史档案。
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session, joinedload

from app.models.equipment import (
    EquipmentInstance,
    InventoryStatusEnum,
    StockTransaction,
    TransactionTypeEnum,
)
from app.models.equipment_binding_history import BindingActionEnum, EquipmentBindingHistory
from app.models.inspection import InspectionCheckItem, InspectionStatusEnum, SiteInspection
from app.services.equipment_unbind_service import rollback_equipment_status_after_unbind

MAX_DISMANTLE_SNS = 200

DISMANTLE_ALLOWED_INSPECTION_STATUSES = {
    InspectionStatusEnum.APPROVED,
    InspectionStatusEnum.COMPLETED,
}
DISMANTLE_ALLOWED_INSTANCE_STATUSES = {
    InventoryStatusEnum.ISSUED,
    InventoryStatusEnum.PENDING_INSPECTION,
    InventoryStatusEnum.INSPECTED,
}


def normalize_sns(raw_sns) -> List[str]:
    """去空白、去重并保持输入顺序；支持列表或按换行/逗号/空白分隔的文本。"""
    if isinstance(raw_sns, str):
        parts = raw_sns.replace(",", " ").replace("，", " ").split()
    else:
        parts = [str(s or "") for s in (raw_sns or [])]
    result: List[str] = []
    seen = set()
    for part in parts:
        sn = part.strip()
        if sn and sn not in seen:
            seen.add(sn)
            result.append(sn)
    return result


def _enum_value(value) -> Optional[str]:
    return getattr(value, "value", value) if value is not None else None


def _latest_binding(db: Session, sn: str) -> Optional[EquipmentBindingHistory]:
    return (
        db.query(EquipmentBindingHistory)
        .filter(EquipmentBindingHistory.equipment_sn == sn)
        .order_by(EquipmentBindingHistory.operated_at.desc(), EquipmentBindingHistory.id.desc())
        .first()
    )


def _bound_check_items(db: Session, inspection_id: str, sn: str) -> List[InspectionCheckItem]:
    return (
        db.query(InspectionCheckItem)
        .filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.equipment_sn == sn,
        )
        .order_by(InspectionCheckItem.id)
        .all()
    )


def evaluate_dismantle(db: Session, sn: str) -> Dict:
    """评估单个 SN 能否拆除，返回展示信息与 eligible/reason。"""
    info: Dict = {
        "sn": sn,
        "eligible": False,
        "reason": None,
        "equipment_name": None,
        "instance_status": None,
        "issued_to": None,
        "issued_to_name": None,
        "site_id": None,
        "site_code": None,
        "site_name": None,
        "sector_id": None,
        "band": None,
        "cell_id": None,
        "inspection_id": None,
        "inspection_status": None,
        "work_order_id": None,
        "work_order_title": None,
    }

    instance = (
        db.query(EquipmentInstance)
        .options(joinedload(EquipmentInstance.equipment), joinedload(EquipmentInstance.issuer))
        .filter(EquipmentInstance.serial_number == sn)
        .first()
    )
    if not instance:
        info["reason"] = "设备SN不存在"
        return info

    issuer = instance.issuer
    info.update(
        {
            "equipment_name": getattr(instance.equipment, "equipment_name", None),
            "instance_status": _enum_value(instance.status),
            "issued_to": instance.issued_to,
            "issued_to_name": (issuer.full_name or issuer.username) if issuer else None,
        }
    )
    if instance.is_voided:
        info["reason"] = "设备实例已撤销"
        return info

    latest = _latest_binding(db, sn)
    if not latest or latest.action == BindingActionEnum.UNBIND:
        info["reason"] = "设备当前未绑定站点，无需拆除"
        return info

    inspection = (
        db.query(SiteInspection)
        .options(joinedload(SiteInspection.site), joinedload(SiteInspection.work_order))
        .filter(SiteInspection.id == latest.inspection_id)
        .first()
    )
    site = getattr(inspection, "site", None)
    work_order = getattr(inspection, "work_order", None)
    info.update(
        {
            "site_id": latest.site_id,
            "site_code": getattr(site, "site_code", None),
            "site_name": getattr(site, "site_name", None),
            "sector_id": latest.sector_id,
            "band": latest.band,
            "cell_id": latest.cell_id,
            "inspection_id": latest.inspection_id,
            "inspection_status": _enum_value(getattr(inspection, "status", None)),
            "work_order_id": getattr(inspection, "work_order_id", None),
            "work_order_title": getattr(work_order, "title", None),
        }
    )

    if not inspection:
        info["reason"] = "绑定的检查记录不存在，请联系管理员处理"
        return info
    if inspection.status in {
        InspectionStatusEnum.DRAFT,
        InspectionStatusEnum.IN_PROGRESS,
        InspectionStatusEnum.REJECTED,
    }:
        info["reason"] = "检查尚未提交，请由执行人在检查中直接解绑"
        return info
    if inspection.status in {InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW}:
        info["reason"] = "检查审核中，请审核通过或驳回后再处理"
        return info
    if inspection.status not in DISMANTLE_ALLOWED_INSPECTION_STATUSES:
        info["reason"] = "检查状态不支持拆除"
        return info

    if instance.status not in DISMANTLE_ALLOWED_INSTANCE_STATUSES:
        info["reason"] = "设备库存状态不支持拆除"
        return info

    pending_return = (
        db.query(StockTransaction.id)
        .filter(
            StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
            StockTransaction.approval_status == "pending_receive",
            StockTransaction.scan_barcode == sn,
        )
        .first()
    )
    if pending_return:
        info["reason"] = "设备已发起退库申请（待仓库收货）"
        return info

    info["eligible"] = True
    return info


def preview_dismantle(db: Session, raw_sns) -> Dict:
    sns = normalize_sns(raw_sns)
    if not sns:
        raise ValueError("请填写设备SN")
    if len(sns) > MAX_DISMANTLE_SNS:
        raise ValueError(f"单次最多处理 {MAX_DISMANTLE_SNS} 台设备")
    items = [evaluate_dismantle(db, sn) for sn in sns]
    return {
        "items": items,
        "total": len(items),
        "eligible_count": sum(1 for item in items if item["eligible"]),
    }


def execute_dismantle(db: Session, *, raw_sns, reason: str, operator_id: int) -> Dict:
    """整批校验通过后才写入；任一 SN 不满足条件则整批不处理。调用方负责 commit。"""
    reason = (reason or "").strip()
    if not reason:
        raise ValueError("请填写拆除原因")

    preview = preview_dismantle(db, raw_sns)
    blocked = [item for item in preview["items"] if not item["eligible"]]
    if blocked:
        first = blocked[0]
        raise ValueError(f"设备 {first['sn']} 无法拆除：{first['reason']}")

    now = datetime.utcnow()
    notes = f"拆除/移机：{reason}"
    unbind_count = 0
    for item in preview["items"]:
        sn = item["sn"]
        latest = _latest_binding(db, sn)
        check_items = _bound_check_items(db, latest.inspection_id, sn)
        # 每个仍绑定该 SN 的检查项写一条解绑记录；检查项数据缺失时按最新绑定记录兜底
        slots = [
            {
                "check_item_id": ci.id,
                "sector_id": str(ci.sector_id or latest.sector_id or ""),
                "band": str(ci.band or latest.band or ""),
                "cell_id": str(ci.cell_id or latest.cell_id or ""),
            }
            for ci in check_items
        ] or [
            {
                "check_item_id": latest.check_item_id,
                "sector_id": latest.sector_id,
                "band": latest.band,
                "cell_id": latest.cell_id,
            }
        ]
        for slot in slots:
            db.add(
                EquipmentBindingHistory(
                    inspection_id=latest.inspection_id,
                    check_item_id=slot["check_item_id"],
                    site_id=latest.site_id,
                    sector_id=slot["sector_id"],
                    band=slot["band"],
                    cell_id=slot["cell_id"],
                    equipment_sn=sn,
                    equipment_type=latest.equipment_type,
                    equipment_model=latest.equipment_model,
                    action=BindingActionEnum.UNBIND,
                    operator_id=operator_id,
                    operated_at=now,
                    previous_equipment_sn=None,
                    notes=notes,
                )
            )
            unbind_count += 1

    db.flush()
    reverted = rollback_equipment_status_after_unbind(
        db,
        sns=[item["sn"] for item in preview["items"]],
        now=now,
    )
    return {
        "dismantled_count": len(preview["items"]),
        "unbind_record_count": unbind_count,
        "reverted_equipment_count": reverted,
        "items": preview["items"],
    }
