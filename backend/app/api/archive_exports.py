"""档案批量导出 PDF 接口：创建后台任务、查询进度、下载 zip。"""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.auth import get_current_user
from app.core.database import SessionLocal
from app.models.user import User
from app.services import archive_batch_export as batch

router = APIRouter()


@router.post("")
def create_batch_export(payload: dict, current_user: User = Depends(get_current_user)):
    """创建批量导出任务；任务在后台排队执行，前端轮询进度。"""
    try:
        return batch.create_job(
            archive_type=str(payload.get("archive_type") or ""),
            ids=payload.get("ids"),
            locale=payload.get("locale"),
            user_id=current_user.id,
            session_factory=SessionLocal,
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
def download_batch_export(job_id: str):
    """浏览器直接下载（无法携带登录头）：job_id 为随机令牌，仅创建者可见，1 小时后失效。"""
    job = batch.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="导出任务不存在或已过期")
    if job["status"] != "done" or not job.get("file_path") or not os.path.exists(job["file_path"]):
        raise HTTPException(status_code=400, detail="导出任务尚未完成")
    return FileResponse(job["file_path"], media_type="application/zip", filename=job["file_name"])
