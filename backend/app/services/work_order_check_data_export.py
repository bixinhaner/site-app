"""工单导出：按检查模板整理检查数据（模板字段值、照片数）。

每个模板生成一张表：固定列（工单、站点、执行人、状态、结算）+ 动态列（模板中每个检查项的每个字段、照片数）。
列的顺序与模板中 分类 → 检查项 → 字段 的顺序一致；扇区/小区级检查项按实际展开的检查项分别成列。
不写死任何字段，因此“零星PO”等由用户自定义的模板（PO 名、工作量、金额……）可直接导出用于结算。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.inspection import InspectionCheckItem, InspectionPhoto, InspectionTemplate, SiteInspection
from app.services.inspection_template_sync import (
    build_field_values_from_data_value,
    is_template_field_active,
    normalize_category_level,
)
from app.utils.archive_pdf import localized_text, pick_localized_text

Label = Tuple[str, str, str]

FIXED_COLUMNS: Sequence[Tuple[str, Label]] = (
    ("id", ("工单ID", "Work Order ID", "ID Perintah Kerja")),
    ("title", ("工单标题", "Work Order Title", "Judul Perintah Kerja")),
    ("site_code", ("站点编码", "Site Code", "Kode Situs")),
    ("site_name", ("站点名称", "Site Name", "Nama Situs")),
    ("assignee_name", ("执行人", "Assignee", "Pelaksana")),
    ("status", ("当前状态", "Current Status", "Status Saat Ini")),
    ("completed_at", ("完成时间", "Completed At", "Waktu Selesai")),
    ("settlement_status", ("结算状态", "Settlement Status", "Status Penyelesaian")),
    ("settlement_batch_no", ("结算批次号", "Settlement Batch No.", "No. Batch Penyelesaian")),
)

PHOTO_COUNT_LABEL: Label = ("照片数", "Photos", "Jumlah Foto")
NO_TEMPLATE_LABEL: Label = ("未关联模板", "No Template", "Tanpa Template")
YES_NO: Tuple[Label, Label] = (("是", "Yes", "Ya"), ("否", "No", "Tidak"))


def _tr(label: Label, locale: str) -> str:
    return localized_text(label[0], locale, label[1], label[2])


def _template_order(template_data: Any) -> Tuple[Dict[str, Tuple[int, int]], Dict[str, dict]]:
    """返回 基础检查项ID → (分类序号, 检查项序号)，以及 基础检查项ID → 模板检查项定义。"""
    order: Dict[str, Tuple[int, int]] = {}
    items: Dict[str, dict] = {}
    categories = (template_data or {}).get("check_categories") or (template_data or {}).get("categories") or []
    for c_idx, category in enumerate(categories if isinstance(categories, list) else []):
        for i_idx, item in enumerate(category.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_id = str(item.get("item_id") or "").strip()
            if item_id and item_id not in order:
                order[item_id] = (c_idx, i_idx)
                items[item_id] = item
    return order, items


def _format_value(value: Any, field: dict, locale: str) -> Any:
    if value is None or value == "":
        return ""
    field_type = str(field.get("type") or "").strip()
    options = field.get("options") if isinstance(field.get("options"), list) else []
    option_labels = {
        str(opt.get("value")): pick_localized_text(opt.get("label"), opt.get("label_i18n"), locale)
        for opt in options
        if isinstance(opt, dict) and opt.get("value") is not None
    }
    if field_type == "boolean":
        truthy = value is True or str(value).strip().lower() in ("true", "1", "yes", "是")
        return _tr(YES_NO[0] if truthy else YES_NO[1], locale)
    if isinstance(value, list):
        return ", ".join(option_labels.get(str(v), str(v)) for v in value if v not in (None, ""))
    if option_labels and str(value) in option_labels:
        return option_labels[str(value)]
    if field_type == "number":
        try:
            number = float(value)
            return int(number) if number.is_integer() else number
        except (TypeError, ValueError):
            return str(value)
    return value if isinstance(value, (int, float)) else str(value)


def _safe_sheet_name(name: str, used: set) -> str:
    base = re.sub(r"[\[\]:*?/\\]", "_", str(name or "").strip())[:31] or "Sheet"
    candidate = base
    idx = 2
    while candidate in used:
        suffix = f"_{idx}"
        candidate = base[: 31 - len(suffix)] + suffix
        idx += 1
    used.add(candidate)
    return candidate


def build_check_data_sheets(
    db: Session,
    work_orders: List[Any],
    base_rows: Dict[str, dict],
    locale: str,
    reserved_sheet_names: Optional[set] = None,
) -> List[Tuple[str, List[str], List[List[Any]]]]:
    """
    按模板生成检查数据表。

    base_rows: 工单ID → 固定列取值（与 FIXED_COLUMNS 的 key 对应，已本地化）。
    返回 [(sheet_name, header, rows)]。
    """
    if not work_orders:
        return []

    wo_ids = [wo.id for wo in work_orders]
    inspection_by_wo: Dict[str, SiteInspection] = {}
    inspection_ids = [wo.inspection_id for wo in work_orders if getattr(wo, "inspection_id", None)]
    if inspection_ids:
        by_id = {ins.id: ins for ins in db.query(SiteInspection).filter(SiteInspection.id.in_(inspection_ids)).all()}
        for wo in work_orders:
            ins = by_id.get(wo.inspection_id)
            if ins:
                inspection_by_wo[wo.id] = ins
    missing = [wid for wid in wo_ids if wid not in inspection_by_wo]
    if missing:
        for ins in db.query(SiteInspection).filter(SiteInspection.work_order_id.in_(missing)).all():
            inspection_by_wo.setdefault(ins.work_order_id, ins)

    ins_ids = [ins.id for ins in inspection_by_wo.values()]
    items_by_ins: Dict[str, List[InspectionCheckItem]] = defaultdict(list)
    photo_counts: Dict[str, int] = {}
    if ins_ids:
        for item in (
            db.query(InspectionCheckItem)
            .filter(InspectionCheckItem.inspection_id.in_(ins_ids), InspectionCheckItem.is_active.isnot(False))
            .all()
        ):
            items_by_ins[item.inspection_id].append(item)
        photo_counts = {
            str(check_item_id): int(count or 0)
            for check_item_id, count in db.query(InspectionPhoto.check_item_id, func.count(InspectionPhoto.id))
            .filter(InspectionPhoto.inspection_id.in_(ins_ids))
            .group_by(InspectionPhoto.check_item_id)
            .all()
            if check_item_id
        }

    def _planned_template_id(wo) -> Optional[str]:
        extra = wo.extra_data if isinstance(getattr(wo, "extra_data", None), dict) else {}
        return str(extra.get("template_id") or "").strip() or None

    # 实际使用的模板：优先取检查记录；尚未接单（未生成检查记录）时取建单时选择的模板
    template_id_by_wo: Dict[str, Optional[str]] = {}
    for wo in work_orders:
        ins = inspection_by_wo.get(wo.id)
        template_id_by_wo[wo.id] = (ins.template_id if ins and ins.template_id else None) or _planned_template_id(wo)

    template_ids = {tid for tid in template_id_by_wo.values() if tid}
    templates = (
        {t.id: t for t in db.query(InspectionTemplate).filter(InspectionTemplate.id.in_(list(template_ids))).all()}
        if template_ids
        else {}
    )

    groups: Dict[Optional[str], List[Any]] = defaultdict(list)
    for wo in work_orders:
        tid = template_id_by_wo.get(wo.id)
        groups[tid if tid in templates else None].append(wo)

    used_names = set(reserved_sheet_names or set())
    sheets: List[Tuple[str, List[str], List[List[Any]]]] = []
    ordered_template_ids = sorted(
        groups.keys(),
        key=lambda tid: (tid is None, (templates.get(tid).template_name if templates.get(tid) else "") or ""),
    )
    for template_id in ordered_template_ids:
        group = groups[template_id]
        template = templates.get(template_id) if template_id else None
        order, template_items = _template_order(template.template_data if template else {})

        # 汇总该模板下出现过的检查项（扇区/小区级按实际展开项分别成列）
        variants: Dict[str, dict] = {}
        for wo in group:
            ins = inspection_by_wo.get(wo.id)
            for item in items_by_ins.get(ins.id, []) if ins else []:
                key = str(item.item_id)
                if key in variants:
                    continue
                base_id = str(item.template_item_id or item.item_id)
                template_item = template_items.get(base_id) or {}
                fields = template_item.get("fields") if isinstance(template_item.get("fields"), list) else item.fields
                fields = [f for f in (fields or []) if isinstance(f, dict) and f.get("field_id") and is_template_field_active(f)]
                name = pick_localized_text(item.item_name, template_item.get("item_name_i18n"), locale) or item.item_name
                has_photo = str(item.required_type or template_item.get("required_type") or "") in ("photo", "both") or any(
                    str(f.get("allow_photo")).lower() in ("true", "1") for f in fields
                )
                variants[key] = {
                    "base_id": base_id,
                    "order": order.get(base_id, (9999, 9999)),
                    "sector": str(item.sector_id or ""),
                    "cell": str(item.cell_id or ""),
                    "name": name,
                    "fields": fields,
                    "has_photo": has_photo,
                }
        # 模板中的站点级检查项即使尚未生成（工单未接单）也成列，保证同一模板的列稳定
        categories = (template.template_data or {}).get("check_categories") if template else None
        for category in categories if isinstance(categories, list) else []:
            if normalize_category_level(category) != "site":
                continue
            for item in category.get("items") or []:
                base_id = str((item or {}).get("item_id") or "").strip()
                if not base_id or base_id in variants or any(
                    str(v.get("base_id")) == base_id for v in variants.values()
                ):
                    continue
                fields = [
                    f for f in (item.get("fields") or [])
                    if isinstance(f, dict) and f.get("field_id") and is_template_field_active(f)
                ]
                variants[base_id] = {
                    "order": order.get(base_id, (9999, 9999)),
                    "sector": "",
                    "cell": "",
                    "name": pick_localized_text(item.get("item_name"), item.get("item_name_i18n"), locale) or base_id,
                    "fields": fields,
                    "has_photo": str(item.get("required_type") or "") in ("photo", "both")
                    or any(str(f.get("allow_photo")).lower() in ("true", "1") for f in fields),
                    "base_id": base_id,
                }

        variant_keys = sorted(
            variants.keys(),
            key=lambda k: (variants[k]["order"], variants[k]["sector"], variants[k]["cell"], k),
        )

        header = [_tr(label, locale) for _, label in FIXED_COLUMNS]
        dynamic_cols: List[Tuple[str, Optional[dict]]] = []  # (check item id, field) ；field 为 None 表示照片数
        for key in variant_keys:
            meta = variants[key]
            for field in meta["fields"]:
                label = pick_localized_text(field.get("label"), field.get("label_i18n"), locale) or field.get("field_id")
                header.append(f"{meta['name']} / {label}")
                dynamic_cols.append((key, field))
            if meta["has_photo"]:
                header.append(f"{meta['name']} / {_tr(PHOTO_COUNT_LABEL, locale)}")
                dynamic_cols.append((key, None))

        rows: List[List[Any]] = []
        for wo in group:
            base = base_rows.get(wo.id, {})
            row = [base.get(key, "") for key, _ in FIXED_COLUMNS]
            ins = inspection_by_wo.get(wo.id)
            item_by_key = {str(i.item_id): i for i in items_by_ins.get(ins.id, [])} if ins else {}
            values_cache: Dict[str, dict] = {}
            for key, field in dynamic_cols:
                item = item_by_key.get(key)
                if item is None:
                    row.append("")
                    continue
                if field is None:
                    row.append(photo_counts.get(str(item.id), 0))
                    continue
                if key not in values_cache:
                    values_cache[key] = build_field_values_from_data_value(item.data_value)
                row.append(_format_value(values_cache[key].get(str(field.get("field_id"))), field, locale))
            rows.append(row)

        sheet_title = template.template_name if template else _tr(NO_TEMPLATE_LABEL, locale)
        sheets.append((_safe_sheet_name(sheet_title, used_names), header, rows))
    return sheets
