from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File, Form, Query
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.ssv_archive import SiteSSVArchive, SiteSSVArchiveVersion, SiteSSVArchiveKVIndex
from app.models.inspection import SiteInspection
from app.services.ssv_archive_service import (
    create_or_append_archive,
    patch_archive,
    make_diff,
    revert_to_version,
    reindex_kv,
)
from app.services.photo_duplicate_guard import (
    detect_duplicate_detail,
    register_first_upload_record,
)
from app.utils.file_handler import save_uploaded_file, calculate_file_hash, extract_exif, compress_image, add_text_watermark_inline
from app.utils.timezone import to_utc_iso
from app.utils.archive_pdf import (
    build_archive_value_rows,
    build_pdf_styles,
    create_pdf_cell,
    localized_text,
    normalize_locale,
    pick_localized_text,
    register_pdf_fonts,
)
from datetime import datetime
import os
import io
import csv
import zipfile
from fastapi.responses import StreamingResponse
import uuid
import jsonpatch


router = APIRouter()


def _require_editor(u: User):
    if getattr(u, "role", None) not in ("admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员或经理权限")


def _is_duplicate_check_item_photo_block_enabled(db: Session, current_user: User) -> bool:
    try:
        from app.api.mobile_settings import _load_mobile_settings, _resolve_bool_for_user

        settings = _load_mobile_settings(db)
        return _resolve_bool_for_user(
            settings,
            key="block_duplicate_check_item_photo_upload",
            user=current_user,
            default=True,
        )
    except Exception:
        return True


def _resolve_target_photo_list(
    content: Dict[str, Any],
    *,
    category_id: str,
    item_id: str,
    level: Optional[str],
    sector_id: Optional[str],
    cell_id: Optional[str],
) -> Optional[List[Dict[str, Any]]]:
    level_norm = str(level or "site").strip().lower()
    for cat in (content or {}).get("check_categories", []) or []:
        if str(cat.get("category_id")) != str(category_id):
            continue
        for it in cat.get("items", []) or []:
            if str(it.get("item_id")) != str(item_id):
                continue
            if level_norm == "sector":
                for sec in it.get("sectors", []) or []:
                    if str(sec.get("sector_id")) == str(sector_id):
                        return sec.setdefault("photos", [])
                return None
            if level_norm == "cell":
                for cell in it.get("cells", []) or []:
                    if str(cell.get("cell_id")) == str(cell_id):
                        return cell.setdefault("photos", [])
                return None
            return it.setdefault("photos", [])
    return None


def _has_duplicate_photo_hash(photos: List[Dict[str, Any]], file_hash: str) -> bool:
    target = str(file_hash or "").strip().lower()
    if not target:
        return False
    for p in photos or []:
        existed = str((p or {}).get("hash_value") or "").strip().lower()
        if existed and existed == target:
            return True
    return False


