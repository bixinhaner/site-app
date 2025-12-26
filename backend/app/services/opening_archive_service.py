from __future__ import annotations

import uuid
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models import (
    Site,
    WorkOrder,
    SiteInspection,
    InspectionTemplate,
    InspectionCheckItem,
    InspectionPhoto,
)
from app.models.work_order import WorkOrderTypeEnum
from app.models.opening_archive import (
    SiteOpeningArchive,
    SiteOpeningArchiveVersion,
    SiteOpeningArchiveKVIndex,
)
from app.utils.timezone import to_utc_iso

try:
    import jsonpatch  # type: ignore
except Exception:  # pragma: no cover
    jsonpatch = None


Snapshot = Dict[str, Any]


def _now_iso() -> str:
    return to_utc_iso(datetime.utcnow())


def _normalize(s: Optional[str]) -> str:
    return (s or '').strip().lower()


def _best_field_id(fields: List[Dict[str, Any]], candidate: str) -> Optional[str]:
    if not fields:
        return None
    cand = _normalize(candidate)
    # 1) exact by field_id
    for f in fields:
        if _normalize(f.get('field_id')) == cand:
            return f.get('field_id')
    # 2) exact by label
    for f in fields:
        if _normalize(f.get('label')) == cand:
            return f.get('field_id')
    # 3) common aliases
    ALIASES = {
        '勘察日期': 'survey_date', 'survey date': 'survey_date', 'survey_date': 'survey_date', 'date': 'survey_date',
        '勘察人员': 'surveyor_name', '勘察人': 'surveyor_name', 'surveyor': 'surveyor_name', 'surveyor_name': 'surveyor_name', 'inspector': 'surveyor_name',
        '联系方式': 'surveyor_phone', '电话': 'surveyor_phone', 'phone': 'surveyor_phone', 'mobile': 'surveyor_phone', 'surveyor_phone': 'surveyor_phone',
    }
    alias = ALIASES.get(cand)
    if alias:
        for f in fields:
            if _normalize(f.get('field_id')) == alias:
                return f.get('field_id')
    # 4) single-field fallback
    if len(fields) == 1:
        return fields[0].get('field_id')
    return None


def _strip_suffix(item_id: Optional[str]) -> str:
    s = item_id or ''
    for token in ("_cell_", "_sector_"):
        idx = s.find(token)
        if idx != -1:
            return s[:idx]
    return s


def _build_snapshot(
    db: Session, inspection: SiteInspection, template: InspectionTemplate
) -> Snapshot:
    """基于检查项自身构建开站档案快照，规则与勘察档案一致。"""

    items: List[InspectionCheckItem] = (
        db.query(InspectionCheckItem)
        .filter(InspectionCheckItem.inspection_id == inspection.id)
        .all()
    )
    photos: List[InspectionPhoto] = (
        db.query(InspectionPhoto).filter(InspectionPhoto.inspection_id == inspection.id).all()
    )
    photos_by_item: Dict[str, List[InspectionPhoto]] = {}
    for p in photos:
        photos_by_item.setdefault(p.check_item_id or "__global__", []).append(p)

    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for it in items:
        base_item_id = _strip_suffix(it.item_id)
        cat_id = it.category_id or 'unknown'
        key = (cat_id, base_item_id)
        if key not in grouped:
            grouped[key] = {
                "category_id": cat_id,
                "category_name": it.category_name,
                "item_id": base_item_id,
                "item_name": it.item_name if _strip_suffix(it.item_id) == (it.item_id or '') else _strip_suffix(it.item_name or '') or it.item_name,
                "required_type": it.required_type,
                "fields": deepcopy(it.fields or []),
                "values": {},
                "sectors": [],
                "cells": [],
                "photos": [],
            }

        rec = grouped[key]
        data = it.data_value or []

        def build_value_map(fields, data_list):
            vm: Dict[str, Any] = {}
            if isinstance(data_list, dict):
                id_set = set()
                label_map = {}
                if isinstance(fields, list):
                    for f in fields:
                        fid = str(f.get('field_id')) if isinstance(f, dict) else str(getattr(f, 'field_id', ''))
                        lbl = str(f.get('label')) if isinstance(f, dict) else str(getattr(f, 'label', ''))
                        if fid:
                            id_set.add(fid)
                        if fid and lbl:
                            label_map[lbl] = fid
                for k, v in data_list.items():
                    key = str(k)
                    mapped = label_map.get(key) or (key if key in id_set else None)
                    vm[mapped or key] = v
                return vm
            for entry in data_list:
                fname_raw = str(entry.get("field_name") or entry.get("field_id") or entry.get("key") or entry.get("field") or entry.get("name") or "")
                target_id = None
                if isinstance(fields, list):
                    for f in fields:
                        if str(f.get('field_id')) == fname_raw:
                            target_id = f.get('field_id')
                            break
                    if target_id is None:
                        for f in fields:
                            if str(f.get('label')) == fname_raw:
                                target_id = f.get('field_id')
                                break
                keyname = target_id or fname_raw
                vm[keyname] = entry.get("value")
            return vm

        value_map = build_value_map(rec.get('fields'), data)
        p_list = [
            {
                "id": p.id,
                "file_path": p.file_path,
                "file_size": p.file_size,
                "mime_type": p.mime_type,
                "latitude": p.latitude,
                "longitude": p.longitude,
                "gps_accuracy": p.gps_accuracy,
                "address": p.address,
                "taken_at": to_utc_iso(p.taken_at) if p.taken_at else None,
                "hash_value": getattr(p, "hash_value", None),
                "uploaded_by": p.uploaded_by,
            }
            for p in photos_by_item.get(it.id, [])
        ]

        if it.cell_id:
            rec["cells"].append({
                "cell_id": it.cell_id,
                "sector_id": it.sector_id,
                "band": it.band,
                "values": value_map,
                "photos": p_list,
            })
        elif it.sector_id:
            rec["sectors"].append({
                "sector_id": it.sector_id,
                "values": value_map,
                "photos": p_list,
            })
        else:
            rec["values"].update(value_map)
            rec["photos"].extend(p_list)

    cats: Dict[str, Dict[str, Any]] = {}
    for (cat_id, _), itrec in grouped.items():
        cat = cats.setdefault(cat_id, {"category_id": cat_id, "category_name": itrec.get("category_name"), "items": []})
        cat["items"].append(itrec)

    categories = list(cats.values())

    site: Optional[Site] = inspection.site

    snapshot: Snapshot = {
        "meta": {
            "site_id": inspection.site_id,
            "site_code": getattr(site, "site_code", None),
            "site_name": getattr(site, "site_name", None),
            "work_order_id": inspection.work_order_id,
            "inspection_id": inspection.id,
            "template": {
                "id": template.id,
                "name": template.template_name,
                "version": (template.template_data or {}).get("template_version") if isinstance(template.template_data, dict) else None,
            },
            "created_at": _now_iso(),
        },
        "check_categories": categories,
    }
    return snapshot


