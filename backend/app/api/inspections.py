from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import os
import uuid
import hashlib
import json
import copy
import logging
import re

from jose import JWTError, jwt
from pydantic import BaseModel

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.site import Site
# 统一使用增强版本的模型
from app.models.inspection import (
    InspectionTemplate, SiteInspection, InspectionCheckItem, 
    InspectionPhoto, InspectionAuditLog, OfflineInspectionData,
    InspectionStatusEnum, CheckItemStatusEnum, InspectionTypeEnum
)
from app.schemas.inspection_enhanced import (
    InspectionTemplateCreate, InspectionTemplateResponse,
    SiteInspectionCreate, SiteInspectionUpdate, SiteInspectionResponse,
    InspectionCheckItemUpdate, InspectionCheckItemResponse,
    InspectionPhotoCreate, InspectionPhotoResponse,
    InspectionReviewRequest, InspectionAuditLogResponse,
    CheckItemReviewRequest, PhotoReviewRequest, InspectionReviewSummary,
    OfflineInspectionDataCreate, InspectionStatistics,
    InspectionSummary, SiteInspectionProgress
)
from app.api.auth import get_current_user
from app.models.work_order import WorkOrder, WorkOrderTypeEnum
from app.utils.file_handler import (
    ImageValidationError,
    generate_watermark,
    save_uploaded_file,
    validate_image_on_disk,
)
from app.utils.gps_utils import reverse_geocode, validate_gps_accuracy
from app.services.template_resolver import create_resolver, ResolveContext
from app.services.cell_generator import CellGenerator
from app.services.photo_duplicate_guard import (
    detect_duplicate_detail,
    register_first_upload_record,
)
from app.services.photo_similarity_guard import (
    DEFAULT_PHASH_THRESHOLD,
    DEFAULT_VECTOR_THRESHOLD,
    DEFAULT_WINDOW_DAYS,
    detect_similar_photo_validation,
    extract_similarity_features,
)
from app.services.authz_service import user_has_any_role_or_permission
from app.services.data_scope_service import get_user_data_scope
from app.services.equipment_unbind_service import (
    is_device_level_check_item,
    rollback_equipment_status_after_unbind,
)
from app.services.work_order_execution_settings_service import (
    WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING,
    WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
    WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO,
    WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
    WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT,
    can_use_web_work_order_execution,
    ensure_web_work_order_execution_allowed,
    is_web_admin_request,
)
from app.utils.timezone import to_utc_iso
from app.utils.field_validator import FieldValidator
from app.schemas.inspection_enhanced import FieldDefinition
from app.models.work_order import WorkOrder, WorkOrderTypeEnum

router = APIRouter()
logger = logging.getLogger(__name__)


PHOTO_PRECHECK_TICKET_TYPE = "inspection_photo_precheck"
DEFAULT_PHOTO_PRECHECK_TTL_MINUTES = 10
PHOTO_CONTENT_HASH_PATTERN = re.compile(r"^[0-9a-f]{16,128}$")


class PhotoUploadPrecheckRequest(BaseModel):
    check_item_id: str
    field_id: Optional[str] = None
    original_content_hash: str

def _is_field_worker(u) -> bool:
    scope = str(get_user_data_scope(u, 'inspections') or 'all').strip() or 'all'
    return scope in ('assigned', 'assigned_survey_only')


def _ensure_surveyor_inspection_type(db: Session, u, inspection: SiteInspection):
    scope = str(get_user_data_scope(u, 'inspections') or 'all').strip() or 'all'
    if scope == 'assigned_survey_only' and inspection and inspection.work_order_id:
        wo = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()
        if not wo or wo.type != WorkOrderTypeEnum.SITE_SURVEY:
            raise HTTPException(status_code=403, detail="仅可操作勘察检查")


def _get_work_order_for_inspection(db: Session, inspection: SiteInspection) -> Optional[WorkOrder]:
    if not inspection or not getattr(inspection, 'work_order_id', None):
        return None
    return db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()


def _ensure_review_access(current_user: User, detail: str = "没有权限执行审核操作") -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager", "reviewer"],
        permission_codes=["workorder:review:write"],
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _ensure_stats_access(current_user: User) -> None:
    if not user_has_any_role_or_permission(
        current_user,
        role_codes=["admin", "manager"],
        permission_codes=["inspection:template:read", "workorder:list:read"],
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )


def _ensure_inspection_not_voided(
    inspection: SiteInspection,
    detail: str = "该检查已作废，不允许继续操作",
) -> None:
    if inspection.status == InspectionStatusEnum.VOIDED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _normalize_photo_content_hash(raw_hash: Optional[str], *, required: bool = False) -> Optional[str]:
    text = str(raw_hash or "").strip().lower()
    if not text:
        if required:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="original_content_hash 不能为空",
            )
        return None
    if not PHOTO_CONTENT_HASH_PATTERN.fullmatch(text):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="original_content_hash 格式无效",
        )
    return text


def _photo_precheck_ttl_minutes() -> int:
    raw = str(os.getenv("PHOTO_PRECHECK_TICKET_TTL_MINUTES", str(DEFAULT_PHOTO_PRECHECK_TTL_MINUTES))).strip()
    try:
        ttl = int(raw)
    except Exception:
        ttl = DEFAULT_PHOTO_PRECHECK_TTL_MINUTES
    return max(1, min(ttl, 1440))


def _create_photo_precheck_ticket(
    *,
    current_user: User,
    inspection_id: str,
    check_item_id: str,
    field_id: Optional[str],
    original_content_hash: str,
) -> Dict[str, Any]:
    expires_at = datetime.utcnow() + timedelta(minutes=_photo_precheck_ttl_minutes())
    payload = {
        "type": PHOTO_PRECHECK_TICKET_TYPE,
        "uid": int(current_user.id),
        "inspection_id": str(inspection_id),
        "check_item_id": str(check_item_id),
        "field_id": str(field_id or ""),
        "original_content_hash": str(original_content_hash),
        "exp": expires_at,
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {
        "token": token,
        "expires_at": expires_at,
    }


def _verify_photo_precheck_ticket(
    *,
    upload_ticket: str,
    current_user: User,
    inspection_id: str,
    check_item_id: str,
    field_id: Optional[str],
    original_content_hash: Optional[str],
) -> Dict[str, Any]:
    token = str(upload_ticket or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_MISSING", "message": "缺少上传预检票据，请重新选择图片后上传"},
        )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_INVALID", "message": "上传预检票据无效或已过期，请重新选择图片后上传"},
        )

    if str(payload.get("type") or "") != PHOTO_PRECHECK_TICKET_TYPE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_INVALID", "message": "上传预检票据类型不匹配，请重新选择图片后上传"},
        )
    if str(payload.get("uid") or "") != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "PHOTO_UPLOAD_TICKET_FORBIDDEN", "message": "上传预检票据与当前用户不匹配"},
        )
    if str(payload.get("inspection_id") or "") != str(inspection_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_SCOPE_MISMATCH", "message": "上传预检票据与当前检查不匹配，请重新选择图片后上传"},
        )
    if str(payload.get("check_item_id") or "") != str(check_item_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_SCOPE_MISMATCH", "message": "上传预检票据与当前检查项不匹配，请重新选择图片后上传"},
        )
    expected_field_id = str(field_id or "")
    ticket_field_id = str(payload.get("field_id") or "")
    if ticket_field_id != expected_field_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_SCOPE_MISMATCH", "message": "上传预检票据与当前拍照字段不匹配，请重新选择图片后上传"},
        )

    ticket_hash = _normalize_photo_content_hash(payload.get("original_content_hash"), required=True)
    provided_hash = _normalize_photo_content_hash(original_content_hash, required=False)
    if provided_hash and provided_hash != ticket_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "PHOTO_UPLOAD_TICKET_HASH_MISMATCH", "message": "上传预检票据与图片特征码不匹配，请重新选择图片后上传"},
        )
    return {
        "original_content_hash": ticket_hash,
    }


def _get_uploadable_inspection_or_raise(
    db: Session,
    inspection_id: str,
    current_user: User,
) -> SiteInspection:
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在",
        )
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该检查")
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"检查状态 {_enum_value(inspection.status)} 下不允许上传照片",
        )
    return inspection


def _resolve_photo_upload_check_item_and_field(
    db: Session,
    *,
    inspection_id: str,
    check_item_id: Optional[str],
    field_id: Optional[str],
) -> tuple[InspectionCheckItem, Optional[str]]:
    if not check_item_id or str(check_item_id).strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_item_id 不能为空，照片必须关联到具体的检查项",
        )
    normalized_check_item_id = str(check_item_id).strip()

    check_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == normalized_check_item_id,
        InspectionCheckItem.inspection_id == inspection_id,
    ).first()
    if not check_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查项不存在",
        )

    normalized_field_id: Optional[str] = None
    allowed_field_id_set = set()
    if str(getattr(check_item, "required_type", None) or "") == "both":
        if isinstance(check_item.fields, list) and check_item.fields:
            for f in check_item.fields:
                if not isinstance(f, dict):
                    continue
                fid_str = str(f.get("field_id") or "").strip()
                if not fid_str:
                    continue
                if _truthy(f.get("allow_photo")):
                    allowed_field_id_set.add(fid_str)

    if allowed_field_id_set:
        if not field_id or str(field_id).strip() == "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="field_id 不能为空，照片必须关联到允许拍照的检查字段",
            )
        normalized_field_id = str(field_id).strip()
        if normalized_field_id not in allowed_field_id_set:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="field_id 无效或该字段禁止拍照",
            )
    else:
        if field_id and str(field_id).strip() != "":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该检查项未启用字段拍照，请勿传入field_id",
            )

    return check_item, normalized_field_id

def _truthy(v) -> bool:
    if v is True:
        return True
    if v is False or v is None:
        return False
    if isinstance(v, (int, float)):
        return v == 1
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "yes", "y")
    return False


def _enum_value(v) -> str:
    if v is None:
        return ""
    return str(getattr(v, "value", v))


def _is_empty_value(v) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, list):
        return len(v) == 0
    return False


