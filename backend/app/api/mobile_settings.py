from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.system_config import SystemConfig


router = APIRouter()


class LocationModeResponse(BaseModel):
  """移动端定位模式响应模型（兼容旧接口，仅返回全局默认值）。"""

  mode: str


class LocationModePayload(BaseModel):
  """更新定位模式（全局默认）的请求载荷。"""

  mode: str


class LocationModeRule(BaseModel):
  """
  单个配置项的生效规则：

  - default: 全局默认值
  - per_role: 按角色覆盖
  - per_user: 按用户覆盖（key 为用户ID字符串）
  """

  default: str = "baidu"
  per_role: Dict[str, str] = {}
  per_user: Dict[str, str] = {}


class BoolRule(BaseModel):
  """
  通用布尔配置项规则：

  - default: 全局默认布尔值
  - per_role: 按角色覆盖
  - per_user: 按用户覆盖（key 为用户ID字符串）
  """

  default: bool = True
  per_role: Dict[str, bool] = {}
  per_user: Dict[str, bool] = {}


class MobileSettingsPayload(BaseModel):
  """
  移动端配置载荷。

  - location_mode: 定位模式配置
  - allow_local_photo_upload: 是否允许检查详情本地上传图片
  - local_upload_watermark_with_geo: 检查详情本地上传水印是否携带经纬度和地址

  未来可在此处继续新增更多配置项，
  每个配置项都采用类似 *Rule 的结构。
  """

  location_mode: Optional[LocationModeRule] = None
  allow_local_photo_upload: Optional[BoolRule] = None
  local_upload_watermark_with_geo: Optional[BoolRule] = None
  enable_legacy_scan_pickup: Optional[BoolRule] = None


class EffectiveMobileSettingsResponse(BaseModel):
  """对当前用户“最终生效”的移动端配置。"""

  location_mode: str
  allow_local_photo_upload: bool = True
  local_upload_watermark_with_geo: bool = True
  enable_legacy_scan_pickup: bool = False


def _normalize_mode(mode: str) -> str:
  value = (mode or "").strip().lower()
  if value not in ("native", "baidu"):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="mode 仅支持 'native' 或 'baidu'",
    )
  return value


def _normalize_location_mode_rule(rule: LocationModeRule) -> Dict[str, Any]:
  """
  规范化前端传入的 LocationModeRule，确保：
  - 所有模式值合法且小写
  - per_user 的 key 为字符串
  """
  normalized_default = _normalize_mode(rule.default)

  per_role: Dict[str, str] = {}
  for role, mode in (rule.per_role or {}).items():
    role_key = (role or "").strip()
    if not role_key:
      continue
    per_role[role_key] = _normalize_mode(mode)

  per_user: Dict[str, str] = {}
  for user_id, mode in (rule.per_user or {}).items():
    key = str(user_id).strip()
    if not key:
      continue
    per_user[key] = _normalize_mode(mode)

  return {
    "default": normalized_default,
    "per_role": per_role,
    "per_user": per_user,
  }


def _normalize_bool_rule(rule: BoolRule) -> Dict[str, Any]:
  """
  规范化前端传入的 BoolRule，确保：
  - default 为布尔值
  - per_role / per_user 的 key 规范化为字符串，值为布尔值
  """
  default_val = bool(rule.default)

  per_role: Dict[str, bool] = {}
  for role, value in (rule.per_role or {}).items():
    role_key = (role or "").strip()
    if not role_key:
      continue
    per_role[role_key] = bool(value)

  per_user: Dict[str, bool] = {}
  for user_id, value in (rule.per_user or {}).items():
    key = str(user_id).strip()
    if not key:
      continue
    per_user[key] = bool(value)

  return {
    "default": default_val,
    "per_role": per_role,
    "per_user": per_user,
  }


def _load_mobile_settings(db: Session) -> Dict[str, Any]:
  row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_settings").first()
  if not row or not row.value:
    return {}
  data = row.value or {}
  if not isinstance(data, dict):
    return {}
  return data


