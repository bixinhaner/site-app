from typing import Optional, Dict, Any, List, Literal
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, field_serializer
from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.system_config import SystemConfig
from app.models.omc_state import OmcDeviceState
from app.models.site import Site
from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
from app.services.omc_client import (
  load_omc_config,
  OmcClient,
  get_omc_client,
  parse_online_flag,
  parse_activated_flag,
  is_success_status_payload,
)
from app.services.omc_state import upsert_omc_device_state
from app.services.omc_monitor import advance_opening_work_orders_by_ever
from app.services.work_order_rule_service import (
  get_ssv_create_by_ever_activated_only,
  upsert_work_order_rules,
)
from app.services.site_progress_metric_service import (
  SITE_PROGRESS_METRIC_MODE_WORKFLOW,
  get_site_progress_metric_mode,
  upsert_site_progress_settings,
)
from app.utils.timezone import to_utc_iso

router = APIRouter()


class OmcConfigPayload(BaseModel):
  base_url: str
  username: str
  password: Optional[str] = None
  timeout_seconds: Optional[int] = 10
  manual_confirm_enabled: Optional[bool] = False
  ssv_create_by_ever_activated_only: Optional[bool] = None
  site_progress_metric_mode: Optional[Literal["workflow", "device_fact"]] = None


class OmcConfigResponse(BaseModel):
  base_url: Optional[str] = None
  username: Optional[str] = None
  timeout_seconds: int = 10
  manual_confirm_enabled: bool = False
  ssv_create_by_ever_activated_only: bool = False
  site_progress_metric_mode: str = SITE_PROGRESS_METRIC_MODE_WORKFLOW


class OmcTestResponse(BaseModel):
  success: bool
  message: str


class OmcDeviceStatusBySnResponse(BaseModel):
  sn: str
  online: bool
  activated: bool
  checked_at: str
  status_payload: Optional[Dict[str, Any]] = None


class OmcDeviceStateItem(BaseModel):
  sn: str
  omc_online_raw: Optional[bool] = None
  omc_active_raw: Optional[bool] = None
  ever_online: bool
  ever_activated: bool
  first_online_at: Optional[datetime] = None
  first_activated_at: Optional[datetime] = None
  last_seen_at: Optional[datetime] = None
  last_source: Optional[str] = None
  current_site_id: Optional[int] = None
  current_site_code: Optional[str] = None
  current_site_name: Optional[str] = None

  @field_serializer("first_online_at", "first_activated_at", "last_seen_at")
  def _serialize_dt(self, dt: Optional[datetime]) -> Optional[str]:
    return to_utc_iso(dt)


class OmcDeviceStateListResponse(BaseModel):
  total: int
  items: List[OmcDeviceStateItem]


def _ensure_admin(user: User) -> None:
  if user.role != "admin":
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="Only admin can manage OMC configuration",
    )


def _load_omc_config(db: Session) -> OmcConfigResponse:
  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  ssv_create_by_ever_activated_only = get_ssv_create_by_ever_activated_only(db)
  site_progress_metric_mode = get_site_progress_metric_mode(db)
  if not row or not row.value:
    return OmcConfigResponse(
      ssv_create_by_ever_activated_only=ssv_create_by_ever_activated_only,
      site_progress_metric_mode=site_progress_metric_mode,
    )
  data = row.value or {}
  return OmcConfigResponse(
    base_url=data.get("base_url"),
    username=data.get("username"),
    timeout_seconds=int(data.get("timeout_seconds") or 10),
    manual_confirm_enabled=bool(data.get("manual_confirm_enabled") or False),
    ssv_create_by_ever_activated_only=ssv_create_by_ever_activated_only,
    site_progress_metric_mode=site_progress_metric_mode,
  )