@router.get("/page")
def page_archives(
    page: int = 1,
    page_size: int = 20,
    site_id: Optional[int] = None,
    template_id: Optional[str] = None,
    keyword: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = (
        db.query(SiteSSVArchive)
        .options(
            joinedload(SiteSSVArchive.site),
            joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.inspector),
            joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.reviewer),
        )
        .join(Site, Site.id == SiteSSVArchive.site_id)
    )
    if site_id:
        q = q.filter(SiteSSVArchive.site_id == site_id)
    if template_id:
        q = q.filter(SiteSSVArchive.template_id == template_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter((Site.site_name.like(kw)) | (Site.site_code.like(kw)))
    if date_from:
        q = q.filter(SiteSSVArchive.updated_at >= date_from)
    if date_to:
        q = q.filter(SiteSSVArchive.updated_at <= date_to)

    total = q.count()
    rows = (
        q.order_by(SiteSSVArchive.updated_at.desc())
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
            # 列表展示用人的信息
            "inspector_name": getattr(getattr(a.inspection, 'inspector', None), 'full_name', None),
            "reviewer_name": getattr(getattr(a.inspection, 'reviewer', None), 'full_name', None),
            "current_version": a.current_version,
            "updated_at": to_utc_iso(a.updated_at) if a.updated_at else None,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/{archive_id}")
def get_archive(
    archive_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    a = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
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
        "updated_at": to_utc_iso(a.updated_at) if a.updated_at else None,
    }


@router.get("/{archive_id}/history")
def list_history(
    archive_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    vers = db.query(SiteSSVArchiveVersion).filter(
        SiteSSVArchiveVersion.archive_id == archive_id
    ).order_by(SiteSSVArchiveVersion.version.asc()).all()

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


@router.get("/{archive_id}/export")
async def export_archive_zip(
    archive_id: str,
    locale: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    a = db.query(SiteSSVArchive).options(
        joinedload(SiteSSVArchive.site),
        joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.inspector),
        joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.reviewer),
    ).filter(SiteSSVArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")

    locale_code = normalize_locale(locale)

    overview = {
        "id": a.id,
        "site_id": a.site_id,
        "site_code": a.site.site_code if a.site else None,
        "site_name": a.site.site_name if a.site else None,
        "work_order_id": a.work_order_id,
        "inspection_id": a.inspection_id,
        "inspector_name": getattr(getattr(a.inspection, 'inspector', None), 'full_name', None),
        "reviewer_name": getattr(getattr(a.inspection, 'reviewer', None), 'full_name', None),
        "template_id": a.template_id,
        "template_version": a.template_version,
        "current_version": a.current_version,
        "updated_at": to_utc_iso(a.updated_at) if a.updated_at else None,
    }
    from app.utils.archive_export import build_archive_zip
    mem_zip = build_archive_zip(
        overview=overview,
        content=a.content or {},
        archive_title=localized_text("SSV档案", locale_code, "SSV Archive", "Arsip SSV"),
    )
    # 构造更有信息量的文件名
    site_code = a.site.site_code if a.site else None
    site_name = a.site.site_name if a.site else None
    ver = a.current_version or 1
    ts = (a.updated_at or datetime.utcnow()).strftime('%Y%m%d_%H%M')
    def slugify(s: str) -> str:
        import re
        s = str(s or '').strip().replace(' ', '_')
        return re.sub(r'[^A-Za-z0-9_\-]+', '', s) or 'NA'
    ascii_base = f"Archive_{slugify(site_code)}_{slugify(site_name)}_v{ver}_{ts}"
    human_base = f"{localized_text('SSV档案', locale_code, 'SSV Archive', 'Arsip SSV')}_{site_code or ''}_{site_name or ''}_v{ver}_{ts}".strip('_')
    from urllib.parse import quote
    headers = {
        "Content-Disposition": f"attachment; filename={ascii_base}.zip; filename*=UTF-8''{quote(human_base + '.zip')}"
    }
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@router.get("/{archive_id}/export-pdf")
async def export_archive_pdf(
    archive_id: str,
    with_thumbs: bool = True,
    locale: Optional[str] = Query(None),
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

    a = db.query(SiteSSVArchive).options(
        joinedload(SiteSSVArchive.site),
        joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.inspector),
        joinedload(SiteSSVArchive.inspection).joinedload(SiteInspection.reviewer),
    ).filter(SiteSSVArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")

    locale_code = normalize_locale(locale)

    # 字体
    def register_cn_fonts() -> tuple[str, str]:
        return register_pdf_fonts()

    FONT_MAIN, FONT_BOLD = register_cn_fonts()
    primary = colors.HexColor("#F56C3A")
    primary_light = colors.HexColor("#FFF6F0")
    text_color = colors.HexColor("#333333")
    border = colors.HexColor('#dddddd')

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=1.8*cm
    )

    styles = build_pdf_styles(FONT_MAIN, FONT_BOLD)

    # 页眉/页脚
    def draw_page_frame(canvas, doc_):
        canvas.saveState()
        # header bar
        canvas.setFillColor(primary)
        canvas.rect(0, A4[1]-1.2*cm, A4[0], 1.2*cm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_BOLD, 12)
        canvas.drawString(
            2*cm,
            A4[1]-0.85*cm,
            localized_text("SSV档案报告", locale_code, "SSV Archive Report", "Laporan Arsip SSV"),
        )
        # footer
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.6)
        canvas.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        canvas.setFont(FONT_MAIN, 9)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawRightString(
            A4[0]-2*cm,
            1.1*cm,
            localized_text("第 {page} 页", locale_code, "Page {page}", "Halaman {page}").format(page=doc_.page),
        )
        canvas.restoreState()

    story = []
    # 封面标题
    story.append(Paragraph(localized_text("SSV档案报告", locale_code, "SSV Archive Report", "Laporan Arsip SSV"), styles["ArchivePdfTitle"]))

    # Meta 卡片（两列表格）
    meta_rows = [
        [create_pdf_cell(localized_text("站点", locale_code, "Site", "Situs"), styles["ArchivePdfBody"]), create_pdf_cell(f"{a.site.site_name if a.site else '-'} ({a.site.site_code if a.site else '-'})", styles["ArchivePdfBody"])],
        [create_pdf_cell(localized_text("版本", locale_code, "Version", "Versi"), styles["ArchivePdfBody"]), create_pdf_cell(str(a.current_version or '-'), styles["ArchivePdfBody"])],
        [create_pdf_cell(localized_text("开站检查人", locale_code, "Inspector", "Pemeriksa"), styles["ArchivePdfBody"]), create_pdf_cell(str(getattr(getattr(a.inspection, 'inspector', None), 'full_name', '-') or '-'), styles["ArchivePdfBody"])],
        [create_pdf_cell(localized_text("审核人", locale_code, "Reviewer", "Peninjau"), styles["ArchivePdfBody"]), create_pdf_cell(str(getattr(getattr(a.inspection, 'reviewer', None), 'full_name', '-') or '-'), styles["ArchivePdfBody"])],
        [create_pdf_cell(localized_text("更新时间", locale_code, "Updated At", "Waktu Pembaruan"), styles["ArchivePdfBody"]), create_pdf_cell((a.updated_at.strftime('%Y-%m-%d %H:%M') if a.updated_at else '-'), styles["ArchivePdfBody"])],
        [create_pdf_cell(localized_text("导出时间", locale_code, "Exported At", "Waktu Ekspor"), styles["ArchivePdfBody"]), create_pdf_cell(datetime.utcnow().strftime('%Y-%m-%d %H:%M'), styles["ArchivePdfBody"])],
    ]
    meta_tbl = Table(meta_rows, colWidths=[3*cm, 12*cm])
    meta_tbl.setStyle(TableStyle([
        ('FONTNAME', (0,0), (-1,-1), FONT_MAIN),
        ('FONTSIZE', (0,0), (-1,-1), 10),
        ('TEXTCOLOR', (0,0), (0,-1), colors.HexColor('#666666')),
        ('BACKGROUND', (0,0), (-1,-1), primary_light),
        ('LINEBEFORE', (0,0), (-1,-1), 0.25, border),
        ('LINEAFTER', (0,0), (-1,-1), 0.25, border),
        ('LINEABOVE', (0,0), (-1,-1), 0.25, border),
        ('LINEBELOW', (0,0), (-1,-1), 0.25, border),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 10))

    # 目录（按分类列出，便于导航）
    cats = (a.content or {}).get("check_categories") or []
    if cats:
        story.append(Spacer(1, 8))
        story.append(Paragraph(localized_text("目录", locale_code, "Contents", "Daftar Isi"), styles["ArchivePdfH2"]))
        for i, cat in enumerate(cats, start=1):
            cat_name = pick_localized_text(cat.get("category_name") or str(cat.get("category_id") or "未命名分类"), cat.get("category_name_i18n"), locale_code)
            cnt = len(cat.get("items") or [])
            story.append(Paragraph(f"{i}. {cat_name}（{cnt}项）", styles["ArchivePdfMeta"]))
        story.append(PageBreak())

    # 内容（字段值/层级/照片，不占位：空字段/空照片不展示）
    def decimals_from_step(step_val) -> int:
        try:
            s = str(step_val)
            if '.' in s:
                return len(s.split('.', 1)[1].rstrip('0'))
            return 0
        except Exception:
            return 0

    def is_blank_raw(v):
        if v is None:
            return True
        if isinstance(v, str):
            return v.strip() == ""
        if isinstance(v, (list, dict)):
            return len(v) == 0
        return False

    def opt_label(options, v):
        try:
            for o in (options or []):
                if str(o.get('value')) == str(v):
                    return o.get('label') or v
        except Exception:
            pass
        return v

    def fmt_value_by_field(fd: dict, v):
        if is_blank_raw(v):
            return None
        try:
            t = str((fd or {}).get('type') or '').lower()
            cons = (fd or {}).get('constraints') or {}
            unit = cons.get('unit') or cons.get('suffix') or ''
            if t == 'rich_text':
                import re as _re
                import html as _html
                s = str(v)
                s = _re.sub(r'(?is)<\s*br\s*/?\s*>', '\n', s)
                s = _re.sub(r'(?is)<[^>]+>', '', s)
                s = _html.unescape(s).strip()
                return s if s else None
            if t == 'boolean' or isinstance(v, bool):
                return ('是' if (v is True or str(v).lower() in ('1','true','yes','y')) else '否') + (f" {unit}" if unit else '')
            if t == 'number' or isinstance(v, (int, float)):
                prec = cons.get('precision')
                if prec is None:
                    prec = decimals_from_step(cons.get('step'))
                try:
                    fval = float(v)
                    if isinstance(prec, int) and prec >= 0:
                        sval = f"{fval:.{prec}f}" if prec > 0 else f"{int(round(fval))}"
                    else:
                        sval = str(fval)
                except Exception:
                    sval = str(v)
                return sval + (f" {unit}" if unit else '')
            if t == 'select_single':
                return str(opt_label((fd or {}).get('options'), v))
            if t == 'select_multi':
                arr = v if isinstance(v, list) else ([v] if v not in (None, '') else [])
                labeled = [str(opt_label((fd or {}).get('options'), x)) for x in arr]
                return '、'.join(labeled) if labeled else None
            if t in ('date','time','datetime'):
                from datetime import datetime as _dt
                s = str(v)
                dt = None
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ","%Y-%m-%dT%H:%M:%S.%f","%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
                    try:
                        dt = _dt.strptime(s, fmt)
                        break
                    except Exception:
                        continue
                if not dt:
                    return s
                if t == 'date':
                    return dt.strftime('%Y-%m-%d')
                if t == 'time':
                    return dt.strftime('%H:%M:%S')
                return dt.strftime('%Y-%m-%d %H:%M')
            if isinstance(v, (dict, list)):
                import json as _json
                return _json.dumps(v, ensure_ascii=False, indent=2)
            return str(v)
        except Exception:
            return str(v)

    def xml_escape(s: str) -> str:
        return (
            str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    def value_cell(s: str):
        return create_pdf_cell(s, styles["ArchivePdfBody"])

    def make_photo_grid(photo_list, cols=2):
        try:
            from reportlab.lib.utils import ImageReader
        except Exception:
            ImageReader = None
        cells = []
        row = []
        for p in photo_list:
            fp = p.get('file_path')
            if not fp or not os.path.exists(fp):
                continue
            try:
                max_w = 7.2*cm if cols == 2 else 5.0*cm
                max_h = 5.4*cm if cols == 2 else 3.8*cm
                if ImageReader:
                    ir = ImageReader(fp)
                    iw, ih = ir.getSize()
                    if iw and ih:
                        scale = min(max_w / float(iw), max_h / float(ih), 1.0)
                        im = Image(fp, width=float(iw) * scale, height=float(ih) * scale)
                    else:
                        im = Image(fp, width=max_w, height=max_h)
                else:
                    im = Image(fp, width=max_w, height=max_h)
                caption = Paragraph(os.path.basename(fp), styles['ArchivePdfCaption'])
                row.append([im, caption])
                if len(row) == cols:
                    cells.append(row)
                    row = []
            except Exception:
                continue
        if row:
            while len(row) < cols:
                row.append("")
            cells.append(row)
        if not cells:
            return None
        cw = [7.6*cm if cols==2 else 5.4*cm] * cols
        t = Table(cells, colWidths=cw)
        t.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ]))
        return t

    for ci, cat in enumerate(cats, start=1):
        story.append(Paragraph(f"{ci}. {pick_localized_text(cat.get('category_name') or str(cat.get('category_id') or '未命名分类'), cat.get('category_name_i18n'), locale_code)}", styles["ArchivePdfH2"]))
        items = cat.get("items") or []
        for ii, it in enumerate(items, start=1):
            title = f"{ci}.{ii} {pick_localized_text(it.get('item_name') or it.get('item_id') or '未命名检查项', it.get('item_name_i18n'), locale_code)}"
            story.append(Paragraph(title, styles["ArchivePdfH3"]))

            fields = it.get("fields") or []
            values = it.get("values") or {}
            rows = build_archive_value_rows(
                fields,
                values,
                locale=locale_code,
                label_style=styles["ArchivePdfBody"],
                value_style=styles["ArchivePdfBody"],
            )
            if rows:
                t = Table(
                    [[
                        create_pdf_cell(localized_text("字段", locale_code, "Field", "Bidang"), styles["ArchivePdfHeader"]),
                        create_pdf_cell(localized_text("值", locale_code, "Value", "Nilai"), styles["ArchivePdfHeader"]),
                    ]] + rows,
                    colWidths=[5*cm, 9*cm]
                )
                t.setStyle(TableStyle([
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('BACKGROUND', (0,0), (-1,0), primary),
                    ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                    ('LINEBEFORE', (0,0), (-1,-1), 0.25, border),
                    ('LINEAFTER', (0,0), (-1,-1), 0.25, border),
                    ('LINEABOVE', (0,0), (-1,-1), 0.25, border),
                    ('LINEBELOW', (0,0), (-1,-1), 0.25, border),
                    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, primary_light]),
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 6))

            if with_thumbs:
                grid = make_photo_grid((it.get("photos") or []), cols=2)
                if grid:
                    story.append(Paragraph(localized_text("站点照片", locale_code, "Site Photos", "Foto Situs"), styles["ArchivePdfH4"]))
                    story.append(grid)
                    story.append(Spacer(1, 6))

            for sec in (it.get("sectors") or []):
                sec_id = sec.get("sector_id")
                sec_rows = build_archive_value_rows(
                    fields,
                    sec.get("values") or {},
                    locale=locale_code,
                    label_style=styles["ArchivePdfBody"],
                    value_style=styles["ArchivePdfBody"],
                )
                sec_photos = sec.get("photos") or []
                if not sec_rows and not sec_photos:
                    continue
                story.append(Paragraph(f"{localized_text('扇区', locale_code, 'Sector', 'Sektor')}：{sec_id}", styles["ArchivePdfH4"]))
                if sec_rows:
                    sec_tbl = Table(
                        [[
                            create_pdf_cell(localized_text("字段", locale_code, "Field", "Bidang"), styles["ArchivePdfHeader"]),
                            create_pdf_cell(localized_text("值", locale_code, "Value", "Nilai"), styles["ArchivePdfHeader"]),
                        ]] + sec_rows,
                        colWidths=[5*cm, 9*cm]
                    )
                    sec_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FDEFE6")),
                        ('TEXTCOLOR', (0,0), (-1,0), primary),
                        ('LINEBEFORE', (0,0), (-1,-1), 0.25, border),
                        ('LINEAFTER', (0,0), (-1,-1), 0.25, border),
                        ('LINEABOVE', (0,0), (-1,-1), 0.25, border),
                        ('LINEBELOW', (0,0), (-1,-1), 0.25, border),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, primary_light]),
                        ('LEFTPADDING', (0,0), (-1,-1), 6),
                        ('RIGHTPADDING', (0,0), (-1,-1), 6),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ]))
                    story.append(sec_tbl)
                    story.append(Spacer(1, 6))
                if with_thumbs and sec_photos:
                    grid = make_photo_grid(sec_photos, cols=2)
                    if grid:
                        story.append(grid)
                        story.append(Spacer(1, 6))

            for cell in (it.get("cells") or []):
                cell_id = cell.get("cell_id")
                cell_rows = build_archive_value_rows(
                    fields,
                    cell.get("values") or {},
                    locale=locale_code,
                    label_style=styles["ArchivePdfBody"],
                    value_style=styles["ArchivePdfBody"],
                )
                cell_photos = cell.get("photos") or []
                if not cell_rows and not cell_photos:
                    continue
                head = f"{localized_text('小区', locale_code, 'Cell', 'Sel')}：{cell_id}"
                if cell.get("sector_id"):
                    head += f"（扇区 {cell.get('sector_id')}）"
                if cell.get("band"):
                    head += f" 频段 {cell.get('band')}"
                story.append(Paragraph(head, styles["ArchivePdfH4"]))
                if cell_rows:
                    cell_tbl = Table(
                        [[
                            create_pdf_cell(localized_text("字段", locale_code, "Field", "Bidang"), styles["ArchivePdfHeader"]),
                            create_pdf_cell(localized_text("值", locale_code, "Value", "Nilai"), styles["ArchivePdfHeader"]),
                        ]] + cell_rows,
                        colWidths=[5*cm, 9*cm]
                    )
                    cell_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#FDEFE6")),
                        ('TEXTCOLOR', (0,0), (-1,0), primary),
                        ('LINEBEFORE', (0,0), (-1,-1), 0.25, border),
                        ('LINEAFTER', (0,0), (-1,-1), 0.25, border),
                        ('LINEABOVE', (0,0), (-1,-1), 0.25, border),
                        ('LINEBELOW', (0,0), (-1,-1), 0.25, border),
                        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, primary_light]),
                        ('LEFTPADDING', (0,0), (-1,-1), 6),
                        ('RIGHTPADDING', (0,0), (-1,-1), 6),
                        ('TOPPADDING', (0,0), (-1,-1), 4),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ]))
                    story.append(cell_tbl)
                    story.append(Spacer(1, 6))
                if with_thumbs and cell_photos:
                    grid = make_photo_grid(cell_photos, cols=2)
                    if grid:
                        story.append(grid)
                        story.append(Spacer(1, 6))

        if ci != len(cats):
            story.append(PageBreak())

    # 附件清单（档案级补充信息）
    attachments = (a.content or {}).get("attachments") or []
    att_rows = []

    def fmt_size(num):
        try:
            n = float(num)
            if n <= 0:
                return "-"
            kb = 1024.0
            mb = kb * 1024.0
            gb = mb * 1024.0
            if n >= gb:
                return f"{n / gb:.2f} GB"
            if n >= mb:
                return f"{n / mb:.2f} MB"
            if n >= kb:
                return f"{n / kb:.2f} KB"
            return f"{int(n)} B"
        except Exception:
            return "-"

    for att in attachments:
        if not isinstance(att, dict):
            continue
        fp = att.get("file_path")
        if not fp:
            continue
        exists = os.path.exists(fp)
        name = att.get("original_name") or os.path.basename(fp)
        mime = att.get("mime_type") or "-"
        size = att.get("file_size") or (os.path.getsize(fp) if exists else None)
        status_txt = "" if exists else "缺失"
        att_rows.append([name, mime, fmt_size(size), status_txt])

    if att_rows:
        story.append(PageBreak())
        story.append(Paragraph(localized_text("附件", locale_code, "Attachments", "Lampiran"), styles["ArchivePdfH2"]))
        t = Table(
            [[
                create_pdf_cell(localized_text("文件", locale_code, "File", "Berkas"), styles["ArchivePdfHeader"]),
                create_pdf_cell(localized_text("类型", locale_code, "Type", "Tipe"), styles["ArchivePdfHeader"]),
                create_pdf_cell(localized_text("大小", locale_code, "Size", "Ukuran"), styles["ArchivePdfHeader"]),
                create_pdf_cell(localized_text("状态", locale_code, "Status", "Status"), styles["ArchivePdfHeader"]),
            ]] + att_rows,
            colWidths=[8.5*cm, 4.0*cm, 2.5*cm, 2.0*cm]
        )
        t.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BACKGROUND', (0,0), (-1,0), primary),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('LINEBEFORE', (0,0), (-1,-1), 0.25, border),
            ('LINEAFTER', (0,0), (-1,-1), 0.25, border),
            ('LINEABOVE', (0,0), (-1,-1), 0.25, border),
            ('LINEBELOW', (0,0), (-1,-1), 0.25, border),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, primary_light]),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)

    doc.build(story, onFirstPage=draw_page_frame, onLaterPages=draw_page_frame)
    buf.seek(0)
    # 构造更有信息量的 PDF 文件名
    site_code = a.site.site_code if a.site else None
    site_name = a.site.site_name if a.site else None
    ver = a.current_version or 1
    ts = (a.updated_at or datetime.utcnow()).strftime('%Y%m%d_%H%M')
    def slugify(s: str) -> str:
        import re
        s = str(s or '').strip().replace(' ', '_')
        return re.sub(r'[^A-Za-z0-9_\-]+', '', s) or 'NA'
    ascii_base = f"Archive_{slugify(site_code)}_{slugify(site_name)}_v{ver}_{ts}"
    human_base = f"{localized_text('SSV档案', locale_code, 'SSV Archive', 'Arsip SSV')}_{site_code or ''}_{site_name or ''}_v{ver}_{ts}".strip('_')
    from urllib.parse import quote
    headers = {
        "Content-Disposition": f"attachment; filename={ascii_base}.pdf; filename*=UTF-8''{quote(human_base + '.pdf')}"
    }
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)


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
    field_id: Optional[str] = Form(None),
    level: Optional[str] = Form(None),
    sector_id: Optional[str] = Form(None),
    cell_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仅上传文件到存储并返回元数据，不修改档案内容、不生成版本。

    前端可在编辑态下调用该接口完成预上传，并在点击“保存”时通过 PATCH 一次性将照片对象追加到内容中。
    """
    _require_editor(current_user)

    # 确认档案存在
    arc = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 存储文件（与正式上传保持一致的处理流程：压缩 + 水印）
    stored_path = await save_uploaded_file(file, category="survey_archives", sub_folder=archive_id)
    file_hash = calculate_file_hash(stored_path)
    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    duplicate_detail = detect_duplicate_detail(
        db,
        content_hash=file_hash,
        block_upload=duplicate_block_enabled,
    )
    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
    if duplicate_detail and duplicate_block_enabled:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=409, detail=duplicate_detail)
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

    temp_photo_id = uuid.uuid4().hex
    if not duplicate_detail:
        register_first_upload_record(
            db,
            content_hash=file_hash,
            source_type="ssv_archive_temp_photo",
            source_id=temp_photo_id,
            site_id=arc.site_id,
            site_name=getattr(getattr(arc, "site", None), "site_name", None),
            uploader_id=current_user.id,
            uploader_name=(current_user.full_name or current_user.username or "").strip(),
            uploaded_at=datetime.utcnow(),
        )
        db.commit()

    # 返回一个可直接写入 content.photos 的对象（但不落库）
    return {
        "id": temp_photo_id,
        "file_path": stored_path,
        "file_size": file_size,
        "mime_type": file.content_type,
        "hash_value": file_hash,
        "uploaded_by": current_user.id,
        "taken_at": None,
        "field_id": field_id,
        "level": level,
        "sector_id": sector_id,
        "cell_id": cell_id,
        "_temp": True,
        "category_id": category_id,
        "item_id": item_id,
        "duplicate_warning": duplicate_warning,
    }


@router.post("/{archive_id}/attachments/temp")
async def upload_temp_attachment(
    archive_id: str,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """仅上传附件到存储并返回元数据，不修改档案内容、不生成版本。"""
    _require_editor(current_user)

    arc = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    stored_path = await save_uploaded_file(file, category="ssv_archives", sub_folder=f"{archive_id}/attachments")
    file_hash = calculate_file_hash(stored_path)
    file_size = os.path.getsize(stored_path) if os.path.exists(stored_path) else None

    return {
        "id": uuid.uuid4().hex,
        "original_name": file.filename,
        "description": description,
        "file_path": stored_path,
        "file_size": file_size,
        "mime_type": file.content_type,
        "hash_value": file_hash,
        "uploaded_by": current_user.id,
        "uploaded_at": to_utc_iso(datetime.utcnow()),
        "_temp": True,
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
    field_id: Optional[str] = Form(None),
    level: Optional[str] = Form(None),
    sector_id: Optional[str] = Form(None),
    cell_id: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传照片并追加到指定项的 photos。生成一个版本。"""
    _require_editor(current_user)

    arc = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 存储文件
    stored_path = await save_uploaded_file(file, category="survey_archives", sub_folder=archive_id)
    file_hash = calculate_file_hash(stored_path)
    duplicate_block_enabled = _is_duplicate_check_item_photo_block_enabled(db, current_user)
    duplicate_detail = detect_duplicate_detail(
        db,
        content_hash=file_hash,
        block_upload=duplicate_block_enabled,
    )
    duplicate_warning = duplicate_detail if (duplicate_detail and not duplicate_block_enabled) else None
    if duplicate_detail and duplicate_block_enabled:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=409, detail=duplicate_detail)
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

    photo_id = uuid.uuid4().hex
    photo_obj = {
        "id": photo_id,
        "file_path": stored_path,
        "file_size": file_size,
        "mime_type": file.content_type,
        "hash_value": file_hash,
        "uploaded_by": current_user.id,
        "taken_at": None,
        "field_id": field_id,
    }

    target_photos = _resolve_target_photo_list(
        new,
        category_id=category_id,
        item_id=item_id,
        level=level,
        sector_id=sector_id,
        cell_id=cell_id,
    )
    if target_photos is None:
        try:
            if stored_path and os.path.exists(stored_path):
                os.remove(stored_path)
        except Exception:
            pass
        raise HTTPException(status_code=400, detail="未找到对应的分类/检查项")
    if duplicate_warning:
        photo_obj["duplicate_warning"] = duplicate_warning
    target_photos.append(photo_obj)

    if not duplicate_detail:
        register_first_upload_record(
            db,
            content_hash=file_hash,
            source_type="ssv_archive_photo",
            source_id=photo_id,
            site_id=arc.site_id,
            site_name=getattr(getattr(arc, "site", None), "site_name", None),
            uploader_id=current_user.id,
            uploader_name=(current_user.full_name or current_user.username or "").strip(),
            uploaded_at=datetime.utcnow(),
        )

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
    return {
        "id": arc.id,
        "current_version": arc.current_version,
        "duplicate_warning": duplicate_warning,
    }


