from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.inspection import (
    CheckItemStatusEnum,
    InspectionCheckItem,
    InspectionPhoto,
    InspectionStatusEnum,
    InspectionTemplate,
    SiteInspection,
)
from app.models.work_order import WorkOrder, WorkOrderTypeEnum
from app.schemas.inspection_enhanced import FieldDefinition
from app.services.cell_generator import CellGenerator
from app.utils.field_validator import FieldValidator


EDITABLE_TEMPLATE_SYNC_STATUSES = {
    InspectionStatusEnum.DRAFT,
    InspectionStatusEnum.IN_PROGRESS,
    InspectionStatusEnum.REJECTED,
}
PENDING_TEMPLATE_SYNC_STATUSES = {
    InspectionStatusEnum.SUBMITTED,
    InspectionStatusEnum.UNDER_REVIEW,
}
FROZEN_TEMPLATE_SYNC_STATUSES = {
    InspectionStatusEnum.APPROVED,
    InspectionStatusEnum.COMPLETED,
    InspectionStatusEnum.VOIDED,
}


@dataclass
class InspectionGenerationContext:
    devices: List[Any]
    sectors: List[str]
    carrier_cells: List[Any]
    equipment_sn_map: Dict[Tuple[str, str], str]


def _enum_value(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _truthy(value: Any) -> bool:
    if value is True:
        return True
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "y")
    return False


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return len(value) == 0
    return False


def _coerce_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except Exception:
        return None


def _eval_dependency_condition(value: Any, condition: Optional[dict]) -> bool:
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
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
        return a is not None and b is not None and a > b
    if operator in (">=", "greater_or_equal"):
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
        return a is not None and b is not None and a >= b
    if operator in ("<", "less_than"):
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
        return a is not None and b is not None and a < b
    if operator in ("<=", "less_or_equal"):
        a = _coerce_float(value)
        b = _coerce_float(cond_value)
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
    return False


def is_template_field_active(field: Optional[dict]) -> bool:
    if not isinstance(field, dict):
        return False
    return not bool(field.get("hidden")) and not bool(field.get("removed_by_template"))


def is_field_visible(field: Optional[dict], field_values: dict) -> bool:
    if not is_template_field_active(field):
        return False

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
            condition_met = _eval_dependency_condition(
                source_value,
                dep.get("condition") if isinstance(dep.get("condition"), dict) else None,
            )
            if condition_met:
                effect = dep.get("effect") if isinstance(dep.get("effect"), dict) else {}
                visible = effect.get("visible", True)
                hidden = not bool(visible)
            else:
                hidden = False
    return not hidden


def build_field_values_from_data_value(data_value: Any) -> dict:
    values = {}
    if isinstance(data_value, dict):
        for key, value in data_value.items():
            values[str(key)] = value
        return values
    if not isinstance(data_value, list):
        return values
    for raw in data_value:
        current = raw.dict() if hasattr(raw, "dict") else (raw or {})
        if not isinstance(current, dict):
            continue
        raw_name = (
            current.get("field_name")
            or current.get("field_id")
            or current.get("key")
            or current.get("field")
            or current.get("name")
        )
        if not raw_name:
            continue
        values[str(raw_name)] = current.get("value")
    return values


def extract_photo_field_rules(fields: Any) -> tuple[set, set, dict, dict]:
    allowed: set = set()
    required: set = set()
    labels: dict = {}
    by_id: dict = {}
    if not isinstance(fields, list):
        return allowed, required, labels, by_id
    for raw in fields:
        if not isinstance(raw, dict) or not is_template_field_active(raw):
            continue
        field_id = str(raw.get("field_id") or "").strip()
        if not field_id:
            continue
        by_id[field_id] = raw
        labels[field_id] = str(raw.get("label") or field_id)
        if _truthy(raw.get("allow_photo")):
            allowed.add(field_id)
            if _truthy(raw.get("photo_required")):
                required.add(field_id)
    return allowed, required, labels, by_id


def normalize_category_level(category: dict) -> str:
    level_type = (category or {}).get("level_type")
    if level_type == "cell":
        return "device"
    if level_type in ("site", "sector", "device", "cell_earfcn"):
        return level_type
    if (category or {}).get("cell_specific"):
        return "device"
    if (category or {}).get("sector_specific"):
        return "sector"
    return "site"


