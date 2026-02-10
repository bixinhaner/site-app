from typing import Any, Callable, Dict, Optional

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


class IntRule(BaseModel):
  """
  通用整型配置项规则（用于距离阈值等）：

  - default: 全局默认值
  - per_role: 按角色覆盖
  - per_user: 按用户覆盖（key 为用户ID字符串）
  """

  default: int = 100
  per_role: Dict[str, int] = {}
  per_user: Dict[str, int] = {}


class FloatRule(BaseModel):
  """
  通用浮点配置项规则（用于相似度阈值等）：

  - default: 全局默认值
  - per_role: 按角色覆盖
  - per_user: 按用户覆盖（key 为用户ID字符串）
  """

  default: float = 0.975
  per_role: Dict[str, float] = {}
  per_user: Dict[str, float] = {}


class MobileSettingsPayload(BaseModel):
  """
  移动端配置载荷。

  - location_mode: 定位模式配置
  - allow_local_photo_upload: 是否允许检查详情本地上传图片
  - local_upload_watermark_with_geo: 检查详情本地上传水印是否携带经纬度和地址
  - enable_photo_location_distance_check: 拍照时是否启用“实拍坐标 vs 规划坐标”距离比对
  - photo_location_distance_threshold_m: 超距阈值（米）
  - distance_exceed_block_upload: 超距是否阻断上传
  - block_duplicate_check_item_photo_upload: 是否阻断检查项重复图片上传
  - enable_check_item_photo_similarity_alert: 是否启用检查项照片相似度提醒
  - check_item_photo_similarity_window_days: 相似度匹配窗口（天）
  - check_item_photo_similarity_phash_threshold: 相似度粗筛阈值（0~64）
  - check_item_photo_similarity_vector_threshold: 相似度精筛阈值（0~1）

  未来可在此处继续新增更多配置项，
  每个配置项都采用类似 *Rule 的结构。
  """

  location_mode: Optional[LocationModeRule] = None
  allow_local_photo_upload: Optional[BoolRule] = None
  local_upload_watermark_with_geo: Optional[BoolRule] = None
  enable_legacy_scan_pickup: Optional[BoolRule] = None
  enable_photo_location_distance_check: Optional[BoolRule] = None
  distance_exceed_block_upload: Optional[BoolRule] = None
  block_duplicate_check_item_photo_upload: Optional[BoolRule] = None
  enable_check_item_photo_similarity_alert: Optional[BoolRule] = None
  check_item_photo_similarity_window_days: Optional[IntRule] = None
  check_item_photo_similarity_phash_threshold: Optional[IntRule] = None
  check_item_photo_similarity_vector_threshold: Optional[FloatRule] = None
  photo_location_distance_threshold_m: Optional[IntRule] = None


class EffectiveMobileSettingsResponse(BaseModel):
  """对当前用户“最终生效”的移动端配置。"""

  location_mode: str
  allow_local_photo_upload: bool = True
  local_upload_watermark_with_geo: bool = True
  enable_legacy_scan_pickup: bool = False
  enable_photo_location_distance_check: bool = True
  distance_exceed_block_upload: bool = False
  block_duplicate_check_item_photo_upload: bool = True
  enable_check_item_photo_similarity_alert: bool = True
  check_item_photo_similarity_window_days: int = 180
  check_item_photo_similarity_phash_threshold: int = 8
  check_item_photo_similarity_vector_threshold: float = 0.975
  photo_location_distance_threshold_m: int = 100


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


def _normalize_distance_threshold(value: Any) -> int:
  try:
    ivalue = int(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="距离阈值必须是整数（米）",
    )

  if ivalue < 1 or ivalue > 10000:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="距离阈值范围必须在 1~10000 米",
    )
  return ivalue


def _normalize_similarity_window_days(value: Any) -> int:
  try:
    ivalue = int(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度窗口天数必须是整数",
    )

  if ivalue < 1 or ivalue > 3650:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度窗口天数范围必须在 1~3650 天",
    )
  return ivalue


def _normalize_similarity_phash_threshold(value: Any) -> int:
  try:
    ivalue = int(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度粗筛阈值必须是整数",
    )

  if ivalue < 0 or ivalue > 64:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度粗筛阈值范围必须在 0~64",
    )
  return ivalue


