from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, Optional

from sqlalchemy.orm import Session

from app.models.inspection import GlobalPhotoHashRegistry, InspectionPhoto
from app.utils.timezone import to_utc_iso


SOURCE_TYPE_LABELS = {
    "inspection_photo": "巡检检查项照片",
    "survey_archive_photo": "勘察档案检查项照片",
    "survey_archive_temp_photo": "勘察档案检查项照片(临时上传)",
    "opening_archive_photo": "开站档案检查项照片",
    "opening_archive_temp_photo": "开站档案检查项照片(临时上传)",
    "ssv_archive_photo": "SSV档案检查项照片",
    "ssv_archive_temp_photo": "SSV档案检查项照片(临时上传)",
}


def normalize_content_hash(content_hash: Optional[str]) -> str:
    return str(content_hash or "").strip().lower()


def _normalize_source_type(source_type: Optional[str]) -> str:
    return str(source_type or "").strip()


def _normalize_source_id(source_id: Optional[str]) -> str:
    return str(source_id or "").strip()


def _source_exists(db: Session, record: GlobalPhotoHashRegistry) -> bool:
    source_type = _normalize_source_type(record.source_type)
    source_id = _normalize_source_id(record.source_id)
    if not source_id:
        return False
    # 目前只对工单巡检照片做“来源是否仍存在”的强校验，避免误清理档案临时上传来源。
    if source_type != "inspection_photo":
        return True
    return (
        db.query(InspectionPhoto.id)
        .filter(InspectionPhoto.id == source_id)
        .first()
        is not None
    )


def delete_registry_records_by_source(
    db: Session,
    *,
    source_type: str,
    source_ids: Iterable[str],
) -> int:
    normalized_type = _normalize_source_type(source_type)
    normalized_ids = [_normalize_source_id(item) for item in source_ids]
    normalized_ids = [item for item in normalized_ids if item]
    if not normalized_type or not normalized_ids:
        return 0
    return (
        db.query(GlobalPhotoHashRegistry)
        .filter(
            GlobalPhotoHashRegistry.source_type == normalized_type,
            GlobalPhotoHashRegistry.source_id.in_(normalized_ids),
        )
        .delete(synchronize_session=False)
    )


def get_first_upload_record(db: Session, content_hash: Optional[str]) -> Optional[GlobalPhotoHashRegistry]:
    normalized_hash = normalize_content_hash(content_hash)
    if not normalized_hash:
        return None
    records = (
        db.query(GlobalPhotoHashRegistry)
        .filter(GlobalPhotoHashRegistry.content_hash == normalized_hash)
        .order_by(GlobalPhotoHashRegistry.id.asc())
        .all()
    )
    for record in records:
        if not _source_exists(db, record):
            db.delete(record)
            continue
        return record
    return None


def _build_duplicate_site_display(site_name: Optional[str], site_id: Optional[int]) -> str:
    if site_name and site_id is not None:
        return f"{site_name}(ID:{site_id})"
    if site_name:
        return site_name
    if site_id is not None:
        return f"站点ID:{site_id}"
    return "未知站点"


def _build_duplicate_uploader_display(uploader_name: Optional[str], uploader_id: Optional[int]) -> str:
    if uploader_name and uploader_id is not None:
        return f"{uploader_name}(ID:{uploader_id})"
    if uploader_name:
        return uploader_name
    if uploader_id is not None:
        return f"用户ID:{uploader_id}"
    return "未知用户"


def build_duplicate_info(record: GlobalPhotoHashRegistry) -> Dict[str, Any]:
    source_type = str(record.source_type or "").strip()
    source_type_label = SOURCE_TYPE_LABELS.get(source_type, source_type)
    uploaded_at_text = to_utc_iso(record.uploaded_at) if record.uploaded_at else None
    return {
        "content_hash": record.content_hash,
        "source_type": source_type,
        "source_type_label": source_type_label,
        "source_id": record.source_id,
        "site_id": record.site_id,
        "site_name": record.site_name,
        "uploader_id": record.uploader_id,
        "uploader_name": record.uploader_name,
        "uploaded_at": uploaded_at_text,
        "site_display": _build_duplicate_site_display(record.site_name, record.site_id),
        "uploader_display": _build_duplicate_uploader_display(record.uploader_name, record.uploader_id),
    }


def build_duplicate_message(info: Dict[str, Any], *, block_upload: bool) -> str:
    action = "已阻断上传" if block_upload else "未阻断，已提示风险"
    source_type_label = info.get("source_type_label") or info.get("source_type") or "未知来源"
    uploaded_at = info.get("uploaded_at") or "-"
    return (
        f"检测到重复图片，{action}。"
        f"首次上传记录：站点[{info.get('site_display')}]，"
        f"上传人[{info.get('uploader_display')}]，"
        f"时间[{uploaded_at}]，来源[{source_type_label}]。"
    )


def build_duplicate_detail(record: GlobalPhotoHashRegistry, *, block_upload: bool) -> Dict[str, Any]:
    info = build_duplicate_info(record)
    return {
        "code": "DUPLICATE_PHOTO",
        "message": build_duplicate_message(info, block_upload=block_upload),
        "block_upload": bool(block_upload),
        "duplicate": info,
    }


def detect_duplicate_detail(
    db: Session,
    *,
    content_hash: Optional[str],
    block_upload: bool,
    exclude_source_type: Optional[str] = None,
    exclude_source_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    normalized_hash = normalize_content_hash(content_hash)
    if not normalized_hash:
        return None
    records = (
        db.query(GlobalPhotoHashRegistry)
        .filter(GlobalPhotoHashRegistry.content_hash == normalized_hash)
        .order_by(GlobalPhotoHashRegistry.id.asc())
        .all()
    )
    if not records:
        return None

    exclude_type = _normalize_source_type(exclude_source_type)
    exclude_id = _normalize_source_id(exclude_source_id)

    for record in records:
        if not _source_exists(db, record):
            db.delete(record)
            continue

        if exclude_id:
            record_source_id = _normalize_source_id(record.source_id)
            source_type_match = True
            if exclude_type:
                source_type_match = _normalize_source_type(record.source_type) == exclude_type
            if source_type_match and record_source_id and record_source_id == exclude_id:
                return None
        return build_duplicate_detail(record, block_upload=block_upload)

    return None


def register_first_upload_record(
    db: Session,
    *,
    content_hash: Optional[str],
    source_type: str,
    source_id: str,
    site_id: Optional[int],
    site_name: Optional[str],
    uploader_id: Optional[int],
    uploader_name: Optional[str],
    uploaded_at: Optional[datetime] = None,
) -> Optional[GlobalPhotoHashRegistry]:
    normalized_hash = normalize_content_hash(content_hash)
    if not normalized_hash:
        return None

    existing = get_first_upload_record(db, normalized_hash)
    if existing:
        return existing

    record = GlobalPhotoHashRegistry(
        content_hash=normalized_hash,
        source_type=str(source_type or "").strip() or "unknown",
        source_id=str(source_id or "").strip() or "unknown",
        site_id=site_id,
        site_name=(str(site_name).strip() if site_name is not None else None),
        uploader_id=uploader_id,
        uploader_name=(str(uploader_name).strip() if uploader_name is not None else None),
        uploaded_at=uploaded_at or datetime.utcnow(),
    )
    db.add(record)
    db.flush()
    return record