def _make_patch(old: Snapshot, new: Snapshot) -> List[Dict[str, Any]]:
    if jsonpatch is None:
        return []
    return jsonpatch.make_patch(old, new).patch


def _flatten_kv(content: Snapshot) -> List[Tuple[str, str, Any]]:
    out: List[Tuple[str, str, Any]] = []
    for cat in content.get("check_categories", []) or []:
        cid = str(cat.get("category_id"))
        for it in cat.get("items", []) or []:
            iid = str(it.get("item_id"))
            values = it.get("values", {}) or {}
            fields = {f.get("field_id"): f.get("label") for f in (it.get("fields") or []) if f.get("field_id")}
            for fid, v in values.items():
                path = f"{cid}.{iid}.{fid}"
                label = fields.get(fid) or fid
                out.append((path, label, v))
    return out


def _infer_type_and_slots(v: Any) -> Tuple[str, Dict[str, Any]]:
    from datetime import datetime as _dt
    t = "json"
    slots: Dict[str, Any] = {"raw_json": v}
    if isinstance(v, bool):
        t = "bool"; slots = {"value_bool": v}
    elif isinstance(v, (int, float)) and not isinstance(v, bool):
        t = "number"; slots = {"value_number": float(v)}
    elif isinstance(v, str):
        try:
            dt = _dt.fromisoformat(v)
            t = "datetime"; slots = {"value_datetime": dt}
        except Exception:
            t = "string"; slots = {"value_string": v}
    elif isinstance(v, dict) or isinstance(v, list):
        t = "json"; slots = {"raw_json": v}
    return t, slots


def reindex_kv(db: Session, archive_id: str, version: int, content: Snapshot) -> int:
    db.query(SiteOpeningArchiveKVIndex).filter(
        SiteOpeningArchiveKVIndex.archive_id == archive_id,
        SiteOpeningArchiveKVIndex.version == version,
    ).delete(synchronize_session=False)

    count = 0
    for path, label, val in _flatten_kv(content):
        t, slots = _infer_type_and_slots(val)
        rec = SiteOpeningArchiveKVIndex(
            archive_id=archive_id,
            version=version,
            path=path,
            field_label=label,
            type=t,
            **slots,
        )
        db.add(rec)
        count += 1
    db.flush()
    return count


