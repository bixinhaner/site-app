import threading
import time
from datetime import datetime
from typing import Dict, List, Tuple
import uuid

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.utils.timezone import to_utc_iso
from app.models.site import Site
from app.models.user import User
from app.models.work_order import (
  WorkOrder,
  WorkOrderStatusEnum,
  WorkOrderTypeEnum,
  AuditEvent,
)
from app.services.omc_client import (
  OmcClient,
  get_omc_client,
  parse_online_flag,
  parse_activated_flag,
  is_success_status_payload,
)
from app.services.omc_state import (
  get_bound_sns_for_site,
  upsert_omc_device_state,
  summarize_site_omc_state,
)
from app.services.site_progress_service import rebuild_site_progress

_monitor_thread: threading.Thread | None = None


def _audit_site_status_change(db: Session, site_id: int, old_status: str, new_status: str, reason: str) -> None:
  """记录站点状态变更审计日志（供 OMC 推进/回滚使用）。"""
  try:
    admin_user = db.query(User).filter(User.username == "admin").first()
    operator_id = admin_user.id if admin_user else 1

    db.add(
      AuditEvent(
        id=str(uuid.uuid4()),
        resource_type="site",
        resource_id=str(site_id),
        action="status_change",
        operator_id=operator_id,
        from_status=old_status,
        to_status=new_status,
        comments=f"系统自动更新: {reason}",
        details={"reason": reason, "old_status": old_status, "new_status": new_status},
      )
    )
  except Exception as exc:  # pragma: no cover
    print(f"[WARN] 记录站点状态变更审计日志失败: {exc}")