def _coerce_float(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        return float(v)
    except Exception:
        return None


def _eval_dependency_condition(value, condition: Optional[dict]) -> bool:
    """评估字段依赖条件（与 UniApp 端 field-dependency.js 行为保持一致的子集）。"""
    if not condition or not isinstance(condition, dict):
        return True

    operator = condition.get("operator")
    cond_value = condition.get("value")

    if operator in ("==", "equals"):
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
        if a is not None and b is not None:
            return a == b
        return str(value) == str(cond_value)
    if operator in ("===", "strict_equals"):
        return type(value) is type(cond_value) and value == cond_value
    if operator in ("!=", "not_equals"):
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
        if a is not None and b is not None:
            return a != b
        return str(value) != str(cond_value)
    if operator in (">", "greater_than"):
        a = _coerce_float(value); b = _coerce_float(cond_value)
        return a is not None and b is not None and a > b
    if operator in (">=", "greater_or_equal"):
        a = _coerce_float(value); b = _coerce_float(cond_value)
        return a is not None and b is not None and a >= b
    if operator in ("<", "less_than"):
        a = _coerce_float(value); b = _coerce_float(cond_value)
        return a is not None and b is not None and a < b
    if operator in ("<=", "less_or_equal"):
        a = _coerce_float(value); b = _coerce_float(cond_value)
        return a is not None and b is not None and a <= b
    if operator in ("in", "includes"):
        return isinstance(cond_value, list) and value in cond_value
    if operator in ("not_in", "not_includes"):
        return not isinstance(cond_value, list) or value not in cond_value
    if operator == "contains":
        if isinstance(value, list):
            return cond_value in value
        return str(cond_value) in str(value)
    if operator == "not_contains":
        if isinstance(value, list):
            return cond_value not in value
        return str(cond_value) not in str(value)
    if operator == "empty":
        return not value or value == "" or (isinstance(value, list) and len(value) == 0)
    if operator == "not_empty":
        return bool(value) and value != "" and (not isinstance(value, list) or len(value) > 0)
    if operator == "true":
        return value is True or value == "true"
    if operator == "false":
        return value is False or value == "false"

    print(f"WARNING: 未知的依赖条件操作符: {operator}")
    return False


def _is_field_visible(field: dict, field_values: dict) -> bool:
    """根据字段依赖判断字段是否可见（与 UniApp 端 shouldShowField + processFieldDependencies 保持一致）。"""
    hidden = bool(field.get("hidden", False))
    deps = field.get("dependencies")
    if isinstance(deps, list):
        for dep in deps:
            if not isinstance(dep, dict):
                continue
            if str(dep.get("type") or "").lower() != "visibility":
                continue
            source_field = dep.get("source_field")
            source_value = field_values.get(source_field)
            condition_met = _eval_dependency_condition(source_value, dep.get("condition") if isinstance(dep.get("condition"), dict) else None)
            if condition_met:
                effect = dep.get("effect") if isinstance(dep.get("effect"), dict) else {}
                visible = effect.get("visible", True)
                hidden = not bool(visible)
            else:
                # removeDependencyEffect: visibility -> hidden = false
                hidden = False
    return not hidden


def _build_field_values_from_data_value(data_value) -> dict:
    values = {}
    if isinstance(data_value, dict):
        for k, v in data_value.items():
            values[str(k)] = v
        return values
    if not isinstance(data_value, list):
        return values
    for dv in data_value:
        d = dv.dict() if hasattr(dv, "dict") else (dv or {})
        if not isinstance(d, dict):
            continue
        raw_name = d.get("field_name") or d.get("field_id") or d.get("key") or d.get("field") or d.get("name")
        if not raw_name:
            continue
        values[str(raw_name)] = d.get("value")
    return values


def _extract_photo_field_rules(fields) -> tuple[set, set, dict, dict]:
    """从检查项字段配置提取拍照规则：允许拍照字段、必拍字段、label 映射、字段配置映射。"""
    allowed: set = set()
    required: set = set()
    labels: dict = {}
    by_id: dict = {}
    if not isinstance(fields, list):
        return allowed, required, labels, by_id
    for f in fields:
        if not isinstance(f, dict):
            continue
        fid = str(f.get("field_id") or "").strip()
        if not fid:
            continue
        by_id[fid] = f
        labels[fid] = str(f.get("label") or fid)
        allow_photo = _truthy(f.get("allow_photo"))
        if allow_photo:
            allowed.add(fid)
            if _truthy(f.get("photo_required")):
                required.add(fid)
    return allowed, required, labels, by_id


def _touch_check_item_and_clear_review(check_item: InspectionCheckItem, now: datetime) -> bool:
    """检查项内容有变更时：更新时间，并清空该检查项的审核结果（若已审核过）。

    用于实现“驳回后增量复审”：只让变动的检查项回到待审核，未变动的保留原审核结果。
    """
    had_review = (
        check_item.review_status is not None
        or check_item.review_comments is not None
        or getattr(check_item, "review_comments_i18n", None) is not None
        or check_item.reviewed_by is not None
        or check_item.reviewed_at is not None
    )
    if had_review:
        check_item.review_status = None
        check_item.review_comments = None
        check_item.review_comments_i18n = None
        check_item.reviewed_by = None
        check_item.reviewed_at = None
    check_item.updated_at = now
    return had_review


def _normalize_category_level(category: dict) -> str:
    """归一化模板分类的检查维度。

    约定：
    - site：站点级
    - sector：扇区级
    - device：设备级（扇区×Band）
    - cell_earfcn：小区级（扇区×Band×EARFCN）

    向后兼容：
    - 旧模板可能只有 sector_specific / cell_specific；
    - 部分旧模板的 level_type 可能为 'cell'，历史上表示“扇区×Band”（本次统一归为 device）。
    """
    lt = (category or {}).get("level_type")
    if lt == "cell":
        return "device"
    if lt in ("site", "sector", "device", "cell_earfcn"):
        return lt

    if (category or {}).get("cell_specific"):
        return "device"
    if (category or {}).get("sector_specific"):
        return "sector"
    return "site"


def _template_requires_lld_cells(template_data: dict) -> bool:
    """判断模板是否包含“按 EARFCN 的小区级”检查。"""
    for cat in (template_data or {}).get("check_categories", []) or []:
        if _normalize_category_level(cat) == "cell_earfcn":
            return True
    return False


def _strip_cell_suffix(item_id: str) -> str:
    """兼容小区级检查项：xxx_cell_1_n41 -> xxx。"""
    s = str(item_id or "").strip()
    if not s:
        return s
    marker = "_cell_"
    if marker in s:
        return s.split(marker, 1)[0]
    return s


def _as_i18n_dict(value):
    """确保 i18n 字段为 dict[str, str]，否则返回 None。"""
    if not isinstance(value, dict):
        return None
    out = {}
    for k, v in value.items():
        if v is None:
            continue
        out[str(k)] = str(v)
    return out or None


def _build_template_i18n_index(template_data: dict) -> dict:
    """构建模板 item_id -> 元信息映射，供检查项接口补充 i18n。"""
    index = {}
    for cat in (template_data or {}).get("check_categories", []) or []:
        if not isinstance(cat, dict):
            continue
        for item in (cat.get("items") or []) or []:
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id") or "").strip()
            if not item_id:
                continue
            field_map = {}
            for f in (item.get("fields") or []) or []:
                if not isinstance(f, dict):
                    continue
                fid = str(f.get("field_id") or "").strip()
                if not fid:
                    continue
                field_map[fid] = f
            index[item_id] = {"category": cat, "item": item, "field_map": field_map}
    return index


def _merge_fields_i18n(fields, template_field_map: Optional[dict]):
    """将模板中的字段 i18n 合并进检查项字段配置（仅响应层，不写回 DB）。"""
    if not isinstance(fields, list) or not template_field_map:
        return fields

    merged = copy.deepcopy(fields)
    for f in merged:
        if not isinstance(f, dict):
            continue
        fid = str(f.get("field_id") or "").strip()
        if not fid:
            continue
        tpl_f = template_field_map.get(fid)
        if not isinstance(tpl_f, dict):
            continue

        for key in ("label_i18n", "placeholder_i18n", "help_text_i18n"):
            v = _as_i18n_dict(tpl_f.get(key))
            if v is not None:
                f[key] = v

        tpl_opts = tpl_f.get("options")
        if not isinstance(tpl_opts, list):
            continue
        opt_map = {}
        for opt in tpl_opts:
            if not isinstance(opt, dict):
                continue
            ov = opt.get("value")
            if ov is None:
                continue
            opt_map[str(ov)] = opt

        cur_opts = f.get("options")
        if not isinstance(cur_opts, list) or not opt_map:
            continue
        for opt in cur_opts:
            if not isinstance(opt, dict):
                continue
            ov = opt.get("value")
            if ov is None:
                continue
            tpl_opt = opt_map.get(str(ov))
            if not isinstance(tpl_opt, dict):
                continue
            label_i18n = _as_i18n_dict(tpl_opt.get("label_i18n"))
            if label_i18n is not None:
                opt["label_i18n"] = label_i18n

    return merged

# 新增工具函数
async def create_default_template(db: Session, site_id: int, inspection_type: str) -> InspectionTemplate:
    """创建默认检查模板"""
    import uuid
    from app.schemas.inspection_enhanced import InspectionTemplateData, CheckCategoryTemplate, CheckItemTemplate
    
    # 根据检查类型创建不同的默认检查项
    template_data = {
        "site_id": str(site_id),
        "site_name": f"站点_{site_id}",
        "template_version": "1.0",
        "check_categories": []
    }
    
    if inspection_type in ['opening', 'OPENING']:
        # 新站点设备安装模板
        template_data["check_categories"] = [
            {
                "category_id": "basic_info",
                "category_name": "基本信息检查",
                "description": "站点基本信息核实",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "tower_id",
                        "item_name": "铁塔编号确认",
                        "description": "核实并拍照记录铁塔编号",
                        "required_type": "photo",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "site_coordinates",
                        "item_name": "站点坐标确认",
                        "description": "使用GPS确认站点实际坐标",
                        "required_type": "data",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            },
            {
                "category_id": "equipment_check",
                "category_name": "设备检查",
                "description": "基站设备状态检查",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "antenna_installation",
                        "item_name": "天线安装检查",
                        "description": "检查天线安装情况和方向角",
                        "required_type": "both",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "cabinet_environment",
                        "item_name": "机柜环境检查",
                        "description": "检查机柜周围环境和安全状况",
                        "required_type": "photo",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            }
        ]
    else:
        # 维护检查模板
        template_data["check_categories"] = [
            {
                "category_id": "maintenance_check",
                "category_name": "维护检查",
                "description": "设备维护状况检查",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "equipment_status",
                        "item_name": "设备状态检查",
                        "description": "检查设备运行状态",
                        "required_type": "both",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "signal_quality",
                        "item_name": "信号质量测试",
                        "description": "测试并记录信号质量参数",
                        "required_type": "data",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            }
        ]
    
    # 创建模板记录
    template = InspectionTemplate(
        id=str(uuid.uuid4()),
        site_id=site_id,
        template_name=f"默认{inspection_type}检查模板",
        template_version="1.0",
        template_data=template_data,
        status="approved"
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return template

def calculate_file_hash(file_path: str) -> str:
    """计算文件哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def _is_duplicate_check_item_photo_block_enabled(db: Session, current_user: User) -> bool:
    """是否启用“检查项重复图片上传阻断”开关（默认开启）。"""
    try:
        from app.api.mobile_settings import _load_mobile_settings, _resolve_bool_for_user

        settings = _load_mobile_settings(db)
        return _resolve_bool_for_user(
            settings,
            key="block_duplicate_check_item_photo_upload",
            user=current_user,
            default=True,
        )
    except Exception:
        return True


def _resolve_similarity_alert_policy(db: Session, current_user: User) -> Dict[str, Any]:
    """解析检查项照片相似度提醒策略（默认开启，窗口180天）。"""
    enabled = True
    window_days = DEFAULT_WINDOW_DAYS
    phash_threshold = DEFAULT_PHASH_THRESHOLD
    vector_threshold = DEFAULT_VECTOR_THRESHOLD
    try:
        from app.api.mobile_settings import (
            _load_mobile_settings,
            _normalize_similarity_phash_threshold,
            _normalize_similarity_vector_threshold,
            _normalize_similarity_window_days,
            _resolve_bool_for_user,
            _resolve_float_for_user,
            _resolve_int_for_user,
        )

        settings = _load_mobile_settings(db)
        enabled = _resolve_bool_for_user(
            settings,
            key="enable_check_item_photo_similarity_alert",
            user=current_user,
            default=True,
        )
        window_days = _resolve_int_for_user(
            settings,
            key="check_item_photo_similarity_window_days",
            user=current_user,
            default=DEFAULT_WINDOW_DAYS,
            value_normalizer=_normalize_similarity_window_days,
        )
        phash_threshold = _resolve_int_for_user(
            settings,
            key="check_item_photo_similarity_phash_threshold",
            user=current_user,
            default=DEFAULT_PHASH_THRESHOLD,
            value_normalizer=_normalize_similarity_phash_threshold,
        )
        vector_threshold = _resolve_float_for_user(
            settings,
            key="check_item_photo_similarity_vector_threshold",
            user=current_user,
            default=DEFAULT_VECTOR_THRESHOLD,
            value_normalizer=_normalize_similarity_vector_threshold,
        )
    except Exception:
        enabled = True
        window_days = DEFAULT_WINDOW_DAYS
        phash_threshold = DEFAULT_PHASH_THRESHOLD
        vector_threshold = DEFAULT_VECTOR_THRESHOLD
    return {
        "enabled": bool(enabled),
        "window_days": max(1, min(int(window_days or DEFAULT_WINDOW_DAYS), 3650)),
        "phash_threshold": max(0, min(int(phash_threshold or DEFAULT_PHASH_THRESHOLD), 64)),
        "vector_threshold": max(0.0, min(float(vector_threshold if vector_threshold is not None else DEFAULT_VECTOR_THRESHOLD), 1.0)),
    }


def _resolve_site_name_by_id(db: Session, site_id: Optional[int]) -> Optional[str]:
    if site_id is None:
        return None
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        return None
    return site.site_name


def _resolve_uploader_name(current_user: User) -> str:
    return (current_user.full_name or current_user.username or "").strip()


def _mark_photo_duplicate_info(
    photo: InspectionPhoto,
    duplicate_detail: Optional[Dict[str, Any]],
) -> None:
    if duplicate_detail and isinstance(duplicate_detail, dict):
        photo.is_duplicate_global = True
        photo.duplicate_info = duplicate_detail.get("duplicate")
        return
    photo.is_duplicate_global = False
    photo.duplicate_info = None


def _mark_photo_similarity_info(
    photo: InspectionPhoto,
    *,
    similarity_features: Optional[Dict[str, Any]],
    similar_warning: Optional[Dict[str, Any]],
    similarity_evaluation: Optional[Dict[str, Any]],
) -> None:
    feature_data = similarity_features if isinstance(similarity_features, dict) else {}
    photo.content_phash = feature_data.get("content_phash")
    photo.content_vector = feature_data.get("content_vector")
    photo.content_vector_backend = feature_data.get("content_vector_backend")

    info_payload: Dict[str, Any] = {}
    warning_payload = similar_warning if isinstance(similar_warning, dict) else {}
    warning_info = warning_payload.get("similar")
    if isinstance(warning_info, dict):
        info_payload.update(warning_info)

    eval_payload = similarity_evaluation if isinstance(similarity_evaluation, dict) else {}
    if eval_payload:
        info_payload["evaluation"] = eval_payload

    feature_phash = feature_data.get("content_phash")
    if feature_phash and "content_phash" not in info_payload:
        info_payload["content_phash"] = feature_phash
    vector_backend = feature_data.get("content_vector_backend")
    if vector_backend and "vector_backend" not in info_payload:
        info_payload["vector_backend"] = vector_backend
    vector_raw = feature_data.get("content_vector")
    if isinstance(vector_raw, list):
        info_payload["content_vector_dim"] = len(vector_raw)

    if similar_warning and isinstance(similar_warning, dict):
        photo.is_similar_risk = True
        photo.similar_info = info_payload or warning_payload.get("similar")
        return
    photo.is_similar_risk = False
    photo.similar_info = info_payload or None


def _detect_similar_warning_if_needed(
    db: Session,
    *,
    file_path: str,
    policy: Dict[str, Any],
    exclude_photo_id: Optional[str] = None,
) -> Dict[str, Any]:
    """提取相似特征并按策略检测高相似风险。"""
    features = extract_similarity_features(file_path)
    warning = None
    evaluation = {
        "checked_at": to_utc_iso(datetime.utcnow()),
        "enabled": bool(policy.get("enabled")),
        "window_days": max(1, min(int(policy.get("window_days", DEFAULT_WINDOW_DAYS) or DEFAULT_WINDOW_DAYS), 3650)),
        "phash_threshold": max(0, min(int(policy.get("phash_threshold", DEFAULT_PHASH_THRESHOLD) or DEFAULT_PHASH_THRESHOLD), 64)),
        "vector_threshold": round(max(0.0, min(float(policy.get("vector_threshold", DEFAULT_VECTOR_THRESHOLD) or DEFAULT_VECTOR_THRESHOLD), 1.0)), 6),
        "decision": "not_checked",
        "reason_code": "POLICY_DISABLED",
    }
    if policy.get("enabled"):
        validation = detect_similar_photo_validation(
            db,
            content_phash=features.get("content_phash"),
            content_vector=features.get("content_vector"),
            content_vector_backend=features.get("content_vector_backend"),
            exclude_photo_id=exclude_photo_id,
            window_days=policy.get("window_days", DEFAULT_WINDOW_DAYS),
            phash_threshold=policy.get("phash_threshold", DEFAULT_PHASH_THRESHOLD),
            vector_threshold=policy.get("vector_threshold", DEFAULT_VECTOR_THRESHOLD),
        )
        warning = validation.get("warning")
        validation_eval = validation.get("evaluation")
        if isinstance(validation_eval, dict):
            evaluation = validation_eval
            evaluation["enabled"] = True
    return {
        "features": features,
        "warning": warning,
        "evaluation": evaluation,
    }


def _cleanup_paths(*paths: Optional[str]) -> None:
    for p in set(paths):
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except Exception as cleanup_err:
            print(f"清理失败: {p}, err={cleanup_err}")


def _merge_warning_messages(*warnings: Optional[Dict[str, Any]]) -> Optional[str]:
    parts: List[str] = []
    for warning in warnings:
        if not warning or not isinstance(warning, dict):
            continue
        message = str(warning.get("message") or "").strip()
        if message:
            parts.append(message)
    if not parts:
        return None
    return "；".join(parts)


def _build_photo_response_with_warnings(
    photo: InspectionPhoto,
    duplicate_warning: Optional[Dict[str, Any]],
    similar_warning: Optional[Dict[str, Any]],
) -> InspectionPhotoResponse:
    payload = InspectionPhotoResponse.model_validate(photo, from_attributes=True)
    updates: Dict[str, Any] = {}
    if duplicate_warning:
        updates["duplicate_warning"] = duplicate_warning
    if similar_warning:
        updates["similar_warning"] = similar_warning
    if updates:
        return payload.model_copy(update=updates)
    return payload

@router.post("/", response_model=SiteInspectionResponse)
async def create_inspection(
    inspection_data: SiteInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建站点检查 - 统一接口"""
    template = None
    
    # 获取站点信息用于解析上下文
    site = db.query(Site).filter(Site.id == inspection_data.site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="站点不存在"
        )
    
    # 获取或解析检查模板
    if inspection_data.template_id:
        # 使用指定的模板
        template = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == inspection_data.template_id
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="检查模板不存在"
            )
    else:
        # 使用模板解析器自动匹配模板
        resolver = create_resolver(db)
        
        # 创建解析上下文
        resolve_context = ResolveContext(
            site_id=inspection_data.site_id,
            site_type=getattr(site, 'site_type', None),  # 如果站点有类型字段
            task_id=inspection_data.task_id,
            task_type=inspection_data.inspection_type,
            region=getattr(site, 'region', None),  # 如果站点有区域字段
            customer=getattr(site, 'customer', None),  # 如果站点有客户字段
            tags=[]  # 可以根据需要添加标签
        )
        
        # 解析最匹配的模板
        match_result = resolver.resolve_template(resolve_context)
        
        if match_result:
            template = match_result.template
        else:
            # 兜底：自动创建默认模板
             template = await create_default_template(db, inspection_data.site_id, inspection_data.inspection_type)

    template_data = template.template_data or {}
    carrier_cells = None
    if _template_requires_lld_cells(template_data):
        carrier_cells = CellGenerator.generate_cells_from_lld(db, inspection_data.site_id)
        if not carrier_cells:
            raise HTTPException(
                status_code=400,
                detail="该检查模板包含“小区级（按EARFCN）”检查项，请先在站点规划（LLD）中导入规划数据",
            )

    # 创建检查记录
    inspection = SiteInspection(
        id=str(uuid.uuid4()),
        site_id=inspection_data.site_id,
        template_id=template.id,
        inspector_id=current_user.id,
        inspection_type=inspection_data.inspection_type,
        start_time=datetime.utcnow(),
        location=inspection_data.location,
        weather=inspection_data.weather,
        temperature=inspection_data.temperature,
        notes=inspection_data.notes
    )
    
    # 设置GPS信息
    if inspection_data.gps_info:
        inspection.latitude = inspection_data.gps_info.latitude
        inspection.longitude = inspection_data.gps_info.longitude
        inspection.gps_accuracy = inspection_data.gps_info.accuracy
        inspection.address = inspection_data.gps_info.address or await reverse_geocode(
            inspection_data.gps_info.latitude, 
            inspection_data.gps_info.longitude
        )
    
    db.add(inspection)
    db.flush()
    
    # 根据模板和站点规划创建检查项
    total_items = 0
    
    # 设备维度（扇区×Band）列表：兼容旧模板“cell_specific”
    devices = CellGenerator.generate_devices_from_planning(db, inspection_data.site_id)
    sectors = sorted({d.sector_id for d in devices})

    print(f"DEBUG: 开始为站点 {inspection_data.site_id} 生成检查项（设备数={len(devices)}，扇区数={len(sectors)}）")
    if carrier_cells is not None:
        print(f"DEBUG: 小区级（按EARFCN）数量={len(carrier_cells)}")

    for i, category in enumerate(template_data.get("check_categories", [])):
        category_name = category.get("category_name", "未知分类")
        category_id = category.get("category_id", "unknown")
        level_type = _normalize_category_level(category)
        print(f"DEBUG: === 处理分类 {i+1}: {category_name} (ID: {category_id}) ===")
        print(f"DEBUG:   level_type(raw)={category.get('level_type')}, level_type(norm)={level_type}")
        
        items = category.get("items", [])
        print(f"DEBUG:   该分类有 {len(items)} 个检查项")
        
        for j, item in enumerate(items):
            base_item_name = item.get("item_name", "未知检查项")
            base_item_id = item.get("item_id", "unknown")
            item_description = item.get("description", "")  # 获取检查项描述
            item_fields = item.get("fields", [])  # 获取字段配置
            required_type = item.get("required_type", "unknown")
            print(f"DEBUG:   --- 处理检查项 {j+1}: {base_item_name} (ID: {base_item_id}) ---")
            print(f"DEBUG:     required_type: {required_type}")
            
            if level_type == "cell_earfcn":
                cells = carrier_cells or []
                print(f"DEBUG:     ✅ 小区级（按EARFCN），为 {len(cells)} 个小区创建检查项")
                for cell in cells:
                    cell_item_id = f"{base_item_id}_cell_{cell.cell_id}"
                    cell_item_name = f"{base_item_name} - 小区 {cell.cell_id}"
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=cell_item_id,
                        item_name=cell_item_name,
                        description=item_description,
                        category_id=category_id,
                        category_name=category_name,
                        sector_id=cell.sector_id,
                        band=cell.band,
                        cell_id=cell.cell_id,
                        required_type=required_type,
                        fields=item_fields,
                        status=CheckItemStatusEnum.PENDING,
                    )
                    db.add(check_item)
                    total_items += 1
            elif level_type == "device":
                print(f"DEBUG:     ✅ 设备级（扇区×Band），为 {len(devices)} 个设备创建检查项")
                for dev in devices:
                    dev_item_id = f"{base_item_id}_cell_{dev.cell_id}"
                    dev_item_name = f"{base_item_name} - 设备 {dev.cell_id}"
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=dev_item_id,
                        item_name=dev_item_name,
                        description=item_description,
                        category_id=category_id,
                        category_name=category_name,
                        sector_id=dev.sector_id,
                        band=dev.band,
                        cell_id=dev.cell_id,
                        required_type=required_type,
                        fields=item_fields,
                        status=CheckItemStatusEnum.PENDING,
                    )
                    db.add(check_item)
                    total_items += 1
            elif level_type == "sector":
                print(f"DEBUG:     ✅ 扇区级，为 {len(sectors)} 个扇区创建检查项")
                for sector_id in sectors:
                    sector_item_id = f"{base_item_id}_sector_{sector_id}"
                    sector_item_name = f"{base_item_name} - 扇区 {sector_id}"
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=sector_item_id,
                        item_name=sector_item_name,
                        description=item_description,
                        category_id=category_id,
                        category_name=category_name,
                        sector_id=sector_id,
                        required_type=required_type,
                        fields=item_fields,
                        status=CheckItemStatusEnum.PENDING,
                    )
                    db.add(check_item)
                    total_items += 1
            else:
                print(f"DEBUG:     ✅ 站点级，创建 1 个检查项")
                check_item = InspectionCheckItem(
                    id=str(uuid.uuid4()),
                    inspection_id=inspection.id,
                    item_id=base_item_id,
                    item_name=base_item_name,
                    description=item_description,
                    category_id=category_id,
                    category_name=category_name,
                    required_type=required_type,
                    fields=item_fields,
                    status=CheckItemStatusEnum.PENDING,
                )
                db.add(check_item)
                total_items += 1
                    
            print(f"DEBUG:     检查项 {base_item_name} 处理完成，当前总数: {total_items}")
            
    print(f"DEBUG: === 检查项创建汇总 ===")
    print(f"DEBUG: 总共创建了 {total_items} 个检查项")
    
    # 更新总检查项数
    inspection.total_items = total_items
    
    db.commit()
    db.refresh(inspection)
    
    # 记录审核日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection.id,
        action="create",
        to_status="draft",
        operator_id=current_user.id,
        comments="创建检查记录"
    )
    db.add(audit_log)
    db.commit()
    
    return inspection