def _normalize_similarity_vector_threshold(value: Any) -> float:
  try:
    fvalue = float(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度精筛阈值必须是数字",
    )

  if fvalue < 0.0 or fvalue > 1.0:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="相似度精筛阈值范围必须在 0~1",
    )
  return round(fvalue, 6)


def _normalize_int_rule(
  rule: IntRule,
  value_normalizer: Callable[[Any], int] = _normalize_distance_threshold,
) -> Dict[str, Any]:
  """
  规范化前端传入的 IntRule，确保：
  - default 为合法整数
  - per_role / per_user 的 key 规范化为字符串，值为合法整数
  """
  default_val = value_normalizer(rule.default)

  per_role: Dict[str, int] = {}
  for role, value in (rule.per_role or {}).items():
    role_key = (role or "").strip()
    if not role_key:
      continue
    per_role[role_key] = value_normalizer(value)

  per_user: Dict[str, int] = {}
  for user_id, value in (rule.per_user or {}).items():
    key = str(user_id).strip()
    if not key:
      continue
    per_user[key] = value_normalizer(value)

  return {
    "default": default_val,
    "per_role": per_role,
    "per_user": per_user,
  }


def _normalize_float_rule(
  rule: FloatRule,
  value_normalizer: Callable[[Any], float] = _normalize_similarity_vector_threshold,
) -> Dict[str, Any]:
  """
  规范化前端传入的 FloatRule，确保：
  - default 为合法浮点数
  - per_role / per_user 的 key 规范化为字符串，值为合法浮点数
  """
  default_val = value_normalizer(rule.default)

  per_role: Dict[str, float] = {}
  for role, value in (rule.per_role or {}).items():
    role_key = (role or "").strip()
    if not role_key:
      continue
    per_role[role_key] = value_normalizer(value)

  per_user: Dict[str, float] = {}
  for user_id, value in (rule.per_user or {}).items():
    key = str(user_id).strip()
    if not key:
      continue
    per_user[key] = value_normalizer(value)

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


def _resolve_int_for_user(
  settings: Dict[str, Any],
  key: str,
  user: Optional[User],
  default: int,
  value_normalizer: Callable[[Any], int] = _normalize_distance_threshold,
) -> int:
  """
  根据配置与用户信息，解析对该用户最终生效的整型配置。

  优先级：
  1. per_user[user.id]
  2. per_role[user.role]
  3. default（若配置中缺失，则回退到传入的 default）
  """
  rule = (settings or {}).get(key) or {}
  raw_default = rule.get("default")
  if raw_default is None:
    default_val = default
  else:
    default_val = value_normalizer(raw_default)

  per_role = rule.get("per_role") or {}
  per_user = rule.get("per_user") or {}

  # 1. 按用户覆盖
  if user is not None and getattr(user, "id", None) is not None:
    ukey = str(user.id)
    if ukey in per_user:
      return value_normalizer(per_user[ukey])

  # 2. 按角色覆盖
  if user is not None and getattr(user, "role", None):
    role_key = user.role
    if role_key in per_role:
      return value_normalizer(per_role[role_key])

  # 3. 全局默认
  return default_val