def template_requires_lld_cells(template_data: dict) -> bool:
    for category in (template_data or {}).get("check_categories", []) or []:
        if normalize_category_level(category) == "cell_earfcn":
            return True
    return False


def strip_generated_item_suffix(item_id: str) -> str:
    current = str(item_id or "").strip()
    if not current:
        return current
    for marker in ("_sector_", "_cell_"):
        if marker in current:
            return current.split(marker, 1)[0]
    return current


def get_template_revision(template: Optional[InspectionTemplate]) -> int:
    if template is None:
        return 1
    try:
        return max(1, int(getattr(template, "revision", 1) or 1))
    except Exception:
        return 1


def get_applied_template_revision(inspection: Optional[SiteInspection]) -> int:
    if inspection is None:
        return 1
    try:
        return max(1, int(getattr(inspection, "applied_template_revision", 1) or 1))
    except Exception:
        return 1


def _clear_check_item_review(check_item: InspectionCheckItem) -> None:
    check_item.review_status = None
    check_item.review_comments = None
    check_item.review_comments_i18n = None
    check_item.reviewed_by = None
    check_item.reviewed_at = None


def _build_runtime_key(
    *,
    template_item_id: str,
    category_id: Optional[str],
    sector_id: Optional[str],
    band: Optional[str],
    cell_id: Optional[str],
) -> tuple[str, str, str, str, str]:
    return (
        str(template_item_id or "").strip(),
        str(category_id or "").strip(),
        str(sector_id or "").strip(),
        str(band or "").strip(),
        str(cell_id or "").strip(),
    )


def _build_runtime_key_from_check_item(check_item: InspectionCheckItem) -> tuple[str, str, str, str, str]:
    return _build_runtime_key(
        template_item_id=getattr(check_item, "template_item_id", None) or strip_generated_item_suffix(check_item.item_id),
        category_id=check_item.category_id,
        sector_id=check_item.sector_id,
        band=check_item.band,
        cell_id=check_item.cell_id,
    )


def _copy_template_fields(fields: Any) -> List[dict]:
    if not isinstance(fields, list):
        return []
    copied = []
    for current in fields:
        if isinstance(current, dict):
            copied.append(copy.deepcopy(current))
    return copied


def _merge_template_fields(existing_fields: Any, template_fields: Any, now: datetime) -> tuple[List[dict], bool]:
    template_fields_list = _copy_template_fields(template_fields)
    existing_fields_list = [copy.deepcopy(field) for field in (existing_fields or []) if isinstance(field, dict)]
    existing_by_id = {}
    removed_fields = []
    for current in existing_fields_list:
        field_id = str(current.get("field_id") or "").strip()
        if not field_id:
            continue
        if current.get("removed_by_template") or current.get("hidden"):
            removed_fields.append(current)
            continue
        existing_by_id[field_id] = current

    merged: List[dict] = []
    changed = False

    for template_field in template_fields_list:
        field_id = str(template_field.get("field_id") or "").strip()
        if not field_id:
            continue
        previous = existing_by_id.pop(field_id, None)
        normalized = copy.deepcopy(template_field)
        normalized.pop("removed_at", None)
        normalized.pop("removed_by_template", None)
        normalized.pop("hidden", None)
        normalized.pop("legacy", None)
        merged.append(normalized)
        if previous != normalized:
            changed = True

    for field_id, previous in existing_by_id.items():
        hidden_field = copy.deepcopy(previous)
        hidden_field["hidden"] = True
        hidden_field["legacy"] = True
        hidden_field["removed_by_template"] = True
        hidden_field["removed_at"] = now.isoformat()
        hidden_field["required"] = False
        hidden_field["allow_photo"] = False
        hidden_field["photo_required"] = False
        merged.append(hidden_field)
        changed = True

    for previous in removed_fields:
        merged.append(previous)

    return merged, changed