@router.get("/", response_model=List[InspectionSummary])
async def get_inspections(
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    task_id: Optional[str] = None,
    status: Optional[InspectionStatusEnum] = None,
    inspector_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取站点检查列表 - 统一接口"""
    query = db.query(SiteInspection)
    
    # 权限过滤：施工员只能看到自己的检查记录
    if _is_field_worker(current_user):
        query = query.filter(SiteInspection.inspector_id == current_user.id)
    
    if site_id:
        query = query.filter(SiteInspection.site_id == site_id)
    
    if task_id:
        query = query.filter(SiteInspection.task_id == task_id)
    
    if status:
        query = query.filter(SiteInspection.status == status)
    
    if inspector_id:
        query = query.filter(SiteInspection.inspector_id == inspector_id)
    
    inspections = query.offset(skip).limit(limit).all()
    
    # 转换为摘要格式
    summaries = []
    for inspection in inspections:
        summary = InspectionSummary(
            id=inspection.id,
            site_id=inspection.site_id,
            site_name=inspection.site.site_name if inspection.site else None,
            inspector_id=inspection.inspector_id,
            inspector_name=inspection.inspector.full_name if inspection.inspector else None,
            inspection_type=inspection.inspection_type,
            status=inspection.status,
            start_time=inspection.start_time,
            completion_rate=inspection.completion_rate,
            score=inspection.score,
            created_at=inspection.created_at
        )
        summaries.append(summary)
    
    return summaries

@router.get("/detail/{inspection_id}", response_model=SiteInspectionResponse)
async def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取站点检查详情 - 统一接口"""
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    _ensure_inspection_not_voided(inspection, detail="已作废检查不能修改")
    
    # 权限检查
    if (_is_field_worker(current_user) and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此检查记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 如果检查关联了工单：获取驳回意见（工单照片链路已废弃，不再合并工单照片）
    if inspection.work_order_id:
        from app.models.work_order import WorkOrder
        
        # 获取工单信息（包括驳回意见）
        work_order = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()
        if work_order and work_order.status.value == "REJECTED" and work_order.review_comments:
            # 如果工单被驳回且有驳回意见，将其添加到检查的review_comments字段
            inspection.review_comments = work_order.review_comments
            inspection.review_comments_i18n = getattr(work_order, "review_comments_i18n", None)
    
    return inspection

@router.put("/detail/{inspection_id}", response_model=SiteInspectionResponse)
async def update_inspection(
    inspection_id: str,
    inspection_update: SiteInspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新站点检查 - 统一接口"""
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (_is_field_worker(current_user) and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此检查记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 更新字段
    old_status = inspection.status
    update_fields = inspection_update.dict(exclude_unset=True)
    print(f"DEBUG: update_inspection调用 - 检查ID: {inspection.id}, 旧状态: {old_status}, 更新字段: {list(update_fields.keys())}, 请求数据: {inspection_update.dict()}")

    # 轻量权限与合法迁移校验：通过/驳回必须走审核接口
    if "status" in update_fields:
        new_status = update_fields["status"]
        if new_status in [InspectionStatusEnum.APPROVED, InspectionStatusEnum.REJECTED]:
            _ensure_review_access(current_user, detail="没有权限进行审核操作，请使用审核接口")
            if old_status not in [InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能从已提交/审核中状态变更为通过/驳回"
                )
    
    for field, value in update_fields.items():
        if field == "gps_info" and value:
            inspection.latitude = value.latitude
            inspection.longitude = value.longitude
            inspection.gps_accuracy = value.accuracy
            if not value.address:
                inspection.address = await reverse_geocode(
                    value.latitude, value.longitude
                )
            else:
                inspection.address = value.address
        else:
            setattr(inspection, field, value)
    
    inspection.updated_at = datetime.utcnow()
    
    # 如果从驳回状态重新提交：清除检查级别旧审核信息（检查项采用“增量复审”，不再全量清空）
    is_resubmit = (old_status == InspectionStatusEnum.REJECTED and 
                   "status" in update_fields and 
                   inspection.status == InspectionStatusEnum.SUBMITTED)
    
    if is_resubmit:
        print(f"[重新提交] 检查 {inspection_id} 从驳回状态重新提交，清除检查级审核信息")
        
        # 1. 清除检查级别的审核信息
        inspection.review_comments = None
        inspection.review_comments_i18n = None
        inspection.reviewed_by = None
        inspection.reviewed_at = None
    
    # 如果状态变更为submitted，且没有设置submitted_at，自动设置
    if "status" in update_fields and inspection.status == InspectionStatusEnum.SUBMITTED:
        if not inspection.submitted_at:
            inspection.submitted_at = datetime.utcnow()
    
    # 记录状态变更日志
    audit_log_to_add = None
    if "status" in update_fields and old_status != inspection.status:
        # 区分首次提交和重新提交
        action = "resubmit" if is_resubmit else "update_status"
        comments = "重新提交检查（保留未变更项审核结果）" if is_resubmit else "更新检查状态"
        
        audit_log_to_add = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            action=action,
            from_status=old_status.value,
            to_status=inspection.status.value,
            operator_id=current_user.id,
            comments=comments
        )
        db.add(audit_log_to_add)
    
    # 如果检查状态变更为submitted，同步工单状态（在提交前）
    should_sync = False
    if "status" in update_fields and inspection.work_order_id:
        # 检查是否更新为submitted状态
        status_check = (inspection.status == InspectionStatusEnum.SUBMITTED or 
                       str(inspection.status).upper() == "SUBMITTED" or
                       getattr(inspection.status, 'value', None) == 'submitted')
        should_sync = status_check
        print(f"DEBUG: 同步检查条件 - status字段存在: True, work_order_id存在: {bool(inspection.work_order_id)}, 状态检查: {status_check}")
        print(f"DEBUG: 检查状态值: {inspection.status}, 类型: {type(inspection.status)}")
        
    if should_sync:
        print(f"DEBUG: 开始同步工单状态 - 检查ID: {inspection.id}, 工单ID: {inspection.work_order_id}")
        from app.services.work_order_sync import get_work_order_sync_service
        sync_service = get_work_order_sync_service(db)
        sync_service.sync_inspection_to_work_order_status(inspection)
    else:
        if "status" in update_fields:
            print(f"DEBUG: 未触发同步 - 检查状态: {inspection.status}, work_order_id: {inspection.work_order_id}")
    
    # 统一提交所有更改
    db.commit()
    db.refresh(inspection)
    
    return inspection

@router.post("/detail/{inspection_id}/photos/precheck")
async def precheck_inspection_photo_upload(
    request: Request,
    inspection_id: str,
    payload: PhotoUploadPrecheckRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """检查项照片上传前预检（基于原图特征码，返回短期上传票据）。"""
    inspection = _get_uploadable_inspection_or_raise(db, inspection_id, current_user)
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
        detail="当前未启用 Web 端照片上传",
    )
    check_item, normalized_field_id = _resolve_photo_upload_check_item_and_field(
        db,
        inspection_id=inspection_id,
        check_item_id=payload.check_item_id,
        field_id=payload.field_id,
    )

    normalized_original_hash = _normalize_photo_content_hash(payload.original_content_hash, required=True)
    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    duplicate_detail = detect_duplicate_detail(
        db,
        content_hash=normalized_original_hash,
        block_upload=duplicate_block_enabled,
    )

    ticket_data = _create_photo_precheck_ticket(
        current_user=current_user,
        inspection_id=inspection_id,
        check_item_id=check_item.id,
        field_id=normalized_field_id,
        original_content_hash=normalized_original_hash,
    )

    should_block = bool(duplicate_detail and duplicate_block_enabled)
    return {
        "ok": True,
        "upload_ticket": ticket_data["token"],
        "expires_at": to_utc_iso(ticket_data["expires_at"]),
        "duplicate_warning": duplicate_detail if isinstance(duplicate_detail, dict) else None,
        "should_block": should_block,
    }


@router.post("/detail/{inspection_id}/photos", response_model=InspectionPhotoResponse)
async def upload_inspection_photo(
    request: Request,
    inspection_id: str,
    file: UploadFile = File(...),
    check_item_id: Optional[str] = Form(None),
    field_id: Optional[str] = Form(None),
    gps_latitude: float = Form(0),
    gps_longitude: float = Form(0),
    gps_accuracy: Optional[float] = Form(None),
    planned_latitude: Optional[float] = Form(None),
    planned_longitude: Optional[float] = Form(None),
    distance_to_plan_m: Optional[float] = Form(None),
    location_distance_threshold_m: Optional[float] = Form(None),
    location_distance_exceeded: Optional[bool] = Form(None),
    plan_coordinate_missing: Optional[bool] = Form(None),
    distance_compare_enabled: Optional[bool] = Form(None),
    distance_exceed_block_upload: Optional[bool] = Form(None),
    has_watermark: bool = Form(False),
    local_upload_without_geo: bool = Form(False),
    replace_existing: bool = Form(False),
    original_content_hash: Optional[str] = Form(None),
    upload_ticket: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传检查照片 - 统一接口"""
    
    # 详细调试日志
    print(f"DEBUG: 照片上传接口调用")
    print(f"  inspection_id: {inspection_id}")
    print(f"  check_item_id: {check_item_id} (type: {type(check_item_id)})")
    print(f"  field_id: {field_id} (type: {type(field_id)})")
    print(f"  gps_latitude: {gps_latitude} (type: {type(gps_latitude)})")
    print(f"  gps_longitude: {gps_longitude} (type: {type(gps_longitude)})")
    print(f"  gps_accuracy: {gps_accuracy} (type: {type(gps_accuracy)})")
    print(f"  planned_latitude: {planned_latitude} (type: {type(planned_latitude)})")
    print(f"  planned_longitude: {planned_longitude} (type: {type(planned_longitude)})")
    print(f"  distance_to_plan_m: {distance_to_plan_m} (type: {type(distance_to_plan_m)})")
    print(f"  location_distance_threshold_m: {location_distance_threshold_m} (type: {type(location_distance_threshold_m)})")
    print(f"  location_distance_exceeded: {location_distance_exceeded} (type: {type(location_distance_exceeded)})")
    print(f"  plan_coordinate_missing: {plan_coordinate_missing} (type: {type(plan_coordinate_missing)})")
    print(f"  distance_compare_enabled: {distance_compare_enabled} (type: {type(distance_compare_enabled)})")
    print(f"  distance_exceed_block_upload: {distance_exceed_block_upload} (type: {type(distance_exceed_block_upload)})")
    print(f"  has_watermark: {has_watermark} (type: {type(has_watermark)})")
    print(f"  local_upload_without_geo: {local_upload_without_geo} (type: {type(local_upload_without_geo)})")
    print(f"  original_content_hash: {original_content_hash} (type: {type(original_content_hash)})")
    print(f"  upload_ticket存在: {bool(str(upload_ticket or '').strip())}")
    print(f"  file.filename: {file.filename}")
    print(f"  file.content_type: {file.content_type}")
    print(f"  current_user: {current_user.username}")
    
    # 尝试从request中获取原始表单数据
    try:
        form = await request.form()
        print(f"  原始表单数据: {dict(form)}")
    except Exception as e:
        print(f"  无法获取原始表单数据: {e}")
    
    # 本地上传（不带经纬度/地址）允许GPS为0，其他场景仍要求有效GPS
    if local_upload_without_geo:
        # 本地上传仍要求前端已加水印（标注“本图片为本地上传照片”）
        if not has_watermark:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="本地上传照片必须带水印"
            )
    else:
        # 验证GPS坐标（拍照等场景必须有有效GPS坐标）
        if gps_latitude == 0 and gps_longitude == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="GPS坐标无效，现场拍照必须包含有效的位置信息"
            )
    
    inspection = _get_uploadable_inspection_or_raise(db, inspection_id, current_user)
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
        detail="当前未启用 Web 端照片上传",
    )
    if local_upload_without_geo:
        ensure_web_work_order_execution_allowed(
            request,
            db,
            current_user,
            work_order_type=work_order.type if work_order else None,
            capability=WORK_ORDER_EXECUTION_CAPABILITY_LOCAL_UPLOAD_WITHOUT_GEO,
            detail="当前未启用 Web 端无定位本地上传",
        )
    check_item, normalized_field_id = _resolve_photo_upload_check_item_and_field(
        db,
        inspection_id=inspection_id,
        check_item_id=check_item_id,
        field_id=field_id,
    )

    _touch_check_item_and_clear_review(check_item, datetime.utcnow())
    
    # 验证文件类型
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持图片文件"
        )
    
    # 照片逻辑：只在明确指定replace_existing=True时才替换
    import os
    
    # 注意：前端现在会主动调用删除API删除不需要的照片
    # 因此这里只在明确指定时才启用替换模式，避免误删其他照片
    should_replace = replace_existing
    
    # 执行照片替换逻辑（仅在明确指定时）
    if should_replace and check_item_id:
        # 删除同一检查项的已有照片
        existing_photos_query = db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == inspection_id,
            InspectionPhoto.check_item_id == check_item.id
        )
        # 字段级：仅替换同一字段下的照片；无字段配置时保持历史行为（整项替换）
        if normalized_field_id is not None:
            existing_photos_query = existing_photos_query.filter(InspectionPhoto.field_id == normalized_field_id)

        existing_photos = existing_photos_query.all()
        
        # 删除旧照片文件和数据库记录
        for old_photo in existing_photos:
            try:
                # 删除物理文件
                if old_photo.file_path and os.path.exists(old_photo.file_path):
                    os.remove(old_photo.file_path)
                # 删除数据库记录
                db.delete(old_photo)
                print(f"替换模式：删除旧检查照片 {old_photo.id}")
            except Exception as e:
                print(f"替换模式：删除旧检查照片失败 {old_photo.id}: {e}")
        
        print(f"检查照片替换模式：should_replace={should_replace}，已清理旧照片")
    else:
        print(f"检查照片添加模式：should_replace={should_replace}，直接添加新照片")

    # 保存文件
    file_path = await save_uploaded_file(file, "inspections", inspection_id)
    raw_content_hash = calculate_file_hash(file_path)

    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    similarity_policy = _resolve_similarity_alert_policy(db, current_user)
    trusted_original_content_hash: Optional[str] = None
    duplicate_detection_hash = raw_content_hash
    upload_ticket_text = str(upload_ticket or "").strip()
    if upload_ticket_text:
        try:
            ticket_info = _verify_photo_precheck_ticket(
                upload_ticket=upload_ticket_text,
                current_user=current_user,
                inspection_id=inspection_id,
                check_item_id=check_item.id,
                field_id=normalized_field_id,
                original_content_hash=original_content_hash,
            )
        except HTTPException:
            _cleanup_paths(file_path)
            raise
        trusted_original_content_hash = ticket_info.get("original_content_hash")
        duplicate_detection_hash = trusted_original_content_hash or raw_content_hash
    elif original_content_hash:
        print("DEBUG: 收到 original_content_hash 但未携带 upload_ticket，按兼容模式忽略原图特征码")

    duplicate_detail = detect_duplicate_detail(
        db,
        content_hash=duplicate_detection_hash,
        block_upload=duplicate_block_enabled,
    )
    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
    if duplicate_detail and duplicate_block_enabled:
        _cleanup_paths(file_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_detail,
        )

    similarity_result = _detect_similar_warning_if_needed(
        db,
        file_path=file_path,
        policy=similarity_policy,
    )
    similar_warning = similarity_result.get("warning")
    
    # 根据是否已有水印决定是否添加水印
    watermarked_path = file_path
    watermark_data = None
    location_compare = {}
    if planned_latitude is not None and planned_longitude is not None:
        location_compare["planned_coordinates"] = f"{planned_latitude:.6f}, {planned_longitude:.6f}"
    if distance_to_plan_m is not None:
        location_compare["distance_to_plan_m"] = round(float(distance_to_plan_m), 2)
    if location_distance_threshold_m is not None:
        location_compare["distance_threshold_m"] = round(float(location_distance_threshold_m), 2)
    if location_distance_exceeded is not None:
        location_compare["distance_exceeded"] = bool(location_distance_exceeded)
    if plan_coordinate_missing is not None:
        location_compare["plan_coordinate_missing"] = bool(plan_coordinate_missing)
    if distance_compare_enabled is not None:
        location_compare["distance_compare_enabled"] = bool(distance_compare_enabled)
    if distance_exceed_block_upload is not None:
        location_compare["distance_exceed_block_upload"] = bool(distance_exceed_block_upload)
    
    if not has_watermark:
        # 前端没有水印，后端添加水印
        print(f"DEBUG: 前端无水印，后端添加水印")
        watermark_data = {
            "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username,
            "accuracy": f"{gps_accuracy}m" if gps_accuracy else "N/A"
        }
        if location_compare:
            watermark_data["location_compare"] = location_compare
        watermarked_path = await generate_watermark(file_path, watermark_data)
    else:
        # 前端已有水印，跳过后端水印处理
        print(f"DEBUG: 前端已有水印，跳过后端水印处理")
        watermark_data = {
            "source": "frontend_watermark",
            "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username
        }
        if location_compare:
            watermark_data["location_compare"] = location_compare

    # 兜底校验：图片必须可完整解码；并检测“下半截空白”异常（Android canvas 偶发）
    try:
        validate_image_on_disk(watermarked_path, detect_blank_bottom=True)
    except ImageValidationError as e:
        print(f"图片校验失败，拒收上传: {e}. path={watermarked_path}")
        # 清理落盘文件，避免脏数据长期占用空间
        _cleanup_paths(file_path, watermarked_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    
    # 计算文件哈希
    file_hash = calculate_file_hash(watermarked_path)
    
    # 获取地址信息（本地上传不带定位信息时，不调用逆地理接口）
    address = None
    if not local_upload_without_geo:
        address = await reverse_geocode(gps_latitude, gps_longitude)
    
    # 创建照片记录
    photo = InspectionPhoto(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        check_item_id=check_item.id,
        field_id=normalized_field_id,
        original_name=file.filename,
        file_path=watermarked_path,
        file_size=file.size,
        mime_type=file.content_type,
        latitude=gps_latitude,
        longitude=gps_longitude,
        gps_accuracy=gps_accuracy,
        address=address,
        taken_at=datetime.utcnow(),
        has_watermark=has_watermark or watermark_data is not None,
        watermark_data=watermark_data,
        content_hash=raw_content_hash,
        original_content_hash=trusted_original_content_hash,
        hash_value=file_hash,
        uploaded_by=current_user.id
    )
    _mark_photo_duplicate_info(photo, duplicate_detail)
    _mark_photo_similarity_info(
        photo,
        similarity_features=similarity_result.get("features"),
        similar_warning=similar_warning,
        similarity_evaluation=similarity_result.get("evaluation"),
    )
    
    db.add(photo)
    try:
        db.flush()
        if not duplicate_detail:
            register_first_upload_record(
                db,
                content_hash=duplicate_detection_hash,
                source_type="inspection_photo",
                source_id=photo.id,
                site_id=inspection.site_id,
                site_name=_resolve_site_name_by_id(db, inspection.site_id),
                uploader_id=current_user.id,
                uploader_name=_resolve_uploader_name(current_user),
                uploaded_at=datetime.utcnow(),
            )
        db.commit()
        db.refresh(photo)
    except Exception:
        db.rollback()
        _cleanup_paths(file_path, watermarked_path)
        raise
    
    return _build_photo_response_with_warnings(photo, duplicate_warning, similar_warning)


@router.delete("/photos/{photo_id}")
async def delete_inspection_photo(
    request: Request,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定检查照片"""
    import os
    
    photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查关联的检查记录权限
    inspection = db.query(SiteInspection).filter(SiteInspection.id == photo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
        
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该照片")
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
        detail="当前未启用 Web 端照片上传",
    )
    
    # 检查检查状态是否允许删除照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许删除照片")

    # 删除照片属于检查项内容变更：触发该检查项回到待审核（仅清空该项，不影响其他项）
    if photo.check_item_id:
        check_item = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.id == photo.check_item_id,
            InspectionCheckItem.inspection_id == photo.inspection_id
        ).first()
        if check_item:
            _touch_check_item_and_clear_review(check_item, datetime.utcnow())
    
    # 删除物理文件
    try:
        if photo.file_path and os.path.exists(photo.file_path):
            os.remove(photo.file_path)
            print(f"已删除检查照片文件: {photo.file_path}")
    except Exception as e:
        print(f"删除检查照片文件失败: {e}")
    
    # 删除数据库记录
    db.delete(photo)
    db.commit()
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=photo.inspection_id,
        action="delete_photo",
        operator_id=current_user.id,
        details={"photo_id": photo_id, "check_item_id": photo.check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return {"message": "照片删除成功"}


@router.put("/photos/{photo_id}", response_model=InspectionPhotoResponse)
async def replace_inspection_photo(
    request: Request,
    photo_id: str,
    file: UploadFile = File(...),
    gps_latitude: Optional[float] = Form(None),
    gps_longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    has_watermark: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """替换指定检查照片"""
    import os
    
    existing_photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
    if not existing_photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查关联的检查记录权限
    inspection = db.query(SiteInspection).filter(SiteInspection.id == existing_photo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
        
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限替换该照片")
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_PHOTO_UPLOAD,
        detail="当前未启用 Web 端照片上传",
    )
    
    # 检查检查状态是否允许替换照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许替换照片")

    # 替换照片属于检查项内容变更：触发该检查项回到待审核（仅清空该项，不影响其他项）
    if existing_photo.check_item_id:
        check_item = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.id == existing_photo.check_item_id,
            InspectionCheckItem.inspection_id == existing_photo.inspection_id
        ).first()
        if check_item:
            _touch_check_item_and_clear_review(check_item, datetime.utcnow())
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")
    
    # 使用传入的GPS坐标，如果没有则使用原照片的坐标
    latitude = gps_latitude if gps_latitude is not None else existing_photo.latitude
    longitude = gps_longitude if gps_longitude is not None else existing_photo.longitude
    accuracy = gps_accuracy if gps_accuracy is not None else existing_photo.gps_accuracy
    
    # 保存新文件
    file_path = await save_uploaded_file(file, "inspections", existing_photo.inspection_id)
    raw_content_hash = calculate_file_hash(file_path)

    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    similarity_policy = _resolve_similarity_alert_policy(db, current_user)
    duplicate_detail = detect_duplicate_detail(
        db,
        content_hash=raw_content_hash,
        block_upload=duplicate_block_enabled,
        exclude_source_type="inspection_photo",
        exclude_source_id=existing_photo.id,
    )
    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
    if duplicate_detail and duplicate_block_enabled:
        _cleanup_paths(file_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=duplicate_detail,
        )

    similarity_result = _detect_similar_warning_if_needed(
        db,
        file_path=file_path,
        policy=similarity_policy,
        exclude_photo_id=existing_photo.id,
    )
    similar_warning = similarity_result.get("warning")
    
    # 根据是否已有水印决定是否添加水印
    watermarked_path = file_path
    watermark_data = None
    
    if not has_watermark:
        # 前端没有水印，后端添加水印
        watermark_data = {
            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username,
            "accuracy": f"{accuracy}m" if accuracy else "N/A"
        }
        watermarked_path = await generate_watermark(file_path, watermark_data)
    else:
        # 前端已有水印，跳过后端水印处理
        watermark_data = {
            "source": "frontend_watermark",
            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username
        }

    # 兜底校验：图片必须可完整解码；并检测“下半截空白”异常（Android canvas 偶发）
    try:
        validate_image_on_disk(watermarked_path, detect_blank_bottom=True)
    except ImageValidationError as e:
        print(f"图片校验失败，拒收上传: {e}. path={watermarked_path}")
        _cleanup_paths(file_path, watermarked_path)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    
    file_hash = calculate_file_hash(watermarked_path)
    address = await reverse_geocode(latitude, longitude)
    
    old_file_path = existing_photo.file_path
    
    # 更新照片记录
    existing_photo.original_name = file.filename
    existing_photo.file_path = watermarked_path
    existing_photo.file_size = file.size
    existing_photo.mime_type = file.content_type
    existing_photo.latitude = latitude
    existing_photo.longitude = longitude
    existing_photo.gps_accuracy = accuracy
    existing_photo.address = address
    existing_photo.taken_at = datetime.utcnow()
    existing_photo.has_watermark = has_watermark or watermark_data is not None
    existing_photo.watermark_data = watermark_data
    existing_photo.content_hash = raw_content_hash
    existing_photo.original_content_hash = None
    existing_photo.hash_value = file_hash
    existing_photo.updated_at = datetime.utcnow()
    _mark_photo_duplicate_info(existing_photo, duplicate_detail)
    _mark_photo_similarity_info(
        existing_photo,
        similarity_features=similarity_result.get("features"),
        similar_warning=similar_warning,
        similarity_evaluation=similarity_result.get("evaluation"),
    )
    
    try:
        if not duplicate_detail:
            register_first_upload_record(
                db,
                content_hash=raw_content_hash,
                source_type="inspection_photo",
                source_id=existing_photo.id,
                site_id=inspection.site_id,
                site_name=_resolve_site_name_by_id(db, inspection.site_id),
                uploader_id=current_user.id,
                uploader_name=_resolve_uploader_name(current_user),
                uploaded_at=datetime.utcnow(),
            )
        db.commit()
        db.refresh(existing_photo)
    except Exception:
        db.rollback()
        _cleanup_paths(file_path, watermarked_path)
        raise

    # 删除旧文件（提交成功后再清理，避免失败时丢失旧图）
    if old_file_path and old_file_path != watermarked_path:
        try:
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
                print(f"已删除旧检查照片文件: {old_file_path}")
        except Exception as e:
            print(f"删除旧检查照片文件失败: {e}")
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=existing_photo.inspection_id,
        action="replace_photo",
        operator_id=current_user.id,
        details={"photo_id": photo_id, "check_item_id": existing_photo.check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return _build_photo_response_with_warnings(existing_photo, duplicate_warning, similar_warning)


@router.post("/detail/{inspection_id}/photos/batch")
async def batch_inspection_photo_operations(
    inspection_id: str,
    operations: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量检查照片操作：删除、更新、添加照片
    
    operations: 操作列表，每个操作包含:
    - action: "delete" | "replace" | "add"
    - photo_id: 照片ID (delete/replace时必需)
    - file_data: base64编码的文件数据 (replace/add时必需)
    - filename: 文件名 (replace/add时必需)
    - check_item_id: 检查项ID (add时必需)
    - field_id: 字段ID (add时可选；若该检查项存在fields则必需)
    - gps_latitude, gps_longitude, gps_accuracy: GPS信息 (replace/add时可选)
    - has_watermark: 是否已有水印 (replace/add时可选)
    """
    import os
    import base64
    import tempfile
    from fastapi import UploadFile
    from io import BytesIO
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="检查记录不存在")
    _ensure_inspection_not_voided(inspection, detail="已作废检查不能清理照片")
        
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该检查照片")
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 检查检查状态是否允许操作照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许操作照片")
    
    results = []
    affected_check_item_ids = set()
    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    similarity_policy = _resolve_similarity_alert_policy(db, current_user)
    
    for i, operation in enumerate(operations):
        try:
            action = operation.get("action")
            photo_id = operation.get("photo_id")
            
            if action == "delete":
                if not photo_id:
                    results.append({"index": i, "action": "delete", "success": False, "error": "缺少photo_id"})
                    continue
                
                # 删除照片
                photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
                if not photo:
                    results.append({"index": i, "action": "delete", "success": False, "error": "照片不存在"})
                    continue

                if photo.check_item_id:
                    affected_check_item_ids.add(photo.check_item_id)
                
                # 删除物理文件
                try:
                    if photo.file_path and os.path.exists(photo.file_path):
                        os.remove(photo.file_path)
                except Exception as e:
                    print(f"批量操作：删除检查照片文件失败: {e}")
                
                # 删除数据库记录
                db.delete(photo)
                results.append({"index": i, "action": "delete", "success": True, "photo_id": photo_id})
                
            elif action == "replace":
                if not photo_id or not operation.get("file_data"):
                    results.append({"index": i, "action": "replace", "success": False, "error": "缺少photo_id或file_data"})
                    continue
                
                # 获取现有照片
                existing_photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
                if not existing_photo:
                    results.append({"index": i, "action": "replace", "success": False, "error": "照片不存在"})
                    continue

                if existing_photo.check_item_id:
                    affected_check_item_ids.add(existing_photo.check_item_id)
                
                # 处理文件数据
                try:
                    file_data = base64.b64decode(operation["file_data"])
                    filename = operation.get("filename", "replaced_photo.jpg")
                    
                    # 创建临时UploadFile对象
                    temp_file = BytesIO(file_data)
                    upload_file = UploadFile(
                        filename=filename,
                        file=temp_file,
                        size=len(file_data),
                        headers={"content-type": "image/jpeg"}
                    )
                    
                    # 使用GPS坐标
                    latitude = operation.get("gps_latitude", existing_photo.latitude)
                    longitude = operation.get("gps_longitude", existing_photo.longitude)
                    accuracy = operation.get("gps_accuracy", existing_photo.gps_accuracy)
                    has_watermark = operation.get("has_watermark", False)
                    
                    # 保存新文件
                    file_path = await save_uploaded_file(upload_file, "inspections", inspection_id)
                    raw_content_hash = calculate_file_hash(file_path)

                    duplicate_detail = detect_duplicate_detail(
                        db,
                        content_hash=raw_content_hash,
                        block_upload=duplicate_block_enabled,
                        exclude_source_type="inspection_photo",
                        exclude_source_id=existing_photo.id,
                    )
                    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
                    if duplicate_detail and duplicate_block_enabled:
                        _cleanup_paths(file_path)
                        results.append({
                            "index": i,
                            "action": "replace",
                            "success": False,
                            "error": duplicate_detail.get("message") if isinstance(duplicate_detail, dict) else "检测到重复图片，已阻断上传",
                            "duplicate_warning": duplicate_detail,
                        })
                        continue

                    similarity_result = _detect_similar_warning_if_needed(
                        db,
                        file_path=file_path,
                        policy=similarity_policy,
                        exclude_photo_id=existing_photo.id,
                    )
                    similar_warning = similarity_result.get("warning")
                    
                    # 根据是否已有水印决定是否添加水印
                    watermarked_path = file_path
                    watermark_data = None
                    
                    if not has_watermark:
                        # 前端没有水印，后端添加水印
                        watermark_data = {
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username,
                            "accuracy": f"{accuracy}m" if accuracy else "N/A"
                        }
                        watermarked_path = await generate_watermark(file_path, watermark_data)
                    else:
                        # 前端已有水印，跳过后端水印处理
                        watermark_data = {
                            "source": "frontend_watermark",
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username
                        }

                    # 兜底校验：图片必须可完整解码；并检测“下半截空白”异常（Android canvas 偶发）
                    try:
                        validate_image_on_disk(watermarked_path, detect_blank_bottom=True)
                    except ImageValidationError as e:
                        print(f"批量操作：图片校验失败，跳过本次replace: {e}. path={watermarked_path}")
                        _cleanup_paths(file_path, watermarked_path)
                        results.append({"index": i, "action": "replace", "success": False, "error": str(e)})
                        continue
                    
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 删除旧文件
                    try:
                        if existing_photo.file_path and os.path.exists(existing_photo.file_path):
                            os.remove(existing_photo.file_path)
                    except Exception as e:
                        print(f"批量操作：删除旧检查照片文件失败: {e}")
                    
                    # 更新照片记录
                    existing_photo.original_name = filename
                    existing_photo.file_path = watermarked_path
                    existing_photo.file_size = len(file_data)
                    existing_photo.mime_type = "image/jpeg"
                    existing_photo.latitude = latitude
                    existing_photo.longitude = longitude
                    existing_photo.gps_accuracy = accuracy
                    existing_photo.address = address
                    existing_photo.taken_at = datetime.utcnow()
                    existing_photo.has_watermark = has_watermark or watermark_data is not None
                    existing_photo.watermark_data = watermark_data
                    existing_photo.content_hash = raw_content_hash
                    existing_photo.original_content_hash = None
                    existing_photo.hash_value = file_hash
                    existing_photo.updated_at = datetime.utcnow()
                    _mark_photo_duplicate_info(existing_photo, duplicate_detail)
                    _mark_photo_similarity_info(
                        existing_photo,
                        similarity_features=similarity_result.get("features"),
                        similar_warning=similar_warning,
                        similarity_evaluation=similarity_result.get("evaluation"),
                    )

                    if not duplicate_detail:
                        register_first_upload_record(
                            db,
                            content_hash=raw_content_hash,
                            source_type="inspection_photo",
                            source_id=existing_photo.id,
                            site_id=inspection.site_id,
                            site_name=_resolve_site_name_by_id(db, inspection.site_id),
                            uploader_id=current_user.id,
                            uploader_name=_resolve_uploader_name(current_user),
                            uploaded_at=datetime.utcnow(),
                        )
                    
                    success_result = {"index": i, "action": "replace", "success": True, "photo_id": photo_id}
                    merged_warning = _merge_warning_messages(duplicate_warning, similar_warning)
                    if merged_warning:
                        success_result["warning"] = merged_warning
                    if duplicate_warning:
                        success_result["duplicate_warning"] = duplicate_warning
                    if similar_warning:
                        success_result["similar_warning"] = similar_warning
                    results.append(success_result)
                    
                except Exception as e:
                    results.append({"index": i, "action": "replace", "success": False, "error": str(e)})
                    
            elif action == "add":
                if not operation.get("file_data") or not operation.get("check_item_id"):
                    results.append({"index": i, "action": "add", "success": False, "error": "缺少file_data或check_item_id"})
                    continue

                check_item_id = operation.get("check_item_id")

                # 校验检查项存在且属于该检查
                check_item = db.query(InspectionCheckItem).filter(
                    InspectionCheckItem.id == check_item_id,
                    InspectionCheckItem.inspection_id == inspection_id
                ).first()
                if not check_item:
                    results.append({"index": i, "action": "add", "success": False, "error": "检查项不存在"})
                    continue

                # 字段级校验：按字段 allow_photo 控制
                normalized_field_id: Optional[str] = None
                allowed_field_id_set = set()
                # 字段拍照仅对 required_type=both 生效（字段来源于 dataFields）
                if str(getattr(check_item, "required_type", None) or "") == "both":
                    if isinstance(check_item.fields, list) and check_item.fields:
                        for f in check_item.fields:
                            if not isinstance(f, dict):
                                continue
                            fid_str = str(f.get("field_id") or "").strip()
                            if not fid_str:
                                continue
                            if _truthy(f.get("allow_photo")):
                                allowed_field_id_set.add(fid_str)

                raw_field_id = operation.get("field_id")
                if allowed_field_id_set:
                    if not raw_field_id or str(raw_field_id).strip() == "":
                        results.append({"index": i, "action": "add", "success": False, "error": "缺少field_id"})
                        continue
                    normalized_field_id = str(raw_field_id).strip()
                    if normalized_field_id not in allowed_field_id_set:
                        results.append({"index": i, "action": "add", "success": False, "error": "field_id无效或字段禁止拍照"})
                        continue
                else:
                    if raw_field_id and str(raw_field_id).strip() != "":
                        results.append({"index": i, "action": "add", "success": False, "error": "该检查项未启用字段拍照，不能指定field_id"})
                        continue

                affected_check_item_ids.add(check_item_id)
                
                # 处理文件数据
                try:
                    file_data = base64.b64decode(operation["file_data"])
                    filename = operation.get("filename", "new_photo.jpg")
                    
                    # 创建临时UploadFile对象
                    temp_file = BytesIO(file_data)
                    upload_file = UploadFile(
                        filename=filename,
                        file=temp_file,
                        size=len(file_data),
                        headers={"content-type": "image/jpeg"}
                    )
                    
                    # GPS坐标
                    latitude = operation.get("gps_latitude", 0)
                    longitude = operation.get("gps_longitude", 0)
                    accuracy = operation.get("gps_accuracy")
                    has_watermark = operation.get("has_watermark", False)
                    
                    # 保存文件
                    file_path = await save_uploaded_file(upload_file, "inspections", inspection_id)
                    raw_content_hash = calculate_file_hash(file_path)

                    duplicate_detail = detect_duplicate_detail(
                        db,
                        content_hash=raw_content_hash,
                        block_upload=duplicate_block_enabled,
                    )
                    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
                    if duplicate_detail and duplicate_block_enabled:
                        _cleanup_paths(file_path)
                        results.append({
                            "index": i,
                            "action": "add",
                            "success": False,
                            "error": duplicate_detail.get("message") if isinstance(duplicate_detail, dict) else "检测到重复图片，已阻断上传",
                            "duplicate_warning": duplicate_detail,
                        })
                        continue

                    similarity_result = _detect_similar_warning_if_needed(
                        db,
                        file_path=file_path,
                        policy=similarity_policy,
                    )
                    similar_warning = similarity_result.get("warning")
                    
                    # 根据是否已有水印决定是否添加水印
                    watermarked_path = file_path
                    watermark_data = None
                    
                    if not has_watermark:
                        # 前端没有水印，后端添加水印
                        watermark_data = {
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username,
                            "accuracy": f"{accuracy}m" if accuracy else "N/A"
                        }
                        watermarked_path = await generate_watermark(file_path, watermark_data)
                    else:
                        # 前端已有水印，跳过后端水印处理
                        watermark_data = {
                            "source": "frontend_watermark",
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username
                        }

                    # 兜底校验：图片必须可完整解码；并检测“下半截空白”异常（Android canvas 偶发）
                    try:
                        validate_image_on_disk(watermarked_path, detect_blank_bottom=True)
                    except ImageValidationError as e:
                        print(f"批量操作：图片校验失败，跳过本次add: {e}. path={watermarked_path}")
                        _cleanup_paths(file_path, watermarked_path)
                        results.append({"index": i, "action": "add", "success": False, "error": str(e)})
                        continue
                    
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 创建新照片记录
                    new_photo = InspectionPhoto(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection_id,
                        check_item_id=check_item_id,
                        field_id=normalized_field_id,
                        original_name=filename,
                        file_path=watermarked_path,
                        file_size=len(file_data),
                        mime_type="image/jpeg",
                        latitude=latitude,
                        longitude=longitude,
                        gps_accuracy=accuracy,
                        address=address,
                        taken_at=datetime.utcnow(),
                        has_watermark=has_watermark or watermark_data is not None,
                        watermark_data=watermark_data,
                        content_hash=raw_content_hash,
                        original_content_hash=None,
                        hash_value=file_hash,
                        uploaded_by=current_user.id
                    )
                    _mark_photo_duplicate_info(new_photo, duplicate_detail)
                    _mark_photo_similarity_info(
                        new_photo,
                        similarity_features=similarity_result.get("features"),
                        similar_warning=similar_warning,
                        similarity_evaluation=similarity_result.get("evaluation"),
                    )
                    db.add(new_photo)
                    if not duplicate_detail:
                        register_first_upload_record(
                            db,
                            content_hash=raw_content_hash,
                            source_type="inspection_photo",
                            source_id=new_photo.id,
                            site_id=inspection.site_id,
                            site_name=_resolve_site_name_by_id(db, inspection.site_id),
                            uploader_id=current_user.id,
                            uploader_name=_resolve_uploader_name(current_user),
                            uploaded_at=datetime.utcnow(),
                        )
                    
                    success_result = {"index": i, "action": "add", "success": True, "photo_id": new_photo.id}
                    merged_warning = _merge_warning_messages(duplicate_warning, similar_warning)
                    if merged_warning:
                        success_result["warning"] = merged_warning
                    if duplicate_warning:
                        success_result["duplicate_warning"] = duplicate_warning
                    if similar_warning:
                        success_result["similar_warning"] = similar_warning
                    results.append(success_result)
                    
                except Exception as e:
                    results.append({"index": i, "action": "add", "success": False, "error": str(e)})
            
            else:
                results.append({"index": i, "action": action, "success": False, "error": "无效的操作类型"})
                
        except Exception as e:
            results.append({"index": i, "action": operation.get("action", "unknown"), "success": False, "error": str(e)})

    # 批量照片操作属于检查项内容变更：触发对应检查项回到待审核（仅清空受影响项）
    if affected_check_item_ids:
        now = datetime.utcnow()
        for cid in affected_check_item_ids:
            if not cid:
                continue
            check_item = db.query(InspectionCheckItem).filter(
                InspectionCheckItem.id == cid,
                InspectionCheckItem.inspection_id == inspection_id
            ).first()
            if check_item:
                _touch_check_item_and_clear_review(check_item, now)
    
    # 提交所有更改
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        action="batch_photo_operations",
        operator_id=current_user.id,
        details={"operations_count": len(operations), "results": results}
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": "批量检查照片操作完成",
        "total_operations": len(operations),
        "results": results
    }


