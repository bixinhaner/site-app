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
from app.models.survey_archive import (
    SiteSurveyArchive,
    SiteSurveyArchiveVersion,
    SiteSurveyArchiveKVIndex,
)

try:
    import jsonpatch  # type: ignore
except Exception:  # pragma: no cover
    jsonpatch = None


Snapshot = Dict[str, Any]


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


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
    """基于检查项自身（携带模板字段快照）构建快照，不依赖当前模板结构，避免结构变更导致丢值。

    规则：
    - 以 inspection_check_items 为唯一事实来源；
    - 归并同一模板项（按 base_item_id = 去除 _cell_/_sector_ 后的 item_id）；
    - 站点级：写入 item.values；扇区/小区级：写入 item.sectors[]/item.cells[]；
    - 字段名严格取 check_item.fields 中的 field_id；data_value 的键必须能在 fields 中找到，找不到则按原名写入（不做兜底推断）。
    """

    # 收集检查项与照片
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

    # 先按 base_item_id 归并
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
                "photos": [],  # 站点级照片
            }

        rec = grouped[key]
        data = it.data_value or []
        # 站点/扇区/小区级分流
        is_cell = bool(it.cell_id)
        is_sector = bool(it.sector_id) and not is_cell

        def build_value_map(fields, data_list):
            vm: Dict[str, Any] = {}
            if isinstance(data_list, dict):
                # 尝试用字段label精确映射到field_id
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
                # 精确映射：先按 field_id，再按 label
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
                "taken_at": p.taken_at.isoformat() if p.taken_at else None,
                "hash_value": getattr(p, "hash_value", None),
                "uploaded_by": p.uploaded_by,
            }
            for p in photos_by_item.get(it.id, [])
        ]

        if is_cell:
            rec["cells"].append({
                "cell_id": it.cell_id,
                "sector_id": it.sector_id,
                "band": it.band,
                "values": value_map,
                "photos": p_list,
            })
        elif is_sector:
            rec["sectors"].append({
                "sector_id": it.sector_id,
                "values": value_map,
                "photos": p_list,
            })
        else:
            # 站点级：合并到 values（字段不冲突则覆盖同名）
            rec["values"].update(value_map)
            rec["photos"].extend(p_list)

    # 组装分类结构（按检查项上的分类名称聚合）
    cats: Dict[str, Dict[str, Any]] = {}
    for (cat_id, _), itrec in grouped.items():
        cat = cats.setdefault(cat_id, {"category_id": cat_id, "category_name": itrec.get("category_name"), "items": []})
        cat["items"].append(itrec)

    categories = list(cats.values())

    site: Optional[Site] = inspection.site
    # 常用元字段兜底（当对应字段仍为空时）
    # 不做兜底填充，严格以检查项数据为准

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
        # 简单兜底：无库时返回空补丁
        return []
    return jsonpatch.make_patch(old, new).patch


def _flatten_kv(content: Snapshot) -> List[Tuple[str, str, Any]]:
    """将快照展平为 (path, label, value) 列表。"""
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
        # 尝试时间解析
        try:
            dt = _dt.fromisoformat(v)
            t = "datetime"; slots = {"value_datetime": dt}
        except Exception:
            t = "string"; slots = {"value_string": v}
    elif isinstance(v, dict) or isinstance(v, list):
        t = "json"; slots = {"raw_json": v}
    return t, slots


def reindex_kv(db: Session, archive_id: str, version: int, content: Snapshot) -> int:
    """重建某版本的KV索引。"""
    db.query(SiteSurveyArchiveKVIndex).filter(
        SiteSurveyArchiveKVIndex.archive_id == archive_id,
        SiteSurveyArchiveKVIndex.version == version,
    ).delete(synchronize_session=False)

    count = 0
    for path, label, val in _flatten_kv(content):
        t, slots = _infer_type_and_slots(val)
        rec = SiteSurveyArchiveKVIndex(
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
) -> SiteSurveyArchive:
    """在审核通过时创建或追加档案版本（按 work_order_id 聚合）。"""
    insp = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not insp or not insp.work_order_id:
        raise ValueError("无效的检查记录或未绑定工单")
    tpl = db.query(InspectionTemplate).filter(InspectionTemplate.id == insp.template_id).first()
    if not tpl:
        raise ValueError("未找到检查模板")

    snapshot = _build_snapshot(db, insp, tpl)

    # 以 work_order_id 作为归档聚合键
    arc = db.query(SiteSurveyArchive).filter(
        SiteSurveyArchive.work_order_id == insp.work_order_id
    ).first()

    if not arc:
        arc = SiteSurveyArchive(
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

        ver = SiteSurveyArchiveVersion(
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

    # 已存在 → 追加新版本
    old_content = deepcopy(arc.content)
    new_content = snapshot
    patch = _make_patch(old_content, new_content)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteSurveyArchiveVersion(
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
) -> SiteSurveyArchive:
    arc = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not arc:
        raise ValueError("档案不存在")
    if base_version is not None and int(base_version) != int(arc.current_version or 1):
        raise RuntimeError("版本冲突，请刷新后重试")

    if jsonpatch is None:
        raise RuntimeError("服务器未安装 jsonpatch 依赖")

    new_content = jsonpatch.apply_patch(deepcopy(arc.content), patch_ops, in_place=False)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteSurveyArchiveVersion(
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
    A = db.query(SiteSurveyArchiveVersion).filter(
        SiteSurveyArchiveVersion.archive_id == archive_id,
        SiteSurveyArchiveVersion.version == a,
    ).first()
    B = db.query(SiteSurveyArchiveVersion).filter(
        SiteSurveyArchiveVersion.archive_id == archive_id,
        SiteSurveyArchiveVersion.version == b,
    ).first()
    if not A or not B:
        raise ValueError("版本不存在")
    return A.content, B.content


def make_diff(db: Session, archive_id: str, a: int, b: int) -> List[Dict[str, Any]]:
    old, new = get_version_pair(db, archive_id, a, b)
    return _make_patch(old, new)


def revert_to_version(
    db: Session, *, archive_id: str, to_version: int, operator_id: Optional[int] = None
) -> SiteSurveyArchive:
    arc = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not arc:
        raise ValueError("档案不存在")
    target = db.query(SiteSurveyArchiveVersion).filter(
        SiteSurveyArchiveVersion.archive_id == archive_id,
        SiteSurveyArchiveVersion.version == to_version,
    ).first()
    if not target:
        raise ValueError("目标版本不存在")

    old_content = deepcopy(arc.content)
    new_content = deepcopy(target.content)
    patch = _make_patch(old_content, new_content)
    new_ver_no = int(arc.current_version or 1) + 1

    ver = SiteSurveyArchiveVersion(
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
