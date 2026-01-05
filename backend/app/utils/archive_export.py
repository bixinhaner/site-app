from __future__ import annotations

import csv
import html
import io
import os
import re
import zipfile
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _safe_component(val: Any, *, fallback: str = "NA", max_len: int = 80) -> str:
    s = str(val or "").strip()
    if not s:
        return fallback
    # keep Chinese; only replace path separators and common illegal characters
    s = s.replace(" ", "_")
    s = re.sub(r"[\/\\\\:\*\?\"<>\|\r\n\t]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        return fallback
    return s[:max_len]


def _is_blank(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == ""
    if isinstance(v, (list, tuple, set, dict)):
        return len(v) == 0
    return False


def _zip_unique_arcname(zf: zipfile.ZipFile, arcname: str) -> str:
    if arcname not in zf.namelist():
        return arcname
    base, ext = os.path.splitext(arcname)
    for i in range(2, 10_000):
        cand = f"{base}__{i}{ext}"
        if cand not in zf.namelist():
            return cand
    return f"{base}__{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{ext}"


def iter_archive_photo_entries(content: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """遍历档案内容中的所有照片条目，包含站点/扇区/小区三级。

    约定结构（来自快照/编辑态）：
      content.check_categories[].items[].photos[]
      content.check_categories[].items[].sectors[].photos[]
      content.check_categories[].items[].cells[].photos[]
    """
    for cat in (content or {}).get("check_categories", []) or []:
        for it in (cat.get("items") or []):
            # site-level
            for p in (it.get("photos") or []):
                yield {
                    "category": cat,
                    "item": it,
                    "level": "site",
                    "sector": None,
                    "cell": None,
                    "photo": p,
                }
            # sector-level
            for sec in (it.get("sectors") or []):
                for p in (sec.get("photos") or []):
                    yield {
                        "category": cat,
                        "item": it,
                        "level": "sector",
                        "sector": sec,
                        "cell": None,
                        "photo": p,
                    }
            # cell-level
            for cell in (it.get("cells") or []):
                for p in (cell.get("photos") or []):
                    yield {
                        "category": cat,
                        "item": it,
                        "level": "cell",
                        "sector": cell,  # cell对象里也可能带 sector_id
                        "cell": cell,
                        "photo": p,
                    }


def iter_file_objects(obj: Any) -> Iterable[Dict[str, Any]]:
    """递归扫描任意对象，提取具备 file_path 的文件对象。

    仅当 file_path 指向实际存在的文件时才视为可导出文件。
    """
    if isinstance(obj, dict):
        fp = obj.get("file_path")
        if isinstance(fp, str) and fp and os.path.exists(fp):
            yield obj
        for v in obj.values():
            yield from iter_file_objects(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from iter_file_objects(v)


def build_archive_zip(
    *,
    overview: Dict[str, Any],
    content: Dict[str, Any],
    archive_title: str,
) -> io.BytesIO:
    """构造 ZIP：包含 overview/content、可读 index.html、以及所有照片/附件文件。"""
    mem_zip = io.BytesIO()

    # 写入文件清单（含缺失项）
    files_csv = io.StringIO()
    fw = csv.writer(files_csv)
    fw.writerow(
        [
            "category",
            "item",
            "level",
            "sector_id",
            "cell_id",
            "field_id",
            "file_name",
            "zip_path",
            "mime_type",
            "file_size",
            "status",
        ]
    )
    missing_csv = io.StringIO()
    mw = csv.writer(missing_csv)
    mw.writerow(["context", "file_path", "reason"])

    # 将照片优先按“分类/检查项/层级”组织；其他文件放 attachments/
    written_by_path: Dict[str, str] = {}
    manifest_photos: List[Dict[str, Any]] = []
    manifest_attachments: List[Dict[str, Any]] = []

    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        import json as _json

        zf.writestr("overview.json", _json.dumps(overview or {}, ensure_ascii=False, indent=2))
        zf.writestr("content.json", _json.dumps(content or {}, ensure_ascii=False, indent=2))

        # CSV 总览
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["key", "value"])
        for k, v in (overview or {}).items():
            w.writerow([k, v])
        zf.writestr("overview.csv", csv_buf.getvalue())

        # 1) 照片（按语义目录）
        for e in iter_archive_photo_entries(content or {}):
            p = e.get("photo") or {}
            fp = p.get("file_path")
            if not fp or not isinstance(fp, str):
                mw.writerow(["photo", fp, "empty file_path"])
                continue
            if not os.path.exists(fp):
                mw.writerow(["photo", fp, "file not found"])
                continue

            cat = e.get("category") or {}
            it = e.get("item") or {}
            level = e.get("level") or "site"
            sector_id = None
            cell_id = None
            if level == "sector":
                sector_id = (e.get("sector") or {}).get("sector_id")
            if level == "cell":
                sector_id = (e.get("cell") or {}).get("sector_id") or (e.get("sector") or {}).get("sector_id")
                cell_id = (e.get("cell") or {}).get("cell_id")

            cat_name = _safe_component(cat.get("category_name") or cat.get("category_id"))
            item_name = _safe_component(it.get("item_name") or it.get("item_id"))

            level_dir = "site"
            if level == "sector":
                level_dir = f"sector_{_safe_component(sector_id)}"
            elif level == "cell":
                level_dir = f"cell_{_safe_component(cell_id)}"

            base = os.path.basename(fp)
            subdir = f"photos/{cat_name}/{item_name}/{level_dir}"
            arcname = f"{subdir}/{_safe_component(base, max_len=120)}"

            if fp in written_by_path:
                zip_path = written_by_path[fp]
            else:
                try:
                    arcname = _zip_unique_arcname(zf, arcname)
                    zf.write(fp, arcname=arcname)
                    written_by_path[fp] = arcname
                    zip_path = arcname
                except Exception as ex:
                    mw.writerow(["photo", fp, f"write failed: {ex}"])
                    continue

            fw.writerow(
                [
                    cat.get("category_name") or cat.get("category_id"),
                    it.get("item_name") or it.get("item_id"),
                    level,
                    sector_id,
                    cell_id,
                    p.get("field_id"),
                    os.path.basename(fp),
                    zip_path,
                    p.get("mime_type"),
                    (os.path.getsize(fp) if os.path.exists(fp) else None),
                    "ok",
                ]
            )
            manifest_photos.append(
                {
                    "category": cat,
                    "item": it,
                    "level": level,
                    "sector_id": sector_id,
                    "cell_id": cell_id,
                    "field_id": p.get("field_id"),
                    "zip_path": zip_path,
                    "file_name": os.path.basename(fp),
                }
            )

        # 2) 其他附件（递归扫描，排除已作为照片导出的文件）
        for fobj in iter_file_objects(content or {}):
            fp = fobj.get("file_path")
            if not fp or not isinstance(fp, str) or not os.path.exists(fp):
                continue
            if fp in written_by_path:
                continue
            base = os.path.basename(fp)
            arcname = f"attachments/{_safe_component(base, max_len=120)}"
            try:
                arcname = _zip_unique_arcname(zf, arcname)
                zf.write(fp, arcname=arcname)
                written_by_path[fp] = arcname
            except Exception as ex:
                mw.writerow(["attachment", fp, f"write failed: {ex}"])
                continue

            fw.writerow(
                [
                    None,
                    None,
                    "attachment",
                    fobj.get("sector_id"),
                    fobj.get("cell_id"),
                    fobj.get("field_id"),
                    os.path.basename(fp),
                    arcname,
                    fobj.get("mime_type"),
                    (os.path.getsize(fp) if os.path.exists(fp) else None),
                    "ok",
                ]
            )
            manifest_attachments.append(
                {
                    "zip_path": arcname,
                    "file_name": os.path.basename(fp),
                    "mime_type": fobj.get("mime_type"),
                }
            )

        zf.writestr("files.csv", files_csv.getvalue())
        zf.writestr("missing_files.csv", missing_csv.getvalue())

        # 可读 index.html（不占位：空字段/空照片不展示）
        zf.writestr(
            "index.html",
            _render_index_html(
                overview=overview or {},
                content=content or {},
                archive_title=archive_title,
                manifest_photos=manifest_photos,
                manifest_attachments=manifest_attachments,
            ),
        )

    mem_zip.seek(0)
    return mem_zip


def _render_index_html(
    *,
    overview: Dict[str, Any],
    content: Dict[str, Any],
    archive_title: str,
    manifest_photos: List[Dict[str, Any]],
    manifest_attachments: List[Dict[str, Any]],
) -> str:
    def esc(s: Any) -> str:
        return html.escape("" if s is None else str(s))

    def is_blank_raw(v: Any) -> bool:
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict, tuple, set)):
            return len(v) == 0
        return False

    def to_text(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            import json
            return json.dumps(v, ensure_ascii=False, indent=2)
        return str(v)

    site_name = overview.get("site_name") or (content.get("meta") or {}).get("site_name") or ""
    site_code = overview.get("site_code") or (content.get("meta") or {}).get("site_code") or ""

    # 建立照片索引：按 category/item/level/sector_id/cell_id 聚合
    photo_groups: Dict[Tuple[str, str, str, str, str], List[Dict[str, Any]]] = {}
    for p in manifest_photos:
        cat = str((p.get("category") or {}).get("category_name") or (p.get("category") or {}).get("category_id") or "")
        it = str((p.get("item") or {}).get("item_name") or (p.get("item") or {}).get("item_id") or "")
        level = str(p.get("level") or "site")
        sec = str(p.get("sector_id") or "")
        cell = str(p.get("cell_id") or "")
        photo_groups.setdefault((cat, it, level, sec, cell), []).append(p)

    parts: List[str] = []
    parts.append("<!doctype html>")
    parts.append("<html lang='zh-CN'><head><meta charset='utf-8'/>")
    parts.append(f"<title>{esc(archive_title)} - {esc(site_name)}</title>")
    parts.append(
        "<style>"
        "body{font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial,PingFang SC,Microsoft YaHei,sans-serif;"
        "margin:24px;color:#222;background:#fafafa}"
        ".card{background:#fff;border:1px solid #eee;border-radius:10px;padding:16px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,.03)}"
        "h1{margin:0 0 8px;font-size:22px}"
        "h2{margin:18px 0 8px;font-size:18px;color:#F56C3A}"
        "h3{margin:14px 0 6px;font-size:15px;color:#333}"
        ".meta{display:grid;grid-template-columns:160px 1fr;gap:6px 12px;font-size:13px}"
        ".kv{width:100%;border-collapse:collapse;font-size:13px}"
        ".kv th,.kv td{border:1px solid #eee;padding:8px;vertical-align:top}"
        ".kv th{background:#FFF6F0;text-align:left;width:220px}"
        ".photos{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}"
        ".photos figure{margin:0;background:#fff;border:1px solid #eee;border-radius:8px;padding:8px}"
        ".photos img{max-width:100%;height:auto;display:block;border-radius:6px}"
        ".photos figcaption{margin-top:6px;font-size:12px;color:#666;word-break:break-all}"
        ".badge{display:inline-block;background:#FFF6F0;color:#F56C3A;border:1px solid #FBD0B9;border-radius:999px;padding:2px 10px;font-size:12px}"
        ".muted{color:#777}"
        "a{color:#1677ff;text-decoration:none}a:hover{text-decoration:underline}"
        "</style></head><body>"
    )

    parts.append("<div class='card'>")
    parts.append(f"<h1>{esc(archive_title)}</h1>")
    parts.append(f"<div class='muted'>{esc(site_name)} {esc(site_code)}</div>")
    parts.append("<div style='height:10px'></div>")
    parts.append("<div class='meta'>")
    for k in ["id", "site_id", "site_code", "site_name", "work_order_id", "inspection_id", "template_id", "template_version", "current_version", "updated_at", "inspector_name", "reviewer_name"]:
        v = overview.get(k)
        if _is_blank(v):
            continue
        parts.append(f"<div class='muted'>{esc(k)}</div><div>{esc(v)}</div>")
    parts.append("</div></div>")

    cats = (content or {}).get("check_categories") or []
    for cat in cats:
        cat_title = cat.get("category_name") or cat.get("category_id")
        if _is_blank(cat_title):
            cat_title = "未命名分类"
        parts.append(f"<h2>{esc(cat_title)}</h2>")
        for it in (cat.get("items") or []):
            it_title = it.get("item_name") or it.get("item_id") or "未命名检查项"
            parts.append("<div class='card'>")
            parts.append(f"<h3>{esc(it_title)}</h3>")

            def render_values_table(values_obj: Dict[str, Any], *, title: Optional[str] = None) -> None:
                rows: List[Tuple[str, str]] = []
                fields = it.get("fields") or []
                for fd in fields:
                    fid = fd.get("field_id")
                    label = fd.get("label") or fid
                    raw = (values_obj or {}).get(fid)
                    if is_blank_raw(raw):
                        continue
                    rows.append((str(label), esc(to_text(raw))))
                # 非模板字段兜底展示
                for k, v in (values_obj or {}).items():
                    if any(str(fd.get("field_id")) == str(k) for fd in fields):
                        continue
                    if is_blank_raw(v):
                        continue
                    rows.append((str(k), esc(to_text(v))))
                if not rows:
                    return
                if title:
                    parts.append(f"<div style='margin-top:10px'><span class='badge'>{esc(title)}</span></div>")
                parts.append("<table class='kv' style='margin-top:8px'><tr><th>字段</th><th>值</th></tr>")
                for a, b in rows:
                    parts.append(f"<tr><td>{esc(a)}</td><td><pre style='margin:0;white-space:pre-wrap'>{b}</pre></td></tr>")
                parts.append("</table>")

            # 站点级字段表
            render_values_table(it.get("values") or {}, title="站点数据")

            # 层级照片展示（站点/扇区/小区）
            def render_photo_block(level: str, sec: str = "", cell: str = "") -> None:
                key = (
                    str(cat.get("category_name") or cat.get("category_id") or ""),
                    str(it.get("item_name") or it.get("item_id") or ""),
                    level,
                    sec,
                    cell,
                )
                photos = photo_groups.get(key) or []
                if not photos:
                    return
                label = "站点照片"
                if level == "sector":
                    label = f"扇区照片（{sec}）"
                if level == "cell":
                    label = f"设备/小区照片（{cell}）"
                parts.append(f"<div style='margin-top:10px'><span class='badge'>{esc(label)}</span></div>")
                parts.append("<div class='photos' style='margin-top:8px'>")
                for p in photos:
                    zp = p.get("zip_path")
                    fn = p.get("file_name")
                    parts.append("<figure>")
                    parts.append(f"<img src='{esc(zp)}' alt='{esc(fn)}'/>")
                    parts.append(f"<figcaption>{esc(fn)}</figcaption>")
                    parts.append("</figure>")
                parts.append("</div>")

            render_photo_block("site")
            for sec in (it.get("sectors") or []):
                sec_id = str(sec.get("sector_id") or "")
                render_values_table(sec.get("values") or {}, title=f"扇区数据（{sec_id}）")
                render_photo_block("sector", sec_id, "")
            for cell in (it.get("cells") or []):
                cell_id = str(cell.get("cell_id") or "")
                sec_id = str(cell.get("sector_id") or "")
                head = f"设备/小区数据（{cell_id}）"
                if sec_id:
                    head += f" / 扇区 {sec_id}"
                if cell.get("band"):
                    head += f" / 频段 {cell.get('band')}"
                render_values_table(cell.get("values") or {}, title=head)
                render_photo_block("cell", sec_id, cell_id)

            parts.append("</div>")

    if manifest_attachments:
        parts.append("<h2>附件</h2>")
        parts.append("<div class='card'><ul>")
        for a in manifest_attachments:
            zp = a.get("zip_path")
            fn = a.get("file_name")
            parts.append(f"<li><a href='{esc(zp)}'>{esc(fn)}</a></li>")
        parts.append("</ul></div>")

    parts.append("</body></html>")
    return "".join(parts)