@router.post("/detail/{inspection_id}/photos/cleanup")
async def cleanup_duplicate_inspection_photos(
    inspection_id: str,
    check_item_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理重复和累积的检查照片，只保留最新的照片"""
    import os
    from collections import defaultdict
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="检查记录不存在")
        
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该检查照片")
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 构建查询条件
    query = db.query(InspectionPhoto).filter(InspectionPhoto.inspection_id == inspection_id)
    if check_item_id:
        query = query.filter(InspectionPhoto.check_item_id == check_item_id)
    
    # 获取所有照片，按检查项分组
    photos = query.order_by(InspectionPhoto.created_at.desc()).all()
    
    # 按检查项 + 字段分组（字段级照片允许同一检查项下多组同时存在）
    photos_by_item = defaultdict(list)
    for photo in photos:
        key = (
            photo.check_item_id or "inspection_level",
            getattr(photo, "field_id", None) or "__unlinked__",
        )
        photos_by_item[key].append(photo)
    
    deleted_count = 0
    kept_count = 0
    affected_check_item_ids = set()
    
    for (item_id, field_id_key), item_photos in photos_by_item.items():
        if len(item_photos) <= 1:
            kept_count += len(item_photos)
            continue
        
        # 保留最新的照片，删除其他的
        latest_photo = item_photos[0]  # 已按created_at倒序排列
        photos_to_delete = item_photos[1:]
        
        for old_photo in photos_to_delete:
            try:
                # 删除物理文件
                if old_photo.file_path and os.path.exists(old_photo.file_path):
                    os.remove(old_photo.file_path)
                # 删除数据库记录
                db.delete(old_photo)
                deleted_count += 1
                print(f"清理累积检查照片: {old_photo.id} (检查项: {item_id}, 字段: {field_id_key})")
            except Exception as e:
                print(f"清理检查照片失败 {old_photo.id}: {e}")
        
        # 照片删除属于检查项内容变更：触发对应检查项回到待审核（仅清空该项，不影响其他项）
        if item_id and item_id != "inspection_level" and photos_to_delete:
            affected_check_item_ids.add(item_id)

        kept_count += 1  # 保留的最新照片

    if affected_check_item_ids:
        now = datetime.utcnow()
        for cid in affected_check_item_ids:
            check_item = db.query(InspectionCheckItem).filter(
                InspectionCheckItem.id == cid,
                InspectionCheckItem.inspection_id == inspection_id
            ).first()
            if check_item:
                _touch_check_item_and_clear_review(check_item, now)
    
    db.commit()
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        action="cleanup_duplicate_photos",
        operator_id=current_user.id,
        details={"deleted_count": deleted_count, "kept_count": kept_count, "check_item_id": check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": "检查照片清理完成",
        "deleted_count": deleted_count,
        "kept_count": kept_count,
        "details": f"已删除 {deleted_count} 张重复照片，保留 {kept_count} 张最新照片"
    }


# Template endpoints moved to template_binding.py
# Old template endpoint removed to avoid routing conflicts

@router.get("/statistics/overview", response_model=InspectionStatistics)
async def get_inspection_statistics(
    site_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查统计信息 - 统一接口"""
    query = db.query(SiteInspection)
    
    if site_id:
        query = query.filter(SiteInspection.site_id == site_id)
    
    if start_date:
        query = query.filter(SiteInspection.created_at >= start_date)
    
    if end_date:
        query = query.filter(SiteInspection.created_at <= end_date)
    
    # 权限过滤
    if _is_field_worker(current_user):
        query = query.filter(SiteInspection.inspector_id == current_user.id)
    
    total_inspections = query.count()
    completed_inspections = query.filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.COMPLETED,
            InspectionStatusEnum.APPROVED
        ])
    ).count()
    pending_inspections = query.filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.DRAFT,
            InspectionStatusEnum.IN_PROGRESS,
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW
        ])
    ).count()
    approved_inspections = query.filter(
        SiteInspection.status == InspectionStatusEnum.APPROVED
    ).count()
    rejected_inspections = query.filter(
        SiteInspection.status == InspectionStatusEnum.REJECTED
    ).count()
    
    # 计算平均分
    avg_score_result = query.filter(
        SiteInspection.score.is_not(None)
    ).with_entities(
        func.avg(SiteInspection.score)
    ).scalar()
    
    completion_rate = (completed_inspections / total_inspections * 100) if total_inspections > 0 else 0
    
    return InspectionStatistics(
        total_inspections=total_inspections,
        completed_inspections=completed_inspections,
        pending_inspections=pending_inspections,
        approved_inspections=approved_inspections,
        rejected_inspections=rejected_inspections,
        average_score=round(avg_score_result, 2) if avg_score_result else None,
        completion_rate=round(completion_rate, 2)
    )

