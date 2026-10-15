"""档案批量导出 PDF：先预估（数量/已生成/大小/分卷/耗时）让用户确认，再后台排队生成并分卷下载。

- PDF 来自 archive_pdf_cache：档案未变化直接复用，只生成新增或变化的档案。
- 导出文件以硬链接引用缓存，不额外占用磁盘；下载时按卷流式打包 zip（每卷约 VOLUME_BYTES）。
- 全局只有一个工作线程（Linux 下降低优先级），用户导出与夜间预生成交替排队，避免占满 CPU。
- 任务登记在进程内（生产为单个 uvicorn 进程），重启后未完成任务失效；完成后 JOB_TTL_SECONDS 清理。
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import shutil
import sys
import threading
import time
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional

from app.i18n.error_localization import localize_text
from app.services import archive_pdf_cache as cache
from app.utils.archive_pdf import localized_text, normalize_locale

logger = logging.getLogger(__name__)

MAX_ARCHIVES = 5000
VOLUME_BYTES = int(os.environ.get("ARCHIVE_EXPORT_VOLUME_MB", "1024")) * 1024 * 1024
JOB_TTL_SECONDS = 6 * 3600
PREWARM_LOCALE = "en-US"
PREWARM_HOUR = int(os.environ.get("ARCHIVE_PDF_PREWARM_HOUR", "2"))
PREWARM_ENABLED = os.environ.get("ARCHIVE_PDF_PREWARM_ENABLED", "1") != "0"
PREWARM_STARTUP_DELAY_SECONDS = 600

EXPORT_ROOT = os.path.join(cache.CACHE_ROOT, "_exports")
ACTIVE_STATUSES = ("queued", "running")


def _lower_priority() -> None:
    # Linux 下 nice 只作用于当前线程：批量生成让位于正常请求
    if sys.platform.startswith("linux"):
        try:
            os.nice(10)
        except OSError:
            pass


_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="archive-batch-export", initializer=_lower_priority)


def _safe_filename(value: str, *, max_len: int = 150) -> str:
    s = re.sub(r"[\/\\:\*\?\"<>\|\r\n\t]+", "_", str(value or "").strip())
    s = re.sub(r"_+", "_", s).strip("_. ")
    return (s or "archive")[:max_len]


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise ValueError("日期格式不正确")


def resolve_ids(db, archive_type: str, ids: Any = None, filters: Any = None) -> List[str]:
    """勾选模式用 ids；全部导出模式按列表页相同的筛选条件取出全部档案。"""
    if archive_type not in cache.ARCHIVE_TYPES:
        raise ValueError("不支持的档案类型")
    if isinstance(filters, dict):
        res = cache.archive_module(archive_type).page_archives(
            page=1,
            page_size=MAX_ARCHIVES + 1,
            site_id=None,
            template_id=None,
            keyword=(str(filters.get("keyword") or "").strip() or None),
            date_from=_parse_dt(filters.get("date_from")),
            date_to=_parse_dt(filters.get("date_to")),
            db=db,
            current_user=None,
        )
        clean = [str(item["id"]) for item in res.get("items") or []]
    else:
        clean = []
        for raw in ids if isinstance(ids, list) else []:
            val = str(raw or "").strip()
            if val and val not in clean:
                clean.append(val)
    if not clean:
        raise ValueError("没有可导出的档案")
    if len(clean) > MAX_ARCHIVES:
        raise ValueError(f"单次最多导出 {MAX_ARCHIVES} 个档案")
    return clean


def _split_volumes(sizes: List[int]) -> int:
    parts, current = 0, 0
    for size in sizes:
        if parts == 0 or (current and current + size > VOLUME_BYTES):
            parts += 1
            current = 0
        current += size
    return parts


def _queue_ahead() -> int:
    with _jobs_lock:
        return sum(1 for j in _jobs.values() if j["status"] in ACTIVE_STATUSES)


def preview(db, *, archive_type: str, ids: Any = None, filters: Any = None, locale: Optional[str] = None) -> Dict[str, Any]:
    """导出前预估：不生成任何文件，只读档案与照片文件信息。"""
    locale_code = normalize_locale(locale)
    archive_ids = resolve_ids(db, archive_type, ids, filters)
    cached_count = render_count = missing_count = 0
    total_bytes = 0
    seconds = 0.0
    sizes: List[int] = []
    for archive_id in archive_ids:
        a = cache.load_archive(db, archive_type, archive_id)
        if not a:
            missing_count += 1
            continue
        est = cache.estimate(archive_type, a, locale_code)
        if est["cached"]:
            cached_count += 1
        else:
            render_count += 1
        total_bytes += est["size"]
        seconds += est["seconds"]
        sizes.append(est["size"])
        db.expunge_all()
    return {
        "archive_type": archive_type,
        "total": len(archive_ids),
        "cached_count": cached_count,
        "render_count": render_count,
        "missing_count": missing_count,
        "estimated_bytes": total_bytes,
        "estimated_seconds": int(round(seconds)),
        "parts": _split_volumes(sizes),
        "volume_bytes": VOLUME_BYTES,
        "queue_ahead": _queue_ahead(),
    }


def _public_job(job: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "job_id": job["id"],
        "archive_type": job["archive_type"],
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "success_count": job["success_count"],
        "cached_count": job["cached_count"],
        "current_name": job.get("current_name"),
        "errors": list(job["errors"]),
        "message": job.get("message"),
        "parts": [{"index": p["index"], "count": len(p["files"]), "size": p["size"]} for p in job.get("parts") or []],
        "created_at": job["created_at"],
        "finished_at": job.get("finished_at"),
    }


def _job_dir(job_id: str) -> str:
    return os.path.join(EXPORT_ROOT, job_id)


def sweep_expired_jobs(now: Optional[float] = None) -> None:
    """清理过期任务与无主导出目录（例如服务重启前遗留的文件）。"""
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


def create_job(db, *, archive_type: str, ids: Any = None, filters: Any = None, locale: Optional[str],
               user_id: int, session_factory) -> Dict[str, Any]:
    archive_ids = resolve_ids(db, archive_type, ids, filters)
    sweep_expired_jobs()
    with _jobs_lock:
        if any(j["user_id"] == user_id and j["status"] in ACTIVE_STATUSES for j in _jobs.values()):
            raise ValueError("已有批量导出任务进行中，请完成后再试")
        job_id = secrets.token_urlsafe(24)
        job = {
            "id": job_id,
            "user_id": user_id,
            "archive_type": archive_type,
            "ids": archive_ids,
            "locale": normalize_locale(locale),
            "status": "queued",
            "total": len(archive_ids),
            "done": 0,
            "success_count": 0,
            "cached_count": 0,
            "current_name": None,
            "errors": [],
            "message": None,
            "parts": [],
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
            job["parts"] = []
        _finish(job, "failed", "批量导出失败，请稍后重试")


def _link_or_copy(src: str, dst: str) -> None:
    try:
        os.link(src, dst)
    except OSError:
        shutil.copyfile(src, dst)


def run_job(job: Dict[str, Any], session_factory) -> None:
    """逐个取缓存或生成 PDF；单个档案失败记录到 errors 并继续，磁盘不足时整体停止。"""
    archive_type = job["archive_type"]
    locale_code = job["locale"]
    work_dir = _job_dir(job["id"])
    os.makedirs(work_dir, exist_ok=True)

    with _jobs_lock:
        job["status"] = "running"

    files: List[Dict[str, Any]] = []
    used_names: set = set()
    db = session_factory()
    try:
        for idx, archive_id in enumerate(job["ids"]):
            a = cache.load_archive(db, archive_type, archive_id)
            site = getattr(a, "site", None) if a else None
            display = " ".join(
                x for x in (getattr(site, "site_code", None), getattr(site, "site_name", None)) if x
            ) or archive_id
            with _jobs_lock:
                job["current_name"] = display

            error = None
            from_cache = False
            if not a:
                error = "档案不存在"
            else:
                try:
                    entry = cache.get_or_render(archive_type, a, locale_code)
                except cache.DiskSpaceError as exc:
                    shutil.rmtree(work_dir, ignore_errors=True)
                    _finish(job, "failed", str(exc))
                    return
                except Exception:
                    logger.exception("批量导出档案 PDF 失败：%s %s", archive_type, archive_id)
                    error = "PDF 生成失败"
                else:
                    from_cache = entry["from_cache"]
                    base = _safe_filename(entry["human_base"])
                    name = f"{base}.pdf"
                    n = 2
                    while name in used_names:
                        name = f"{base}_{n}.pdf"
                        n += 1
                    used_names.add(name)
                    local = os.path.join(work_dir, f"{idx:05d}.pdf")
                    _link_or_copy(entry["path"], local)
                    files.append({"path": local, "name": name, "size": os.path.getsize(local)})
            db.expunge_all()

            with _jobs_lock:
                job["done"] += 1
                if error:
                    job["errors"].append({"id": archive_id, "name": display, "message": error})
                else:
                    job["success_count"] += 1
                    if from_cache:
                        job["cached_count"] += 1
    finally:
        db.close()

    if not files:
        shutil.rmtree(work_dir, ignore_errors=True)
        _finish(job, "failed", "所选档案均导出失败")
        return

    parts: List[Dict[str, Any]] = []
    for f in files:
        if not parts or (parts[-1]["size"] and parts[-1]["size"] + f["size"] > VOLUME_BYTES):
            parts.append({"index": len(parts) + 1, "files": [], "size": 0})
        parts[-1]["files"].append(f)
        parts[-1]["size"] += f["size"]
    with _jobs_lock:
        job["parts"] = parts
    _finish(job, "done")


def download_name(job: Dict[str, Any], part_index: int) -> str:
    locale_code = job["locale"]
    zh, en, id_text = cache.ARCHIVE_TYPES[job["archive_type"]]["title"]
    title = localized_text(zh, locale_code, en, id_text)
    label = localized_text("批量导出", locale_code, "Batch_Export", "Ekspor_Massal")
    ts = (job.get("finished_at") or job["created_at"])[:16].replace("-", "").replace("T", "_").replace(":", "")
    total = len(job["parts"])
    suffix = f"_part{part_index}of{total}" if total > 1 else ""
    return _safe_filename(f"{title}_{label}_{ts}{suffix}") + ".zip"


class _StreamSink:
    """只写缓冲：zipfile 写入这里，生成器逐块取走（无 seek，zipfile 自动使用数据描述符）。"""

    def __init__(self) -> None:
        self.buf = bytearray()
        self.pos = 0

    def write(self, data) -> int:
        self.buf += data
        self.pos += len(data)
        return len(data)

    def tell(self) -> int:
        return self.pos

    def flush(self) -> None:
        pass

    def take(self) -> bytes:
        out = bytes(self.buf)
        self.buf.clear()
        return out


def iter_part_zip(job: Dict[str, Any], part_index: int, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
    part = job["parts"][part_index - 1]
    sink = _StreamSink()
    with zipfile.ZipFile(sink, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=1, allowZip64=True) as zf:
        if part_index == 1 and job["errors"]:
            lines = [f"{e['name']}: {localize_text(e['message'], job['locale'])}" for e in job["errors"]]
            name = localized_text("导出失败清单", job["locale"], "export_failures", "daftar_gagal_ekspor") + ".txt"
            zf.writestr(name, "\n".join(lines) + "\n")
            yield sink.take()
        for f in part["files"]:
            zinfo = zipfile.ZipInfo(f["name"], date_time=time.localtime()[:6])
            zinfo.compress_type = zipfile.ZIP_DEFLATED
            zinfo._compresslevel = 1  # PDF 内是 JPEG，高压缩级别只耗 CPU
            with open(f["path"], "rb") as src, zf.open(zinfo, "w", force_zip64=True) as dst:
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    dst.write(chunk)
                    if len(sink.buf) >= chunk_size:
                        yield sink.take()
            yield sink.take()
    yield sink.take()


# ---- 夜间预生成（只生成新增或变化的档案，默认英文）----

_prewarm_lock = threading.Lock()
_prewarm: Dict[str, Any] = {"running": False, "queue": deque(), "rendered": 0, "skipped": 0, "failed": 0}


def start_prewarm(session_factory) -> bool:
    """排入一轮预生成；每次只处理一个档案再重新排队，让用户导出任务可以插队。"""
    with _prewarm_lock:
        if _prewarm["running"]:
            return False
        _prewarm.update({"running": True, "queue": deque(), "rendered": 0, "skipped": 0, "failed": 0})
    db = session_factory()
    try:
        existing: Dict[str, set] = {}
        for archive_type in cache.ARCHIVE_TYPES:
            res = cache.archive_module(archive_type).page_archives(
                page=1, page_size=1_000_000, site_id=None, template_id=None, keyword=None,
                date_from=None, date_to=None, db=db, current_user=None,
            )
            ids = [str(item["id"]) for item in res.get("items") or []]
            existing[archive_type] = set(ids)
            _prewarm["queue"].extend((archive_type, i) for i in ids)
        removed = cache.remove_orphans(existing)
        if removed:
            logger.info("清理已删除档案的 PDF 缓存目录 %s 个", removed)
    except Exception:
        logger.exception("档案 PDF 预生成准备失败")
        with _prewarm_lock:
            _prewarm["running"] = False
        return False
    finally:
        db.close()
    logger.info("开始预生成档案 PDF：共 %s 个档案", len(_prewarm["queue"]))
    _executor.submit(_prewarm_step, session_factory)
    return True


def _prewarm_step(session_factory) -> None:
    with _prewarm_lock:
        item = _prewarm["queue"].popleft() if _prewarm["queue"] else None
    if item is None:
        with _prewarm_lock:
            _prewarm["running"] = False
        logger.info(
            "档案 PDF 预生成完成：新生成 %s，已是最新 %s，失败 %s",
            _prewarm["rendered"], _prewarm["skipped"], _prewarm["failed"],
        )
        return
    archive_type, archive_id = item
    db = session_factory()
    try:
        a = cache.load_archive(db, archive_type, archive_id)
        if a is not None:
            if cache.lookup(archive_type, a, PREWARM_LOCALE):
                _prewarm["skipped"] += 1
            else:
                cache.get_or_render(archive_type, a, PREWARM_LOCALE, allow_evict=False)
                _prewarm["rendered"] += 1
    except cache.DiskSpaceError:
        logger.warning("磁盘剩余空间低于 %.1f GB（含数据库备份余量），停止档案 PDF 预生成", cache.min_free_bytes() / 1024 ** 3)
        with _prewarm_lock:
            _prewarm["queue"].clear()
    except Exception:
        _prewarm["failed"] += 1
        logger.exception("预生成档案 PDF 失败：%s %s", archive_type, archive_id)
    finally:
        db.close()
    _executor.submit(_prewarm_step, session_factory)


_scheduler_started = False


def start_prewarm_scheduler(session_factory) -> None:
    """启动后约 10 分钟补跑一轮，之后每天 PREWARM_HOUR 点（服务器本地时间）跑一轮。"""
    global _scheduler_started
    if _scheduler_started or not PREWARM_ENABLED:
        return
    _scheduler_started = True

    def loop() -> None:
        started = time.time()
        startup_done = False
        last_day = None
        while True:
            try:
                now = datetime.now()
                if not startup_done and time.time() - started >= PREWARM_STARTUP_DELAY_SECONDS:
                    startup_done = True
                    last_day = now.date() if now.hour >= PREWARM_HOUR else last_day
                    start_prewarm(session_factory)
                elif now.hour == PREWARM_HOUR and last_day != now.date():
                    last_day = now.date()
                    start_prewarm(session_factory)
                sweep_expired_jobs()
            except Exception:
                logger.exception("档案 PDF 预生成调度异常")
            time.sleep(60)

    threading.Thread(target=loop, name="ArchivePdfPrewarm", daemon=True).start()
