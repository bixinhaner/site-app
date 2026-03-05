from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.models.equipment import EquipmentInstance, InventoryStatusEnum
from app.models.inspection import InspectionCheckItem


def is_device_level_check_item(item: Optional[InspectionCheckItem]) -> bool:
    """判断检查项是否为设备级（扇区+频段唯一设备位）。"""
    if not item or not item.sector_id or not item.band:
        return False
    key = f"{item.sector_id}_{item.band}"
    # 防御：cell_id 缺失时仍按设备级处理，避免漏掉解绑后的状态回退
    if not item.cell_id:
        return True
    return str(item.cell_id) == key


def rollback_equipment_status_after_unbind(
    db: Session,
    *,
    sns: Iterable[str],
    now: datetime,
) -> int:
    """设备解绑后统一回退状态：
    pending_inspection / inspected -> issued。
    """
    uniq_sns = []
    seen = set()
    for raw in sns:
        sn = str(raw or "").strip()
        if not sn or sn in seen:
            continue
        seen.add(sn)
        uniq_sns.append(sn)

    if not uniq_sns:
        return 0

    rows = db.query(EquipmentInstance).filter(
        EquipmentInstance.serial_number.in_(uniq_sns)
    ).all()

    changed = 0
    for inst in rows:
        if inst.status in {
            InventoryStatusEnum.PENDING_INSPECTION,
            InventoryStatusEnum.INSPECTED,
        }:
            inst.status = InventoryStatusEnum.ISSUED
            inst.updated_at = now
            changed += 1

    return changed