@router.get("/detail/{inspection_id}/items", response_model=List[InspectionCheckItemResponse])
async def get_inspection_items(
    inspection_id: str,
    equipment_sn: Optional[str] = None,
    has_equipment: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取检查项列表
    
    Args:
        inspection_id: 检查记录ID
        equipment_sn: 设备SN筛选（模糊查询）
        has_equipment: 绑定状态筛选（True=已绑定，False=未绑定）
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        检查项列表
    """
    from sqlalchemy.orm import joinedload

    # 验证检查记录存在
    inspection = (
        db.query(SiteInspection)
        .options(joinedload(SiteInspection.template))
        .filter(SiteInspection.id == inspection_id)
        .first()
    )
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (_is_field_worker(current_user) and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此检查记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    template_data = {}
    try:
        tpl = inspection.template
        if tpl is not None and isinstance(getattr(tpl, "template_data", None), dict):
            template_data = tpl.template_data or {}
    except Exception:
        template_data = {}

    template_index = _build_template_i18n_index(template_data)

    # 获取检查项，包括照片
    query = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.photos)
    ).filter(
        InspectionCheckItem.inspection_id == inspection_id
    )
    
    # 设备SN筛选（模糊查询）
    if equipment_sn:
        query = query.filter(InspectionCheckItem.equipment_sn.like(f"%{equipment_sn}%"))
    
    # 绑定状态筛选
    if has_equipment is True:
        query = query.filter(InspectionCheckItem.equipment_sn.isnot(None))
    elif has_equipment is False:
        # 仅筛选小区级检查项中未绑定的
        query = query.filter(
            InspectionCheckItem.equipment_sn.is_(None),
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.band.isnot(None)
        )
    
    check_items = query.all()

    resp_items = []
    for check_item in check_items:
        base_item_id = _strip_cell_suffix(check_item.item_id)
        meta = template_index.get(base_item_id) or template_index.get(check_item.item_id)

        cat_i18n = None
        item_i18n = None
        desc_i18n = None
        template_fields_map = None
        if meta:
            cat_i18n = _as_i18n_dict(meta.get("category", {}).get("category_name_i18n"))
            item_i18n = _as_i18n_dict(meta.get("item", {}).get("item_name_i18n"))
            desc_i18n = _as_i18n_dict(meta.get("item", {}).get("description_i18n"))
            template_fields_map = meta.get("field_map") or None

        merged_fields = _merge_fields_i18n(check_item.fields, template_fields_map)

        base = InspectionCheckItemResponse.model_validate(check_item, from_attributes=True)
        update_payload = {"fields": merged_fields}
        if cat_i18n is not None:
            update_payload["category_name_i18n"] = cat_i18n
        if item_i18n is not None:
            update_payload["item_name_i18n"] = item_i18n
        if desc_i18n is not None:
            update_payload["description_i18n"] = desc_i18n
        resp_items.append(base.model_copy(update=update_payload))

    return resp_items

@router.put("/detail/{inspection_id}/items/{item_id}", response_model=InspectionCheckItemResponse)
async def update_inspection_item(
    request: Request,
    inspection_id: str,
    item_id: str,
    item_update: InspectionCheckItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新检查项"""
    # 验证检查记录存在
    from sqlalchemy.orm import joinedload

    inspection = (
        db.query(SiteInspection)
        .options(joinedload(SiteInspection.template))
        .filter(SiteInspection.id == inspection_id)
        .first()
    )
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (_is_field_worker(current_user) and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此检查记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_ENABLED,
        detail="当前未启用 Web 工单填写",
    )

    # 检查状态门禁：仅允许草稿/进行中/驳回继续更新检查项（避免已提交/审核中/已通过/已完成继续修改）
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"检查状态 {_enum_value(inspection.status)} 下不允许更新检查项"
        )

    template_data = {}
    try:
        tpl = inspection.template
        if tpl is not None and isinstance(getattr(tpl, "template_data", None), dict):
            template_data = tpl.template_data or {}
    except Exception:
        template_data = {}
    template_index = _build_template_i18n_index(template_data)
    
    # 验证检查项存在
    check_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == inspection_id
    ).first()
    
    if not check_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查项不存在"
        )
    
    # 更新检查项
    update_fields = item_update.dict(exclude_unset=True)
    content_changed = False

    # 对于勘察类任务，严格要求 data_value 的 field_name 与模板 field_id 一致；
    # 允许客户端使用 field_id/key/field/name 提交，但最终统一写入为 field_name=field_id。
    if 'data_value' in update_fields and update_fields['data_value'] is not None:
        # 构建 field_id 集合
        field_ids = set()
        label_to_id = {}
        if isinstance(check_item.fields, list):
            for f in check_item.fields:
                fid = f.get('field_id') if isinstance(f, dict) else getattr(f, 'field_id', None)
                lbl = f.get('label') if isinstance(f, dict) else getattr(f, 'label', None)
                if fid:
                    field_ids.add(str(fid))
                if fid and lbl:
                    label_to_id[str(lbl)] = str(fid)

        normalized = []
        invalid = []
        for dv in update_fields['data_value']:
            d = dv.dict() if hasattr(dv, 'dict') else (dv or {})
            raw_name = d.get('field_name') or d.get('field_id') or d.get('key') or d.get('field') or d.get('name')
            if not raw_name:
                invalid.append('(missing field_name)')
                continue
            name = str(raw_name)
            if field_ids and name not in field_ids:
                # 精确以字段label匹配一次（非推断）
                mapped = label_to_id.get(name)
                if mapped:
                    name = mapped
                else:
                    invalid.append(name)
                    continue
            normalized.append({
                'field_name': name,
                'value': d.get('value'),
                'unit': d.get('unit'),
            })

        if invalid:
            allowed = ','.join(sorted(field_ids)) if field_ids else '无字段定义'
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"存在未定义字段: {invalid}；允许的 field_id: {allowed}"
            )
        update_fields['data_value'] = normalized
    
    # 如果更新包含data_value且检查项有字段定义，执行字段验证（非严格：允许部分填写）
    if 'data_value' in update_fields and check_item.fields:
        try:
            # 将check_item.fields转换为FieldDefinition对象列表
            field_definitions = []
            if isinstance(check_item.fields, list):
                for field_dict in check_item.fields:
                    try:
                        field_def = FieldDefinition(**field_dict)
                        field_definitions.append(field_def)
                    except Exception as e:
                        print(f"WARNING: 无法解析字段定义: {field_dict}, 错误: {e}")
            
            # 执行验证（非严格模式，允许部分填写）
            if field_definitions and update_fields['data_value']:
                # 将CheckItemDataValue对象列表转换为字典列表
                data_values_dict = []
                for dv in update_fields['data_value']:
                    if hasattr(dv, 'dict'):
                        data_values_dict.append(dv.dict())
                    elif isinstance(dv, dict):
                        data_values_dict.append(dv)
                
                validation_result = FieldValidator.validate_check_item_data(
                    field_definitions,
                    data_values_dict,
                    strict=False  # 勘察允许部分填写；未知字段在上一步已拒绝
                )
                
                # 存储验证结果
                check_item.validation_result = validation_result
                
                # 如果有验证错误，记录但不阻止保存（允许保存草稿）
                if not validation_result['valid']:
                    print(f"INFO: 检查项 {item_id} 存在字段验证错误: {validation_result['errors']}")
        except HTTPException:
            raise  # 重新抛出HTTP异常
        except Exception as e:
            print(f"WARNING: 字段验证过程出错: {e}")
            # 验证出错不阻止保存，但记录错误

    # 判断本次是否存在实际内容变更（仅看客户端提交字段，不包含 checked_at/updated_at 等元数据）
    def _norm(v):
        if v is None:
            return None
        return getattr(v, 'value', v)

    for field, value in update_fields.items():
        if field not in ('status', 'data_value', 'sector_id', 'notes'):
            continue
        if _norm(getattr(check_item, field, None)) != _norm(value):
            content_changed = True
            break
    
    for field, value in update_fields.items():
        setattr(check_item, field, value)
    
    # 更新检查人员和时间
    now = datetime.utcnow()
    check_item.checked_by = current_user.id
    check_item.checked_at = now
    check_item.updated_at = now

    # 内容变更：清空该检查项既有审核结果（若已审核过），以便增量复审
    if content_changed:
        _touch_check_item_and_clear_review(check_item, now)

    # 完成态数据校验：
    # - required_type=data：必须至少提交1个字段值；且所有“可见(required=true)”字段必须填写并通过约束
    # - required_type=both：必须至少提交1个字段值；且所有“可见(required=true)”字段必须填写并通过约束
    if check_item.status == CheckItemStatusEnum.COMPLETED and str(check_item.required_type) in ("data", "both"):
        data_value = getattr(check_item, "data_value", None)
        values = _build_field_values_from_data_value(data_value)

        # 规则：至少 1 个字段有“有效值”
        has_any_value = any(not _is_empty_value(v) for v in values.values())
        if not has_any_value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该检查项需要填写至少1个字段数据"
            )

        # 若存在字段定义，则按“可见字段”进行严格校验（隐藏字段不参与必填）
        errors = {}
        label_map = {}
        visible_field_ids = []
        if isinstance(check_item.fields, list) and check_item.fields:
            for f in check_item.fields:
                if not isinstance(f, dict):
                    continue
                fid = str(f.get("field_id") or "").strip()
                if not fid:
                    continue
                label_map[fid] = str(f.get("label") or fid)
                if not _is_field_visible(f, values):
                    continue
                visible_field_ids.append(fid)

                try:
                    field_def = FieldDefinition(**f)
                except Exception as e:
                    print(f"WARNING: 无法解析字段定义用于完成态校验: {f}, 错误: {e}")
                    continue

                ok, msg = FieldValidator.validate_field_value(field_def, values.get(field_def.field_id), strict=True)
                if not ok:
                    errors[field_def.field_id] = msg

            # 若存在可见字段定义：至少 1 个可见字段应有值（避免仅提交隐藏字段导致“空完成”）
            if visible_field_ids:
                has_any_visible_value = any(
                    (fid in values) and (not _is_empty_value(values.get(fid)))
                    for fid in visible_field_ids
                )
                if not has_any_visible_value:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="该检查项需要填写至少1个字段数据"
                    )

        if errors:
            error_messages = '; '.join([f"{label_map.get(k, k)}: {v}" for k, v in errors.items()])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"字段验证失败，无法标记为完成: {error_messages}"
            )

    # 字段级照片校验：
    # - 若检查项要求照片(photo/both)，且本次要标记为完成，则校验：
    #   1) 若存在 allow_photo=True 且 photo_required=True 的可见字段：每个字段至少 1 张照片
    #   2) 否则：若存在 allow_photo=True 的字段：至少 1 张“字段照片”(带 field_id)
    #   3) 否则：走“未关联照片”模式：至少 1 张照片
    if check_item.status == CheckItemStatusEnum.COMPLETED and str(check_item.required_type) in ("photo", "both"):
        req_type = str(check_item.required_type)
        photos = db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == inspection_id,
            InspectionPhoto.check_item_id == check_item.id
        ).all()

        # photo 类型：只要求至少 1 张照片（不做字段级归属约束）
        if req_type == "photo":
            if len(photos) <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="该检查项需要至少上传1张照片"
                )
        else:
            # both 类型：字段级规则生效（allow_photo / photo_required）
            allowed_field_ids, required_field_ids, field_labels, field_by_id = _extract_photo_field_rules(check_item.fields)

            counts = {}
            for p in photos:
                fid = str(getattr(p, "field_id", None) or "").strip()
                if not fid:
                    continue
                counts[fid] = counts.get(fid, 0) + 1

            field_values = _build_field_values_from_data_value(check_item.data_value)
            visible_required = set()
            for fid in required_field_ids:
                fcfg = field_by_id.get(fid) or {}
                if _is_field_visible(fcfg, field_values):
                    visible_required.add(fid)

            if visible_required:
                missing = [fid for fid in sorted(visible_required) if counts.get(fid, 0) <= 0]
                if missing:
                    missing_labels = [field_labels.get(fid, fid) for fid in missing]
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"缺少必拍字段照片: {', '.join(missing_labels)}"
                    )
            else:
                if allowed_field_ids:
                    linked_total = sum(counts.get(fid, 0) for fid in allowed_field_ids)
                    if linked_total <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该检查项需要至少上传1张字段照片"
                        )
                else:
                    if len(photos) <= 0:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="该检查项需要至少上传1张照片"
                        )
    
    # 如果检查项已完成且绑定了设备，更新设备状态为"已检查"
    if (check_item.status == CheckItemStatusEnum.COMPLETED and 
        check_item.equipment_sn):
        from app.models.equipment import EquipmentInstance, InventoryStatusEnum
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == check_item.equipment_sn
        ).first()
        
        if equipment_instance:
            equipment_instance.status = InventoryStatusEnum.INSPECTED
            equipment_instance.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(check_item)
    
    # 重新计算检查完成率
    total_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id
    ).count()
    
    completed_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
    ).count()
    
    failed_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.status == CheckItemStatusEnum.FAILED
    ).count()
    
    # 更新检查记录的统计信息
    inspection.total_items = total_items
    inspection.completed_items = completed_items
    inspection.failed_items = failed_items
    inspection.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
    
    # 检查是否所有项都已完成，如果是则自动更新检查状态并同步工单状态
    if inspection.completion_rate == 100.0:
        from app.services.work_order_sync import get_work_order_sync_service
        from datetime import datetime as dt
        
        print(f"DEBUG: 检查项更新完成100% - 检查ID: {inspection.id}, 当前状态: {inspection.status}, submitted_at: {inspection.submitted_at}")
        
        auto_submit_allowed = True
        if is_web_admin_request(request) and work_order is not None:
            auto_submit_allowed = can_use_web_work_order_execution(
                db,
                current_user,
                work_order_type=work_order.type,
                capability=WORK_ORDER_EXECUTION_CAPABILITY_SUBMIT,
            )

        if auto_submit_allowed:
            # 如果检查状态还是进行中，更新为已提交
            if inspection.status == InspectionStatusEnum.IN_PROGRESS:
                inspection.status = InspectionStatusEnum.SUBMITTED
                inspection.end_time = dt.utcnow()
                print(f"DEBUG: 状态从IN_PROGRESS更新为SUBMITTED: {inspection.id}")
            
            # 如果检查状态是SUBMITTED但没有submitted_at，设置它
            if inspection.status == InspectionStatusEnum.SUBMITTED and not inspection.submitted_at:
                inspection.submitted_at = dt.utcnow()
                print(f"DEBUG: 设置submitted_at时间戳: {inspection.id}, 时间: {inspection.submitted_at}")
            
            # 如果检查关联了工单，同步工单状态（无论检查当前状态如何）
            if inspection.work_order_id:
                print(f"DEBUG: 开始同步工单状态 - 检查ID: {inspection.id}, 工单ID: {inspection.work_order_id}")
                sync_service = get_work_order_sync_service(db)
                sync_service.sync_inspection_to_work_order_status(inspection)
    
    db.commit()
    
    base_item_id = _strip_cell_suffix(check_item.item_id)
    meta = template_index.get(base_item_id) or template_index.get(check_item.item_id)
    cat_i18n = None
    item_i18n = None
    desc_i18n = None
    template_fields_map = None
    if meta:
        cat_i18n = _as_i18n_dict(meta.get("category", {}).get("category_name_i18n"))
        item_i18n = _as_i18n_dict(meta.get("item", {}).get("item_name_i18n"))
        desc_i18n = _as_i18n_dict(meta.get("item", {}).get("description_i18n"))
        template_fields_map = meta.get("field_map") or None

    merged_fields = _merge_fields_i18n(check_item.fields, template_fields_map)
    base = InspectionCheckItemResponse.model_validate(check_item, from_attributes=True)
    update_payload = {"fields": merged_fields}
    if cat_i18n is not None:
        update_payload["category_name_i18n"] = cat_i18n
    if item_i18n is not None:
        update_payload["item_name_i18n"] = item_i18n
    if desc_i18n is not None:
        update_payload["description_i18n"] = desc_i18n
    return base.model_copy(update=update_payload)