@router.get("/config", response_model=OmcConfigResponse)
async def get_omc_config(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取 OMC API 配置（仅 admin 可见）。
  """
  _ensure_admin(current_user)
  return _load_omc_config(db)


@router.put("/config", response_model=OmcConfigResponse)
async def update_omc_config(
  payload: OmcConfigPayload,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  更新 OMC API 配置（仅 admin 可修改）。
  """
  _ensure_admin(current_user)

  raw_url = (payload.base_url or "").strip()
  # 若用户未包含协议，默认加上 http://
  if "://" not in raw_url:
    raw_url = f"http://{raw_url}"
  base_url = raw_url.rstrip("/")
  username = payload.username.strip()
  new_password = (payload.password or "").strip()
  timeout = payload.timeout_seconds or 10
  manual_confirm_enabled = bool(payload.manual_confirm_enabled or False)
  ssv_create_by_ever_activated_only = (
    get_ssv_create_by_ever_activated_only(db)
    if payload.ssv_create_by_ever_activated_only is None
    else bool(payload.ssv_create_by_ever_activated_only)
  )
  site_progress_metric_mode = (
    get_site_progress_metric_mode(db)
    if payload.site_progress_metric_mode is None
    else str(payload.site_progress_metric_mode)
  )

  row = db.query(SystemConfig).filter(SystemConfig.key == "omc_api").first()
  if not row:
    data = {
      "base_url": base_url,
      "username": username,
      "password": new_password,
      "timeout_seconds": timeout,
      "manual_confirm_enabled": manual_confirm_enabled,
    }
    row = SystemConfig(key="omc_api", value=data)
    db.add(row)
  else:
    data = row.value or {}
    data["base_url"] = base_url
    data["username"] = username
    data["timeout_seconds"] = timeout
    data["manual_confirm_enabled"] = manual_confirm_enabled
    # 只有在传入非空 password 时才更新存储的密码
    if new_password:
      data["password"] = new_password
    row.value = data
    # JSON 字段需要显式标记已修改，SQLAlchemy 才会持久化变更
    flag_modified(row, "value")

  upsert_work_order_rules(
    db,
    {"ssv_create_by_ever_activated_only": ssv_create_by_ever_activated_only},
  )
  upsert_site_progress_settings(
    db,
    {"metric_mode": site_progress_metric_mode},
  )
  db.commit()

  return OmcConfigResponse(
    base_url=base_url,
    username=username,
    timeout_seconds=timeout,
    manual_confirm_enabled=manual_confirm_enabled,
    ssv_create_by_ever_activated_only=ssv_create_by_ever_activated_only,
    site_progress_metric_mode=site_progress_metric_mode,
  )


@router.get("/states", response_model=OmcDeviceStateListResponse)
async def list_omc_device_states(
  page: int = Query(1, ge=1, description="页码（从1开始）"),
  page_size: int = Query(20, ge=1, le=100, description="每页条数"),
  sn: Optional[str] = Query(None, description="按设备SN模糊搜索"),
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  OMC 设备状态聚合列表（仅 admin/manager 可见）。
  """
  _ensure_admin(current_user)

  query = db.query(OmcDeviceState)
  if sn:
    like_expr = f"%{sn.strip()}%"
    query = query.filter(OmcDeviceState.sn.ilike(like_expr))

  total = query.count()

  states: List[OmcDeviceState] = (
    query.order_by(OmcDeviceState.sn)
    .offset((page - 1) * page_size)
    .limit(page_size)
    .all()
  )

  if not states:
    return OmcDeviceStateListResponse(total=0, items=[])

  # 查询当前绑定站点（按 SN 维度）
  sns = [s.sn for s in states]

  binding_latest_at_subq = (
    db.query(
      EquipmentBindingHistory.equipment_sn.label("sn"),
      func.max(EquipmentBindingHistory.operated_at).label("latest_at"),
    )
    .filter(EquipmentBindingHistory.equipment_sn.in_(sns))
    .group_by(EquipmentBindingHistory.equipment_sn)
    .subquery()
  )

  binding_latest_id_subq = (
    db.query(
      EquipmentBindingHistory.equipment_sn.label("sn"),
      func.max(EquipmentBindingHistory.id).label("latest_id"),
    )
    .join(
      binding_latest_at_subq,
      and_(
        EquipmentBindingHistory.equipment_sn == binding_latest_at_subq.c.sn,
        EquipmentBindingHistory.operated_at == binding_latest_at_subq.c.latest_at,
      ),
    )
    .filter(EquipmentBindingHistory.equipment_sn.in_(sns))
    .group_by(EquipmentBindingHistory.equipment_sn)
    .subquery()
  )

  latest_bindings = (
    db.query(EquipmentBindingHistory, Site)
    .join(binding_latest_id_subq, EquipmentBindingHistory.id == binding_latest_id_subq.c.latest_id)
    .join(Site, EquipmentBindingHistory.site_id == Site.id)
    .filter(EquipmentBindingHistory.action != BindingActionEnum.UNBIND)
    .all()
  )

  # 构建 SN -> 站点 的映射
  sn_site_map: Dict[str, Dict[str, Any]] = {}
  for bh, site in latest_bindings:
    key = (bh.equipment_sn or "").strip()
    if not key:
      continue
    sn_site_map[key] = {
      "site_id": site.id,
      "site_code": site.site_code,
      "site_name": site.site_name,
    }

  items: List[OmcDeviceStateItem] = []
  for state in states:
    site_info = sn_site_map.get(state.sn or "", {})
    items.append(
      OmcDeviceStateItem(
        sn=state.sn,
        omc_online_raw=state.omc_online_raw,
        omc_active_raw=state.omc_active_raw,
        ever_online=bool(state.ever_online),
        ever_activated=bool(state.ever_activated),
        first_online_at=state.first_online_at,
        first_activated_at=state.first_activated_at,
        last_seen_at=state.last_seen_at,
        last_source=state.last_source,
        current_site_id=site_info.get("site_id"),
        current_site_code=site_info.get("site_code"),
        current_site_name=site_info.get("site_name"),
      )
    )

  return OmcDeviceStateListResponse(total=total, items=items)


@router.post("/test", response_model=OmcTestResponse)
async def test_omc_connection(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  使用当前配置测试与 OMC API 的连通性（仅 admin）。

  - 会尝试调用 /northboundApi/v1/access/token 获取 Token
  - 成功则返回 success=True；失败则返回具体错误信息
  """
  _ensure_admin(current_user)

  cfg = load_omc_config(db)
  if not cfg:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="未找到有效的 OMC 配置，请先保存配置后再测试。",
    )

  try:
    # 使用当前配置尝试获取 Token，用于同时验证连通性和账号密码是否正确
    client = OmcClient(
      base_url=cfg["base_url"],
      username=cfg["username"],
      password=cfg["password"],
      timeout_seconds=cfg.get("timeout_seconds", 10),
    )
    token = client._get_access_token()  # noqa: SLF001
    preview = token[:16] + "..." if token else ""
    return OmcTestResponse(
      success=True,
      message=f"与 OMC 连通成功，账号密码校验通过，Token 前缀: {preview}",
    )
  except Exception as exc:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"连接 OMC 或校验账号失败: {exc}",
    ) from exc