def _resolve_float_for_user(
  settings: Dict[str, Any],
  key: str,
  user: Optional[User],
  default: float,
  value_normalizer: Callable[[Any], float] = _normalize_similarity_vector_threshold,
) -> float:
  """
  根据配置与用户信息，解析对该用户最终生效的浮点配置。

  优先级：
  1. per_user[user.id]
  2. per_role[user.role]
  3. default（若配置中缺失，则回退到传入的 default）
  """
  rule = (settings or {}).get(key) or {}
  raw_default = rule.get("default")
  if raw_default is None:
    default_val = default
  else:
    default_val = value_normalizer(raw_default)

  per_role = rule.get("per_role") or {}
  per_user = rule.get("per_user") or {}

  # 1. 按用户覆盖
  if user is not None and getattr(user, "id", None) is not None:
    ukey = str(user.id)
    if ukey in per_user:
      return value_normalizer(per_user[ukey])

  # 2. 按角色覆盖
  if user is not None and getattr(user, "role", None):
    role_key = user.role
    if role_key in per_role:
      return value_normalizer(per_role[role_key])

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
  location_distance_check_rule = raw.get("enable_photo_location_distance_check") or {}
  distance_block_upload_rule = raw.get("distance_exceed_block_upload") or {}
  duplicate_check_item_photo_rule = raw.get("block_duplicate_check_item_photo_upload") or {}
  similarity_alert_rule = raw.get("enable_check_item_photo_similarity_alert") or {}
  similarity_window_days_rule = raw.get("check_item_photo_similarity_window_days") or {}
  similarity_phash_threshold_rule = raw.get("check_item_photo_similarity_phash_threshold") or {}
  similarity_vector_threshold_rule = raw.get("check_item_photo_similarity_vector_threshold") or {}
  distance_threshold_rule = raw.get("photo_location_distance_threshold_m") or {}

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

  location_distance_check = BoolRule(
    default=location_distance_check_rule.get("default") if isinstance(location_distance_check_rule.get("default"), bool) else True,
    per_role=location_distance_check_rule.get("per_role") or {},
    per_user=location_distance_check_rule.get("per_user") or {},
  )

  distance_block_upload = BoolRule(
    default=distance_block_upload_rule.get("default") if isinstance(distance_block_upload_rule.get("default"), bool) else False,
    per_role=distance_block_upload_rule.get("per_role") or {},
    per_user=distance_block_upload_rule.get("per_user") or {},
  )

  duplicate_check_item_photo_upload = BoolRule(
    default=duplicate_check_item_photo_rule.get("default") if isinstance(duplicate_check_item_photo_rule.get("default"), bool) else True,
    per_role=duplicate_check_item_photo_rule.get("per_role") or {},
    per_user=duplicate_check_item_photo_rule.get("per_user") or {},
  )

  similarity_alert = BoolRule(
    default=similarity_alert_rule.get("default") if isinstance(similarity_alert_rule.get("default"), bool) else True,
    per_role=similarity_alert_rule.get("per_role") or {},
    per_user=similarity_alert_rule.get("per_user") or {},
  )

  similarity_window_days = IntRule(
    default=_normalize_similarity_window_days(similarity_window_days_rule.get("default")) if similarity_window_days_rule.get("default") is not None else 180,
    per_role={
      str(k): _normalize_similarity_window_days(v)
      for k, v in (similarity_window_days_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_window_days(v)
      for k, v in (similarity_window_days_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  similarity_phash_threshold = IntRule(
    default=_normalize_similarity_phash_threshold(similarity_phash_threshold_rule.get("default")) if similarity_phash_threshold_rule.get("default") is not None else 8,
    per_role={
      str(k): _normalize_similarity_phash_threshold(v)
      for k, v in (similarity_phash_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_phash_threshold(v)
      for k, v in (similarity_phash_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  similarity_vector_threshold = FloatRule(
    default=_normalize_similarity_vector_threshold(similarity_vector_threshold_rule.get("default")) if similarity_vector_threshold_rule.get("default") is not None else 0.975,
    per_role={
      str(k): _normalize_similarity_vector_threshold(v)
      for k, v in (similarity_vector_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_vector_threshold(v)
      for k, v in (similarity_vector_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  distance_threshold = IntRule(
    default=_normalize_distance_threshold(distance_threshold_rule.get("default")) if distance_threshold_rule.get("default") is not None else 100,
    per_role={
      str(k): _normalize_distance_threshold(v)
      for k, v in (distance_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_distance_threshold(v)
      for k, v in (distance_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
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
    enable_photo_location_distance_check=location_distance_check,
    distance_exceed_block_upload=distance_block_upload,
    block_duplicate_check_item_photo_upload=duplicate_check_item_photo_upload,
    enable_check_item_photo_similarity_alert=similarity_alert,
    check_item_photo_similarity_window_days=similarity_window_days,
    check_item_photo_similarity_phash_threshold=similarity_phash_threshold,
    check_item_photo_similarity_vector_threshold=similarity_vector_threshold,
    photo_location_distance_threshold_m=distance_threshold,
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

  if payload.enable_photo_location_distance_check is not None:
    settings["enable_photo_location_distance_check"] = _normalize_bool_rule(payload.enable_photo_location_distance_check)

  if payload.distance_exceed_block_upload is not None:
    settings["distance_exceed_block_upload"] = _normalize_bool_rule(payload.distance_exceed_block_upload)

  if payload.block_duplicate_check_item_photo_upload is not None:
    settings["block_duplicate_check_item_photo_upload"] = _normalize_bool_rule(payload.block_duplicate_check_item_photo_upload)

  if payload.enable_check_item_photo_similarity_alert is not None:
    settings["enable_check_item_photo_similarity_alert"] = _normalize_bool_rule(payload.enable_check_item_photo_similarity_alert)

  if payload.check_item_photo_similarity_window_days is not None:
    settings["check_item_photo_similarity_window_days"] = _normalize_int_rule(
      payload.check_item_photo_similarity_window_days,
      value_normalizer=_normalize_similarity_window_days,
    )

  if payload.check_item_photo_similarity_phash_threshold is not None:
    settings["check_item_photo_similarity_phash_threshold"] = _normalize_int_rule(
      payload.check_item_photo_similarity_phash_threshold,
      value_normalizer=_normalize_similarity_phash_threshold,
    )

  if payload.check_item_photo_similarity_vector_threshold is not None:
    settings["check_item_photo_similarity_vector_threshold"] = _normalize_float_rule(
      payload.check_item_photo_similarity_vector_threshold,
      value_normalizer=_normalize_similarity_vector_threshold,
    )

  if payload.photo_location_distance_threshold_m is not None:
    settings["photo_location_distance_threshold_m"] = _normalize_int_rule(payload.photo_location_distance_threshold_m)

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

  location_distance_check_rule = settings.get("enable_photo_location_distance_check") or {}
  location_distance_check = BoolRule(
    default=location_distance_check_rule.get("default") if isinstance(location_distance_check_rule.get("default"), bool) else True,
    per_role=location_distance_check_rule.get("per_role") or {},
    per_user=location_distance_check_rule.get("per_user") or {},
  )

  distance_block_upload_rule = settings.get("distance_exceed_block_upload") or {}
  distance_block_upload = BoolRule(
    default=distance_block_upload_rule.get("default") if isinstance(distance_block_upload_rule.get("default"), bool) else False,
    per_role=distance_block_upload_rule.get("per_role") or {},
    per_user=distance_block_upload_rule.get("per_user") or {},
  )

  duplicate_check_item_photo_rule = settings.get("block_duplicate_check_item_photo_upload") or {}
  duplicate_check_item_photo_upload = BoolRule(
    default=duplicate_check_item_photo_rule.get("default") if isinstance(duplicate_check_item_photo_rule.get("default"), bool) else True,
    per_role=duplicate_check_item_photo_rule.get("per_role") or {},
    per_user=duplicate_check_item_photo_rule.get("per_user") or {},
  )

  similarity_alert_rule = settings.get("enable_check_item_photo_similarity_alert") or {}
  similarity_alert = BoolRule(
    default=similarity_alert_rule.get("default") if isinstance(similarity_alert_rule.get("default"), bool) else True,
    per_role=similarity_alert_rule.get("per_role") or {},
    per_user=similarity_alert_rule.get("per_user") or {},
  )

  similarity_window_days_rule = settings.get("check_item_photo_similarity_window_days") or {}
  similarity_window_days = IntRule(
    default=_normalize_similarity_window_days(similarity_window_days_rule.get("default")) if similarity_window_days_rule.get("default") is not None else 180,
    per_role={
      str(k): _normalize_similarity_window_days(v)
      for k, v in (similarity_window_days_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_window_days(v)
      for k, v in (similarity_window_days_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  similarity_phash_threshold_rule = settings.get("check_item_photo_similarity_phash_threshold") or {}
  similarity_phash_threshold = IntRule(
    default=_normalize_similarity_phash_threshold(similarity_phash_threshold_rule.get("default")) if similarity_phash_threshold_rule.get("default") is not None else 8,
    per_role={
      str(k): _normalize_similarity_phash_threshold(v)
      for k, v in (similarity_phash_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_phash_threshold(v)
      for k, v in (similarity_phash_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  similarity_vector_threshold_rule = settings.get("check_item_photo_similarity_vector_threshold") or {}
  similarity_vector_threshold = FloatRule(
    default=_normalize_similarity_vector_threshold(similarity_vector_threshold_rule.get("default")) if similarity_vector_threshold_rule.get("default") is not None else 0.975,
    per_role={
      str(k): _normalize_similarity_vector_threshold(v)
      for k, v in (similarity_vector_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_similarity_vector_threshold(v)
      for k, v in (similarity_vector_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  distance_threshold_rule = settings.get("photo_location_distance_threshold_m") or {}
  distance_threshold = IntRule(
    default=_normalize_distance_threshold(distance_threshold_rule.get("default")) if distance_threshold_rule.get("default") is not None else 100,
    per_role={
      str(k): _normalize_distance_threshold(v)
      for k, v in (distance_threshold_rule.get("per_role") or {}).items()
      if str(k).strip() != ""
    },
    per_user={
      str(k): _normalize_distance_threshold(v)
      for k, v in (distance_threshold_rule.get("per_user") or {}).items()
      if str(k).strip() != ""
    },
  )

  return MobileSettingsPayload(
    location_mode=lm,
    allow_local_photo_upload=allow_upload,
    local_upload_watermark_with_geo=local_upload_watermark,
    enable_legacy_scan_pickup=legacy_scan_pickup,
    enable_photo_location_distance_check=location_distance_check,
    distance_exceed_block_upload=distance_block_upload,
    block_duplicate_check_item_photo_upload=duplicate_check_item_photo_upload,
    enable_check_item_photo_similarity_alert=similarity_alert,
    check_item_photo_similarity_window_days=similarity_window_days,
    check_item_photo_similarity_phash_threshold=similarity_phash_threshold,
    check_item_photo_similarity_vector_threshold=similarity_vector_threshold,
    photo_location_distance_threshold_m=distance_threshold,
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
  enable_photo_location_distance_check = _resolve_bool_for_user(
    settings,
    key="enable_photo_location_distance_check",
    user=current_user,
    default=True,
  )
  distance_exceed_block_upload = _resolve_bool_for_user(
    settings,
    key="distance_exceed_block_upload",
    user=current_user,
    default=False,
  )
  block_duplicate_check_item_photo_upload = _resolve_bool_for_user(
    settings,
    key="block_duplicate_check_item_photo_upload",
    user=current_user,
    default=True,
  )
  enable_check_item_photo_similarity_alert = _resolve_bool_for_user(
    settings,
    key="enable_check_item_photo_similarity_alert",
    user=current_user,
    default=True,
  )
  check_item_photo_similarity_window_days = _resolve_int_for_user(
    settings,
    key="check_item_photo_similarity_window_days",
    user=current_user,
    default=180,
    value_normalizer=_normalize_similarity_window_days,
  )
  check_item_photo_similarity_phash_threshold = _resolve_int_for_user(
    settings,
    key="check_item_photo_similarity_phash_threshold",
    user=current_user,
    default=8,
    value_normalizer=_normalize_similarity_phash_threshold,
  )
  check_item_photo_similarity_vector_threshold = _resolve_float_for_user(
    settings,
    key="check_item_photo_similarity_vector_threshold",
    user=current_user,
    default=0.975,
    value_normalizer=_normalize_similarity_vector_threshold,
  )
  photo_location_distance_threshold_m = _resolve_int_for_user(
    settings,
    key="photo_location_distance_threshold_m",
    user=current_user,
    default=100,
    value_normalizer=_normalize_distance_threshold,
  )
  return EffectiveMobileSettingsResponse(
    location_mode=location_mode,
    allow_local_photo_upload=allow_local_photo_upload,
    local_upload_watermark_with_geo=local_upload_watermark_with_geo,
    enable_legacy_scan_pickup=enable_legacy_scan_pickup,
    enable_photo_location_distance_check=enable_photo_location_distance_check,
    distance_exceed_block_upload=distance_exceed_block_upload,
    block_duplicate_check_item_photo_upload=block_duplicate_check_item_photo_upload,
    enable_check_item_photo_similarity_alert=enable_check_item_photo_similarity_alert,
    check_item_photo_similarity_window_days=check_item_photo_similarity_window_days,
    check_item_photo_similarity_phash_threshold=check_item_photo_similarity_phash_threshold,
    check_item_photo_similarity_vector_threshold=check_item_photo_similarity_vector_threshold,
    photo_location_distance_threshold_m=photo_location_distance_threshold_m,
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
