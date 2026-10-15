"""档案批量导出 PDF：后台单线程逐个渲染，照片压缩后写入 PDF，再打包成 zip 临时文件供下载。

- 勘察/开站/SSV 三类档案共用，PDF 版式沿用各模块单个导出的 _render_archive_pdf。
- 开站档案原图中位数约 50~110 MB，批量导出把照片缩到长边 PHOTO_MAX_PX，单个 PDF 约 15~25 MB。
- 任务登记在进程内（生产为单个 uvicorn 进程），重启后未完成任务失效；文件 JOB_TTL_SECONDS 后清理。
- 全局只有一个工作线程，多个任务排队执行，避免批量渲染占满 CPU 影响正常使用。
"""

from __future__ import annotations

import hashlib
import importlib
import logging
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from app.i18n.error_localization import localize_text
from app.utils.archive_pdf import localized_text, normalize_locale

logger = logging.getLogger(__name__)

MAX_BATCH_SIZE = 30
PHOTO_MAX_PX = 1280
PHOTO_JPEG_QUALITY = 75
JOB_TTL_SECONDS = 3600
MIN_FREE_BYTES = 1024 * 1024 * 1024

EXPORT_ROOT = os.path.join(tempfile.gettempdir(), "site-app-archive-exports")

# archive_type -> (路由模块, 中文/英文/印尼语档案名)
ARCHIVE_TYPES: Dict[str, Dict[str, Any]] = {
    "survey": {"module": "app.api.survey_archives", "title": ("勘察档案", "Survey Archive", "Arsip Survei")},
    "opening": {
        "module": "app.api.opening_archives",
        "title": ("开站档案", "Site Installation Archive", "Arsip Instalasi Situs"),
    },
    "ssv": {"module": "app.api.ssv_archives", "title": ("SSV档案", "SSV Archive", "Arsip SSV")},
}

_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="archive-batch-export")

ACTIVE_STATUSES = ("queued", "running")


def _safe_filename(value: str, *, max_len: int = 150) -> str:
    s = re.sub(r"[\/\\:\*\?\"<>\|\r\n\t]+", "_", str(value or "").strip())
    s = re.sub(r"_+", "_", s).strip("_. ")
    return (s or "archive")[:max_len]


def make_photo_resizer(cache_dir: str, *, max_px: int = PHOTO_MAX_PX, quality: int = PHOTO_JPEG_QUALITY) -> Callable[[str], str]:
    """返回 原图路径 -> 压缩图路径 的映射函数；无需压缩或压缩失败时返回原图。"""
    from PIL import Image as PILImage

    os.makedirs(cache_dir, exist_ok=True)
    cache: Dict[str, str] = {}

    def resize(fp: str) -> str:
        if fp in cache:
            return cache[fp]
        out = fp
        try:
            with PILImage.open(fp) as im:
                if max(im.size) > max_px or (im.format != "JPEG"):
                    target = os.path.join(cache_dir, hashlib.sha1(fp.encode("utf-8")).hexdigest() + ".jpg")
                    im.thumbnail((max_px, max_px))
                    im.convert("RGB").save(target, "JPEG", quality=quality, optimize=True)
                    out = target
        except Exception:
            logger.warning("批量导出压缩照片失败，改用原图：%s", fp, exc_info=True)
            out = fp
        cache[fp] = out
        return out

    return resize


def _archive_module(archive_type: str):
    return importlib.import_module(ARCHIVE_TYPES[archive_type]["module"])


def _public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": job["id"],
        "archive_type": job["archive_type"],
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "success_count": job["success_count"],
        "current_name": job.get("current_name"),
        "errors": list(job["errors"]),
        "message": job.get("message"),
        "file_name": job.get("file_name"),
        "file_size": job.get("file_size"),
        "created_at": job["created_at"],
        "finished_at": job.get("finished_at"),
    }


def _job_dir(job_id: str) -> str:
    return os.path.join(EXPORT_ROOT, job_id)


def sweep_expired_jobs(now: Optional[float] = None) -> None:
    """清理过期任务与无主临时目录（例如服务重启前遗留的文件）。"""
    now = now or time.time()
    with _jobs_lock:
        for job_id, job in list(_jobs.items()):
            finished = job.get("finished_ts")
            if finished and now - finished > JOB_TTL_SECONDS:
                _jobs.pop(job_id, None)
                shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        known = set(_jobs)
    if os.path.isdir(EXPORT_ROOT):
        for name in os.listdir(EXPORT_ROOT):
            if name not in known:
                shutil.rmtree(os.path.join(EXPORT_ROOT, name), ignore_errors=True)