def _save_mobile_settings(db: Session, settings: Dict[str, Any]) -> None:
  row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_settings").first()
  if not row:
    row = SystemConfig(key="mobile_settings", value=settings)
    db.add(row)
  else:
    row.value = settings
    flag_modified(row, "value")
  db.commit()


def _get_legacy_location_mode(db: Session) -> str:
  """
  兼容旧版本，仅使用 SystemConfig(key='mobile_location_mode') 里的简单结构。
  """
  row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_location_mode").first()
  if not row or not row.value:
    return "baidu"

  data = row.value or {}
  mode = str(data.get("mode") or "").strip().lower()
  if mode not in ("native", "baidu"):
    return "baidu"
  return mode


def _resolve_location_mode_for_user(
  settings: Dict[str, Any],
  user: Optional[User],
  db: Optional[Session] = None,
) -> str:
  """
  根据配置与用户信息，解析对该用户最终生效的 location_mode。

  优先级：
  1. per_user[user.id]
  2. per_role[user.role]
  3. default
  4. 若上述都无效，则：
     - 若存在旧配置 mobile_location_mode，则使用旧配置
     - 否则默认 'baidu'
  """
  rule = (settings or {}).get("location_mode") or {}
  default_val = str(rule.get("default") or "").strip().lower()
  per_role = rule.get("per_role") or {}
  per_user = rule.get("per_user") or {}

  # 1. 按用户覆盖
  if user is not None and getattr(user, "id", None) is not None:
    key = str(user.id)
    user_mode = str(per_user.get(key) or "").strip().lower()
    if user_mode in ("native", "baidu"):
      return user_mode

  # 2. 按角色覆盖
  if user is not None and getattr(user, "role", None):
    role_mode = str(per_role.get(user.role) or "").strip().lower()
    if role_mode in ("native", "baidu"):
      return role_mode

  # 3. 全局默认
  if default_val in ("native", "baidu"):
    return default_val

  # 4. 兼容旧配置
  if db is not None:
    return _get_legacy_location_mode(db)

  return "baidu"


def _resolve_bool_for_user(
  settings: Dict[str, Any],
  key: str,
  user: Optional[User],
  default: bool,
) -> bool:
  """
  根据配置与用户信息，解析对该用户最终生效的布尔配置。

  优先级：
  1. per_user[user.id]
  2. per_role[user.role]
  3. default（若配置中缺失，则回退到传入的 default）
  """
  rule = (settings or {}).get(key) or {}
  raw_default = rule.get("default")
  if isinstance(raw_default, bool):
    default_val = raw_default
  else:
    default_val = default

  per_role = rule.get("per_role") or {}
  per_user = rule.get("per_user") or {}

  # 1. 按用户覆盖
  if user is not None and getattr(user, "id", None) is not None:
    ukey = str(user.id)
    if ukey in per_user:
      return bool(per_user[ukey])

  # 2. 按角色覆盖
  if user is not None and getattr(user, "role", None):
    role_key = user.role
    if role_key in per_role:
      return bool(per_role[role_key])

  # 3. 全局默认
  return default_val


def _get_location_mode_default(db: Session) -> str:
  """
  获取 location_mode 的全局默认值（不考虑 per_user、per_role）。

  - 优先从 mobile_settings.location_mode.default 读取
  - 若不存在，则回退到旧配置 mobile_location_mode
  - 最终默认值为 'baidu'
  """
  settings = _load_mobile_settings(db)
  rule = (settings or {}).get("location_mode") or {}
  default_val = str(rule.get("default") or "").strip().lower()
  if default_val in ("native", "baidu"):
    return default_val
  return _get_legacy_location_mode(db)


def _require_admin_or_manager(user: User) -> None:
  if user.role not in ("admin", "manager"):
    raise HTTPException(
      status_code=status.HTTP_403_FORBIDDEN,
      detail="只有管理员或项目经理可以修改配置",
    )


