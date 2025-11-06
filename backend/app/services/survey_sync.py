from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Tuple, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.work_order import WorkOrder
from app.models.survey import SiteSurvey, SiteSurveyPhoto
from app.models.inspection import InspectionTemplate, InspectionCheckItem, InspectionPhoto, SiteInspection


class PhotoPolicy(str, Enum):
    first_per_item = 'first_per_item'
    categorized_best = 'categorized_best'
    all = 'all'


class SyncMode(str, Enum):
    on_submit = 'on_submit'
    on_approve = 'on_approve'


@dataclass
class SyncOptions:
    mode: SyncMode
    overwrite_fields: bool = False
    photo_policy: PhotoPolicy = PhotoPolicy.first_per_item
    per_category_limit: int = 6
    persist_audit: bool = True


def ensure_survey_for_work_order(db: Session, wo: WorkOrder, inspector) -> SiteSurvey:
    survey = db.query(SiteSurvey).filter(SiteSurvey.work_order_id == wo.id).first()
    if survey:
        return survey
    # fallback site info
    survey = SiteSurvey(
        id=str(__import__('uuid').uuid4().hex),
        site_id=wo.site_id,
        survey_date=datetime.utcnow(),
        surveyor_name=getattr(inspector, 'full_name', None) or getattr(inspector, 'username', None),
        created_by=getattr(inspector, 'id', None),
        work_order_id=wo.id,
        feasibility='conditionally_feasible'
    )
    db.add(survey)
    db.flush()
    return survey


