import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple

from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.models.site import Site
from app.models.work_order import (
  WorkOrder,
  WorkOrderStatusEnum,
  WorkOrderTypeEnum,
)
from app.services.omc_client import (
  OmcClient,
  get_omc_client,
  parse_online_flag,
  parse_activated_flag,
)

_monitor_thread: threading.Thread | None = None


def _get_bound_sns_for_site(db: Session, site_id: int) -> List[str]:
  """
  基于设备绑定历史，推导当前站点已绑定的设备 SN 列表。
  规则：同一 SN 取最新一条记录，若 action != UNBIND 则视为仍然绑定。
  """
  subq = (
    db.query(
      EquipmentBindingHistory.equipment_sn.label("sn"),
      func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
    )
    .filter(EquipmentBindingHistory.site_id == site_id)
    .group_by(EquipmentBindingHistory.equipment_sn)
    .subquery()
  )

  latest_rows: List[EquipmentBindingHistory] = (
    db.query(EquipmentBindingHistory)
    .join(
      subq,
      and_(
        EquipmentBindingHistory.equipment_sn == subq.c.sn,
        EquipmentBindingHistory.operated_at == subq.c.latest_at,
      ),
    )
    .all()
  )

  sns: List[str] = []
  for row in latest_rows:
    if row.action != BindingActionEnum.UNBIND and row.equipment_sn:
      sns.append(row.equipment_sn)
  return sns


def _check_site_devices_status(
  client: OmcClient,
  sns: List[str],
) -> Tuple[Dict[str, bool], Dict[str, bool]]:
  """
  对站点设备 SN 列表进行在线 / 激活状态检查。

  返回:
    online_map:   { sn: True/False }
    activated_map:{ sn: True/False }  （仅当全部在线时才检查激活，否则为空字典）
  """
  online_map: Dict[str, bool] = {}
  activated_map: Dict[str, bool] = {}

  # 先检查在线状态
  for sn in sns:
    try:
      resp = client.get_enodeb_status(sn)
      online_map[sn] = parse_online_flag(resp)
    except Exception as exc:  # pragma: no cover - 网络异常不终止整体流程
      print(f"[OMC] 查询在线状态失败 SN={sn}: {exc}")
      online_map[sn] = False

  if not sns or not all(online_map.values()):
    # 未全部在线，不进行激活状态检查
    return online_map, activated_map

  # 全部在线后再检查激活状态
  for sn in sns:
    try:
      resp = client.get_cert_status(sn)
      activated_map[sn] = parse_activated_flag(resp)
    except Exception as exc:  # pragma: no cover
      print(f"[OMC] 查询激活状态失败 SN={sn}: {exc}")
      activated_map[sn] = False

  return online_map, activated_map


