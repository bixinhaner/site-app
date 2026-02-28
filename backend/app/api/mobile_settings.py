import re
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


_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_HEX_COLOR_PATTERN = re.compile(r"^#([0-9A-Fa-f]{6})$")
_WATERMARK_POSITION_OPTIONS = ("topLeft", "topRight", "bottomLeft", "bottomRight", "center")


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


class WatermarkTemplateStyle(BaseModel):
  """照片水印样式配置。"""

  position: str = "bottomLeft"
  text_color: str = "#FF6600"
  background_color: str = "#000000"
  background_opacity: float = 0.7
  font_size: int = 28
  padding: int = 15
  margin: int = 20
  line_height: int = 35
  border_radius: int = 8
  max_width_ratio: float = 0.9
  area_ratio: float = 0.08


class WatermarkTemplateContent(BaseModel):
  """照片水印内容配置。"""

  show_icon: bool = True
  show_local_upload_note: bool = True
  show_gps: bool = True
  show_accuracy: bool = True
  show_address: bool = True
  show_timestamp: bool = True
  show_inspector: bool = True
  show_check_item: bool = True
  show_site_name: bool = True
  coordinate_precision: int = 6
  custom_prefix: str = ""
  custom_suffix: str = ""


class WatermarkTemplate(BaseModel):
  """单个照片水印模板。"""

  name: str = "默认模板"
  version: int = 1
  style: WatermarkTemplateStyle = WatermarkTemplateStyle()
  content: WatermarkTemplateContent = WatermarkTemplateContent()


class WatermarkTemplateRule(BaseModel):
  """
  水印模板分配规则：

  - default: 全局默认模板ID
  - per_role: 按角色覆盖模板ID
  - per_user: 按用户覆盖模板ID（key 为用户ID字符串）
  """

  default: str = "default"
  per_role: Dict[str, str] = {}
  per_user: Dict[str, str] = {}


class WatermarkScenePolicy(BaseModel):
  """照片水印场景策略。"""

  apply_for_camera: bool = True
  apply_for_album: bool = True
  force_local_upload_note_when_geo_disabled: bool = True


class EffectivePhotoWatermarkConfig(BaseModel):
  """当前用户生效的照片水印配置。"""

  template_id: str = "default"
  template: WatermarkTemplate = WatermarkTemplate()
  scene_policy: WatermarkScenePolicy = WatermarkScenePolicy()


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
  - photo_watermark_templates: 照片水印模板集合（key 为模板ID）
  - photo_watermark_template_rule: 照片水印模板分配规则（default/per_role/per_user）
  - photo_watermark_scene_policy: 照片水印场景策略（拍照/相册）

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
  photo_watermark_templates: Optional[Dict[str, WatermarkTemplate]] = None
  photo_watermark_template_rule: Optional[WatermarkTemplateRule] = None
  photo_watermark_scene_policy: Optional[WatermarkScenePolicy] = None


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
  photo_watermark_effective: EffectivePhotoWatermarkConfig = EffectivePhotoWatermarkConfig()


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


def _normalize_template_id(value: Any, field_name: str = "template_id") -> str:
  text = str(value or "").strip()
  if not text:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 不能为空",
    )
  if not _TEMPLATE_ID_PATTERN.match(text):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 仅支持字母、数字、下划线和中划线，长度 1~64",
    )
  return text


def _normalize_hex_color(value: Any, field_name: str) -> str:
  text = str(value or "").strip()
  if not _HEX_COLOR_PATTERN.match(text):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 必须是 #RRGGBB 格式",
    )
  return text.upper()


def _normalize_short_text(value: Any, field_name: str, max_len: int, default: str = "") -> str:
  text = str(value if value is not None else default).strip()
  if len(text) > max_len:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 长度不能超过 {max_len}",
    )
  return text


def _normalize_int_range(value: Any, field_name: str, min_value: int, max_value: int) -> int:
  try:
    ivalue = int(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 必须是整数",
    )
  if ivalue < min_value or ivalue > max_value:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 范围必须在 {min_value}~{max_value}",
    )
  return ivalue


def _normalize_float_range(value: Any, field_name: str, min_value: float, max_value: float) -> float:
  try:
    fvalue = float(value)
  except Exception:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 必须是数字",
    )
  if fvalue < min_value or fvalue > max_value:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"{field_name} 范围必须在 {min_value}~{max_value}",
    )
  return round(fvalue, 6)