def prepare_generation_context(
    db: Session,
    inspection: SiteInspection,
    template_data: Optional[dict],
) -> InspectionGenerationContext:
    devices = CellGenerator.generate_devices_from_planning(db, inspection.site_id)
    carrier_cells: List[Any] = []
    if template_requires_lld_cells(template_data or {}):
        carrier_cells = CellGenerator.generate_cells_from_lld(db, inspection.site_id)
        if not carrier_cells:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"模板包含“小区级（按EARFCN）”检查项，但站点 {inspection.site_id} 尚未导入 LLD 规划数据",
            )

    equipment_sn_map: Dict[Tuple[str, str], str] = {}
    work_order = None
    if inspection.work_order_id:
        work_order = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()

    if work_order and work_order.type == WorkOrderTypeEnum.EQUIPMENT_REPLACEMENT:
        extra_data = work_order.extra_data or {}
        raw_targets = extra_data.get("replacement_targets") or []
        target_slots = set()
        for target in raw_targets:
            if not isinstance(target, dict):
                continue
            sector_id = str(target.get("sector_id") or "").strip()
            band = str(target.get("band") or "").strip()
            if sector_id and band:
                target_slots.add((sector_id, band))
        if not target_slots:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="设备更换工单缺少 replacement_targets，无法同步检查模板",
            )

        devices = [device for device in devices if (str(device.sector_id), str(device.band)) in target_slots]
        carrier_cells = [
            cell for cell in carrier_cells if (str(cell.sector_id), str(cell.band)) in target_slots
        ]

        for current in extra_data.get("replacement_old_devices") or []:
            if not isinstance(current, dict):
                continue
            sector_id = str(current.get("sector_id") or "").strip()
            band = str(current.get("band") or "").strip()
            old_sn = str(current.get("old_sn") or "").strip()
            if sector_id and band and old_sn:
                equipment_sn_map[(sector_id, band)] = old_sn

    sectors = sorted({str(device.sector_id) for device in devices if getattr(device, "sector_id", None) not in (None, "")})
    return InspectionGenerationContext(
        devices=devices,
        sectors=sectors,
        carrier_cells=carrier_cells,
        equipment_sn_map=equipment_sn_map,
    )


def iter_template_check_item_specs(
    template_data: Optional[dict],
    context: InspectionGenerationContext,
) -> List[dict]:
    specs: List[dict] = []
    for category in (template_data or {}).get("check_categories", []) or []:
        if not isinstance(category, dict):
            continue
        category_id = str(category.get("category_id") or "unknown")
        category_name = category.get("category_name", "未知分类")
        level_type = normalize_category_level(category)
        for item in category.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            template_item_id = str(item.get("item_id") or "unknown")
            base_spec = {
                "template_item_id": template_item_id,
                "item_name": item.get("item_name", "未知检查项"),
                "description": item.get("description"),
                "category_id": category_id,
                "category_name": category_name,
                "required_type": item.get("required_type", "photo"),
                "fields": _copy_template_fields(item.get("fields") or []),
            }

            if level_type == "cell_earfcn":
                for cell in context.carrier_cells:
                    specs.append(
                        {
                            **base_spec,
                            "item_id": f"{template_item_id}_cell_{cell.cell_id}",
                            "item_name": f"{base_spec['item_name']} - 小区 {cell.cell_id}",
                            "sector_id": str(cell.sector_id),
                            "band": str(cell.band),
                            "cell_id": str(cell.cell_id),
                            "equipment_sn": None,
                        }
                    )
            elif level_type == "device":
                for device in context.devices:
                    sector_id = str(device.sector_id)
                    band = str(device.band)
                    cell_id = str(device.cell_id)
                    specs.append(
                        {
                            **base_spec,
                            "item_id": f"{template_item_id}_cell_{cell_id}",
                            "item_name": f"{base_spec['item_name']} - 设备 {cell_id}",
                            "sector_id": sector_id,
                            "band": band,
                            "cell_id": cell_id,
                            "equipment_sn": context.equipment_sn_map.get((sector_id, band)),
                        }
                    )
            elif level_type == "sector":
                for sector_id in context.sectors:
                    specs.append(
                        {
                            **base_spec,
                            "item_id": f"{template_item_id}_sector_{sector_id}",
                            "item_name": f"{base_spec['item_name']} - 扇区 {sector_id}",
                            "sector_id": sector_id,
                            "band": None,
                            "cell_id": None,
                            "equipment_sn": None,
                        }
                    )
            else:
                specs.append(
                    {
                        **base_spec,
                        "item_id": template_item_id,
                        "sector_id": None,
                        "band": None,
                        "cell_id": None,
                        "equipment_sn": None,
                    }
                )
    return specs