@router.get("/devices/{sn}/status", response_model=OmcDeviceStatusBySnResponse)
async def get_device_status_by_sn(
  sn: str,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
) -> OmcDeviceStatusBySnResponse:
  """
  按设备 SN 直接查询 OMC 在线 / 激活状态。

  - 在线状态：OMC /northboundApi/v1/enodeb/infos/status/{sn}
  - 激活状态：OMC /northboundApi/v1/enodeb/infos/cert/status/{sn}
  - 所有登录用户均可查询
  """
  # 仅要求登录即可；不做角色限制
  _ = current_user

  client = get_omc_client(db)
  if not client:
    raise HTTPException(
      status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
      detail="OMC 未配置，请先在后台配置 OMC API",
    )

  try:
    status_payload = client.get_enodeb_status(sn)
  except Exception as exc:
    # 兜底：遇到 404 等异常返回离线状态，仍向前端返回 200，便于查看最新状态
    # 同时写入聚合表，避免保留旧值
    online = False
    activated = False
    status_payload = {"error": str(exc)}
    upsert_omc_device_state(
      db=db,
      sn=sn,
      online_raw=online,
      activated_raw=activated,
      source="api_poll",
      status_payload=status_payload,
    )
    db.commit()
    return OmcDeviceStatusBySnResponse(
      sn=sn,
      online=online,
      activated=activated,
      checked_at=datetime.utcnow().isoformat() + "Z",
      status_payload=status_payload,
    )

  online = parse_online_flag(status_payload)
  # 设备激活: 基于 /enodeb/infos/status 返回中的 cellStatus 判断
  activated = parse_activated_flag(status_payload)

  checked_at = datetime.utcnow().isoformat() + "Z"

  # 写入 SN 聚合状态（只升不降 ever，但原始状态可回退），无论 OMC 返回是否成功都更新 omc_online_raw
  upsert_omc_device_state(
    db=db,
    sn=sn,
    online_raw=bool(online),
    activated_raw=bool(activated),
    source="api_poll",
    status_payload=status_payload,
  )

  # 若该 SN 当前绑定站点存在，则基于聚合表尝试推进开站工单/站点状态（仅向前推进）
  try:
    binding = db.query(EquipmentBindingHistory).filter(
      EquipmentBindingHistory.equipment_sn == sn,
      EquipmentBindingHistory.action != BindingActionEnum.UNBIND
    ).order_by(EquipmentBindingHistory.operated_at.desc()).first()
    if binding and binding.site_id:
      advance_opening_work_orders_by_ever(db, binding.site_id)
  except Exception as exc:  # pragma: no cover
    print(f"[OMC] SN={sn} 推进工单/站点状态失败: {exc}")

  db.commit()

  return OmcDeviceStatusBySnResponse(
    sn=sn,
    online=bool(online),
    activated=bool(activated),
    checked_at=checked_at,
    status_payload=status_payload,
  )