def _build_default_watermark_template() -> Dict[str, Any]:
  return {
    "name": "默认模板",
    "version": 1,
    "style": {
      "position": "bottomLeft",
      "text_color": "#FF6600",
      "background_color": "#000000",
      "background_opacity": 0.7,
      "font_size": 28,
      "padding": 15,
      "margin": 20,
      "line_height": 35,
      "border_radius": 8,
      "max_width_ratio": 0.9,
      "area_ratio": 0.08,
    },
    "content": {
      "show_icon": True,
      "show_local_upload_note": True,
      "show_gps": True,
      "show_accuracy": True,
      "show_address": True,
      "show_timestamp": True,
      "show_inspector": True,
      "show_check_item": True,
      "show_site_name": True,
      "coordinate_precision": 6,
      "custom_prefix": "",
      "custom_suffix": "",
    },
  }


def _build_default_watermark_templates() -> Dict[str, Any]:
  return {"default": _build_default_watermark_template()}


def _build_default_watermark_scene_policy() -> Dict[str, Any]:
  return {
    "apply_for_camera": True,
    "apply_for_album": True,
    "force_local_upload_note_when_geo_disabled": True,
  }


def _normalize_watermark_template_style(style: WatermarkTemplateStyle) -> Dict[str, Any]:
  position = str(style.position or "").strip()
  if position not in _WATERMARK_POSITION_OPTIONS:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"水印位置仅支持: {', '.join(_WATERMARK_POSITION_OPTIONS)}",
    )

  return {
    "position": position,
    "text_color": _normalize_hex_color(style.text_color, "文字颜色"),
    "background_color": _normalize_hex_color(style.background_color, "背景颜色"),
    "background_opacity": _normalize_float_range(style.background_opacity, "背景透明度", 0.0, 1.0),
    "font_size": _normalize_int_range(style.font_size, "字体大小", 12, 96),
    "padding": _normalize_int_range(style.padding, "内边距", 0, 120),
    "margin": _normalize_int_range(style.margin, "外边距", 0, 120),
    "line_height": _normalize_int_range(style.line_height, "行高", 16, 140),
    "border_radius": _normalize_int_range(style.border_radius, "圆角", 0, 80),
    "max_width_ratio": _normalize_float_range(style.max_width_ratio, "最大宽度比例", 0.3, 1.0),
    "area_ratio": _normalize_float_range(style.area_ratio, "水印区域占比", 0.01, 0.4),
  }


def _normalize_watermark_template_content(content: WatermarkTemplateContent) -> Dict[str, Any]:
  return {
    "show_icon": bool(content.show_icon),
    "show_local_upload_note": bool(content.show_local_upload_note),
    "show_gps": bool(content.show_gps),
    "show_accuracy": bool(content.show_accuracy),
    "show_address": bool(content.show_address),
    "show_timestamp": bool(content.show_timestamp),
    "show_inspector": bool(content.show_inspector),
    "show_check_item": bool(content.show_check_item),
    "show_site_name": bool(content.show_site_name),
    "coordinate_precision": _normalize_int_range(content.coordinate_precision, "坐标精度", 2, 8),
    "custom_prefix": _normalize_short_text(content.custom_prefix, "前缀文本", 80, ""),
    "custom_suffix": _normalize_short_text(content.custom_suffix, "后缀文本", 80, ""),
  }


def _normalize_watermark_template(template: WatermarkTemplate) -> Dict[str, Any]:
  name = _normalize_short_text(template.name, "模板名称", 40, "未命名模板") or "未命名模板"
  version = _normalize_int_range(template.version, "模板版本号", 1, 999999)
  return {
    "name": name,
    "version": version,
    "style": _normalize_watermark_template_style(template.style),
    "content": _normalize_watermark_template_content(template.content),
  }


def _sanitize_watermark_templates_map(raw_templates: Any) -> Dict[str, Any]:
  if not isinstance(raw_templates, dict):
    return _build_default_watermark_templates()

  normalized: Dict[str, Any] = {}
  for raw_id, raw_tpl in raw_templates.items():
    try:
      tid = _normalize_template_id(raw_id, "模板ID")
      tpl_model = raw_tpl if isinstance(raw_tpl, WatermarkTemplate) else WatermarkTemplate(**(raw_tpl or {}))
      normalized[tid] = _normalize_watermark_template(tpl_model)
    except Exception:
      continue

  if not normalized:
    return _build_default_watermark_templates()

  if "default" not in normalized:
    normalized["default"] = _build_default_watermark_template()

  return normalized


