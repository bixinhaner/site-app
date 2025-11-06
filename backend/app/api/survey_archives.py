from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.survey_archive import SiteSurveyArchive, SiteSurveyArchiveVersion, SiteSurveyArchiveKVIndex
from app.services.survey_archive_service import (
    create_or_append_archive,
    patch_archive,
    make_diff,
    revert_to_version,
    reindex_kv,
)
from app.utils.file_handler import save_uploaded_file, calculate_file_hash, extract_exif, compress_image, add_text_watermark_inline
from datetime import datetime
import os
import uuid
import jsonpatch


router = APIRouter()


def _require_editor(u: User):
    if getattr(u, "role", None) not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员或经理权限")


@router.get("/page")
def page_archives(
    page: int = 1,
    page_size: int = 20,
    site_id: Optional[int] = None,
    template_id: Optional[str] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SiteSurveyArchive).join(Site, Site.id == SiteSurveyArchive.site_id)
    if site_id:
        q = q.filter(SiteSurveyArchive.site_id == site_id)
    if template_id:
        q = q.filter(SiteSurveyArchive.template_id == template_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter((Site.site_name.like(kw)) | (Site.site_code.like(kw)))

    total = q.count()
    rows = (
        q.order_by(SiteSurveyArchive.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for a in rows:
        items.append({
            "id": a.id,
            "site_id": a.site_id,
            "site_name": a.site.site_name if a.site else None,
            "site_code": a.site.site_code if a.site else None,
            "work_order_id": a.work_order_id,
            "inspection_id": a.inspection_id,
            "template_id": a.template_id,
            "template_version": a.template_version,
            "current_version": a.current_version,
            "updated_at": a.updated_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{archive_id}")
def get_archive(
    archive_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")
    return {
        "id": a.id,
        "site_id": a.site_id,
        "work_order_id": a.work_order_id,
        "inspection_id": a.inspection_id,
        "template_id": a.template_id,
        "template_version": a.template_version,
        "current_version": a.current_version,
        "content": a.content,
        "updated_at": a.updated_at,
    }


@router.get("/{archive_id}/history")
def list_history(
    archive_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vers = db.query(SiteSurveyArchiveVersion).filter(
        SiteSurveyArchiveVersion.archive_id == archive_id
    ).order_by(SiteSurveyArchiveVersion.version.asc()).all()

    def _get(ci: int, ii: int, content: dict):
        cats = (content or {}).get('check_categories') or []
        if not isinstance(ci, int) or ci < 0 or ci >= len(cats):
            return None, None, None
        cat = cats[ci]
        items = cat.get('items') or []
        if not isinstance(ii, int) or ii < 0 or ii >= len(items):
            return cat, None, None
        item = items[ii]
        fields = {f.get('field_id'): f for f in (item.get('fields') or [])}
        return cat, item, fields

    def _unescape(s: str) -> str:
        return str(s).replace('~1', '/').replace('~0', '~')

    results = []
    prev_content = None
    for v in vers:
        # 统计与细粒度明细
        field_changes = 0
        photo_adds = 0
        photo_removes = 0
        lines = []

        try:
            for op in (v.diff or []):
                path = str(op.get('path', ''))
                typ = str(op.get('op', '')).lower()
                # 值变更：/check_categories/{ci}/items/{ii}/values/{field}
                if '/values/' in path and typ in ('replace', 'add'):
                    try:
                        parts = [p for p in path.split('/') if p]
                        ci = int(parts[1]); ii = int(parts[3]); fid = _unescape(parts[5])
                        cat, item, fields = _get(ci, ii, v.content)
                        # label 信息
                        cat_name = (cat or {}).get('category_name') or (cat or {}).get('category_id') or str(ci)
                        item_name = (item or {}).get('item_name') or (item or {}).get('item_id') or str(ii)
                        field_label = (fields or {}).get(fid, {}).get('label') or fid
                        # 旧值从上一版本读取
                        old_val = None
                        if prev_content:
                            try:
                                pc = (prev_content or {}).get('check_categories') or []
                                pit = (((pc[ci] or {}).get('items') or [])[ii] or {})
                                old_val = ((pit.get('values') or {}).get(fid))
                            except Exception:
                                old_val = None
                        new_val = (item or {}).get('values', {}).get(fid)
                        field_changes += 1
                        # 友好格式化
                        def fmt(vv):
                            if vv is None or vv == '':
                                return '-'
                            if isinstance(vv, bool):
                                return '是' if vv else '否'
                            return vv
                        lines.append(f"{cat_name}/{item_name}/{field_label}：{fmt(old_val)} → {fmt(new_val)}")
                    except Exception:
                        field_changes += 1
                        continue
                # 照片变更：/check_categories/{ci}/items/{ii}/photos
                elif '/photos' in path:
                    try:
                        parts = [p for p in path.split('/') if p]
                        ci = int(parts[1]); ii = int(parts[3])
                        cat, item, _ = _get(ci, ii, v.content)
                        cat_name = (cat or {}).get('category_name') or (cat or {}).get('category_id') or str(ci)
                        item_name = (item or {}).get('item_name') or (item or {}).get('item_id') or str(ii)
                        if typ == 'add':
                            val = op.get('value', None)
                            cnt = len(val) if isinstance(val, list) else 1
                            photo_adds += cnt
                            lines.append(f"{cat_name}/{item_name}：新增照片 {cnt} 张")
                        elif typ == 'remove':
                            photo_removes += 1
                            lines.append(f"{cat_name}/{item_name}：删除照片 1 张")
                    except Exception:
                        # ignore
                        pass
        except Exception:
            pass

        # 形成摘要
        parts = []
        if field_changes:
            parts.append(f"更新了 {field_changes} 个字段")
        if photo_adds:
            parts.append(f"上传照片 {photo_adds} 张")
        if photo_removes:
            parts.append(f"删除照片 {photo_removes} 张")
        summary = '；'.join(parts) if parts else (v.change_summary or ('创建档案' if v.version == 1 else '用户编辑'))

        results.append({
            "version": v.version,
            "changed_by": v.changed_by,
            "operator_name": getattr(getattr(v, 'changer', None), 'full_name', None),
            "changed_at": v.changed_at,
            "summary": summary,
            "change_summary": v.change_summary,
            "details": lines,
            "stats": {
                "field_changes": field_changes,
                "photo_adds": photo_adds,
                "photo_removes": photo_removes,
            }
        })

        prev_content = v.content

    # 按时间倒序返回（最新在前）
    results.sort(key=lambda r: (r.get('changed_at') or 0, r.get('version') or 0), reverse=True)
    return results


@router.get("/{archive_id}/diff")
def diff_versions(
    archive_id: str,
    a: int,
    b: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return make_diff(db, archive_id, a, b)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{archive_id}/revert")
def revert(
    archive_id: str,
    to_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_editor(current_user)
    try:
        arc = revert_to_version(db, archive_id=archive_id, to_version=to_version, operator_id=current_user.id)
        db.commit()
        return {"id": arc.id, "current_version": arc.current_version}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{archive_id}/photos/temp")
async def upload_temp_photo(
    archive_id: str,
    category_id: str = Form(...),
    item_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仅上传文件到存储并返回元数据，不修改档案内容、不生成版本。

    前端可在编辑态下调用该接口完成预上传，并在点击“保存”时通过 PATCH 一次性将照片对象追加到内容中。
    """
    _require_editor(current_user)

    # 确认档案存在
    arc = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 存储文件（与正式上传保持一致的处理流程：压缩 + 水印）
    stored_path = await save_uploaded_file(file, category="survey_archives", sub_folder=archive_id)
    file_hash = calculate_file_hash(stored_path)
    is_image = (file.content_type or '').startswith('image/')
    if is_image:
        try:
            _ = extract_exif(stored_path)
            stored_path = await compress_image(stored_path)
            wm_text = f"Archive {archive_id} | {current_user.username} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            add_text_watermark_inline(stored_path, wm_text)
        except Exception:
            pass
    file_size = os.path.getsize(stored_path) if os.path.exists(stored_path) else None

    # 返回一个可直接写入 content.photos 的对象（但不落库）
    return {
        "id": uuid.uuid4().hex,
        "file_path": stored_path,
        "file_size": file_size,
        "mime_type": file.content_type,
        "hash_value": file_hash,
        "uploaded_by": current_user.id,
        "taken_at": None,
        "_temp": True,
        "category_id": category_id,
        "item_id": item_id,
    }


@router.patch("/{archive_id}")
def patch(
    archive_id: str,
    patch_ops: List[Dict[str, Any]] = Body(...),
    base_version: Optional[int] = None,
    change_summary: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_editor(current_user)
    try:
        arc = patch_archive(
            db,
            archive_id=archive_id,
            base_version=base_version,
            patch_ops=patch_ops,
            operator_id=current_user.id,
            change_summary=change_summary,
        )
        db.commit()
        return {"id": arc.id, "current_version": arc.current_version}
    except RuntimeError as e:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


# 审核通过时调用的创建/追加接口只供内部服务使用，不暴露为公共API


@router.post("/{archive_id}/photos")
async def upload_photo(
    archive_id: str,
    category_id: str = Form(...),
    item_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传照片并追加到指定项的 photos。生成一个版本。"""
    _require_editor(current_user)

    arc = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 存储文件
    stored_path = await save_uploaded_file(file, category="survey_archives", sub_folder=archive_id)
    file_hash = calculate_file_hash(stored_path)
    is_image = (file.content_type or '').startswith('image/')
    if is_image:
        try:
            _ = extract_exif(stored_path)
            stored_path = await compress_image(stored_path)
            wm_text = f"Archive {archive_id} | {current_user.username} | {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}"
            add_text_watermark_inline(stored_path, wm_text)
        except Exception:
            pass
    file_size = os.path.getsize(stored_path) if os.path.exists(stored_path) else None

    # 生成新内容
    old = arc.content
    new = jsonpatch.apply_patch(old, [], in_place=False)  # 深拷贝

    # 定位到指定项
    found = False
    for cat in new.get("check_categories", []) or []:
        if str(cat.get("category_id")) != str(category_id):
            continue
        for it in cat.get("items", []) or []:
            if str(it.get("item_id")) != str(item_id):
                continue
            it.setdefault("photos", []).append({
                "id": uuid.uuid4().hex,
                "file_path": stored_path,
                "file_size": file_size,
                "mime_type": file.content_type,
                "hash_value": file_hash,
                "uploaded_by": current_user.id,
                "taken_at": None,
            })
            found = True
            break
    if not found:
        raise HTTPException(status_code=400, detail="未找到对应的分类/检查项")

    patch_ops = jsonpatch.make_patch(old, new).patch
    try:
        arc = patch_archive(
            db,
            archive_id=archive_id,
            base_version=arc.current_version,
            patch_ops=patch_ops,
            operator_id=current_user.id,
            change_summary=f"上传照片到 {category_id}/{item_id}",
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": arc.id, "current_version": arc.current_version}


@router.delete("/{archive_id}/photos/{photo_id}")
def delete_photo(
    archive_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_editor(current_user)
    arc = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    old = arc.content
    new = jsonpatch.apply_patch(old, [], in_place=False)
    removed = False
    for cat in new.get("check_categories", []) or []:
        for it in cat.get("items", []) or []:
            photos = it.get("photos") or []
            for i, p in enumerate(list(photos)):
                if str(p.get("id")) == str(photo_id):
                    photos.pop(i)
                    removed = True
                    break
            if removed:
                break
        if removed:
            break
    if not removed:
        raise HTTPException(status_code=404, detail="照片不存在于档案内容中")

    patch_ops = jsonpatch.make_patch(old, new).patch
    try:
        arc = patch_archive(
            db,
            archive_id=archive_id,
            base_version=arc.current_version,
            patch_ops=patch_ops,
            operator_id=current_user.id,
            change_summary="删除照片",
        )
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return {"id": arc.id, "current_version": arc.current_version}


@router.post("/{archive_id}/reindex")
def rebuild_index(
    archive_id: str,
    version: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_editor(current_user)
    a = db.query(SiteSurveyArchive).filter(SiteSurveyArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")
    ver = int(version or a.current_version or 1)
    v = db.query(SiteSurveyArchiveVersion).filter(
        SiteSurveyArchiveVersion.archive_id == archive_id,
        SiteSurveyArchiveVersion.version == ver,
    ).first()
    content = (v.content if v else a.content)
    try:
        n = reindex_kv(db, archive_id, ver, content)
        db.commit()
        return {"reindexed": n, "version": ver}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/search")
def search_kv(
    path_prefix: Optional[str] = None,
    keyword: Optional[str] = None,
    site_id: Optional[int] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(SiteSurveyArchiveKVIndex).join(
        SiteSurveyArchive, SiteSurveyArchive.id == SiteSurveyArchiveKVIndex.archive_id
    )
    if path_prefix:
        like = f"{path_prefix}%"
        q = q.filter(SiteSurveyArchiveKVIndex.path.like(like))
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter((SiteSurveyArchiveKVIndex.value_string.like(kw)) | (SiteSurveyArchiveKVIndex.raw_json.isnot(None)))
    if site_id:
        q = q.filter(SiteSurveyArchive.site_id == site_id)
    rows = q.order_by(SiteSurveyArchiveKVIndex.updated_at.desc()).limit(limit).all()
    return [
        {
            "archive_id": r.archive_id,
            "version": r.version,
            "path": r.path,
            "label": r.field_label,
            "type": r.type,
            "value_string": r.value_string,
            "value_number": r.value_number,
            "value_bool": r.value_bool,
            "value_datetime": r.value_datetime,
        }
        for r in rows
    ]


@router.post("/rebuild-for-work-order/{work_order_id}")
def rebuild_for_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """为指定工单（需为勘察类且已产生 inspection_id）创建/追加档案。"""
    _require_editor(current_user)
    from app.models.work_order import WorkOrder, WorkOrderTypeEnum
    from app.models.inspection import SiteInspection
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.type not in [WorkOrderTypeEnum.SITE_SURVEY]:
        raise HTTPException(status_code=400, detail="仅支持勘察类工单重建档案")
    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未创建检查记录(inspection)")
    try:
        arc = create_or_append_archive(
            db,
            inspection_id=wo.inspection_id,
            operator_id=current_user.id,
            change_summary="手动重建档案",
        )
        db.commit()
        return {"archive_id": arc.id, "current_version": arc.current_version}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