def create_check_items_from_template(
    db: Session,
    inspection: SiteInspection,
    template_data: Optional[dict],
) -> int:
    context = prepare_generation_context(db, inspection, template_data)
    total_items = 0
    for spec in iter_template_check_item_specs(template_data, context):
        check_item = InspectionCheckItem(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            item_id=spec["item_id"],
            template_item_id=spec["template_item_id"],
            item_name=spec["item_name"],
            description=spec["description"],
            category_id=spec["category_id"],
            category_name=spec["category_name"],
            sector_id=spec["sector_id"],
            band=spec["band"],
            cell_id=spec["cell_id"],
            equipment_sn=spec["equipment_sn"],
            required_type=spec["required_type"],
            fields=spec["fields"],
            status=CheckItemStatusEnum.PENDING,
            is_active=True,
            removed_by_template=False,
        )
        db.add(check_item)
        total_items += 1
    inspection.total_items = total_items
    inspection.completed_items = 0
    inspection.failed_items = 0
    inspection.completion_rate = 0
    return total_items


def recalculate_inspection_stats(db: Session, inspection: SiteInspection) -> None:
    active_items = (
        db.query(InspectionCheckItem)
        .filter(
            InspectionCheckItem.inspection_id == inspection.id,
            InspectionCheckItem.is_active.is_(True),
        )
        .all()
    )
    total_items = len(active_items)
    completed_items = sum(1 for item in active_items if item.status == CheckItemStatusEnum.COMPLETED)
    failed_items = sum(1 for item in active_items if item.status == CheckItemStatusEnum.FAILED)
    inspection.total_items = total_items
    inspection.completed_items = completed_items
    inspection.failed_items = failed_items
    inspection.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0


def collect_check_item_submit_errors(
    db: Session,
    inspection_id: str,
    check_item: InspectionCheckItem,
) -> List[str]:
    if not bool(getattr(check_item, "is_active", True)):
        return []

    errors: List[str] = []
    if check_item.status != CheckItemStatusEnum.COMPLETED:
        errors.append("检查项未完成")
        return errors

    values = build_field_values_from_data_value(getattr(check_item, "data_value", None))

    if str(check_item.required_type) in ("data", "both"):
        has_any_value = any(not _is_empty_value(value) for value in values.values())
        if not has_any_value:
            errors.append("需要填写至少 1 个字段数据")
        else:
            field_errors = []
            label_map = {}
            visible_field_ids = []
            if isinstance(check_item.fields, list):
                for raw in check_item.fields:
                    if not isinstance(raw, dict) or not is_template_field_active(raw):
                        continue
                    field_id = str(raw.get("field_id") or "").strip()
                    if not field_id:
                        continue
                    label_map[field_id] = str(raw.get("label") or field_id)
                    if not is_field_visible(raw, values):
                        continue
                    visible_field_ids.append(field_id)
                    try:
                        field_definition = FieldDefinition(**raw)
                    except Exception:
                        continue
                    ok, message = FieldValidator.validate_field_value(
                        field_definition,
                        values.get(field_definition.field_id),
                        strict=True,
                    )
                    if not ok:
                        field_errors.append(f"{label_map.get(field_id, field_id)}: {message}")
            if visible_field_ids:
                has_any_visible_value = any(
                    (field_id in values) and (not _is_empty_value(values.get(field_id)))
                    for field_id in visible_field_ids
                )
                if not has_any_visible_value:
                    field_errors.append("可见字段至少需要填写 1 项")
            if field_errors:
                errors.append("字段校验失败: " + "；".join(field_errors))

    if str(check_item.required_type) in ("photo", "both"):
        photos = (
            db.query(InspectionPhoto)
            .filter(
                InspectionPhoto.inspection_id == inspection_id,
                InspectionPhoto.check_item_id == check_item.id,
            )
            .all()
        )
        if str(check_item.required_type) == "photo":
            if len(photos) <= 0:
                errors.append("至少需要上传 1 张照片")
        else:
            allowed_field_ids, required_field_ids, field_labels, field_by_id = extract_photo_field_rules(check_item.fields)
            counts = {}
            for photo in photos:
                field_id = str(getattr(photo, "field_id", None) or "").strip()
                if not field_id:
                    continue
                counts[field_id] = counts.get(field_id, 0) + 1

            visible_required = set()
            for field_id in required_field_ids:
                if is_field_visible(field_by_id.get(field_id) or {}, values):
                    visible_required.add(field_id)

            if visible_required:
                missing = [field_id for field_id in sorted(visible_required) if counts.get(field_id, 0) <= 0]
                if missing:
                    errors.append(
                        "缺少必拍字段照片: " + ", ".join(field_labels.get(field_id, field_id) for field_id in missing)
                    )
            elif allowed_field_ids:
                linked_total = sum(counts.get(field_id, 0) for field_id in allowed_field_ids)
                if linked_total <= 0:
                    errors.append("至少需要上传 1 张字段照片")
            elif len(photos) <= 0:
                errors.append("至少需要上传 1 张照片")

    return errors