def _normalize_watermark_templates_map(templates: Dict[str, WatermarkTemplate]) -> Dict[str, Any]:
  if not isinstance(templates, dict):
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="photo_watermark_templates 必须是对象",
    )
  if len(templates) > 50:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="水印模板数量不能超过 50",
    )

  normalized: Dict[str, Any] = {}
  for template_id, template in templates.items():
    tid = _normalize_template_id(template_id, "模板ID")
    normalized[tid] = _normalize_watermark_template(template)

  if not normalized:
    normalized = _build_default_watermark_templates()

  if "default" not in normalized:
    normalized["default"] = _build_default_watermark_template()

  return normalized


def _sanitize_watermark_template_rule(rule: Any, templates_map: Dict[str, Any]) -> Dict[str, Any]:
  allowed = set((templates_map or {}).keys())
  if not allowed:
    allowed = {"default"}

  raw_rule = rule if isinstance(rule, dict) else {}
  raw_default = str(raw_rule.get("default") or "").strip()
  default_template_id = raw_default if raw_default in allowed else ("default" if "default" in allowed else next(iter(allowed)))

  per_role: Dict[str, str] = {}
  for role, template_id in (raw_rule.get("per_role") or {}).items():
    role_key = str(role or "").strip()
    tid = str(template_id or "").strip()
    if not role_key or not tid:
      continue
    if tid in allowed:
      per_role[role_key] = tid

  per_user: Dict[str, str] = {}
  for user_id, template_id in (raw_rule.get("per_user") or {}).items():
    uid = str(user_id or "").strip()
    tid = str(template_id or "").strip()
    if not uid or not tid:
      continue
    if tid in allowed:
      per_user[uid] = tid

  return {
    "default": default_template_id,
    "per_role": per_role,
    "per_user": per_user,
  }


def _normalize_watermark_template_rule(rule: WatermarkTemplateRule, templates_map: Dict[str, Any]) -> Dict[str, Any]:
  allowed = set((templates_map or {}).keys())
  if not allowed:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="缺少可用的水印模板",
    )

  default_template_id = _normalize_template_id(rule.default, "默认模板ID")
  if default_template_id not in allowed:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"默认模板ID不存在: {default_template_id}",
    )

  per_role: Dict[str, str] = {}
  for role, template_id in (rule.per_role or {}).items():
    role_key = str(role or "").strip()
    tid = str(template_id or "").strip()
    if not role_key or not tid:
      continue
    normalized_tid = _normalize_template_id(tid, f"角色 {role_key} 的模板ID")
    if normalized_tid not in allowed:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"角色 {role_key} 的模板ID不存在: {normalized_tid}",
      )
    per_role[role_key] = normalized_tid

  per_user: Dict[str, str] = {}
  for user_id, template_id in (rule.per_user or {}).items():
    uid = str(user_id or "").strip()
    tid = str(template_id or "").strip()
    if not uid or not tid:
      continue
    normalized_tid = _normalize_template_id(tid, f"用户 {uid} 的模板ID")
    if normalized_tid not in allowed:
      raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"用户 {uid} 的模板ID不存在: {normalized_tid}",
      )
    per_user[uid] = normalized_tid

  return {
    "default": default_template_id,
    "per_role": per_role,
    "per_user": per_user,
  }


def _sanitize_watermark_scene_policy(raw_policy: Any) -> Dict[str, Any]:
  raw = raw_policy if isinstance(raw_policy, dict) else {}
  defaults = _build_default_watermark_scene_policy()
  return {
    "apply_for_camera": bool(raw.get("apply_for_camera")) if "apply_for_camera" in raw else defaults["apply_for_camera"],
    "apply_for_album": bool(raw.get("apply_for_album")) if "apply_for_album" in raw else defaults["apply_for_album"],
    "force_local_upload_note_when_geo_disabled": (
      bool(raw.get("force_local_upload_note_when_geo_disabled"))
      if "force_local_upload_note_when_geo_disabled" in raw
      else defaults["force_local_upload_note_when_geo_disabled"]
    ),
  }


def _normalize_watermark_scene_policy(policy: WatermarkScenePolicy) -> Dict[str, Any]:
  return {
    "apply_for_camera": bool(policy.apply_for_camera),
    "apply_for_album": bool(policy.apply_for_album),
    "force_local_upload_note_when_geo_disabled": bool(policy.force_local_upload_note_when_geo_disabled),
  }


def _resolve_watermark_template_id_for_user(
  settings: Dict[str, Any],
  user: Optional[User],
  templates_map: Dict[str, Any],
) -> str:
  rule = _sanitize_watermark_template_rule(
    (settings or {}).get("photo_watermark_template_rule") or {},
    templates_map,
  )

  per_user = rule.get("per_user") or {}
  per_role = rule.get("per_role") or {}
  default_template_id = str(rule.get("default") or "").strip()

  if user is not None and getattr(user, "id", None) is not None:
    uid = str(user.id)
    if uid in per_user:
      return per_user[uid]

  if user is not None and getattr(user, "role", None):
    role_key = str(user.role or "").strip()
    if role_key in per_role:
      return per_role[role_key]

  if default_template_id and default_template_id in templates_map:
    return default_template_id
  if "default" in templates_map:
    return "default"
  return next(iter(templates_map.keys()))