def _check_site_devices_status(
  db: Session,
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
  status_payloads: Dict[str, Dict] = {}

  # 先检查在线状态
  for sn in sns:
    try:
      resp = client.get_enodeb_status(sn)
      status_payloads[sn] = resp
      online_flag = parse_online_flag(resp)
      activated_flag = parse_activated_flag(resp)
      online_map[sn] = online_flag

      # 写入 SN 聚合表（只升不降 ever，raw 记录本次观测）。无论成功/404 都写入，便于离线落库
      try:
        state, newly_online, newly_activated = upsert_omc_device_state(
          db=db,
          sn=sn,
          online_raw=bool(online_flag),
          activated_raw=bool(activated_flag),
          source="monitor",
          status_payload=resp,
        )
        # 尝试同步 cellName：首次上线会触发；如果之前未绑定则未写入，这里每次检查都会尝试，
        # 仅在找到绑定且未同步过时真正调用，避免遗漏后续绑定场景。
        try:
          from app.services.omc_sync import sync_cellname_if_needed
          sync_cellname_if_needed(db, client, sn)
        except Exception as sync_exc:  # pragma: no cover
          print(f"[OMC] 同步 cellName 失败 SN={sn}: {sync_exc}")
      except Exception as exc:  # pragma: no cover - 聚合表异常不影响主流程
        print(f"[OMC] 写入 OmcDeviceState 失败 SN={sn}: {exc}")
    except Exception as exc:  # pragma: no cover - 网络异常不终止整体流程
      print(f"[OMC] 查询在线状态失败 SN={sn}: {exc}")
      online_map[sn] = False

  if not sns or not all(online_map.values()):
    # 未全部在线，不进行激活状态检查
    return online_map, activated_map

  # 全部在线后再检查激活状态
  for sn in sns:
    try:
      payload = status_payloads.get(sn) or {}
      activated_map[sn] = parse_activated_flag(payload)
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

  sns = get_bound_sns_for_site(db, wo.site_id)
  if not sns:
    summary = {
      "sns": [],
      "online": {},
      "activated": {},
      "all_online": False,
      "all_activated": False,
      "checked_at": to_utc_iso(datetime.utcnow()),
    }
  else:
    online_map, activated_map = _check_site_devices_status(db, client, sns)
    all_online = all(online_map.values()) if sns else False
    all_activated = sns and activated_map and all(activated_map.values())

    summary = {
      "sns": sns,
      "online": online_map,
      "activated": activated_map,
      "all_online": bool(all_online),
      "all_activated": bool(all_activated),
      "checked_at": to_utc_iso(datetime.utcnow()),
    }

  # 基于 SN 聚合表的 ever 状态进行站点/工单状态推进
  ever_summary = summarize_site_omc_state(db, wo.site_id)
  ever_all_online = bool(ever_summary.get("all_ever_online"))
  ever_all_activated = bool(ever_summary.get("all_ever_activated"))

  # 将 ever 聚合结果写入 summary，方便前端或排查
  summary["all_ever_online"] = ever_all_online
  summary["all_ever_activated"] = ever_all_activated

  # 状态推进：仅向前推进，不回退
  if ever_all_online and wo.status == WorkOrderStatusEnum.APPROVED:
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
          f"状态从 {old_site_status} 更新为 {site.status} (站点所有设备曾经全部在线)"
        )

  if ever_all_activated and wo.status in (
    WorkOrderStatusEnum.APPROVED,
    WorkOrderStatusEnum.ACTIVATED,
  ):
    # 全部激活（ever）-> 工单视为完成，站点进入 operational
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()

    # 规则：站点设备已激活（ever）即视为已开通，站点进入 operational（不要求所有开站工单都完成）
    site = db.query(Site).filter(Site.id == wo.site_id).first()
    if site and site.status not in ("operational", "maintenance"):
      old_site_status = site.status
      site.status = "operational"
      print(
        f"[站点状态自动更新] 站点 {site.id} ({site.site_name}) 站点设备已激活，"
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
  rebuild_site_progress(
    db,
    wo.site_id,
    reason="refresh_opening_work_order_omc_status",
  )

  return summary


def refresh_replacement_work_order_omc_status(db: Session, client: OmcClient, wo: WorkOrder) -> Dict:
  """
  针对“设备更换工单”(equipment_replacement)：
  - 读取站点当前绑定设备 SN
  - 调用 OMC 查询在线 & 激活状态
  - 当全部在线 / 全部激活时，自动推进工单状态
  - 当工单完成时，将站点状态回滚到 site_status_before（接受工单时记录）
  - 将结果写入工单 extra_data.omc_status 方便前端展示
  """
  if wo.type != WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
    return {}

  sns = get_bound_sns_for_site(db, wo.site_id)
  if not sns:
    summary = {
      "sns": [],
      "online": {},
      "activated": {},
      "all_online": False,
      "all_activated": False,
      "checked_at": to_utc_iso(datetime.utcnow()),
    }
  else:
    online_map, activated_map = _check_site_devices_status(db, client, sns)
    all_online = all(online_map.values()) if sns else False
    all_activated = sns and activated_map and all(activated_map.values())

    summary = {
      "sns": sns,
      "online": online_map,
      "activated": activated_map,
      "all_online": bool(all_online),
      "all_activated": bool(all_activated),
      "checked_at": to_utc_iso(datetime.utcnow()),
    }

  ever_summary = summarize_site_omc_state(db, wo.site_id)
  ever_all_online = bool(ever_summary.get("all_ever_online"))
  ever_all_activated = bool(ever_summary.get("all_ever_activated"))
  summary["all_ever_online"] = ever_all_online
  summary["all_ever_activated"] = ever_all_activated

  # 状态推进：仅向前推进，不回退
  if ever_all_online and wo.status == WorkOrderStatusEnum.APPROVED:
    wo.status = WorkOrderStatusEnum.ACTIVATED
    wo.activated_at = datetime.utcnow()

  if ever_all_activated and wo.status in (
    WorkOrderStatusEnum.APPROVED,
    WorkOrderStatusEnum.ACTIVATED,
  ):
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()

    # 工单完成：站点状态回滚到 site_status_before
    try:
      site = db.query(Site).filter(Site.id == wo.site_id).first()
      extra = wo.extra_data or {}
      before = (extra.get("site_status_before") or "").strip()
      if site and before and site.status != before:
        old_site_status = site.status
        site.status = before
        _audit_site_status_change(db, site.id, old_site_status, site.status, "设备更换工单完成，站点状态回滚")
    except Exception as exc:  # pragma: no cover
      print(f"[WARN] 设备更换工单完成回滚站点状态失败: {exc}")

  extra = wo.extra_data or {}
  extra["omc_status"] = summary
  wo.extra_data = extra
  wo.updated_at = datetime.utcnow()
  rebuild_site_progress(
    db,
    wo.site_id,
    reason="refresh_replacement_work_order_omc_status",
  )
  return summary


def advance_opening_work_orders_by_ever(db: Session, site_id: int) -> Dict:
  """根据聚合表的 ever 状态推进开站工单/站点状态，不再调用 OMC 实时接口。

  - 使用 summarize_site_omc_state 的 all_ever_online / all_ever_activated
  - 仅做“只升不降”的推进：APPROVED -> ACTIVATED -> COMPLETED；站点 construction/pending_online -> online_pending_activation -> operational
  - 返回推进结果摘要，便于日志/调试
  """

  summary = summarize_site_omc_state(db, site_id)
  ever_all_online = bool(summary.get("all_ever_online"))
  ever_all_activated = bool(summary.get("all_ever_activated"))

  result = {
    "site_id": site_id,
    "ever_all_online": ever_all_online,
    "ever_all_activated": ever_all_activated,
    "work_orders": [],
  }

  wos = db.query(WorkOrder).filter(
    WorkOrder.site_id == site_id,
    WorkOrder.type == WorkOrderTypeEnum.OPENING_INSPECTION,
    WorkOrder.status.in_([WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED]),
  ).all()

  site = db.query(Site).filter(Site.id == site_id).first()

  # 规则：站点设备已激活（ever）即视为已开通，站点进入 operational（不要求所有开站工单都完成）
  if ever_all_activated and site and site.status not in ("operational", "maintenance"):
    site.status = "operational"

  for wo in wos:
    changed = False
    # ever 全在线 -> 已上线待激活
    if ever_all_online and wo.status == WorkOrderStatusEnum.APPROVED:
      wo.status = WorkOrderStatusEnum.ACTIVATED
      wo.activated_at = datetime.utcnow()
      changed = True
      if site and site.status in ("construction", "pending_online"):
        site.status = "online_pending_activation"

    # ever 全激活 -> 完成
    if ever_all_activated and wo.status in (WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED):
      wo.status = WorkOrderStatusEnum.COMPLETED
      wo.completed_at = datetime.utcnow()
      changed = True

    if changed:
      result["work_orders"].append({"id": wo.id, "status": wo.status.value})

  rebuild_site_progress(
    db,
    site_id,
    reason="advance_opening_work_orders_by_ever",
  )
  return result


def advance_replacement_work_orders_by_ever(db: Session, site_id: int) -> Dict:
  """根据聚合表的 ever 状态推进设备更换工单状态，不再调用 OMC 实时接口。"""
  summary = summarize_site_omc_state(db, site_id)
  ever_all_online = bool(summary.get("all_ever_online"))
  ever_all_activated = bool(summary.get("all_ever_activated"))

  result = {
    "site_id": site_id,
    "ever_all_online": ever_all_online,
    "ever_all_activated": ever_all_activated,
    "work_orders": [],
  }

  wos = db.query(WorkOrder).filter(
    WorkOrder.site_id == site_id,
    WorkOrder.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT,
    WorkOrder.status.in_([WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED]),
  ).all()

  site = db.query(Site).filter(Site.id == site_id).first()

  for wo in wos:
    changed = False
    if ever_all_online and wo.status == WorkOrderStatusEnum.APPROVED:
      wo.status = WorkOrderStatusEnum.ACTIVATED
      wo.activated_at = datetime.utcnow()
      changed = True

    if ever_all_activated and wo.status in (WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED):
      wo.status = WorkOrderStatusEnum.COMPLETED
      wo.completed_at = datetime.utcnow()
      changed = True

      # 完成时回滚站点状态
      try:
        extra = wo.extra_data or {}
        before = (extra.get("site_status_before") or "").strip()
        if site and before and site.status != before:
          old_site_status = site.status
          site.status = before
          _audit_site_status_change(db, site.id, old_site_status, site.status, "设备更换工单完成，站点状态回滚")
      except Exception as exc:  # pragma: no cover
        print(f"[WARN] 回滚站点状态失败: {exc}")

    if changed:
      result["work_orders"].append({"id": wo.id, "status": wo.status.value})

  rebuild_site_progress(
    db,
    site_id,
    reason="advance_replacement_work_orders_by_ever",
  )
  return result


def run_omc_check_for_work_order(work_order_id: str) -> None:
  """
  针对单个工单执行一次 OMC 状态检查（供 API / 审核后触发调用）。
  """
  db = SessionLocal()
  try:
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or wo.type not in (WorkOrderTypeEnum.OPENING_INSPECTION, WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT):
      return

    client = get_omc_client(db)
    if not client:
      print("[OMC] 未配置 OMC API 信息，跳过检查")
      return

    if wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
      refresh_opening_work_order_omc_status(db, client, wo)
    elif wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
      refresh_replacement_work_order_omc_status(db, client, wo)
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
            WorkOrder.type.in_(
              [WorkOrderTypeEnum.OPENING_INSPECTION, WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT]
            ),
            WorkOrder.status.in_([WorkOrderStatusEnum.APPROVED, WorkOrderStatusEnum.ACTIVATED]),
          )
          .all()
        )

        for wo in work_orders:
          try:
            if wo.type == WorkOrderTypeEnum.OPENING_INSPECTION:
              refresh_opening_work_order_omc_status(db, client, wo)
            elif wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
              refresh_replacement_work_order_omc_status(db, client, wo)
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