@router.post("/detail/{inspection_id}/reset")
async def reset_inspection_for_rejected_task(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """为被驳回的任务重置检查记录状态，允许重新编辑"""
    # 验证检查记录存在
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查：只有现场人员本人可以重置自己的检查记录
    if (_is_field_worker(current_user) and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限重置此检查记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 检查关联的任务是否被驳回
    if inspection.work_order_id:
        from app.models.work_order import WorkOrder
        work_order = db.query(WorkOrder).filter(
            WorkOrder.id == inspection.work_order_id
        ).first()
        
        if not work_order or work_order.status.value != "REJECTED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能重置被驳回任务的检查记录"
            )
    
    try:
        # 重置检查记录状态为 in_progress
        inspection.status = InspectionStatusEnum.IN_PROGRESS
        inspection.end_time = None
        inspection.submitted_at = None
        inspection.updated_at = datetime.utcnow()
        
        # 重置所有已完成的检查项为待处理状态，允许重新检查
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.status.in_([
                CheckItemStatusEnum.COMPLETED,
                CheckItemStatusEnum.FAILED
            ])
        ).all()
        
        for item in check_items:
            item.status = CheckItemStatusEnum.PENDING
            item.result_data = None
            item.notes = None
            item.checked_by = None
            item.checked_at = None
            _touch_check_item_and_clear_review(item, datetime.utcnow())
        
        # 重新计算完成率
        total_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).count()
        
        completed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
        ).count()
        
        inspection.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        db.commit()
        db.refresh(inspection)
        
        return {
            "message": "检查记录已重置，可以重新编辑",
            "inspection": inspection
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置检查记录失败: {str(e)}"
        )

