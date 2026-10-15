"""档案 PDF 缓存：每个档案 + 语言只保留一份压缩照片版 PDF，档案未变化时直接复用。

- 单个导出（详情页「导出PDF」）与批量导出共用同一份缓存，内容完全一致。
- 是否变化由「指纹」判断：档案内容、版本、站点名称、检查人/审核人、语言、照片文件大小与修改时间、渲染版本。
  任一变化都会重新生成，并删除该档案该语言的旧缓存。
- 照片缩到长边 PHOTO_MAX_PX 写入 PDF（开站档案约 15~35 MB/份）；需要原图请用详情页「导出Zip」。
- 写缓存前检查磁盘剩余空间：至少保留 MIN_FREE_BYTES + 当前数据库大小（给数据库备份留足空间），
  不足时按最久未使用顺序清理旧缓存（预生成不清理，直接停止）。
"""

from __future__ import annotations

import hashlib
import importlib
import json
import logging
import os
import shutil
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.utils.archive_pdf import normalize_locale

logger = logging.getLogger(__name__)

# 修改 PDF 版式或照片压缩参数时递增，使旧缓存全部失效
RENDER_VERSION = "1"
PHOTO_MAX_PX = 1280
PHOTO_JPEG_QUALITY = 75
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024

# 未生成档案的估算参数（Surge 实测：132 张照片 24 MB / 19 秒，150 张 34 MB / 19 秒）
EST_BYTES_BASE = 100 * 1024
EST_BYTES_PER_PHOTO = 220 * 1024
EST_SECONDS_BASE = 2.0
EST_SECONDS_PER_PHOTO = 0.14

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_ROOT = os.environ.get("ARCHIVE_PDF_CACHE_DIR") or os.path.join(_BACKEND_ROOT, "archive-pdf-cache")
_INTERNAL_DIRS = ("_exports", "_tmp")

# archive_type -> 路由模块、中文/英文/印尼语档案名
ARCHIVE_TYPES: Dict[str, Dict[str, Any]] = {
    "survey": {"module": "app.api.survey_archives", "title": ("勘察档案", "Survey Archive", "Arsip Survei")},
    "opening": {
        "module": "app.api.opening_archives",
        "title": ("开站档案", "Site Installation Archive", "Arsip Instalasi Situs"),
    },
    "ssv": {"module": "app.api.ssv_archives", "title": ("SSV档案", "SSV Archive", "Arsip SSV")},
}


class DiskSpaceError(RuntimeError):
    pass


_key_locks: Dict[str, threading.Lock] = {}
_key_locks_guard = threading.Lock()


def _key_lock(key: str) -> threading.Lock:
    with _key_locks_guard:
        lock = _key_locks.get(key)
        if lock is None:
            lock = _key_locks[key] = threading.Lock()
        return lock


def archive_module(archive_type: str):
    return importlib.import_module(ARCHIVE_TYPES[archive_type]["module"])


def load_archive(db, archive_type: str, archive_id: str):
    return archive_module(archive_type)._load_archive_for_export(db, archive_id)


def _photo_files(content: Any) -> List[str]:
    out: List[str] = []

    def walk(obj: Any) -> None:
        if isinstance(obj, dict):
            fp = obj.get("file_path")
            if isinstance(fp, str) and fp:
                out.append(fp)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(content or {})
    return out


def _file_stamps(paths: List[str]) -> List[Any]:
    stamps = []
    for fp in sorted(set(paths)):
        try:
            st = os.stat(fp)
            stamps.append([fp, st.st_size, int(st.st_mtime)])
        except OSError:
            stamps.append([fp, None, None])
    return stamps