def resolve_template_bindings(template: Optional[InspectionTemplate]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not template:
        return mapping
    try:
        cats = (template.template_data or {}).get('check_categories', [])
        for cat in cats:
            cat_id = cat.get('category_id') or 'unknown'
            for it in cat.get('items', []):
                item_id = it.get('item_id') or 'unknown'
                fields = it.get('fields') or []
                for f in fields:
                    # 优先使用 field_id 以与提交的数据项 field_name 对应
                    key = f.get('field_id') or f.get('key') or f.get('field') or 'value'
                    bind_to = f.get('bind_to')
                    if isinstance(bind_to, str) and bind_to.startswith('site_surveys.'):
                        src = f"{cat_id}.{item_id}.{key}"
                        mapping[src] = bind_to.split('.', 1)[1]
    except Exception:
        pass
    return mapping


def default_mapping() -> Dict[str, str]:
    m: Dict[str, str] = {}
    def add(p, c):
        m[p] = c
    # 基本信息
    add('basic_info.survey_meta.survey_date', 'survey_date')
    add('basic_info.survey_meta.surveyor_name', 'surveyor_name')
    add('basic_info.survey_meta.surveyor_phone', 'surveyor_phone')
    # 坐标
    add('gps.location.latitude', 'latitude')
    add('gps.location.longitude', 'longitude')
    add('gps.location.accuracy', 'gps_accuracy')
    add('gps.location.address', 'address')
    # 结构
    add('structure.site.site_type', 'site_type')
    add('structure.tower.tower_type', 'tower_type')
    add('structure.tower.available_height_m', 'available_height_m')
    add('structure.tower.load_capacity_kg', 'load_capacity_kg')
    # 供电/接地
    add('power.supply.power_available', 'power_available')
    add('power.supply.power_distance_m', 'power_distance_m')
    add('power.supply.power_capacity_kw', 'power_capacity_kw')
    add('power.earthing.earthing_feasible', 'earthing_feasible')
    # 传输与微波
    add('transmission.fiber.fiber_available', 'fiber_available')
    add('transmission.fiber.fiber_distance_m', 'fiber_distance_m')
    add('transmission.duct.duct_notes', 'duct_notes')
    add('transmission.microwave.microwave_los', 'microwave_los')
    add('transmission.microwave.los_azimuth_deg', 'los_azimuth_deg')
    add('transmission.microwave.los_distance_km', 'los_distance_km')
    # 环境
    add('environment.impact.sensitive_points', 'sensitive_points')
    add('environment.safety.safety_notes', 'safety_notes')
    add('environment.compliance.permits_constraints', 'permits_constraints')
    # 业主/出入
    add('access.owner.owner_name', 'owner_name')
    add('access.owner.owner_phone', 'owner_phone')
    add('access.entry.access_time_window', 'access_time_window')
    add('access.entry.entry_constraints', 'entry_constraints')
    # 结论与建议
    add('conclusion.summary.feasibility', 'feasibility')
    add('conclusion.summary.risks', 'risks')
    add('conclusion.summary.recommendations', 'recommendations')
    return m


def build_effective_mapping(template: Optional[InspectionTemplate]) -> Dict[str, str]:
    eff = default_mapping()
    tmap = resolve_template_bindings(template)
    eff.update(tmap)
    return eff


def _norm_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ('1', 'true', 'yes', 'y', '是', '有'):
        return True
    if s in ('0', 'false', 'no', 'n', '否', '无'):
        return False
    return None


def _norm_float(v: Any) -> Optional[float]:
    try:
        if v is None or v == '':
            return None
        return float(str(v).replace(',', ''))
    except Exception:
        return None


def _norm_time(v: Any) -> Optional[datetime]:
    if isinstance(v, datetime):
        return v
    if v is None:
        return None
    s = str(v).strip()
    for fmt in ('%Y-%m-%d %H:%M', '%Y-%m-%d', '%Y/%m/%d %H:%M', '%Y/%m/%d'):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _norm_feasibility(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip().lower()
    mapping = {
        '可行': 'feasible',
        'feasible': 'feasible',
        '有条件可行': 'conditionally_feasible',
        'conditionally_feasible': 'conditionally_feasible',
        '不可行': 'infeasible',
        'infeasible': 'infeasible'
    }
    return mapping.get(s, None)


def coerce_value(val: Any, target_field: str) -> Any:
    if target_field in ('survey_date',):
        return _norm_time(val)
    if target_field in (
        'latitude', 'longitude', 'gps_accuracy',
        'available_height_m', 'load_capacity_kg',
        'power_distance_m', 'power_capacity_kw',
        'fiber_distance_m', 'los_azimuth_deg', 'los_distance_km'
    ):
        return _norm_float(val)
    if target_field in (
        'power_available', 'earthing_feasible', 'fiber_available', 'microwave_los'
    ):
        return _norm_bool(val)
    if target_field == 'feasibility':
        return _norm_feasibility(val) or 'conditionally_feasible'
    return val


def collect_inspection_values(db: Session, inspection_id: str) -> Tuple[List[InspectionCheckItem], List[InspectionPhoto]]:
    items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id).all()
    photos = db.query(InspectionPhoto).filter(InspectionPhoto.inspection_id == inspection_id).all()
    return items, photos


def map_items_to_survey_fields(items: List[InspectionCheckItem], mapping: Dict[str, str]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    direct: Dict[str, Any] = {}
    extra: Dict[str, Any] = {}
    for it in items:
        cat = it.category_id or 'unknown'
        iid = it.item_id or 'unknown'
        data = it.data_value or []
        if isinstance(data, dict):
            iterable = [{'key': k, 'value': v} for k, v in data.items()]
        else:
            iterable = data
        for entry in iterable:
            # 数据项来自 InspectionCheckItemUpdate.CheckItemDataValue，字段名为 field_name
            key = str(entry.get('field_name') or entry.get('key') or entry.get('field') or 'value')
            path = f"{cat}.{iid}.{key}"
            target = mapping.get(path)
            value = entry.get('value') if isinstance(entry, dict) else None
            if target:
                direct[target] = coerce_value(value, target)
            else:
                extra.setdefault(cat, {}).setdefault(iid, {})[key] = value
    return direct, extra


def _guess_category(name: str) -> str:
    n = (name or '').lower()
    if any(k in n for k in ['power', '配电', '电力']):
        return 'power'
    if any(k in n for k in ['room', '机房', '机柜']):
        return 'room'
    if any(k in n for k in ['duct', '管道', '走线', '弱电']):
        return 'duct'
    if any(k in n for k in ['roof', '屋面', '塔', '天面']):
        return 'roof'
    if any(k in n for k in ['hazard', '隐患', '安全']):
        return 'hazard'
    return 'overview'


def select_photos(items: List[InspectionCheckItem], photos: List[InspectionPhoto], policy: PhotoPolicy, per_category_limit: int) -> List[Dict[str, Any]]:
    by_item = {}
    for p in photos:
        by_item.setdefault(p.check_item_id, []).append(p)
    selected: List[Dict[str, Any]] = []

    if policy == PhotoPolicy.first_per_item:
        for it in items:
            plist = by_item.get(it.id, [])
            if plist:
                p = plist[0]
                selected.append({'photo': p, 'category': _guess_category(it.category_name or it.item_name)})
        return selected

    if policy == PhotoPolicy.all:
        for p in photos:
            selected.append({'photo': p, 'category': 'custom'})
        return selected

    # categorized_best
    buckets: Dict[str, List[InspectionPhoto]] = {}
    for it in items:
        plist = by_item.get(it.id, [])
        cat = _guess_category(it.category_name or it.item_name)
        if plist:
            buckets.setdefault(cat, []).extend(plist)
    for cat, plist in buckets.items():
        def score(ph: InspectionPhoto) -> int:
            s = 0
            if ph.latitude and ph.longitude:
                s += 2
            if ph.taken_at:
                s += 1
            return s
        ordered = sorted(plist, key=score, reverse=True)[:per_category_limit]
        for p in ordered:
            selected.append({'photo': p, 'category': cat})
    return selected


def upsert_survey(db: Session, survey: SiteSurvey, direct_fields: Dict[str, Any], extra_patch: Dict[str, Any], overwrite: bool) -> SiteSurvey:
    for k, v in direct_fields.items():
        if v is None:
            continue
        if overwrite or getattr(survey, k, None) in (None, ''):
            setattr(survey, k, v)
    extra = survey.extra_data or {}
    # shallow merge
    for cat, items in (extra_patch or {}).items():
        extra.setdefault(cat, {}).update(items)
    survey.extra_data = extra
    survey.updated_at = datetime.utcnow()
    db.flush()
    return survey


def upsert_survey_photos(db: Session, survey: SiteSurvey, selected: List[Dict[str, Any]]) -> int:
    if not selected:
        return 0
    existing = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == survey.id).all()
    seen = {(p.hash_value, p.file_path) for p in existing}
    max_order = db.query(func.max(SiteSurveyPhoto.sort_order)).filter(SiteSurveyPhoto.survey_id == survey.id).scalar() or 0
    count = 0
    for sel in selected:
        p: InspectionPhoto = sel['photo']
        key = (p.hash_value, p.file_path)
        if key in seen:
            continue
        max_order += 1
        rec = SiteSurveyPhoto(
            id=str(__import__('uuid').uuid4().hex),
            survey_id=survey.id,
            original_name=p.original_name,
            file_path=p.file_path,
            file_size=p.file_size,
            mime_type=p.mime_type,
            category=sel.get('category'),
            sort_order=max_order,
            latitude=p.latitude,
            longitude=p.longitude,
            gps_accuracy=p.gps_accuracy,
            address=p.address,
            taken_at=p.taken_at,
            has_watermark=getattr(p, 'has_watermark', False),
            hash_value=p.hash_value,
            uploaded_by=p.uploaded_by,
        )
        db.add(rec)
        count += 1
    db.flush()
    return count


def sync_inspection_to_survey(db: Session, inspection_id: str, options: SyncOptions) -> Optional[SiteSurvey]:
    insp = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not insp:
        return None
    wo = db.query(WorkOrder).filter(WorkOrder.id == insp.work_order_id).first() if insp.work_order_id else None
    if not wo:
        return None
    survey = db.query(SiteSurvey).filter(SiteSurvey.work_order_id == wo.id).first()
    if not survey:
        survey = ensure_survey_for_work_order(db, wo, insp.inspector)

    template = db.query(InspectionTemplate).filter(InspectionTemplate.id == insp.template_id).first()
    mapping = build_effective_mapping(template)
    items, photos = collect_inspection_values(db, inspection_id)
    direct, extra = map_items_to_survey_fields(items, mapping)
    upsert_survey(db, survey, direct, extra, overwrite=options.overwrite_fields)
    selected = select_photos(items, photos, options.photo_policy, options.per_category_limit)
    upsert_survey_photos(db, survey, selected)
    return survey
