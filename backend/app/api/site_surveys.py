from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Body
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
from datetime import datetime
import io
import os
import uuid
import zipfile
import csv

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.survey import SiteSurvey, SiteSurveyPhoto
from app.models.work_order import AuditEvent
from app.schemas.site_survey import (
    SiteSurveyCreate, SiteSurveyUpdate,
    SiteSurveyResponse, SiteSurveyPhotoResponse,
    SiteSurveySummary,
)
from app.utils.file_handler import save_uploaded_file, calculate_file_hash, extract_exif, compress_image, add_text_watermark_inline


router = APIRouter()


def _require_admin(current_user: User) -> None:
    if getattr(current_user, "role", None) not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员/经理权限")


def _audit(
    db: Session,
    resource_id: str,
    action: str,
    operator_id: int,
    comments: Optional[str] = None,
    details: Optional[dict] = None,
):
    evt = AuditEvent(
        id=uuid.uuid4().hex,
        resource_type="site_survey",
        resource_id=resource_id,
        action=action,
        operator_id=operator_id,
        comments=comments,
        details=details or {},
    )
    db.add(evt)


def _jsonify_val(v):
    if isinstance(v, datetime):
        try:
            return v.isoformat()
        except Exception:
            return str(v)
    return v

def _jsonify_dict(d: dict) -> dict:
    try:
        return {k: _jsonify_val(v) for k, v in d.items()}
    except Exception:
        return {}

# Human-readable labels for common fields
FIELD_LABELS = {
    "survey_date": "勘察日期",
    "surveyor_name": "勘察人",
    "surveyor_phone": "勘察人电话",
    "feasibility": "结论",
    "address": "地址",
    "latitude": "纬度",
    "longitude": "经度",
    "risks": "风险",
    "recommendations": "建议",
}

def _fmt_val(v):
    if isinstance(v, datetime):
        try:
            return v.strftime('%Y-%m-%d %H:%M')
        except Exception:
            return v.isoformat()
    if isinstance(v, float):
        return round(v, 6)
    if v is None:
        return "-"
    return v

def _values_different(a, b) -> bool:
    # Normalize datetimes
    if isinstance(a, datetime) and isinstance(b, datetime):
        return a.replace(microsecond=0) != b.replace(microsecond=0)
    # Floats tolerance
    if isinstance(a, float) and isinstance(b, float):
        return abs(a - b) > 1e-9
    return a != b


@router.post("/", response_model=SiteSurveyResponse)
async def create_survey(
    payload: SiteSurveyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # admin/manager（在鉴权代理下等同admin）
    _require_admin(current_user)

    site = db.query(Site).filter(Site.id == payload.site_id).first()
    if not site:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="站点不存在")

    survey = SiteSurvey(
        id=uuid.uuid4().hex,
        created_by=current_user.id,
        **payload.dict(exclude_unset=True),
    )
    db.add(survey)
    db.commit()
    # audit
    try:
        _audit(db, survey.id, "create", current_user.id, details={"site_id": survey.site_id})
        db.commit()
    except Exception:
        db.rollback()
    db.refresh(survey)
    return survey


@router.get("/import-template")
async def download_import_template():
    """下载Excel导入模板

    注意：此静态路径必须在 `/{survey_id}` 动态路径之前注册，
    否则会被当作 survey_id 捕获导致 404。
    """
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "SiteSurveys"
    headers = [
        "site_code",
        "survey_date(YYYY-MM-DD)",
        "surveyor_name",
        "surveyor_phone",
        "feasibility(feasible|conditionally_feasible|infeasible)",
        "latitude",
        "longitude",
        "address",
        "power_available(true/false)",
        "fiber_available(true/false)",
        "microwave_los(true/false)",
        "los_azimuth_deg",
        "los_distance_km",
        "risks",
        "recommendations",
    ]
    ws.append(headers)
    # one sample row
    ws.append([
        "BJ-001", "2025-10-23", "张三", "13800000000", "feasible",
        39.9, 116.3, "北京市朝阳区XX路", True, True, False, None, None, "周边学校", "建议使用光纤回传",
    ])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    return StreamingResponse(
        stream, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=site_survey_import_template.xlsx"}
    )