def fingerprint(archive_type: str, a, locale: str) -> str:
    inspection = getattr(a, "inspection", None)
    payload = {
        "render": [RENDER_VERSION, PHOTO_MAX_PX, PHOTO_JPEG_QUALITY],
        "type": archive_type,
        "id": a.id,
        "version": a.current_version,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        "site": [getattr(a.site, "site_code", None), getattr(a.site, "site_name", None)] if a.site else None,
        "inspector": getattr(getattr(inspection, "inspector", None), "full_name", None),
        "reviewer": getattr(getattr(inspection, "reviewer", None), "full_name", None),
        "locale": normalize_locale(locale),
        "content": a.content or {},
        "files": _file_stamps(_photo_files(a.content)),
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _entry_dir(archive_type: str, archive_id: str) -> str:
    safe_id = "".join(ch for ch in str(archive_id) if ch.isalnum() or ch in "-_") or "NA"
    return os.path.join(CACHE_ROOT, archive_type, safe_id)


def _entry_paths(archive_type: str, archive_id: str, locale: str, fp: str):
    base = os.path.join(_entry_dir(archive_type, archive_id), f"{normalize_locale(locale)}-{fp[:20]}")
    return base + ".pdf", base + ".json"


def _read_entry(pdf_path: str, meta_path: str) -> Optional[Dict[str, Any]]:
    if not (os.path.exists(pdf_path) and os.path.exists(meta_path)):
        return None
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        return {"path": pdf_path, "human_base": meta["human_base"], "size": os.path.getsize(pdf_path)}
    except Exception:
        return None


def lookup(archive_type: str, a, locale: str, fp: Optional[str] = None) -> Optional[Dict[str, Any]]:
    fp = fp or fingerprint(archive_type, a, locale)
    return _read_entry(*_entry_paths(archive_type, a.id, locale, fp))


def estimate(archive_type: str, a, locale: str) -> Dict[str, Any]:
    """不生成 PDF，只判断是否已有缓存并估算大小与耗时。"""
    entry = lookup(archive_type, a, locale)
    if entry:
        return {"cached": True, "size": entry["size"], "seconds": 0.0}
    photos = sum(1 for fp in set(_photo_files(a.content)) if os.path.exists(fp))
    return {
        "cached": False,
        "size": EST_BYTES_BASE + photos * EST_BYTES_PER_PHOTO,
        "seconds": EST_SECONDS_BASE + photos * EST_SECONDS_PER_PHOTO,
    }


def _cached_pdfs() -> List[str]:
    files = []
    if not os.path.isdir(CACHE_ROOT):
        return files
    for root, dirs, names in os.walk(CACHE_ROOT):
        if root == CACHE_ROOT:
            dirs[:] = [d for d in dirs if d not in _INTERNAL_DIRS]
        files.extend(os.path.join(root, n) for n in names if n.endswith(".pdf"))
    return files


def _free_bytes() -> int:
    os.makedirs(CACHE_ROOT, exist_ok=True)
    return shutil.disk_usage(CACHE_ROOT).free


def _database_bytes() -> int:
    try:
        from app.core.database import engine

        path = engine.url.database if engine.url.get_backend_name() == "sqlite" else None
        return os.path.getsize(path) if path and os.path.exists(path) else 0
    except Exception:
        return 0


def min_free_bytes() -> int:
    """缓存写入后磁盘至少保留的空间：固定余量 + 数据库大小（数据库备份需要约一份数据库的空间）。"""
    return MIN_FREE_BYTES + _database_bytes()


def ensure_free_space(*, allow_evict: bool, keep: Optional[str] = None) -> None:
    required = min_free_bytes()
    if _free_bytes() >= required:
        return
    if allow_evict:
        candidates = []
        for path in _cached_pdfs():
            if path == keep:
                continue
            try:
                candidates.append((os.path.getmtime(path), path))
            except OSError:
                continue
        for _mtime, path in sorted(candidates):
            for p in (path, path[:-4] + ".json"):
                try:
                    os.remove(p)
                except OSError:
                    pass
            logger.info("磁盘空间不足，清理最久未使用的档案 PDF 缓存：%s", path)
            if _free_bytes() >= required:
                return
    raise DiskSpaceError("服务器磁盘空间不足，已停止导出")


def make_photo_resizer(cache_dir: str, *, max_px: int = PHOTO_MAX_PX, quality: int = PHOTO_JPEG_QUALITY):
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
                if max(im.size) > max_px or im.format != "JPEG":
                    target = os.path.join(cache_dir, hashlib.sha1(fp.encode("utf-8")).hexdigest() + ".jpg")
                    im.thumbnail((max_px, max_px))
                    im.convert("RGB").save(target, "JPEG", quality=quality, optimize=True)
                    out = target
        except Exception:
            logger.warning("压缩档案照片失败，改用原图：%s", fp, exc_info=True)
        cache[fp] = out
        return out

    return resize


def get_or_render(archive_type: str, a, locale: str, *, allow_evict: bool = True) -> Dict[str, Any]:
    """返回缓存的 PDF（path/human_base/size/from_cache）；没有或已变化时生成并替换旧缓存。"""
    locale = normalize_locale(locale)
    fp = fingerprint(archive_type, a, locale)
    pdf_path, meta_path = _entry_paths(archive_type, a.id, locale, fp)
    with _key_lock(f"{archive_type}:{a.id}:{locale}"):
        entry = _read_entry(pdf_path, meta_path)
        if entry:
            try:
                os.utime(pdf_path)  # 记录最近使用时间，磁盘不足时按此清理
            except OSError:
                pass
            return {**entry, "from_cache": True}

        ensure_free_space(allow_evict=allow_evict)
        tmp_dir = os.path.join(CACHE_ROOT, "_tmp", uuid.uuid4().hex)
        try:
            buf, _ascii_base, human_base = archive_module(archive_type)._render_archive_pdf(
                a,
                with_thumbs=True,
                locale_code=locale,
                image_source=make_photo_resizer(os.path.join(tmp_dir, "img")),
            )
            entry_dir = os.path.dirname(pdf_path)
            os.makedirs(entry_dir, exist_ok=True)
            part = os.path.join(tmp_dir, "out.pdf")
            with open(part, "wb") as f:
                f.write(buf.getvalue())
            with open(meta_path + ".part", "w", encoding="utf-8") as f:
                json.dump(
                    {"human_base": human_base, "fingerprint": fp, "created_at": datetime.utcnow().isoformat() + "Z"},
                    f,
                    ensure_ascii=False,
                )
            os.replace(part, pdf_path)
            os.replace(meta_path + ".part", meta_path)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

        # 删除同一档案同一语言的旧版本缓存
        prefix = f"{locale}-"
        keep = {os.path.basename(pdf_path), os.path.basename(meta_path)}
        for name in os.listdir(os.path.dirname(pdf_path)):
            if name.startswith(prefix) and name not in keep:
                try:
                    os.remove(os.path.join(os.path.dirname(pdf_path), name))
                except OSError:
                    pass
        return {"path": pdf_path, "human_base": human_base, "size": os.path.getsize(pdf_path), "from_cache": False}


def remove_orphans(existing: Dict[str, set]) -> int:
    """删除已不存在档案的缓存目录；existing: archive_type -> 现存档案 id 集合。"""
    removed = 0
    for archive_type, ids in existing.items():
        type_dir = os.path.join(CACHE_ROOT, archive_type)
        if not os.path.isdir(type_dir):
            continue
        safe_ids = {os.path.basename(_entry_dir(archive_type, i)) for i in ids}
        for name in os.listdir(type_dir):
            if name not in safe_ids:
                shutil.rmtree(os.path.join(type_dir, name), ignore_errors=True)
                removed += 1
    return removed