def validate_inspection_for_submit(db: Session, inspection: SiteInspection) -> None:
    active_items = (
        db.query(InspectionCheckItem)
        .filter(
            InspectionCheckItem.inspection_id == inspection.id,
            InspectionCheckItem.is_active.is_(True),
        )
        .all()
    )
    if not active_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="当前检查没有有效检查项，无法提交",
        )

    violations = []
    for check_item in active_items:
        errors = collect_check_item_submit_errors(db, inspection.id, check_item)
        if not errors:
            continue
        violations.append(
            {
                "check_item_id": check_item.id,
                "item_name": check_item.item_name,
                "errors": errors,
            }
        )

    if violations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "inspection_submit_validation_failed",
                "message": "仍有检查项未完成或不符合最新模板要求，请先补充后再提交",
                "violations": violations,
            },
        )

    recalculate_inspection_stats(db, inspection)


def _apply_spec_to_check_item(
    db: Session,
    inspection: SiteInspection,
    check_item: InspectionCheckItem,
    spec: dict,
    now: datetime,
) -> tuple[bool, bool]:
    changed = False
    reopened = False

    for field_name in (
        "item_id",
        "template_item_id",
        "item_name",
        "description",
        "category_id",
        "category_name",
        "sector_id",
        "band",
        "cell_id",
        "equipment_sn",
        "required_type",
    ):
        next_value = spec.get(field_name)
        if getattr(check_item, field_name) != next_value:
            setattr(check_item, field_name, next_value)
            changed = True

    merged_fields, fields_changed = _merge_template_fields(check_item.fields, spec.get("fields") or [], now)
    if fields_changed or merged_fields != (check_item.fields or []):
        check_item.fields = merged_fields
        changed = True

    if not bool(getattr(check_item, "is_active", True)):
        check_item.is_active = True
        changed = True
    if bool(getattr(check_item, "removed_by_template", False)):
        check_item.removed_by_template = False
        changed = True
    if getattr(check_item, "removed_at", None) is not None:
        check_item.removed_at = None
        changed = True

    if check_item.status == CheckItemStatusEnum.COMPLETED:
        errors = collect_check_item_submit_errors(db, inspection.id, check_item)
        if errors:
            check_item.status = CheckItemStatusEnum.IN_PROGRESS
            check_item.validation_result = {
                "valid": False,
                "source": "template_sync",
                "errors": errors,
            }
            _clear_check_item_review(check_item)
            changed = True
            reopened = True
    if changed:
        check_item.updated_at = now
    return changed, reopened