@router.get("/page")
async def page_surveys(
    page: int = 1,
    page_size: int = 20,
    keyword: Optional[str] = None,
    site_id: Optional[int] = None,
    feasibility: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    sort_by: Optional[str] = "created_at",  # created_at|survey_date|site_code
    sort_dir: Optional[str] = "desc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(SiteSurvey).join(Site, Site.id == SiteSurvey.site_id)
    if site_id:
        query = query.filter(SiteSurvey.site_id == site_id)
    if feasibility:
        query = query.filter(SiteSurvey.feasibility == feasibility)
    if date_from:
        query = query.filter(SiteSurvey.survey_date >= date_from)
    if date_to:
        query = query.filter(SiteSurvey.survey_date <= date_to)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(
            Site.site_name.like(kw),
            Site.site_code.like(kw),
            SiteSurvey.surveyor_name.like(kw),
            SiteSurvey.feasibility.like(kw)
        ))

    # Total
    total = query.with_entities(func.count(SiteSurvey.id)).scalar() or 0

    # Sorting
    sort_expr = SiteSurvey.created_at.desc()
    if sort_by == "survey_date":
        sort_expr = SiteSurvey.survey_date.desc() if sort_dir == "desc" else SiteSurvey.survey_date.asc()
    elif sort_by == "site_code":
        sort_expr = Site.site_code.desc() if sort_dir == "desc" else Site.site_code.asc()
    else:
        sort_expr = SiteSurvey.created_at.desc() if sort_dir == "desc" else SiteSurvey.created_at.asc()

    rows = (query.order_by(sort_expr)
                 .offset((page - 1) * page_size)
                 .limit(page_size)
                 .all())

    items: List[SiteSurveySummary] = []
    for s in rows:
        items.append(
            SiteSurveySummary(
                id=s.id,
                site_id=s.site_id,
                site_name=s.site.site_name if s.site else None,
                site_code=s.site.site_code if s.site else None,
                survey_date=s.survey_date,
                surveyor_name=s.surveyor_name,
                feasibility=s.feasibility,
                created_at=s.created_at,
            )
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/import-excel")
async def import_excel(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量导入勘察数据（Excel）

    注意：置于 `/{survey_id}` 动态路径之前，避免被误匹配。
    """
    _require_admin(current_user)
    from openpyxl import load_workbook

    content = await file.read()
    stream = io.BytesIO(content)
    wb = load_workbook(stream)
    ws = wb.active

    header_row = next(ws.iter_rows(min_row=1, max_row=1))
    header = [cell.value for cell in header_row[0:]]

    success = 0
    failed = 0
    errors: List[dict] = []

    # Build simple site_code -> id map
    sites = db.query(Site).all()
    site_by_code = {s.site_code: s for s in sites}

    for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        try:
            site_code = row[0]
            survey_date_s = row[1]
            surveyor_name = row[2]
            surveyor_phone = row[3]
            feasibility = row[4]

            if not site_code or not survey_date_s or not surveyor_name or not feasibility:
                raise ValueError("必填列缺失: site_code/survey_date/surveyor_name/feasibility")

            site_obj = site_by_code.get(str(site_code))
            if not site_obj:
                raise ValueError(f"站点编码不存在: {site_code}")

            # Parse date
            if isinstance(survey_date_s, datetime):
                survey_date = survey_date_s
            else:
                survey_date = datetime.fromisoformat(str(survey_date_s))

            survey = SiteSurvey(
                id=uuid.uuid4().hex,
                site_id=site_obj.id,
                survey_date=survey_date,
                surveyor_name=str(surveyor_name),
                surveyor_phone=str(surveyor_phone) if surveyor_phone else None,
                feasibility=str(feasibility),
                latitude=float(row[5]) if row[5] is not None else None,
                longitude=float(row[6]) if row[6] is not None else None,
                address=str(row[7]) if row[7] is not None else None,
                power_available=bool(row[8]) if row[8] is not None else None,
                fiber_available=bool(row[9]) if row[9] is not None else None,
                microwave_los=bool(row[10]) if row[10] is not None else None,
                los_azimuth_deg=float(row[11]) if row[11] is not None else None,
                los_distance_km=float(row[12]) if row[12] is not None else None,
                risks=str(row[13]) if row[13] is not None else None,
                recommendations=str(row[14]) if row[14] is not None else None,
                created_by=current_user.id,
            )
            db.add(survey)
            success += 1
        except Exception as e:
            failed += 1
            row_dict = {str(header[idx] or idx): row[idx] for idx in range(min(len(header), len(row)))}
            errors.append({"row_index": i, "row_values": row_dict, "error": str(e)})

    db.commit()
    # audit each created survey (optional lightweight)
    try:
        # 为避免逐条查询，简单记录一次导入汇总
        _audit(db, resource_id="bulk", action="import", operator_id=current_user.id,
               details={"success": success, "failed": failed})
        db.commit()
    except Exception:
        db.rollback()

    return {"success": success, "failed": failed, "errors": errors}

@router.get("/", response_model=List[SiteSurveySummary])
async def list_surveys(
    skip: int = 0,
    limit: int = 50,
    site_id: Optional[int] = None,
    surveyor_name: Optional[str] = None,
    feasibility: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(SiteSurvey)
    if site_id:
        query = query.filter(SiteSurvey.site_id == site_id)
    if surveyor_name:
        query = query.filter(SiteSurvey.surveyor_name.like(f"%{surveyor_name}%"))
    if feasibility:
        query = query.filter(SiteSurvey.feasibility == feasibility)
    if date_from:
        query = query.filter(SiteSurvey.survey_date >= date_from)
    if date_to:
        query = query.filter(SiteSurvey.survey_date <= date_to)

    rows = query.order_by(SiteSurvey.created_at.desc()).offset(skip).limit(limit).all()

    summaries: List[SiteSurveySummary] = []
    for s in rows:
        summaries.append(
            SiteSurveySummary(
                id=s.id,
                site_id=s.site_id,
                site_name=s.site.site_name if s.site else None,
                site_code=s.site.site_code if s.site else None,
                survey_date=s.survey_date,
                surveyor_name=s.surveyor_name,
                feasibility=s.feasibility,
                created_at=s.created_at,
            )
        )
    return summaries


 


@router.get("/{survey_id}", response_model=SiteSurveyResponse)
async def get_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="勘察记录不存在")

    # Ordered photos
    photos = (
        db.query(SiteSurveyPhoto)
        .filter(SiteSurveyPhoto.survey_id == survey_id)
        .order_by(SiteSurveyPhoto.sort_order.asc().nulls_last(), SiteSurveyPhoto.created_at.asc())
        .all()
    )

    # Build response explicitly to包含 site_name/site_code
    from app.schemas.site_survey import SiteSurveyPhotoResponse  # local import to avoid cycle
    photo_items = [SiteSurveyPhotoResponse.model_validate(p) for p in photos]

    return {
        "id": survey.id,
        "site_id": survey.site_id,
        "site_name": survey.site.site_name if survey.site else None,
        "site_code": survey.site.site_code if survey.site else None,
        "survey_date": survey.survey_date,
        "surveyor_name": survey.surveyor_name,
        "surveyor_phone": survey.surveyor_phone,
        "latitude": survey.latitude,
        "longitude": survey.longitude,
        "address": survey.address,
        "gps_accuracy": survey.gps_accuracy,
        "site_type": survey.site_type,
        "tower_type": survey.tower_type,
        "available_height_m": survey.available_height_m,
        "load_capacity_kg": survey.load_capacity_kg,
        "power_available": survey.power_available,
        "power_distance_m": survey.power_distance_m,
        "power_capacity_kw": survey.power_capacity_kw,
        "earthing_feasible": survey.earthing_feasible,
        "fiber_available": survey.fiber_available,
        "fiber_distance_m": survey.fiber_distance_m,
        "duct_notes": survey.duct_notes,
        "microwave_los": survey.microwave_los,
        "los_azimuth_deg": survey.los_azimuth_deg,
        "los_distance_km": survey.los_distance_km,
        "sensitive_points": survey.sensitive_points,
        "safety_notes": survey.safety_notes,
        "permits_constraints": survey.permits_constraints,
        "owner_name": survey.owner_name,
        "owner_phone": survey.owner_phone,
        "access_time_window": survey.access_time_window,
        "entry_constraints": survey.entry_constraints,
        "feasibility": survey.feasibility,
        "risks": survey.risks,
        "recommendations": survey.recommendations,
        "extra_data": survey.extra_data,
        "created_by": survey.created_by,
        "created_at": survey.created_at,
        "updated_at": survey.updated_at,
        "photos": photo_items,
    }


@router.put("/{survey_id}", response_model=SiteSurveyResponse)
async def update_survey(
    survey_id: str,
    payload: SiteSurveyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="勘察记录不存在")
    incoming = payload.dict(exclude_unset=True)
    # build diff（仅记录值真正发生变化的字段）
    before = {}
    after = {}
    for k, v in incoming.items():
        old = getattr(survey, k)
        if _values_different(old, v):
            before[k] = old
            after[k] = v
        # 仍然赋值，确保更新
        setattr(survey, k, v)
    survey.updated_at = datetime.utcnow()
    db.commit()
    # audit（仅当有真实变更时记录）
    try:
        if after:
            changed = []
            for k in after.keys():
                changed.append({
                    "field": k,
                    "label": FIELD_LABELS.get(k, k),
                    "before": _fmt_val(before.get(k)),
                    "after": _fmt_val(after.get(k)),
                })
            _audit(
                db, survey.id, "update", current_user.id,
                details={
                    "before": _jsonify_dict(before),
                    "after": _jsonify_dict(after),
                    "changed": changed,
                    "changed_keys": list(after.keys()),
                }
            )
            db.commit()
    except Exception:
        db.rollback()
    db.refresh(survey)
    return survey


@router.delete("/{survey_id}")
async def delete_survey(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="勘察记录不存在")

    # 删除文件
    for p in list(survey.photos or []):
        try:
            if p.file_path and os.path.exists(p.file_path):
                os.remove(p.file_path)
        except Exception:
            pass
    db.delete(survey)
    db.commit()
    # audit
    try:
        _audit(db, survey_id, "delete", current_user.id, details={"site_id": survey.site_id})
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True}


@router.post("/{survey_id}/photos", response_model=SiteSurveyPhotoResponse)
async def upload_photo(
    survey_id: str,
    file: UploadFile = File(...),
    category: Optional[str] = Form(None),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    taken_at: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="勘察记录不存在")

    stored_path = await save_uploaded_file(file, category="site_surveys", sub_folder=survey_id)
    file_hash = calculate_file_hash(stored_path)

    # Process images: compress + simple watermark; extract exif
    is_image = (file.content_type or '').startswith('image/')
    raw_exif = None
    if is_image:
        try:
            # Compress
            stored_path = await compress_image(stored_path)
            # Add watermark (user, time)
            wm_text = f"Survey {survey_id} | {current_user.username} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            add_text_watermark_inline(stored_path, wm_text)
            # Extract EXIF
            raw_exif = extract_exif(stored_path)
        except Exception:
            raw_exif = None

    taken_dt: Optional[datetime] = None
    if taken_at:
        try:
            taken_dt = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except Exception:
            taken_dt = None

    # Auto taken_at from EXIF if not provided
    if not taken_dt and isinstance(raw_exif, dict):
        dt_str = raw_exif.get('DateTimeOriginal') or raw_exif.get('DateTime')
        if isinstance(dt_str, str):
            try:
                # EXIF format "YYYY:MM:DD HH:MM:SS"
                dt_fmt = dt_str.replace(':', '-', 2)
                taken_dt = datetime.fromisoformat(dt_fmt)
            except Exception:
                taken_dt = None

    # Determine next sort_order
    max_order = db.query(func.max(SiteSurveyPhoto.sort_order)).filter(SiteSurveyPhoto.survey_id == survey_id).scalar()
    next_order = (max_order or 0) + 1

    photo = SiteSurveyPhoto(
        id=uuid.uuid4().hex,
        survey_id=survey_id,
        original_name=file.filename,
        file_path=stored_path,
        file_size=None,
        mime_type=file.content_type,
        category=category,
        sort_order=next_order,
        latitude=latitude,
        longitude=longitude,
        gps_accuracy=gps_accuracy,
        address=address,
        taken_at=taken_dt,
        hash_value=file_hash,
        uploaded_by=current_user.id,
    )
    try:
        if os.path.exists(stored_path):
            photo.file_size = os.path.getsize(stored_path)
    except Exception:
        pass

    # Persist EXIF json if available
    if raw_exif:
        try:
            photo.exif = raw_exif
        except Exception:
            pass
    db.add(photo)
    db.commit()
    # audit
    try:
        _audit(db, survey_id, "photo_upload", current_user.id, details={
            "photo_id": photo.id,
            "category": category,
            "mime_type": file.content_type,
            "original_name": file.filename,
        })
        db.commit()
    except Exception:
        db.rollback()
    db.refresh(photo)
    return photo


@router.get("/{survey_id}/photos", response_model=List[SiteSurveyPhotoResponse])
async def list_photos(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    photos = (
        db.query(SiteSurveyPhoto)
        .filter(SiteSurveyPhoto.survey_id == survey_id)
        .order_by(SiteSurveyPhoto.sort_order.asc().nulls_last(), SiteSurveyPhoto.created_at.asc())
        .all()
    )
    return photos


@router.delete("/photos/{photo_id}")
async def delete_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    p = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.id == photo_id).first()
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="照片不存在")
    try:
        if p.file_path and os.path.exists(p.file_path):
            os.remove(p.file_path)
    except Exception:
        pass
    # capture for audit
    details = {"photo_id": p.id, "category": p.category, "original_name": p.original_name}
    db.delete(p)
    db.commit()
    try:
        _audit(db, p.survey_id, "photo_delete", current_user.id, details=details)
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True}




@router.get("/{survey_id}/export")
async def export_survey_zip(
    survey_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="勘察记录不存在")

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # JSON summary
        summary = {
            "id": survey.id,
            "site_id": survey.site_id,
            "site_name": survey.site.site_name if survey.site else None,
            "survey_date": survey.survey_date.isoformat() if survey.survey_date else None,
            "surveyor_name": survey.surveyor_name,
            "feasibility": survey.feasibility,
            "latitude": survey.latitude,
            "longitude": survey.longitude,
            "address": survey.address,
            "risks": survey.risks,
            "recommendations": survey.recommendations,
        }
        zf.writestr("summary.json", __import__("json").dumps(summary, ensure_ascii=False, indent=2))

        # CSV
        csv_buf = io.StringIO()
        writer = csv.writer(csv_buf)
        writer.writerow(["key", "value"])
        for k, v in summary.items():
            writer.writerow([k, v])
        zf.writestr("summary.csv", csv_buf.getvalue())

        # Photos
        photos = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == survey_id).all()
        for p in photos:
            if p.file_path and os.path.exists(p.file_path):
                # put under photos/{category}/filename
                base_name = os.path.basename(p.file_path)
                subdir = f"photos/{p.category or 'uncategorized'}"
                arcname = f"{subdir}/{base_name}"
                zf.write(p.file_path, arcname=arcname)

    mem_zip.seek(0)
    filename = f"site_survey_{survey_id}.zip"
    return StreamingResponse(mem_zip, media_type="application/zip", headers={"Content-Disposition": f"attachment; filename={filename}"})


@router.get("/export-batch")
async def export_batch_zip(
    keyword: Optional[str] = None,
    site_id: Optional[int] = None,
    feasibility: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    include_photos: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Build query
    query = db.query(SiteSurvey).join(Site, Site.id == SiteSurvey.site_id)
    if site_id:
        query = query.filter(SiteSurvey.site_id == site_id)
    if feasibility:
        query = query.filter(SiteSurvey.feasibility == feasibility)
    if date_from:
        query = query.filter(SiteSurvey.survey_date >= date_from)
    if date_to:
        query = query.filter(SiteSurvey.survey_date <= date_to)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(or_(
            Site.site_name.like(kw),
            Site.site_code.like(kw),
            SiteSurvey.surveyor_name.like(kw),
            SiteSurvey.feasibility.like(kw)
        ))

    rows = query.order_by(SiteSurvey.created_at.desc()).all()

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        index_csv = io.StringIO()
        writer = csv.writer(index_csv)
        writer.writerow(["survey_id", "site_code", "site_name", "survey_date", "surveyor_name", "feasibility"]) 

        if not rows:
            # 写入空索引与说明文件，返回空包而非404
            zf.writestr("index.csv", index_csv.getvalue())
            zf.writestr("README.txt", "No survey records matched the export filters.")
        else:
            for s in rows:
                site_code = s.site.site_code if s.site else ''
                site_name = s.site.site_name if s.site else ''
                survey_folder = f"{site_code or 'site'}/{s.id}"

            summary = {
                "id": s.id,
                "site_id": s.site_id,
                "site_code": site_code,
                "site_name": site_name,
                "survey_date": s.survey_date.isoformat() if s.survey_date else None,
                "surveyor_name": s.surveyor_name,
                "feasibility": s.feasibility,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "address": s.address,
                "risks": s.risks,
                "recommendations": s.recommendations,
            }
            zf.writestr(f"{survey_folder}/summary.json", __import__("json").dumps(summary, ensure_ascii=False, indent=2))

            csv_buf = io.StringIO()
            w = csv.writer(csv_buf)
            for k, v in summary.items():
                w.writerow([k, v])
            zf.writestr(f"{survey_folder}/summary.csv", csv_buf.getvalue())

            writer.writerow([
                s.id, site_code, site_name, summary["survey_date"], s.surveyor_name, s.feasibility
            ])

            if include_photos:
                photos = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == s.id).all()
                for p in photos:
                    if p.file_path and os.path.exists(p.file_path):
                        base = os.path.basename(p.file_path)
                        pdir = f"{survey_folder}/photos/{p.category or 'uncategorized'}"
                        zf.write(p.file_path, arcname=f"{pdir}/{base}")

            zf.writestr("index.csv", index_csv.getvalue())

    mem_zip.seek(0)
    return StreamingResponse(mem_zip, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=site_surveys_batch.zip"})


@router.get("/{survey_id}/audit-logs")
async def get_survey_audit_logs(
    survey_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 允许所有已登录用户查看此勘察的审计历史
    logs = (
        db.query(AuditEvent)
        .filter(AuditEvent.resource_type == "site_survey", AuditEvent.resource_id.in_([survey_id, "bulk"]))
        .order_by(AuditEvent.created_at.desc())
        .offset(skip).limit(limit).all()
    )
    data = []
    for ev in logs:
        op = ev.operator
        data.append({
            "id": ev.id,
            "action": ev.action,
            "operator_id": ev.operator_id,
            "operator_name": (op.full_name or op.username) if op else None,
            "comments": ev.comments,
            "details": ev.details,
            "created_at": ev.created_at,
        })
    return data

@router.put("/photos/{photo_id}", response_model=SiteSurveyPhotoResponse)
async def update_photo_metadata(
    photo_id: str,
    category: Optional[str] = Form(None),
    taken_at: Optional[str] = Form(None),
    sort_order: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    p = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.id == photo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="照片不存在")
    before = {"category": p.category, "taken_at": p.taken_at.isoformat() if p.taken_at else None, "sort_order": p.sort_order}
    if category is not None:
        p.category = category
    if sort_order is not None:
        p.sort_order = sort_order
    if taken_at:
        try:
            p.taken_at = datetime.fromisoformat(taken_at.replace("Z", "+00:00"))
        except Exception:
            pass
    db.commit()
    db.refresh(p)
    after = {"category": p.category, "taken_at": p.taken_at.isoformat() if p.taken_at else None, "sort_order": p.sort_order}
    try:
        # Build changed list for readability
        changed = []
        for k in after.keys():
            if before.get(k) != after.get(k):
                lbl = {"category": "分类", "taken_at": "拍摄时间", "sort_order": "显示顺序"}.get(k, k)
                changed.append({"field": k, "label": lbl, "before": before.get(k), "after": after.get(k)})
        _audit(db, p.survey_id, "photo_update", current_user.id, details={"before": before, "after": after, "photo_id": p.id, "changed": changed, "changed_keys": [c["field"] for c in changed]})
        db.commit()
    except Exception:
        db.rollback()
    return p


@router.put("/{survey_id}/photos/reorder")
async def reorder_photos(
    survey_id: str,
    orders: List[str] = Form(...),  # list of photo_ids in desired order
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    photos = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == survey_id).all()
    id_to_photo = {p.id: p for p in photos}
    for idx, pid in enumerate(orders, start=1):
        if pid in id_to_photo:
            id_to_photo[pid].sort_order = idx
    db.commit()
    try:
        _audit(db, survey_id, "photo_reorder", current_user.id, details={"orders": orders})
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True}


@router.post("/{survey_id}/photos/batch")
async def upload_photos_batch(
    survey_id: str,
    files: List[UploadFile] = File(...),
    category: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    results = []
    for f in files:
        # Reuse single upload flow by calling within same request logic
        stored_path = await save_uploaded_file(f, category="site_surveys", sub_folder=survey_id)
        file_hash = calculate_file_hash(stored_path)
        is_image = (f.content_type or '').startswith('image/')
        raw_exif = None
        if is_image:
            try:
                stored_path = await compress_image(stored_path)
                wm_text = f"Survey {survey_id} | {current_user.username} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
                add_text_watermark_inline(stored_path, wm_text)
                raw_exif = extract_exif(stored_path)
            except Exception:
                raw_exif = None
        max_order = db.query(func.max(SiteSurveyPhoto.sort_order)).filter(SiteSurveyPhoto.survey_id == survey_id).scalar()
        next_order = (max_order or 0) + 1
        p = SiteSurveyPhoto(
            id=uuid.uuid4().hex,
            survey_id=survey_id,
            original_name=f.filename,
            file_path=stored_path,
            file_size=os.path.getsize(stored_path) if os.path.exists(stored_path) else None,
            mime_type=f.content_type,
            category=category,
            sort_order=next_order,
            has_watermark=is_image,
            hash_value=file_hash,
            uploaded_by=current_user.id,
        )
        if raw_exif:
            p.exif = raw_exif
        db.add(p)
        results.append({"id": p.id, "file_path": p.file_path, "category": p.category})
    db.commit()
    try:
        _audit(db, survey_id, "photo_batch_upload", current_user.id, details={"count": len(results), "items": results[:10]})
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True, "count": len(results), "items": results}


@router.delete("/{survey_id}/photos")
async def delete_photos_batch(
    survey_id: str,
    photo_ids: List[str] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    _require_admin(current_user)
    photos = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.survey_id == survey_id, SiteSurveyPhoto.id.in_(photo_ids)).all()
    deleted = []
    for p in photos:
        try:
            if p.file_path and os.path.exists(p.file_path):
                os.remove(p.file_path)
        except Exception:
            pass
        deleted.append({"photo_id": p.id, "category": p.category, "original_name": p.original_name})
        db.delete(p)
    db.commit()
    try:
        _audit(db, survey_id, "photo_batch_delete", current_user.id, details={"count": len(deleted), "items": [x["photo_id"] for x in deleted]})
        db.commit()
    except Exception:
        db.rollback()
    return {"success": True, "deleted": len(photos)}


@router.get("/photos/{photo_id}/exif")
async def get_photo_exif(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    p = db.query(SiteSurveyPhoto).filter(SiteSurveyPhoto.id == photo_id).first()
    if not p:
        raise HTTPException(status_code=404, detail="照片不存在")
    data = p.exif or {}
    return data


@router.get("/{survey_id}/export-pdf")
async def export_survey_pdf(
    survey_id: str,
    with_thumbs: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.units import cm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    except Exception:
        raise HTTPException(status_code=500, detail="后端缺少 reportlab 依赖，请先安装")

    survey = db.query(SiteSurvey).filter(SiteSurvey.id == survey_id).first()
    if not survey:
        raise HTTPException(status_code=404, detail="勘察记录不存在")

    # Register Chinese-capable fonts
    def register_cn_fonts() -> tuple[str, str]:
        fonts_dir = os.path.join("backend", "fonts")
        candidates = [
            ("NotoSansSC-Regular.ttf", "NotoSansSC-Bold.ttf"),
            ("SourceHanSansSC-Regular.ttf", "SourceHanSansSC-Bold.ttf"),
            ("NotoSansCJKsc-Regular.otf", "NotoSansCJKsc-Bold.otf"),
        ]
        for reg, bold in candidates:
            reg_p = os.path.join(fonts_dir, reg)
            bold_p = os.path.join(fonts_dir, bold)
            if os.path.exists(reg_p):
                try:
                    pdfmetrics.registerFont(TTFont("CN", reg_p))
                    if os.path.exists(bold_p):
                        pdfmetrics.registerFont(TTFont("CN-Bold", bold_p))
                    else:
                        pdfmetrics.registerFont(TTFont("CN-Bold", reg_p))
                    return "CN", "CN-Bold"
                except Exception:
                    pass
        # Fallback to built-in CID font (no embedding, but wide coverage)
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            return "STSong-Light", "STSong-Light"
        except Exception:
            # final fallback to Helvetica (may break CJK)
            return "Helvetica", "Helvetica-Bold"

    FONT_MAIN, FONT_BOLD = register_cn_fonts()
    primary = colors.HexColor("#F56C3A")  # Orange primary
    accent_bg = colors.HexColor("#FFF6F0")  # Light orange
    text_color = colors.HexColor("#333333")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=1.8*cm
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCN", fontName=FONT_BOLD, fontSize=24, leading=30, textColor=primary))
    styles.add(ParagraphStyle(name="H2CN", fontName=FONT_BOLD, fontSize=16, leading=22, textColor=primary, spaceBefore=6, spaceAfter=8))
    styles.add(ParagraphStyle(name="BodyCN", fontName=FONT_MAIN, fontSize=11, leading=16, textColor=text_color))
    styles.add(ParagraphStyle(name="MetaCN", fontName=FONT_MAIN, fontSize=10, leading=14, textColor=colors.HexColor('#666666')))
    styles.add(ParagraphStyle(name="CaptionCN", fontName=FONT_MAIN, fontSize=9, leading=12, textColor=colors.HexColor('#666666'), alignment=1))

    def draw_page_frame(c, d):
        c.saveState()
        # Header bar
        c.setFillColor(primary)
        c.rect(0, A4[1]-1.2*cm, A4[0], 1.2*cm, stroke=0, fill=1)
        c.setFillColor(colors.white)
        c.setFont(FONT_BOLD, 12)
        c.drawString(2*cm, A4[1]-0.85*cm, "站点勘察报告 Site Survey Report")
        # Footer line and page number
        c.setStrokeColor(primary)
        c.setLineWidth(0.6)
        c.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        c.setFont(FONT_MAIN, 9)
        c.setFillColor(colors.HexColor('#888888'))
        c.drawRightString(A4[0]-2*cm, 1.1*cm, f"第 {d.page} 页")
        c.restoreState()

    elements: list = []

    # Cover
    elements.append(Spacer(1, 4*cm))
    elements.append(Paragraph("站点勘察报告", styles["TitleCN"]))
    elements.append(Spacer(1, 0.6*cm))
    site_name = survey.site.site_name if survey.site else ""
    site_code = survey.site.site_code if survey.site else ""
    elements.append(Paragraph(f"{site_name} ({site_code})", styles["BodyCN"]))
    elements.append(Spacer(1, 0.2*cm))
    meta = [
        f"勘察日期：{survey.survey_date.strftime('%Y-%m-%d %H:%M') if survey.survey_date else '-'}",
        f"勘察人：{survey.surveyor_name or '-'}",
        f"结论：{survey.feasibility or '-'}",
        f"坐标：{(survey.latitude or '-')}, {(survey.longitude or '-')}",
        f"地址：{survey.address or '-'}",
    ]
    for m in meta:
        elements.append(Paragraph(m, styles["MetaCN"]))
    elements.append(PageBreak())

    # Summary section as a key-value table
    elements.append(Paragraph("概览", styles["H2CN"]))
    kv = [
        ("站点名称", site_name),
        ("站点编码", site_code),
        ("勘察日期", survey.survey_date.strftime('%Y-%m-%d %H:%M') if survey.survey_date else "-"),
        ("勘察人", survey.surveyor_name or "-"),
        ("结论", survey.feasibility or "-"),
        ("地址", survey.address or "-"),
        ("坐标", f"{survey.latitude or ''}, {survey.longitude or ''}"),
        ("风险", survey.risks or "-"),
        ("建议", survey.recommendations or "-"),
    ]
    data = [[Paragraph(f"<b>{k}</b>", styles["BodyCN"]), Paragraph(v, styles["BodyCN"])] for k, v in kv]
    table = Table(data, colWidths=[3*cm, 12*cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,-1), colors.white),
        ("ROWBACKGROUNDS", (0,0), (-1,-1), [colors.white, accent_bg]),
        ("TEXTCOLOR", (0,0), (0,-1), primary),
        ("LINEBELOW", (0,0), (-1,-1), 0.25, colors.HexColor('#eeeeee')),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 6),
        ("RIGHTPADDING", (0,0), (-1,-1), 6),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
    ]))
    elements.append(table)

    # Photos grid
    photos = (
        db.query(SiteSurveyPhoto)
        .filter(SiteSurveyPhoto.survey_id == survey_id)
        .order_by(SiteSurveyPhoto.sort_order.asc().nulls_last(), SiteSurveyPhoto.created_at.asc())
        .all()
    )
    if photos:
        elements.append(Spacer(1, 0.6*cm))
        elements.append(Paragraph("照片索引", styles["H2CN"]))
        row: list = []
        grid: list = []
        for idx, p in enumerate(photos, start=1):
            if not p.file_path or not os.path.exists(p.file_path):
                continue
            try:
                img = Image(p.file_path, width=7.4*cm, height=5.0*cm)
                caption = Paragraph(f"{p.category or '未分类'} - {os.path.basename(p.file_path)}", styles["CaptionCN"])
                cell = Table([[img],[caption]], colWidths=[7.4*cm])
                cell.setStyle(TableStyle([
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ]))
                row.append(cell)
                if len(row) == 2:
                    grid.append(row)
                    row = []
            except Exception:
                continue
        if row:
            # fill last row
            row.append(Spacer(7.4*cm, 0))
            grid.append(row)
        if grid:
            grid_table = Table(grid, colWidths=[7.6*cm, 7.6*cm], hAlign='LEFT', spaceBefore=6)
            grid_table.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING", (0,0), (-1,-1), 4),
                ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("TOPPADDING", (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ]))
            elements.append(grid_table)

    # Build
    doc.build(elements, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename=site_survey_{survey_id}.pdf"})
