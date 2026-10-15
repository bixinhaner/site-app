"""档案批量导出 PDF 接口：导出前预估、创建后台任务、查询进度、分卷下载 zip。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.auth import get_current_user
from app.core.database import SessionLocal, get_db
from app.models.user import User
from app.services import archive_batch_export as batch

router = APIRouter()


def _selection(payload: dict) -> dict:
    """ids：勾选的档案；filters：按列表页筛选条件导出全部（keyword/date_from/date_to）。"""
    filters = payload.get("filters")
    return {
        "archive_type": str(payload.get("archive_type") or ""),
        "ids": None if isinstance(filters, dict) else payload.get("ids"),
        "filters": filters if isinstance(filters, dict) else None,
    }


@router.post("/preview")
def preview_batch_export(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出前预估数量、已生成/待生成、大小、分卷和耗时，供用户确认；不生成文件。"""
    try:
        return batch.preview(db, locale=payload.get("locale"), **_selection(payload))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("")
def create_batch_export(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """用户确认后创建导出任务；任务在后台排队执行，前端轮询进度。"""
    try:
        return batch.create_job(
            db,
            locale=payload.get("locale"),
            user_id=current_user.id,
            session_factory=SessionLocal,
            **_selection(payload),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{job_id}")
def get_batch_export(job_id: str, current_user: User = Depends(get_current_user)):
    job = batch.get_job(job_id)
    if not job or (job["user_id"] != current_user.id and not current_user.is_admin):
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    return batch.public_job(job)


@router.get("/{job_id}/download")
def download_batch_export(job_id: str, part: int = Query(1, ge=1)):
    """浏览器直接下载（无法携带登录头）：job_id 为随机令牌，仅创建者可见，6 小时后失效。"""
    job = batch.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    if job["status"] != "done" or not job.get("parts"):
        raise HTTPException(status_code=400, detail="导出任务尚未完成")
    if part > len(job["parts"]):
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    name = batch.download_name(job, part)
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"}
    return StreamingResponse(batch.iter_part_zip(job, part), media_type="application/zip", headers=headers)