@router.post("/detail/{inspection_id}/review")
async def review_inspection(
    inspection_id: str,
    review: InspectionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查审核：approve/reject，记录审核人与日志"""
    _ensure_review_access(current_user, detail="没有权限执行检查审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    old_status = inspection.status
    if old_status not in [InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"当前状态不允许审核：{old_status}")

    try:
        now = datetime.utcnow()
        if review.action == "approve":
            inspection.status = InspectionStatusEnum.APPROVED
        else:
            inspection.status = InspectionStatusEnum.REJECTED

        # 回填审核信息
        inspection.reviewed_by = current_user.id
        inspection.reviewed_at = now
        if review.comments:
            inspection.review_comments = review.comments
        if review.score is not None:
            inspection.score = review.score

        db.commit()
        db.refresh(inspection)

        # 审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            action="approve" if review.action == "approve" else "reject",
            from_status=old_status.value if old_status else None,
            to_status=inspection.status.value,
            operator_id=current_user.id,
            comments=review.comments
        )
        db.add(audit_log)
        db.commit()

        return {
            "message": "检查审核成功",
            "inspection": inspection
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检查审核失败: {str(e)}")

@router.post("/detail/{inspection_id}/items/{item_id}/review")
async def review_inspection_item(
    inspection_id: str,
    item_id: str,
    review: CheckItemReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查项审核：pass/fail/warning"""
    _ensure_review_access(current_user, detail="没有权限执行检查项审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    check_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == inspection_id
    ).first()
    if not check_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查项不存在")

    try:
        item_status_value = getattr(check_item.status, "value", check_item.status)
        if str(item_status_value) != CheckItemStatusEnum.COMPLETED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"检查项未完成提交，无法审核（当前状态：{item_status_value}）"
            )
        now = datetime.utcnow()
        check_item.review_status = review.action
        check_item.review_comments = review.comments
        check_item.review_comments_i18n = review.comments_i18n
        check_item.reviewed_by = current_user.id
        check_item.reviewed_at = now
        check_item.updated_at = now
        db.commit()
        db.refresh(check_item)

        # 写审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection_id,
            action="item_review",
            from_status=None,
            to_status=None,
            operator_id=current_user.id,
            comments=review.comments,
            details={"item_id": item_id, "result": review.action}
        )
        db.add(audit_log)
        db.commit()

        # 更新检查结果汇总（pass/fail/warning）
        _update_inspection_result_from_item_reviews(db, inspection_id)

        return {"message": "检查项审核成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检查项审核失败: {str(e)}")