def sync_inspection_with_template(
    db: Session,
    inspection: SiteInspection,
    template: Optional[InspectionTemplate] = None,
    *,
    force: bool = False,
) -> dict:
    template = template or db.query(InspectionTemplate).filter(InspectionTemplate.id == inspection.template_id).first()
    if template is None:
        return {
            "applied": False,
            "inspection_id": inspection.id,
            "reason": "template_missing",
        }

    current_revision = get_template_revision(template)
    applied_revision = get_applied_template_revision(inspection)
    if not force and current_revision <= applied_revision:
        return {
            "applied": False,
            "inspection_id": inspection.id,
            "template_revision": current_revision,
            "applied_template_revision": applied_revision,
            "reason": "up_to_date",
        }

    now = datetime.utcnow()
    context = prepare_generation_context(db, inspection, template.template_data or {})
    desired_specs = iter_template_check_item_specs(template.template_data or {}, context)
    desired_map = {
        _build_runtime_key(
            template_item_id=spec["template_item_id"],
            category_id=spec["category_id"],
            sector_id=spec.get("sector_id"),
            band=spec.get("band"),
            cell_id=spec.get("cell_id"),
        ): spec
        for spec in desired_specs
    }

    existing_items = (
        db.query(InspectionCheckItem)
        .filter(InspectionCheckItem.inspection_id == inspection.id)
        .all()
    )
    existing_map: Dict[tuple[str, str, str, str, str], InspectionCheckItem] = {}
    duplicate_items: List[InspectionCheckItem] = []
    for check_item in existing_items:
        runtime_key = _build_runtime_key_from_check_item(check_item)
        if runtime_key in existing_map:
            duplicate_items.append(check_item)
            continue
        existing_map[runtime_key] = check_item

    created_items = 0
    updated_items = 0
    removed_items = 0
    reopened_items = 0

    for runtime_key, spec in desired_map.items():
        current_item = existing_map.pop(runtime_key, None)
        if current_item is None:
            db.add(
                InspectionCheckItem(
                    id=str(uuid.uuid4()),
                    inspection_id=inspection.id,
                    item_id=spec["item_id"],
                    template_item_id=spec["template_item_id"],
                    item_name=spec["item_name"],
                    description=spec["description"],
                    category_id=spec["category_id"],
                    category_name=spec["category_name"],
                    sector_id=spec.get("sector_id"),
                    band=spec.get("band"),
                    cell_id=spec.get("cell_id"),
                    equipment_sn=spec.get("equipment_sn"),
                    required_type=spec.get("required_type", "photo"),
                    fields=spec.get("fields") or [],
                    status=CheckItemStatusEnum.PENDING,
                    is_active=True,
                    removed_by_template=False,
                    created_at=now,
                    updated_at=now,
                )
            )
            created_items += 1
            continue

        changed, reopened = _apply_spec_to_check_item(db, inspection, current_item, spec, now)
        if changed:
            updated_items += 1
        if reopened:
            reopened_items += 1

    for check_item in list(existing_map.values()) + duplicate_items:
        if bool(getattr(check_item, "is_active", True)) or not bool(getattr(check_item, "removed_by_template", False)):
            check_item.is_active = False
            check_item.removed_by_template = True
            check_item.removed_at = now
            check_item.updated_at = now
            removed_items += 1

    inspection.applied_template_revision = current_revision
    inspection.updated_at = now
    recalculate_inspection_stats(db, inspection)

    return {
        "applied": True,
        "inspection_id": inspection.id,
        "template_revision": current_revision,
        "applied_template_revision": current_revision,
        "created_items": created_items,
        "updated_items": updated_items,
        "removed_items": removed_items,
        "reopened_items": reopened_items,
        "active_items": inspection.total_items,
    }


def apply_pending_template_if_editable(
    db: Session,
    inspection: SiteInspection,
    template: Optional[InspectionTemplate] = None,
) -> dict:
    template = template or getattr(inspection, "template", None)
    if template is None:
        template = db.query(InspectionTemplate).filter(InspectionTemplate.id == inspection.template_id).first()
    if template is None:
        return {
            "applied": False,
            "inspection_id": inspection.id,
            "reason": "template_missing",
        }

    current_revision = get_template_revision(template)
    applied_revision = get_applied_template_revision(inspection)
    if current_revision <= applied_revision:
        return {
            "applied": False,
            "inspection_id": inspection.id,
            "template_revision": current_revision,
            "applied_template_revision": applied_revision,
            "reason": "up_to_date",
        }

    if inspection.status not in EDITABLE_TEMPLATE_SYNC_STATUSES:
        return {
            "applied": False,
            "inspection_id": inspection.id,
            "template_revision": current_revision,
            "applied_template_revision": applied_revision,
            "reason": "not_editable",
        }

    return sync_inspection_with_template(db, inspection, template, force=True)


