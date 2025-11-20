"""
OMC 库存（Inventory）相关的服务骨架。

当前仅提供接口占位，不在主流程中调用，后续可按实际
FTP/CSV 格式接入，实现批量同步全网设备状态。
"""

from typing import Iterable, Dict

from sqlalchemy.orm import Session

from app.services.omc_state import upsert_omc_device_state


def sync_from_inventory_snapshot(
    db: Session,
    rows: Iterable[Dict],
    *,
    source_label: str = "inventory_ftp",
) -> None:
    """
    从库存快照（例如 CSV 行列表）中同步设备状态到 OmcDeviceState。

    每一行预期包含:
      - sn: 设备序列号
      - online: "1"/"0" 或布尔
      - active: "1"/"0" 或布尔

    具体字段名和映射规则可在接入真实 OMC 库存格式时补充。

    当前函数不会在任何地方自动调用，仅作为未来集成的入口。
    """
    for row in rows:
        sn = (row.get("sn") or "").strip()
        if not sn:
            continue

        online_val = row.get("online")
        active_val = row.get("active")

        online_raw = None if online_val is None else str(online_val).strip() == "1"
        activated_raw = None if active_val is None else str(active_val).strip() == "1"

        if online_raw is None and activated_raw is None:
            continue

        upsert_omc_device_state(
            db=db,
            sn=sn,
            online_raw=online_raw,
            activated_raw=activated_raw,
            source=source_label,
            status_payload=row,
        )