def create_job(*, archive_type: str, ids: Any, locale: Optional[str], user_id: int, session_factory) -> Dict[str, Any]:
    if archive_type not in ARCHIVE_TYPES:
        raise ValueError("不支持的档案类型")
    clean_ids: List[str] = []
    for raw in ids if isinstance(ids, list) else []:
        val = str(raw or "").strip()
        if val and val not in clean_ids:
            clean_ids.append(val)
    if not clean_ids:
        raise ValueError("请选择要导出的档案")
    if len(clean_ids) > MAX_BATCH_SIZE:
        raise ValueError(f"单次最多导出 {MAX_BATCH_SIZE} 个档案")

    sweep_expired_jobs()
    with _jobs_lock:
        if any(j["user_id"] == user_id and j["status"] in ACTIVE_STATUSES for j in _jobs.values()):
            raise ValueError("已有批量导出任务进行中，请完成后再试")
        job_id = secrets.token_urlsafe(24)
        job = {
            "id": job_id,
            "user_id": user_id,
            "archive_type": archive_type,
            "ids": clean_ids,
            "locale": normalize_locale(locale),
            "status": "queued",
            "total": len(clean_ids),
            "done": 0,
            "success_count": 0,
            "current_name": None,
            "errors": [],
            "message": None,
            "file_path": None,
            "file_name": None,
            "file_size": None,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "finished_at": None,
            "finished_ts": None,
        }
        _jobs[job_id] = job
    _executor.submit(_run_job_safely, job_id, session_factory)
    return _public_job(job)


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _jobs_lock:
        return _jobs.get(job_id)


def public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    with _jobs_lock:
        return _public_job(job)


def _finish(job: Dict[str, Any], status: str, message: Optional[str] = None) -> None:
    with _jobs_lock:
        job["status"] = status
        job["message"] = message
        job["current_name"] = None
        job["finished_at"] = datetime.utcnow().isoformat() + "Z"
        job["finished_ts"] = time.time()


def _run_job_safely(job_id: str, session_factory) -> None:
    job = get_job(job_id)
    if not job:
        return
    try:
        run_job(job, session_factory)
    except Exception:
        logger.exception("档案批量导出任务失败：%s", job_id)
        shutil.rmtree(_job_dir(job_id), ignore_errors=True)
        with _jobs_lock:
            job["file_path"] = None
        _finish(job, "failed", "批量导出失败，请稍后重试")


def run_job(job: Dict[str, Any], session_factory) -> None:
    """逐个渲染 PDF 写入 zip；单个档案失败记录到 errors 并继续，磁盘不足时整体停止。"""
    archive_type = job["archive_type"]
    locale_code = job["locale"]
    module = _archive_module(archive_type)
    zh, en, id_text = ARCHIVE_TYPES[archive_type]["title"]
    title = localized_text(zh, locale_code, en, id_text)

    work_dir = _job_dir(job["id"])
    os.makedirs(work_dir, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M")
    batch_label = localized_text("批量导出", locale_code, "Batch_Export", "Ekspor_Massal")
    file_name = _safe_filename(f"{title}_{batch_label}_{ts}") + ".zip"
    zip_path = os.path.join(work_dir, "export.zip")

    with _jobs_lock:
        job["status"] = "running"

    used_names: set = set()
    db = session_factory()
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
            for archive_id in job["ids"]:
                if shutil.disk_usage(work_dir).free < MIN_FREE_BYTES:
                    zf.close()
                    shutil.rmtree(work_dir, ignore_errors=True)
                    _finish(job, "failed", "服务器磁盘空间不足，已停止导出")
                    return

                archive = module._load_archive_for_export(db, archive_id)
                site = getattr(archive, "site", None) if archive else None
                display = " ".join(
                    x for x in (getattr(site, "site_code", None), getattr(site, "site_name", None)) if x
                ) or archive_id
                with _jobs_lock:
                    job["current_name"] = display

                if not archive:
                    error = "档案不存在"
                else:
                    cache_dir = os.path.join(work_dir, "img")
                    try:
                        buf, _ascii_base, human_base = module._render_archive_pdf(
                            archive,
                            with_thumbs=True,
                            locale_code=locale_code,
                            image_source=make_photo_resizer(cache_dir),
                        )
                        base = _safe_filename(human_base)
                        name = f"{base}.pdf"
                        n = 2
                        while name in used_names:
                            name = f"{base}_{n}.pdf"
                            n += 1
                        used_names.add(name)
                        zf.writestr(name, buf.getvalue())
                        error = None
                    except Exception:
                        logger.exception("批量导出档案 PDF 失败：%s %s", archive_type, archive_id)
                        error = "PDF 生成失败"
                    finally:
                        shutil.rmtree(cache_dir, ignore_errors=True)
                        db.expire_all()

                with _jobs_lock:
                    job["done"] += 1
                    if error:
                        job["errors"].append({"id": archive_id, "name": display, "message": error})
                    else:
                        job["success_count"] += 1

            if job["errors"]:
                lines = [
                    f"{e['name']}: {localize_text(e['message'], locale_code)}" for e in job["errors"]
                ]
                zf.writestr(
                    localized_text("导出失败清单", locale_code, "export_failures", "daftar_gagal_ekspor") + ".txt",
                    "\n".join(lines) + "\n",
                )
    finally:
        db.close()

    if job["success_count"] == 0:
        shutil.rmtree(work_dir, ignore_errors=True)
        _finish(job, "failed", "所选档案均导出失败")
        return

    with _jobs_lock:
        job["file_path"] = zip_path
        job["file_name"] = file_name
        job["file_size"] = os.path.getsize(zip_path)
    _finish(job, "done")