def _build_effective_photo_watermark(
  settings: Dict[str, Any],
  user: Optional[User],
) -> Dict[str, Any]:
  templates_map = _sanitize_watermark_templates_map(
    (settings or {}).get("photo_watermark_templates") or {},
  )
  scene_policy = _sanitize_watermark_scene_policy(
    (settings or {}).get("photo_watermark_scene_policy") or {},
  )
  template_id = _resolve_watermark_template_id_for_user(settings, user, templates_map)
  template = templates_map.get(template_id) or templates_map.get("default") or _build_default_watermark_template()
  return {
    "template_id": template_id,
    "template": template,
    "scene_policy": scene_policy,
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


def _build_mobile_settings_payload_from_raw(raw: Dict[str, Any]) -> MobileSettingsPayload:
  safe_raw = raw if isinstance(raw, dict) else {}

  location_rule = safe_raw.get("location_mode") or {}
  allow_upload_rule = safe_raw.get("allow_local_photo_upload") or {}
  local_upload_watermark_rule = safe_raw.get("local_upload_watermark_with_geo") or {}
  legacy_scan_pickup_rule = safe_raw.get("enable_legacy_scan_pickup") or {}
  location_distance_check_rule = safe_raw.get("enable_photo_location_distance_check") or {}
  distance_block_upload_rule = safe_raw.get("distance_exceed_block_upload") or {}
  duplicate_check_item_photo_rule = safe_raw.get("block_duplicate_check_item_photo_upload") or {}
  similarity_alert_rule = safe_raw.get("enable_check_item_photo_similarity_alert") or {}
  similarity_window_days_rule = safe_raw.get("check_item_photo_similarity_window_days") or {}
  similarity_phash_threshold_rule = safe_raw.get("check_item_photo_similarity_phash_threshold") or {}
  similarity_vector_threshold_rule = safe_raw.get("check_item_photo_similarity_vector_threshold") or {}
  distance_threshold_rule = safe_raw.get("photo_location_distance_threshold_m") or {}

  templates_map = _sanitize_watermark_templates_map(
    safe_raw.get("photo_watermark_templates") or {},
  )
  template_rule = _sanitize_watermark_template_rule(
    safe_raw.get("photo_watermark_template_rule") or {},
    templates_map,
  )
  scene_policy = _sanitize_watermark_scene_policy(
    safe_raw.get("photo_watermark_scene_policy") or {},
  )

  return MobileSettingsPayload(
    location_mode=LocationModeRule(
      default=location_rule.get("default") or "baidu",
      per_role=location_rule.get("per_role") or {},
      per_user=location_rule.get("per_user") or {},
    ),
    allow_local_photo_upload=BoolRule(
      default=allow_upload_rule.get("default") if isinstance(allow_upload_rule.get("default"), bool) else True,
      per_role=allow_upload_rule.get("per_role") or {},
      per_user=allow_upload_rule.get("per_user") or {},
    ),
    local_upload_watermark_with_geo=BoolRule(
      default=local_upload_watermark_rule.get("default") if isinstance(local_upload_watermark_rule.get("default"), bool) else True,
      per_role=local_upload_watermark_rule.get("per_role") or {},
      per_user=local_upload_watermark_rule.get("per_user") or {},
    ),
    enable_legacy_scan_pickup=BoolRule(
      default=legacy_scan_pickup_rule.get("default") if isinstance(legacy_scan_pickup_rule.get("default"), bool) else False,
      per_role=legacy_scan_pickup_rule.get("per_role") or {},
      per_user=legacy_scan_pickup_rule.get("per_user") or {},
    ),
    enable_photo_location_distance_check=BoolRule(
      default=location_distance_check_rule.get("default") if isinstance(location_distance_check_rule.get("default"), bool) else True,
      per_role=location_distance_check_rule.get("per_role") or {},
      per_user=location_distance_check_rule.get("per_user") or {},
    ),
    distance_exceed_block_upload=BoolRule(
      default=distance_block_upload_rule.get("default") if isinstance(distance_block_upload_rule.get("default"), bool) else False,
      per_role=distance_block_upload_rule.get("per_role") or {},
      per_user=distance_block_upload_rule.get("per_user") or {},
    ),
    block_duplicate_check_item_photo_upload=BoolRule(
      default=duplicate_check_item_photo_rule.get("default") if isinstance(duplicate_check_item_photo_rule.get("default"), bool) else True,
      per_role=duplicate_check_item_photo_rule.get("per_role") or {},
      per_user=duplicate_check_item_photo_rule.get("per_user") or {},
    ),
    enable_check_item_photo_similarity_alert=BoolRule(
      default=similarity_alert_rule.get("default") if isinstance(similarity_alert_rule.get("default"), bool) else True,
      per_role=similarity_alert_rule.get("per_role") or {},
      per_user=similarity_alert_rule.get("per_user") or {},
    ),
    check_item_photo_similarity_window_days=IntRule(
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
    ),
    check_item_photo_similarity_phash_threshold=IntRule(
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
    ),
    check_item_photo_similarity_vector_threshold=FloatRule(
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
    ),
    photo_location_distance_threshold_m=IntRule(
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
    ),
    photo_watermark_templates={
      template_id: WatermarkTemplate(**template_value)
      for template_id, template_value in templates_map.items()
    },
    photo_watermark_template_rule=WatermarkTemplateRule(
      default=template_rule.get("default") or "default",
      per_role=template_rule.get("per_role") or {},
      per_user=template_rule.get("per_user") or {},
    ),
    photo_watermark_scene_policy=WatermarkScenePolicy(
      apply_for_camera=scene_policy.get("apply_for_camera", True),
      apply_for_album=scene_policy.get("apply_for_album", True),
      force_local_upload_note_when_geo_disabled=scene_policy.get("force_local_upload_note_when_geo_disabled", True),
    ),
  )


@router.get("/mobile-settings", response_model=MobileSettingsPayload)
async def get_mobile_settings(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取完整的移动端配置（仅管理员/项目经理可见）。

  - 目前包含 location_mode / 本地上传 / 水印定位信息 / 旧流程扫码领货 / 照片水印模板等配置项
  - 返回原始配置结构（包含 default/per_role/per_user）
  """
  _require_admin_or_manager(current_user)

  raw = _load_mobile_settings(db)
  return _build_mobile_settings_payload_from_raw(raw)


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

  templates_changed = False
  if payload.photo_watermark_templates is not None:
    settings["photo_watermark_templates"] = _normalize_watermark_templates_map(payload.photo_watermark_templates)
    templates_changed = True

  if payload.photo_watermark_scene_policy is not None:
    settings["photo_watermark_scene_policy"] = _normalize_watermark_scene_policy(payload.photo_watermark_scene_policy)

  current_templates = _sanitize_watermark_templates_map(
    settings.get("photo_watermark_templates") or {},
  )
  settings["photo_watermark_templates"] = current_templates

  if payload.photo_watermark_template_rule is not None:
    settings["photo_watermark_template_rule"] = _normalize_watermark_template_rule(
      payload.photo_watermark_template_rule,
      current_templates,
    )
  elif templates_changed:
    # 模板集发生变化时，自动清理失效引用并回退到可用默认模板
    settings["photo_watermark_template_rule"] = _sanitize_watermark_template_rule(
      settings.get("photo_watermark_template_rule") or {},
      current_templates,
    )
  else:
    settings["photo_watermark_template_rule"] = _sanitize_watermark_template_rule(
      settings.get("photo_watermark_template_rule") or {},
      current_templates,
    )

  settings["photo_watermark_scene_policy"] = _sanitize_watermark_scene_policy(
    settings.get("photo_watermark_scene_policy") or {},
  )

  _save_mobile_settings(db, settings)
  return _build_mobile_settings_payload_from_raw(settings)


@router.get("/mobile-settings/effective", response_model=EffectiveMobileSettingsResponse)
async def get_effective_mobile_settings(
  db: Session = Depends(get_db),
  current_user: User = Depends(get_current_user),
):
  """
  获取“对当前登录用户”最终生效的移动端配置。

  - APP 侧应优先调用本接口，以便支持按用户/角色的覆盖配置
  - 若未配置，则自动回退到全局默认或旧配置
  - 返回字段包含当前用户生效的照片水印模板（photo_watermark_effective）
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
  photo_watermark_effective = _build_effective_photo_watermark(
    settings,
    current_user,
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
    photo_watermark_effective=EffectivePhotoWatermarkConfig(
      template_id=photo_watermark_effective.get("template_id") or "default",
      template=WatermarkTemplate(**(photo_watermark_effective.get("template") or _build_default_watermark_template())),
      scene_policy=WatermarkScenePolicy(**(photo_watermark_effective.get("scene_policy") or _build_default_watermark_scene_policy())),
    ),
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