def build_template_sync_info(
    inspection: SiteInspection,
    template: Optional[InspectionTemplate] = None,
    sync_result: Optional[dict] = None,
) -> dict:
    current_revision = get_template_revision(template)
    applied_revision = get_applied_template_revision(inspection)
    has_pending_update = current_revision > applied_revision
    current_status = inspection.status
    apply_mode = None
    message = None

    if sync_result and sync_result.get("applied"):
        apply_mode = "applied_now"
        message = "检查模板已更新，当前工单已同步到最新检查项，请按最新模板补充后再提交。"
        has_pending_update = False
        applied_revision = current_revision
    elif has_pending_update and current_status in PENDING_TEMPLATE_SYNC_STATUSES:
        apply_mode = "next_submit"
        message = "检查模板已更新，本次状态保持不变；待下次重新提交时，将按最新模板校验。"
    elif has_pending_update and current_status in FROZEN_TEMPLATE_SYNC_STATUSES:
        apply_mode = "frozen"
        message = "该工单已冻结，后续模板更新不会影响当前记录。"

    return {
        "template_revision": current_revision,
        "applied_template_revision": applied_revision,
        "has_pending_update": has_pending_update,
        "editable_now": current_status in EDITABLE_TEMPLATE_SYNC_STATUSES,
        "frozen": current_status in FROZEN_TEMPLATE_SYNC_STATUSES,
        "apply_mode": apply_mode,
        "just_applied": bool(sync_result and sync_result.get("applied")),
        "message": message,
        "summary": sync_result if sync_result and sync_result.get("applied") else None,
    }


def attach_template_sync_metadata(
    db: Session,
    inspection: SiteInspection,
    *,
    template: Optional[InspectionTemplate] = None,
    sync_result: Optional[dict] = None,
) -> dict:
    template = template or getattr(inspection, "template", None)
    if template is None:
        template = db.query(InspectionTemplate).filter(InspectionTemplate.id == inspection.template_id).first()
    info = build_template_sync_info(inspection, template, sync_result=sync_result)
    setattr(inspection, "template_revision", info["template_revision"])
    setattr(inspection, "template_sync", info)
    inspection.applied_template_revision = info["applied_template_revision"]
    return info


def get_template_usage_counts(db: Session, template_id: str) -> dict:
    inspections = db.query(SiteInspection).filter(SiteInspection.template_id == template_id).all()
    immediate = 0
    pending = 0
    frozen = 0
    for inspection in inspections:
        if inspection.status in EDITABLE_TEMPLATE_SYNC_STATUSES:
            immediate += 1
        elif inspection.status in PENDING_TEMPLATE_SYNC_STATUSES:
            pending += 1
        else:
            frozen += 1
    return {
        "total": len(inspections),
        "immediate": immediate,
        "pending": pending,
        "frozen": frozen,
    }


def sync_template_to_editable_inspections(
    db: Session,
    template: InspectionTemplate,
) -> dict:
    inspections = db.query(SiteInspection).filter(SiteInspection.template_id == template.id).all()
    synced_inspections = 0
    pending_inspections = 0
    frozen_inspections = 0
    created_items = 0
    updated_items = 0
    removed_items = 0
    reopened_items = 0

    for inspection in inspections:
        if inspection.status in EDITABLE_TEMPLATE_SYNC_STATUSES:
            sync_result = sync_inspection_with_template(db, inspection, template, force=True)
            if sync_result.get("applied"):
                synced_inspections += 1
                created_items += int(sync_result.get("created_items") or 0)
                updated_items += int(sync_result.get("updated_items") or 0)
                removed_items += int(sync_result.get("removed_items") or 0)
                reopened_items += int(sync_result.get("reopened_items") or 0)
        elif inspection.status in PENDING_TEMPLATE_SYNC_STATUSES:
            pending_inspections += 1
        else:
            frozen_inspections += 1

    return {
        "synced_inspections": synced_inspections,
        "pending_inspections": pending_inspections,
        "frozen_inspections": frozen_inspections,
        "created_items": created_items,
        "updated_items": updated_items,
        "removed_items": removed_items,
        "reopened_items": reopened_items,
    }