@router.get("/mobile-settings", response_model=MobileSettingsPayload)
async def get_mobile_settings(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取完整的移动端配置（仅管理员/项目经理可见）。

  - 目前包含 location_mode / 本地上传 / 水印定位信息 / 旧流程扫码领货等配置项
  - 返回原始配置结构（包含 default/per_role/per_user）
  """
  _require_admin_or_manager(current_user)

  raw = _load_mobile_settings(db)
  location_rule = raw.get("location_mode") or {}
  # allow_local_photo_upload 若不存在，则使用默认结构
  allow_upload_rule = raw.get("allow_local_photo_upload") or {}
  local_upload_watermark_rule = raw.get("local_upload_watermark_with_geo") or {}
  legacy_scan_pickup_rule = raw.get("enable_legacy_scan_pickup") or {}

  # 构造 LocationModeRule，保证字段存在
  lm = LocationModeRule(
    default=location_rule.get("default") or "baidu",
    per_role=location_rule.get("per_role") or {},
    per_user=location_rule.get("per_user") or {},
  )

  allow_upload = BoolRule(
    default=allow_upload_rule.get("default") if isinstance(allow_upload_rule.get("default"), bool) else True,
    per_role=allow_upload_rule.get("per_role") or {},
    per_user=allow_upload_rule.get("per_user") or {},
  )

  local_upload_watermark = BoolRule(
    default=local_upload_watermark_rule.get("default") if isinstance(local_upload_watermark_rule.get("default"), bool) else True,
    per_role=local_upload_watermark_rule.get("per_role") or {},
    per_user=local_upload_watermark_rule.get("per_user") or {},
  )

  return MobileSettingsPayload(
    location_mode=lm,
    allow_local_photo_upload=allow_upload,
    local_upload_watermark_with_geo=local_upload_watermark,
    enable_legacy_scan_pickup=BoolRule(
      default=legacy_scan_pickup_rule.get("default") if isinstance(legacy_scan_pickup_rule.get("default"), bool) else False,
      per_role=legacy_scan_pickup_rule.get("per_role") or {},
      per_user=legacy_scan_pickup_rule.get("per_user") or {},
    ),
  )


@router.put("/mobile-settings", response_model=MobileSettingsPayload)
async def update_mobile_settings(
  payload: MobileSettingsPayload,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  更新移动端配置（仅管理员/项目经理）。

  - 支持多项移动端配置项（见 MobileSettingsPayload）
  - 每个配置项都采用 default/per_role/per_user 结构
  """
  _require_admin_or_manager(current_user)

  settings = _load_mobile_settings(db)

  if payload.location_mode is not None:
    settings["location_mode"] = _normalize_location_mode_rule(payload.location_mode)

    # 同步更新旧配置中的全局默认值，保留兼容性
    legacy_default = settings["location_mode"]["default"]
    legacy_row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_location_mode").first()
    if not legacy_row:
      legacy_row = SystemConfig(key="mobile_location_mode", value={"mode": legacy_default})
      db.add(legacy_row)
    else:
      legacy_data = legacy_row.value or {}
      legacy_data["mode"] = legacy_default
      legacy_row.value = legacy_data
      flag_modified(legacy_row, "value")

  if payload.allow_local_photo_upload is not None:
    settings["allow_local_photo_upload"] = _normalize_bool_rule(payload.allow_local_photo_upload)

  if payload.local_upload_watermark_with_geo is not None:
    settings["local_upload_watermark_with_geo"] = _normalize_bool_rule(payload.local_upload_watermark_with_geo)

  if payload.enable_legacy_scan_pickup is not None:
    settings["enable_legacy_scan_pickup"] = _normalize_bool_rule(payload.enable_legacy_scan_pickup)

  _save_mobile_settings(db, settings)

  # 返回最新配置
  location_rule = settings.get("location_mode") or {}
  lm = LocationModeRule(
    default=location_rule.get("default") or "baidu",
    per_role=location_rule.get("per_role") or {},
    per_user=location_rule.get("per_user") or {},
  )

  allow_upload_rule = settings.get("allow_local_photo_upload") or {}
  allow_upload = BoolRule(
    default=allow_upload_rule.get("default") if isinstance(allow_upload_rule.get("default"), bool) else True,
    per_role=allow_upload_rule.get("per_role") or {},
    per_user=allow_upload_rule.get("per_user") or {},
  )

  local_upload_watermark_rule = settings.get("local_upload_watermark_with_geo") or {}
  local_upload_watermark = BoolRule(
    default=local_upload_watermark_rule.get("default") if isinstance(local_upload_watermark_rule.get("default"), bool) else True,
    per_role=local_upload_watermark_rule.get("per_role") or {},
    per_user=local_upload_watermark_rule.get("per_user") or {},
  )

  legacy_scan_pickup_rule = settings.get("enable_legacy_scan_pickup") or {}
  legacy_scan_pickup = BoolRule(
    default=legacy_scan_pickup_rule.get("default") if isinstance(legacy_scan_pickup_rule.get("default"), bool) else False,
    per_role=legacy_scan_pickup_rule.get("per_role") or {},
    per_user=legacy_scan_pickup_rule.get("per_user") or {},
  )

  return MobileSettingsPayload(
    location_mode=lm,
    allow_local_photo_upload=allow_upload,
    local_upload_watermark_with_geo=local_upload_watermark,
    enable_legacy_scan_pickup=legacy_scan_pickup,
  )


@router.get("/mobile-settings/effective", response_model=EffectiveMobileSettingsResponse)
async def get_effective_mobile_settings(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取“对当前登录用户”最终生效的移动端配置。

  - APP 侧应优先调用本接口，以便支持按用户/角色的覆盖配置
  - 若未配置，则自动回退到全局默认或旧配置
  """
  settings = _load_mobile_settings(db)
  location_mode = _resolve_location_mode_for_user(settings, current_user, db=db)
  allow_local_photo_upload = _resolve_bool_for_user(
    settings,
    key="allow_local_photo_upload",
    user=current_user,
    default=True,
  )
  local_upload_watermark_with_geo = _resolve_bool_for_user(
    settings,
    key="local_upload_watermark_with_geo",
    user=current_user,
    default=True,
  )
  enable_legacy_scan_pickup = _resolve_bool_for_user(
    settings,
    key="enable_legacy_scan_pickup",
    user=current_user,
    default=False,
  )
  return EffectiveMobileSettingsResponse(
    location_mode=location_mode,
    allow_local_photo_upload=allow_local_photo_upload,
    local_upload_watermark_with_geo=local_upload_watermark_with_geo,
    enable_legacy_scan_pickup=enable_legacy_scan_pickup,
  )


@router.get("/location-mode", response_model=LocationModeResponse)
async def get_location_mode(
  db: Session = Depends(get_db),
):
  """
  获取当前移动端定位模式的“全局默认”值（兼容旧接口）。

  - 返回值示例：{"mode": "baidu"} 或 {"mode": "native"}
  - 该接口对所有客户端开放，不强制登录，仅用于读取全局默认配置
  """
  mode = _get_location_mode_default(db)
  return LocationModeResponse(mode=mode)


@router.put("/location-mode", response_model=LocationModeResponse)
async def update_location_mode(
  payload: LocationModePayload,
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  更新移动端定位模式的“全局默认”值（兼容旧接口，仅管理员/项目经理可用）。

  - mode 仅支持 'native' 或 'baidu'
  - 将同步更新：
    1) mobile_settings.location_mode.default
    2) legacy SystemConfig(key='mobile_location_mode') 的 mode 字段
  """
  _require_admin_or_manager(current_user)

  mode = _normalize_mode(payload.mode)

  # 更新新结构中的 default
  settings = _load_mobile_settings(db)
  rule = settings.get("location_mode") or {}
  rule["default"] = mode
  rule.setdefault("per_role", {})
  rule.setdefault("per_user", {})
  settings["location_mode"] = rule

  _save_mobile_settings(db, settings)

  # 同步更新旧结构中的 mode
  legacy_row = db.query(SystemConfig).filter(SystemConfig.key == "mobile_location_mode").first()
  if not legacy_row:
    legacy_row = SystemConfig(key="mobile_location_mode", value={"mode": mode})
    db.add(legacy_row)
  else:
    legacy_data = legacy_row.value or {}
    legacy_data["mode"] = mode
    legacy_row.value = legacy_data
    flag_modified(legacy_row, "value")

  db.commit()

  return LocationModeResponse(mode=mode)
