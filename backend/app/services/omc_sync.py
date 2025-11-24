from typing import Optional
from sqlalchemy.orm import Session

from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.planning import SitePlanningCell
from app.models.omc_cellname_sync import OmcCellNameSync
from app.services.omc_client import OmcClient


def _latest_binding_for_sn(db: Session, sn: str) -> Optional[EquipmentBindingHistory]:
    return (
        db.query(EquipmentBindingHistory)
        .filter(EquipmentBindingHistory.equipment_sn == sn)
        .order_by(EquipmentBindingHistory.operated_at.desc())
        .first()
    )


def _cellname_from_planning(db: Session, site_id: int, cell_id: Optional[str], band: Optional[str]) -> Optional[str]:
    """基于站点规划表推测 cell name。
    - 优先匹配 local_cell_id = cell_id 前缀中的数字部分
    - band_code 近似匹配 band（忽略大小写）
    """
    if not site_id:
        return None
    cid_num = None
    if cell_id:
        try:
            cid_num = int(str(cell_id).split('_')[0])
        except Exception:
            cid_num = None
    q = db.query(SitePlanningCell).filter(SitePlanningCell.site_id == site_id)
    if cid_num is not None:
        q = q.filter(SitePlanningCell.local_cell_id == cid_num)
    if band:
        b = str(band).lower()
        q = q.filter(SitePlanningCell.band_code.ilike(f"%{b}%"))
    cell = q.first()
    return cell.cell_name if cell else None


def sync_cellname_if_needed(db: Session, client: OmcClient, sn: str) -> bool:
    """
    当设备首次上线时，同步规划的 CELL NAME 到 OMC。
    - 若已同步过，直接返回 False
    - 找不到规划名称或绑定信息则跳过
    """
    if not sn:
        return False

    # 已同步过直接跳过
    if db.query(OmcCellNameSync).filter(OmcCellNameSync.sn == sn).first():
        return False

    binding = _latest_binding_for_sn(db, sn)
    if not binding or binding.action == BindingActionEnum.UNBIND:
        return False

    cell_name = _cellname_from_planning(db, binding.site_id, binding.cell_id, binding.band)
    if not cell_name:
        return False

    try:
        resp = client.set_cell_name(sn, cell_name)
        status = 'success'
        message = str(resp)
    except Exception as exc:
        status = 'failed'
        message = str(exc)

    rec = OmcCellNameSync(
        sn=sn,
        cell_name=cell_name,
        status=status,
        message=message,
        site_id=binding.site_id,
        work_order_id=getattr(binding, 'work_order_id', None),
    )
    db.add(rec)
    db.commit()
    return status == 'success'