def create_or_append_archive(
    db: Session,
    *,
    inspection_id: str,
    operator_id: Optional[int] = None,
    change_summary: Optional[str] = None,
) -> SiteOpeningArchive:
    """在开站工单审核通过时创建或追加档案版本（按 work_order_id 聚合）。"""
    insp = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not insp or not insp.work_order_id:
        raise ValueError("无效的检查记录或未绑定工单")

    wo = db.query(WorkOrder).filter(WorkOrder.id == insp.work_order_id).first()
    if not wo:
        raise ValueError("未找到关联工单")
    if wo.type != WorkOrderTypeEnum.OPENING_INSPECTION:
        raise ValueError(f"仅支持开站工单生成开站档案，当前工单类型为: {wo.type}")

    tpl = db.query(InspectionTemplate).filter(InspectionTemplate.id == insp.template_id).first()
    if not tpl:
        raise ValueError("未找到检查模板")

    snapshot = _build_snapshot(db, insp, tpl)

    arc = db.query(SiteOpeningArchive).filter(
        SiteOpeningArchive.work_order_id == insp.work_order_id
    ).first()

    if not arc:
        arc = SiteOpeningArchive(
            id=uuid.uuid4().hex,
            site_id=insp.site_id,
            work_order_id=insp.work_order_id,
            inspection_id=insp.id,
            template_id=tpl.id,
            template_version=(tpl.template_data or {}).get("template_version") if isinstance(tpl.template_data, dict) else None,
            current_version=1,
            content=snapshot,
            status="active",
            created_by=operator_id,
            updated_by=operator_id,
        )
        db.add(arc)

        ver = SiteOpeningArchiveVersion(
            id=uuid.uuid4().hex,
            archive_id=arc.id,
            version=1,
            content=snapshot,
            diff=None,
            change_summary=change_summary or "首次建立（审核通过）",
            changed_by=operator_id,
        )
        db.add(ver)
        reindex_kv(db, arc.id, 1, snapshot)
        db.flush()
        return arc

    old_content = deepcopy(arc.content)
    new_content = snapshot
    patch = _make_patch(old_content, new_content)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteOpeningArchiveVersion(
        id=uuid.uuid4().hex,
        archive_id=arc.id,
        version=new_ver_no,
        content=new_content,
        diff=patch,
        change_summary=change_summary or "审核通过追加版本",
        changed_by=operator_id,
    )
    db.add(ver)

    arc.content = new_content
    arc.current_version = new_ver_no
    arc.updated_by = operator_id
    arc.updated_at = datetime.utcnow()

    reindex_kv(db, arc.id, new_ver_no, new_content)
    db.flush()
    return arc


def patch_archive(
    db: Session,
    *,
    archive_id: str,
    base_version: Optional[int],
    patch_ops: List[Dict[str, Any]],
    operator_id: Optional[int] = None,
    change_summary: Optional[str] = None,
) -> SiteOpeningArchive:
    arc = db.query(SiteOpeningArchive).filter(SiteOpeningArchive.id == archive_id).first()
    if not arc:
        raise ValueError("档案不存在")
    if base_version is not None and int(base_version) != int(arc.current_version or 1):
        raise RuntimeError("版本冲突，请刷新后重试")

    if jsonpatch is None:
        raise RuntimeError("服务器未安装 jsonpatch 依赖")

    new_content = jsonpatch.apply_patch(deepcopy(arc.content), patch_ops, in_place=False)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteOpeningArchiveVersion(
        id=uuid.uuid4().hex,
        archive_id=arc.id,
        version=new_ver_no,
        content=new_content,
        diff=patch_ops,
        change_summary=change_summary or "用户编辑",
        changed_by=operator_id,
    )
    db.add(ver)

    arc.content = new_content
    arc.current_version = new_ver_no
    arc.updated_by = operator_id
    arc.updated_at = datetime.utcnow()

    reindex_kv(db, arc.id, new_ver_no, new_content)
    db.flush()
    return arc


def get_version_pair(db: Session, archive_id: str, a: int, b: int) -> Tuple[Snapshot, Snapshot]:
    A = db.query(SiteOpeningArchiveVersion).filter(
        SiteOpeningArchiveVersion.archive_id == archive_id,
        SiteOpeningArchiveVersion.version == a,
    ).first()
    B = db.query(SiteOpeningArchiveVersion).filter(
        SiteOpeningArchiveVersion.archive_id == archive_id,
        SiteOpeningArchiveVersion.version == b,
    ).first()
    if not A or not B:
        raise ValueError("版本不存在")
    return A.content, B.content


def make_diff(db: Session, archive_id: str, a: int, b: int) -> List[Dict[str, Any]]:
    old, new = get_version_pair(db, archive_id, a, b)
    return _make_patch(old, new)


def revert_to_version(
    db: Session, *, archive_id: str, to_version: int, operator_id: Optional[int] = None
) -> SiteOpeningArchive:
    arc = db.query(SiteOpeningArchive).filter(SiteOpeningArchive.id == archive_id).first()
    if not arc:
        raise ValueError("档案不存在")
    target = db.query(SiteOpeningArchiveVersion).filter(
        SiteOpeningArchiveVersion.archive_id == archive_id,
        SiteOpeningArchiveVersion.version == to_version,
    ).first()
    if not target:
        raise ValueError("目标版本不存在")

    old_content = deepcopy(arc.content)
    new_content = deepcopy(target.content)
    patch = _make_patch(old_content, new_content)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteOpeningArchiveVersion(
        id=uuid.uuid4().hex,
        archive_id=arc.id,
        version=new_ver_no,
        content=new_content,
        diff=patch,
        change_summary=f"回滚到版本 {to_version}",
        changed_by=operator_id,
    )
    db.add(ver)

    arc.content = new_content
    arc.current_version = new_ver_no
    arc.updated_by = operator_id
    arc.updated_at = datetime.utcnow()

    reindex_kv(db, arc.id, new_ver_no, new_content)
    db.flush()
    return arc