@router.post("/detail/{inspection_id}/photos/{photo_id}/review")
async def review_inspection_photo(
    inspection_id: str,
    photo_id: str,
    review: PhotoReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """照片审核：approved/rejected"""
    _ensure_review_access(current_user, detail="没有权限执行照片审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    photo = db.query(InspectionPhoto).filter(
        InspectionPhoto.id == photo_id,
        InspectionPhoto.inspection_id == inspection_id
    ).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="照片不存在")

    try:
        photo.review_status = review.action
        photo.review_comments = review.comments
        db.commit()
        db.refresh(photo)

        # 写审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection_id,
            action="photo_review",
            from_status=None,
            to_status=None,
            operator_id=current_user.id,
            comments=review.comments,
            details={"photo_id": photo_id, "result": review.action}
        )
        db.add(audit_log)
        db.commit()

        return {"message": "照片审核成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"照片审核失败: {str(e)}")

@router.get("/detail/{inspection_id}/review-summary", response_model=InspectionReviewSummary)
async def get_inspection_review_summary(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查审核汇总（基于检查项 review_status）"""
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    # 权限：现场人员仅可看自己，其他角色可看
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问此检查记录")
    _ensure_surveyor_inspection_type(db, current_user, inspection)

    total = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id).count()
    pass_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "pass").count()
    fail_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "fail").count()
    warning_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "warning").count()
    pending_count = total - pass_count - fail_count - warning_count

    return InspectionReviewSummary(
        total_items=total,
        pass_count=pass_count,
        fail_count=fail_count,
        warning_count=warning_count,
        pending_count=pending_count
    )

# 内部工具：根据检查项审核结果更新检查记录的 result 字段
def _update_inspection_result_from_item_reviews(db: Session, inspection_id: str) -> None:
    try:
        items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id).all()
        # 确定结果优先级：fail > warning > pass > pending
        result = None
        has_fail = any(i.review_status == "fail" for i in items)
        has_warning = any(i.review_status == "warning" for i in items)
        all_pass_or_pending = all(i.review_status in (None, "pass") for i in items)
        has_pass = any(i.review_status == "pass" for i in items)

        if has_fail:
            result = "fail"
        elif has_warning:
            result = "warning"
        elif all_pass_or_pending and has_pass:
            result = "pass"
        else:
            result = None

        inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
        if inspection:
            inspection.result = result
            inspection.updated_at = datetime.utcnow()
            db.commit()
    except Exception:
        db.rollback()
        raise


# 新增：设备验证和绑定接口
@router.get("/equipment/check-pickup/{sn}")
async def check_equipment_pickup_status(
    sn: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """验证设备是否已被当前用户领料。

    放宽校验：支持已出库(ISSUED)与待检查(PENDING_INSPECTION)两种状态，
    以兼容已完成首次绑定但再次扫描校验的场景。
    """
    sn_norm = (sn or "").strip()
    try:
        from app.models.equipment import EquipmentInstance, InventoryStatusEnum

        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == sn_norm
        ).first()

        if not equipment_instance:
            raise HTTPException(status_code=404, detail=f"设备序列号 {sn_norm} 不存在")

        # 允许以下状态进入检查流程：已出库、待检查、已检查（便于复核/返检）
        allowed_status = {
            InventoryStatusEnum.ISSUED,
            InventoryStatusEnum.PENDING_INSPECTION,
            InventoryStatusEnum.INSPECTED,
        }
        if equipment_instance.status not in allowed_status:
            raise HTTPException(status_code=400, detail="设备未出库，无法进行检查")

        if equipment_instance.issued_to != current_user.id:
            raise HTTPException(status_code=403, detail="设备未被当前用户领料，无法进行检查")

        return {
            "success": True,
            "equipment_sn": sn_norm,
            "equipment_name": equipment_instance.equipment.equipment_name if equipment_instance.equipment else "未知设备",
            "issued_date": equipment_instance.issued_date,
            "message": "设备验证通过，可以进行检查"
        }
    except HTTPException:
        raise
    except Exception:
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "check_equipment_pickup_status failed error_id=%s sn=%s user_id=%s",
            error_id,
            sn_norm,
            getattr(current_user, "id", None),
        )
        raise HTTPException(
            status_code=500,
            detail=f"系统异常，设备校验失败，请稍后重试或联系管理员（错误编号：{error_id}）",
        )


@router.post("/detail/{inspection_id}/bind-equipment")
async def bind_equipment_to_sector(
    request: Request,
    inspection_id: str,
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """绑定设备到小区检查项"""
    equipment_sn = request_data.get("equipment_sn")
    if isinstance(equipment_sn, str):
        equipment_sn = equipment_sn.strip()
    sector_id = request_data.get("sector_id")
    band = request_data.get("band")
    
    if not sector_id:
        raise HTTPException(
            status_code=400,
            detail="扇区ID不能为空"
        )
    
    # 如果设备SN为空或空字符串，表示解绑操作
    is_unbind = not equipment_sn
    
    # 验证检查记录存在且属于当前用户
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id,
        SiteInspection.inspector_id == current_user.id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="检查记录不存在或无权限操作"
        )
    _ensure_inspection_not_voided(inspection, detail="已作废检查不能绑定或解绑设备")
    work_order = _get_work_order_for_inspection(db, inspection)
    ensure_web_work_order_execution_allowed(
        request,
        db,
        current_user,
        work_order_type=work_order.type if work_order else None,
        capability=WORK_ORDER_EXECUTION_CAPABILITY_DEVICE_BINDING,
        detail="当前未启用 Web 端设备绑定",
    )

    # 识别工单类型（设备更换工单允许“直接换绑”）
    wo: Optional[WorkOrder] = work_order
    is_replacement_wo = False
    if getattr(inspection, "work_order_id", None):
        wo = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()
        if wo and wo.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
            is_replacement_wo = True
    
    # 验证设备状态（仅在绑定操作时验证）
    equipment_instance = None
    if not is_unbind:
        # 若设备已发起“待收货退库”，则禁止继续绑定检查项，避免出现仓库不感知的账实错乱
        try:
            from app.models.equipment import StockTransaction, TransactionTypeEnum

            pending_return = db.query(StockTransaction).filter(
                StockTransaction.transaction_type == TransactionTypeEnum.RETURN,
                StockTransaction.approval_status == "pending_receive",
                StockTransaction.scan_barcode == equipment_sn,
            ).first()
            if pending_return:
                raise HTTPException(
                    status_code=400,
                    detail="设备已发起退库申请（待仓库收货），无法继续绑定检查项；请等待仓库收货完成或取消退库申请后再绑定",
                )
        except HTTPException:
            raise
        except Exception:
            # 兼容老库/字段缺失等场景：不阻断绑定
            pass

        from app.models.equipment import EquipmentInstance, InventoryStatusEnum
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == equipment_sn
        ).first()
        if not equipment_instance:
            raise HTTPException(status_code=404, detail=f"设备序列号 {equipment_sn} 不存在")

        allowed_status = {
            InventoryStatusEnum.ISSUED,
            InventoryStatusEnum.PENDING_INSPECTION,
            InventoryStatusEnum.INSPECTED,
        }
        if equipment_instance.status not in allowed_status:
            raise HTTPException(status_code=400, detail="设备未出库，无法进行检查")

        if equipment_instance.issued_to != current_user.id:
            raise HTTPException(status_code=403, detail="设备未被当前用户领料，无法绑定")
    
    # 构造cell_id
    cell_id = f"{sector_id}_{band}" if band else sector_id
    
    # 查找该小区的检查项
    check_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.sector_id == sector_id
    )
    
    if band:
        check_items = check_items.filter(InspectionCheckItem.band == band)
    
    check_items = check_items.all()
    
    if not check_items:
        raise HTTPException(
            status_code=404,
            detail=f"未找到扇区 {sector_id} 的检查项"
        )

    # 仅在绑定操作时检查是否已有其他设备绑定到该小区
    if not is_unbind:
        slot_sns = []
        for it in check_items:
            sn0 = (getattr(it, "equipment_sn", None) or "").strip()
            if sn0:
                slot_sns.append(sn0)
        slot_unique = [s for s in dict.fromkeys(slot_sns) if s]

        if len(slot_unique) > 1:
            raise HTTPException(status_code=409, detail="该设备位存在多个已绑定SN，无法绑定/更换，请联系管理员处理")

        slot_current_sn = slot_unique[0] if slot_unique else None

        # 非设备更换工单：仍要求先解绑再绑定，避免误操作覆盖
        if slot_current_sn and slot_current_sn != str(equipment_sn).strip() and not is_replacement_wo:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"设备（扇区 {sector_id}"
                    f"{'，频段 ' + str(band) if band else ''}）已绑定其他设备: {slot_current_sn}"
                    "；如需更换，请先解绑该设备位后再绑定"
                ),
            )

        # 阻止同一设备SN被绑定到其他设备位：以绑定历史“最新动作”判定当前是否仍绑定
        try:
            from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
            from sqlalchemy.orm import joinedload

            eq_sn = (equipment_sn or "").strip()
            if eq_sn:
                latest = (
                    db.query(EquipmentBindingHistory)
                    .options(
                        joinedload(EquipmentBindingHistory.site),
                        joinedload(EquipmentBindingHistory.operator),
                    )
                    .filter(EquipmentBindingHistory.equipment_sn == eq_sn)
                    .order_by(EquipmentBindingHistory.operated_at.desc(), EquipmentBindingHistory.id.desc())
                    .first()
                )

                if latest and latest.action != BindingActionEnum.UNBIND:
                    same_slot = (
                        int(getattr(latest, "site_id", 0) or 0) == int(getattr(inspection, "site_id", 0) or 0)
                        and str(getattr(latest, "sector_id", "") or "") == str(sector_id or "")
                        and str(getattr(latest, "band", "") or "") == str(band or "")
                        and str(getattr(latest, "cell_id", "") or "") == str(cell_id or "")
                    )
                    if not same_slot:
                        site_name = getattr(getattr(latest, "site", None), "site_name", None) or "未知站点"
                        site_id = getattr(latest, "site_id", None) or "N/A"
                        conflict_cell = getattr(latest, "sector_id", None) or "-"
                        conflict_band = getattr(latest, "band", None) or "-"
                        conflict_cell_str = getattr(latest, "cell_id", None) or f"{conflict_cell}_{conflict_band}"
                        binder = getattr(latest, "operator", None)
                        binder_name = (
                            (binder.full_name or binder.username) if binder else "未知用户"
                        )

                        detail_msg = (
                            f"设备 {eq_sn} 已被使用，无法绑定！\n"
                            f"已绑定站点：{site_name} (ID: {site_id})\n"
                            f"已绑定设备位：{conflict_cell_str}\n"
                            f"绑定操作人：{binder_name}\n"
                            f"请先解绑该设备后再进行绑定操作"
                        )
                        raise HTTPException(status_code=409, detail=detail_msg)
        except HTTPException:
            raise
        except Exception:
            # 兼容：历史表缺失/异常时回退为原逻辑（保守阻断）
            from sqlalchemy.orm import joinedload

            conflict = db.query(InspectionCheckItem).options(
                joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.site),
                joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.inspector)
            ).filter(
                InspectionCheckItem.equipment_sn == equipment_sn,
                or_(
                    InspectionCheckItem.sector_id != sector_id,
                    func.coalesce(InspectionCheckItem.band, "") != func.coalesce(band, "")
                )
            ).first()

            if conflict:
                conflict_cell = conflict.sector_id
                conflict_band = getattr(conflict, 'band', None)
                conflict_cell_str = f"{conflict_cell}_{conflict_band}" if conflict_band else f"{conflict_cell}"

                conflict_inspection = conflict.inspection
                site_name = conflict_inspection.site.site_name if conflict_inspection and conflict_inspection.site else "未知站点"
                site_id = conflict_inspection.site_id if conflict_inspection else "N/A"

                binder_id = conflict.checked_by if conflict.checked_by else (conflict_inspection.inspector_id if conflict_inspection else None)
                binder_name = "未知用户"
                if binder_id:
                    binder = db.query(User).filter(User.id == binder_id).first()
                    if binder:
                        binder_name = binder.full_name or binder.username

                detail_msg = (
                    f"设备 {equipment_sn} 已被使用，无法绑定！\n"
                    f"已绑定站点：{site_name} (ID: {site_id})\n"
                    f"已绑定小区：{conflict_cell_str}\n"
                    f"绑定操作人：{binder_name}\n"
                    f"请先解绑该设备后再进行绑定操作"
                )
                raise HTTPException(status_code=409, detail=detail_msg)
    
    # 绑定或解绑设备到所有相关检查项
    try:
        # 导入历史记录模型
        from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum

        now = datetime.utcnow()

        # 设备更换：写入旧设备 UNBIND 记录（一次即可），确保“当前绑定推导/退库判定”不被历史 SN 卡死
        old_slot_sn = None
        if is_replacement_wo and not is_unbind:
            sns = []
            for it in check_items:
                sn0 = (getattr(it, "equipment_sn", None) or "").strip()
                if sn0:
                    sns.append(sn0)
            unique = [s for s in dict.fromkeys(sns) if s]
            if len(unique) == 1:
                old_slot_sn = unique[0]
            elif len(unique) > 1:
                raise HTTPException(status_code=409, detail="该设备位存在多个已绑定SN，无法更换，请联系管理员处理")

            new_sn_norm = (equipment_sn or "").strip()
            if old_slot_sn and new_sn_norm and old_slot_sn != new_sn_norm:
                # 绑定历史记录：旧 SN -> UNBIND
                first_item = check_items[0]
                db.add(
                    EquipmentBindingHistory(
                        inspection_id=inspection_id,
                        check_item_id=first_item.id,
                        site_id=inspection.site_id,
                        sector_id=sector_id,
                        band=band or "",
                        cell_id=first_item.cell_id or cell_id,
                        equipment_sn=old_slot_sn,
                        action=BindingActionEnum.UNBIND,
                        operator_id=current_user.id,
                        previous_equipment_sn=None,
                        latitude=request_data.get("latitude"),
                        longitude=request_data.get("longitude"),
                        gps_accuracy=request_data.get("gps_accuracy"),
                        notes="设备更换：解绑旧设备",
                    )
                )

                # 旧设备归属交接：issued_to -> 执行人（不自动退库）
                try:
                    from app.models.equipment import EquipmentInstance, InventoryStatusEnum
                    from app.models.work_order import AuditEvent

                    old_inst = db.query(EquipmentInstance).filter(EquipmentInstance.serial_number == old_slot_sn).first()
                    if old_inst:
                        old_issued_to = getattr(old_inst, "issued_to", None)
                        old_status = getattr(old_inst, "status", None)
                        old_inst.issued_to = current_user.id
                        old_inst.status = InventoryStatusEnum.ISSUED
                        old_inst.updated_at = now

                        # 设备审计：归属交接
                        db.add(
                            AuditEvent(
                                id=str(uuid.uuid4()),
                                resource_type="equipment_instance",
                                resource_id=str(old_inst.id),
                                action="handover_issued_to",
                                operator_id=current_user.id,
                                from_status=str(getattr(old_status, "value", old_status)),
                                to_status=str(InventoryStatusEnum.ISSUED.value),
                                comments="设备更换工单自动交接（仅变更领料人归属，不自动退库）",
                                details={
                                    "reason": "equipment_replacement",
                                    "work_order_id": getattr(wo, "id", None),
                                    "site_id": getattr(inspection, "site_id", None),
                                    "sector_id": sector_id,
                                    "band": band or "",
                                    "old_sn": old_slot_sn,
                                    "new_sn": new_sn_norm,
                                    "from_issued_to": old_issued_to,
                                    "to_issued_to": current_user.id,
                                },
                            )
                        )
                except Exception:
                    # 审计/交接失败不阻断主流程
                    pass

                # 写入工单 replacement_history（用于前端追溯）
                try:
                    if wo:
                        extra = wo.extra_data or {}
                        hist = extra.get("replacement_history") or []
                        if not isinstance(hist, list):
                            hist = []
                        hist.append(
                            {
                                "sector_id": str(sector_id),
                                "band": str(band or ""),
                                "old_sn": old_slot_sn,
                                "new_sn": new_sn_norm,
                                "operator_id": current_user.id,
                                "replaced_at": now.isoformat() + "Z",
                            }
                        )
                        extra["replacement_history"] = hist
                        wo.extra_data = extra
                        wo.updated_at = now
                except Exception:
                    pass

        unbound_device_sns = set()
        for item in check_items:
            # 记录之前的设备SN（用于历史记录）
            previous_sn = item.equipment_sn
            previous_sn_norm = str(previous_sn or "").strip()

            # 更新设备绑定
            item.equipment_sn = equipment_sn if not is_unbind else None
            _touch_check_item_and_clear_review(item, now)

            # 创建历史记录
            if is_unbind:
                if previous_sn_norm and is_device_level_check_item(item):
                    unbound_device_sns.add(previous_sn_norm)
                if previous_sn:
                    db.add(
                        EquipmentBindingHistory(
                            inspection_id=inspection_id,
                            check_item_id=item.id,
                            site_id=inspection.site_id,
                            sector_id=sector_id,
                            band=band or "",
                            cell_id=item.cell_id or cell_id,
                            equipment_sn=previous_sn,
                            action=BindingActionEnum.UNBIND,
                            operator_id=current_user.id,
                            previous_equipment_sn=None,
                            latitude=request_data.get("latitude"),
                            longitude=request_data.get("longitude"),
                            gps_accuracy=request_data.get("gps_accuracy"),
                            notes=request_data.get("notes"),
                        )
                    )
            else:
                prev_norm = previous_sn_norm
                new_norm = (equipment_sn or "").strip()
                if prev_norm == new_norm:
                    continue
                db.add(
                    EquipmentBindingHistory(
                        inspection_id=inspection_id,
                        check_item_id=item.id,
                        site_id=inspection.site_id,
                        sector_id=sector_id,
                        band=band or "",
                        cell_id=item.cell_id or cell_id,
                        equipment_sn=new_norm,
                        action=BindingActionEnum.REBIND if prev_norm else BindingActionEnum.BIND,
                        operator_id=current_user.id,
                        previous_equipment_sn=prev_norm if prev_norm else None,
                        latitude=request_data.get("latitude"),
                        longitude=request_data.get("longitude"),
                        gps_accuracy=request_data.get("gps_accuracy"),
                        notes=request_data.get("notes"),
                    )
                )
        
        # 更新设备状态
        if not is_unbind and equipment_instance:
            # 绑定时，设备状态更新为"待检查"
            from app.models.equipment import InventoryStatusEnum
            equipment_instance.status = InventoryStatusEnum.PENDING_INSPECTION
            equipment_instance.updated_at = now
        reverted_equipment_count = 0
        if is_unbind and unbound_device_sns:
            reverted_equipment_count = rollback_equipment_status_after_unbind(
                db,
                sns=unbound_device_sns,
                now=now,
            )
        
        db.commit()
        
        if is_unbind:
            return {
                "success": True,
                "message": f"成功解绑扇区 {sector_id} 的设备",
                "action": "unbind",
                "sector_id": sector_id,
                "band": band,
                "cell_id": cell_id,
                "affected_items_count": len(check_items),
                "reverted_equipment_count": reverted_equipment_count,
            }
        else:
            return {
                "success": True,
                "message": f"成功绑定设备 {equipment_sn} 到扇区 {sector_id}，设备状态已更新为待检查",
                "action": "bind",
                "equipment_sn": equipment_sn,
                "sector_id": sector_id,
                "band": band,
                "cell_id": cell_id,
                "bound_items_count": len(check_items),
                "equipment_name": equipment_instance.equipment.equipment_name if equipment_instance and equipment_instance.equipment else "未知设备",
                "equipment_status": "pending_inspection"
            }
        
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "bind_equipment_to_sector integrity_error error_id=%s inspection_id=%s sn=%s sector_id=%s band=%s user_id=%s",
            error_id,
            inspection_id,
            equipment_sn,
            sector_id,
            band,
            getattr(current_user, "id", None),
        )
        raise HTTPException(
            status_code=409,
            detail=f"绑定发生冲突（可能是重复提交或并发操作），请刷新后重试（错误编号：{error_id}）",
        )
    except Exception:
        db.rollback()
        error_id = uuid.uuid4().hex[:8]
        logger.exception(
            "bind_equipment_to_sector failed error_id=%s inspection_id=%s sn=%s sector_id=%s band=%s user_id=%s",
            error_id,
            inspection_id,
            equipment_sn,
            sector_id,
            band,
            getattr(current_user, "id", None),
        )
        raise HTTPException(
            status_code=500,
            detail=f"系统异常，绑定失败，请稍后重试或联系管理员（错误编号：{error_id}）",
        )


@router.get("/binding-history/{check_item_id}")
async def get_binding_history(
    check_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取检查项的设备绑定历史记录
    
    Args:
        check_item_id: 检查项ID
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        设备绑定历史记录列表
    """
    from app.models.equipment_binding_history import EquipmentBindingHistory
    from sqlalchemy.orm import joinedload
    
    # 验证检查项存在且有权限查看
    check_item = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.inspection)
    ).filter(InspectionCheckItem.id == check_item_id).first()
    
    if not check_item:
        raise HTTPException(
            status_code=404,
            detail="检查项不存在"
        )
    
    # 权限检查
    inspection = check_item.inspection
    if _is_field_worker(current_user) and inspection.inspector_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="没有权限查看此检查项的历史记录"
        )
    _ensure_surveyor_inspection_type(db, current_user, inspection)
    
    # 查询历史记录
    history_records = db.query(EquipmentBindingHistory).options(
        joinedload(EquipmentBindingHistory.operator)
    ).filter(
        EquipmentBindingHistory.check_item_id == check_item_id
    ).order_by(
        EquipmentBindingHistory.operated_at.desc()
    ).all()
    
    # 格式化返回数据
    from app.utils.timezone import to_utc_iso

    result = []
    for record in history_records:
        result.append({
            "id": record.id,
            "action": record.action.value,
            "equipment_sn": record.equipment_sn,
            "previous_equipment_sn": record.previous_equipment_sn,
            "operator": {
                "id": record.operator.id,
                "name": record.operator.full_name or record.operator.username
            },
            # operated_at 由数据库 CURRENT_TIMESTAMP 写入，视为 UTC
            "operated_at": to_utc_iso(record.operated_at) if record.operated_at else None,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "gps_accuracy": record.gps_accuracy,
            "notes": record.notes,
            "cell_info": {
                "sector_id": record.sector_id,
                "band": record.band,
                "cell_id": record.cell_id
            }
        })
    
    return {
        "check_item_id": check_item_id,
        "check_item_name": check_item.item_name,
        "history": result
    }


@router.get("/equipment-history/{equipment_sn}")
async def get_equipment_binding_history(
    equipment_sn: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取设备的完整绑定历史记录（用于设备追踪）
    
    Args:
        equipment_sn: 设备序列号
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        设备的完整绑定历史
    """
    from app.models.equipment_binding_history import EquipmentBindingHistory
    from sqlalchemy.orm import joinedload
    
    # 查询该设备的所有绑定历史
    history_records = db.query(EquipmentBindingHistory).options(
        joinedload(EquipmentBindingHistory.operator),
        joinedload(EquipmentBindingHistory.site),
        joinedload(EquipmentBindingHistory.inspection)
    ).filter(
        EquipmentBindingHistory.equipment_sn == equipment_sn
    ).order_by(
        EquipmentBindingHistory.operated_at.desc()
    ).all()
    
    if not history_records:
        return {
            "equipment_sn": equipment_sn,
            "history": [],
            "message": "该设备尚无绑定历史记录"
        }
    
    # 格式化返回数据
    from app.utils.timezone import to_utc_iso

    result = []
    for record in history_records:
        result.append({
            "id": record.id,
            "action": record.action.value,
            "site": {
                "id": record.site_id,
                "name": record.site.site_name if record.site else "未知站点"
            },
            "cell_info": {
                "sector_id": record.sector_id,
                "band": record.band,
                "cell_id": record.cell_id
            },
            "operator": {
                "id": record.operator.id,
                "name": record.operator.full_name or record.operator.username
            },
            # operated_at 由数据库 CURRENT_TIMESTAMP 写入，视为 UTC
            "operated_at": to_utc_iso(record.operated_at) if record.operated_at else None,
            "previous_equipment_sn": record.previous_equipment_sn,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "gps_accuracy": record.gps_accuracy,
            "notes": record.notes,
            "inspection_id": record.inspection_id
        })

    # 追加 OMC 首次上线/激活事件（若存在）
    try:
        from app.models.omc_state import OmcDeviceState
        state = db.query(OmcDeviceState).filter(OmcDeviceState.sn == equipment_sn).first()
        if state:
            if state.first_online_at:
                result.append({
                    "id": f"omc-first-online-{equipment_sn}",
                    "action": "omc_first_online",
                    "site": None,
                    "cell_info": {},
                    "operator": {"id": None, "name": "系统(OMC)"},
                    # OMC 时间在写入时使用 utcnow，直接视为 UTC
                    "operated_at": to_utc_iso(state.first_online_at),
                    "previous_equipment_sn": None,
                    "latitude": None,
                    "longitude": None,
                    "gps_accuracy": None,
                    "notes": "OMC 记录的首次上线时间",
                    "inspection_id": None
                })
            if state.first_activated_at:
                result.append({
                    "id": f"omc-first-activated-{equipment_sn}",
                    "action": "omc_first_activated",
                    "site": None,
                    "cell_info": {},
                    "operator": {"id": None, "name": "系统(OMC)"},
                    "operated_at": to_utc_iso(state.first_activated_at),
                    "previous_equipment_sn": None,
                    "latitude": None,
                    "longitude": None,
                    "gps_accuracy": None,
                    "notes": "OMC 记录的首次激活时间",
                    "inspection_id": None
                })
        # 按时间倒序排序，确保时间线顺序正确
        result.sort(key=lambda x: x.get("operated_at") or "", reverse=True)
    except Exception as exc:  # pragma: no cover
        print(f"[WARN] 附加 OMC 生命周期事件失败: {exc}")
    
    return {
        "equipment_sn": equipment_sn,
        "total_records": len(result),
        "history": result
    }


# === 统计汇总 ===
from sqlalchemy import func
from app.models.inspection import SiteInspection, InspectionStatusEnum


@router.get("/stats/summary", response_model=InspectionStatistics)
async def get_inspection_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查记录统计（管理员/经理）"""
    _ensure_stats_access(current_user)

    total = db.query(func.count(SiteInspection.id)).scalar() or 0

    completed = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.COMPLETED
    ).scalar() or 0

    approved = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.APPROVED
    ).scalar() or 0

    rejected = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.REJECTED
    ).scalar() or 0

    pending = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.DRAFT,
            InspectionStatusEnum.IN_PROGRESS,
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW
        ])
    ).scalar() or 0

    avg_score = db.query(func.avg(SiteInspection.score)).scalar()
    avg_score = float(avg_score) if avg_score is not None else None

    avg_completion_rate = db.query(func.avg(SiteInspection.completion_rate)).scalar() or 0.0

    return InspectionStatistics(
        total_inspections=int(total),
        completed_inspections=int(completed),
        pending_inspections=int(pending),
        approved_inspections=int(approved),
        rejected_inspections=int(rejected),
        average_score=avg_score,
        completion_rate=float(avg_completion_rate or 0.0)
    )