def refresh_opening_work_order_omc_status(db: Session, client: OmcClient, wo: WorkOrder) -> Dict:
  """
  针对“开站工单”(opening_inspection)：
  - 读取站点绑定的设备 SN
  - 调用 OMC 查询在线 & 激活状态
  - 当全部在线 / 全部激活时，自动推进工单 & 站点状态
  - 将结果写入工单 extra_data.omc_status 方便前端展示
  """
  if wo.type != WorkOrderTypeEnum.OPENING_INSPECTION:
    return {}

  sns = _get_bound_sns_for_site(db, wo.site_id)
  if not sns:
    summary = {
      "sns": [],
      "online": {},
      "activated": {},
      "all_online": False,
      "all_activated": False,
      "checked_at": datetime.utcnow().isoformat(),
    }
  else:
    online_map, activated_map = _check_site_devices_status(client, sns)
    all_online = all(online_map.values()) if sns else False
    all_activated = sns and activated_map and all(activated_map.values())

    summary = {
      "sns": sns,
      "online": online_map,
      "activated": activated_map,
      "all_online": bool(all_online),
      "all_activated": bool(all_activated),
      "checked_at": datetime.utcnow().isoformat(),
    }

    # 状态推进：仅向前推进，不回退
    if all_online and wo.status == WorkOrderStatusEnum.APPROVED:
      old_status = wo.status
      wo.status = WorkOrderStatusEnum.ACTIVATED  # 90%: 已上线待激活
      wo.activated_at = datetime.utcnow()

      site = db.query(Site).filter(Site.id == wo.site_id).first()
      if site:
        old_site_status = site.status
        if old_site_status in ("construction", "pending_online"):
          site.status = "online_pending_activation"
          print(
            f"[站点状态自动更新] 站点 {site.id} ({site.site_name}) "
            f"状态从 {old_site_status} 更新为 {site.status} (设备全部在线)"
          )

  if summary["all_activated"] and wo.status in (
    WorkOrderStatusEnum.APPROVED,
    WorkOrderStatusEnum.ACTIVATED,
  ):
    # 全部激活 -> 工单视为完成，站点进入 operational（通过原有逻辑）
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()

    # 站点状态：当该站点所有开站工单都完成后，进入 operational
    opening_work_orders = db.query(WorkOrder).filter(
      WorkOrder.site_id == wo.site_id,
      WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
    ).all()
    all_completed = all(
      item.status == WorkOrderStatusEnum.COMPLETED for item in opening_work_orders
    )

    if all_completed and opening_work_orders:
      site = db.query(Site).filter(Site.id == wo.site_id).first()
      if site and site.status != "operational":
        old_site_status = site.status
        site.status = "operational"
        print(
          f"[站点状态自动更新] 站点 {site.id} ({site.site_name}) 所有开站工单已完成，"
          f"状态从 {old_site_status} 更新为 {site.status}"
        )

    print(
      f"[工单自动更新] 开站工单 {wo.id} 全部设备已激活，状态从 {old_status} 更新为 {wo.status}"
    )

  # 写入 extra_data.omc_status
  extra = wo.extra_data or {}
  extra["omc_status"] = summary
  wo.extra_data = extra
  wo.updated_at = datetime.utcnow()

  return summary


def run_omc_check_for_work_order(work_order_id: str) -> None:
  """
  针对单个工单执行一次 OMC 状态检查（供 API / 审核后触发调用）。
  """
  db = SessionLocal()
  try:
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or wo.type != WorkOrderTypeEnum.OPENING_INSPECTION:
      return

    client = get_omc_client(db)
    if not client:
      print("[OMC] 未配置 OMC API 信息，跳过检查")
      return

    refresh_opening_work_order_omc_status(db, client, wo)
    db.commit()
  except Exception as exc:  # pragma: no cover
    db.rollback()
    print(f"[OMC] 单工单检查失败 work_order_id={work_order_id}: {exc}")
  finally:
    db.close()


def _monitor_loop(interval_seconds: int = 300) -> None:
  """
  后台轮询线程：每 interval_seconds 针对未完成的开站工单执行一次 OMC 检查。
  """
  while True:
    try:
      db = SessionLocal()
      try:
        client = get_omc_client(db)
        if not client:
          # 未配置 OMC，则不做任何操作
          time.sleep(interval_seconds)
          continue

        work_orders = (
          db.query(WorkOrder)
          .filter(
            WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
            WorkOrder.status.in_(
              [WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED]
            ),
          )
          .all()
        )

        for wo in work_orders:
          try:
            refresh_opening_work_order_omc_status(db, client, wo)
          except Exception as exc:
            print(f"[OMC] 定时检查工单 {wo.id} 失败: {exc}")

        db.commit()
      finally:
        db.close()
    except Exception as exc:  # pragma: no cover
      print(f"[OMC] 定时检查循环异常: {exc}")

    time.sleep(interval_seconds)


def start_background_omc_monitor(interval_seconds: int = 300) -> None:
  """
  启动后台 OMC 状态轮询线程（如已启动则忽略）。
  """
  global _monitor_thread
  if _monitor_thread and _monitor_thread.is_alive():
    return

  _monitor_thread = threading.Thread(
    target=_monitor_loop, args=(interval_seconds,), name="omc-monitor", daemon=True
  )
  _monitor_thread.start()