@router.delete("/{archive_id}/photos/{photo_id}")
def delete_photo(
    archive_id: str,
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_editor(current_user)
    arc = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
    if not arc:
        raise HTTPException(status_code=404, detail="档案不存在")

    old = arc.content
    new = jsonpatch.apply_patch(old, [], in_place=False)
    removed = False
    for cat in new.get("check_categories", []) or []:
        for it in cat.get("items", []) or []:
            targets = [it]
            targets.extend(it.get("sectors") or [])
            targets.extend(it.get("cells") or [])

            for tgt in targets:
                photos = tgt.get("photos") or []
                for i, p in enumerate(list(photos)):
                    if str(p.get("id")) == str(photo_id):
                        photos.pop(i)
                        removed = True
                        break
                if removed:
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
    a = db.query(SiteSSVArchive).filter(SiteSSVArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")
    ver = int(version or a.current_version or 1)
    v = db.query(SiteSSVArchiveVersion).filter(
        SiteSSVArchiveVersion.archive_id == archive_id,
        SiteSSVArchiveVersion.version == ver,
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
    q = db.query(SiteSSVArchiveKVIndex).join(
        SiteSSVArchive, SiteSSVArchive.id == SiteSSVArchiveKVIndex.archive_id
    )
    if path_prefix:
        like = f"{path_prefix}%"
        q = q.filter(SiteSSVArchiveKVIndex.path.like(like))
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter((SiteSSVArchiveKVIndex.value_string.like(kw)) | (SiteSSVArchiveKVIndex.raw_json.isnot(None)))
    if site_id:
        q = q.filter(SiteSSVArchive.site_id == site_id)
    rows = q.order_by(SiteSSVArchiveKVIndex.updated_at.desc()).limit(limit).all()
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
    """为指定 SSV 工单（需已产生 inspection_id）创建/追加档案。"""
    _require_editor(current_user)
    from app.models.work_order import WorkOrder, WorkOrderTypeEnum
    from app.models.inspection import SiteInspection
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.type not in [WorkOrderTypeEnum.SSV]:
        raise HTTPException(status_code=400, detail="仅支持 SSV 工单重建档案")
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
