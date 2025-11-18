from fastapi import APIRouter, Depends, HTTPException, status, Body, UploadFile, File, Form
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.survey_archive import SiteSurveyArchive, SiteSurveyArchiveVersion, SiteSurveyArchiveKVIndex
from app.models.inspection import SiteInspection
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
        db.query(SiteSurveyArchive)
        .options(
            joinedload(SiteSurveyArchive.site),
            joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.inspector),
            joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.reviewer),
        )
        .join(Site, Site.id == SiteSurveyArchive.site_id)
    )
    if site_id:
        q = q.filter(SiteSurveyArchive.site_id == site_id)
    if template_id:
        q = q.filter(SiteSurveyArchive.template_id == template_id)
    if keyword:
        kw = f"%{keyword}%"
        q = q.filter((Site.site_name.like(kw)) | (Site.site_code.like(kw)))
    if date_from:
        q = q.filter(SiteSurveyArchive.updated_at >= date_from)
    if date_to:
        q = q.filter(SiteSurveyArchive.updated_at <= date_to)

    total = q.count()
    rows = (
        q.order_by(SiteSurveyArchive.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    # 计算每个档案在其站点内的勘察轮次（按创建时间升序）
    survey_round_map: Dict[str, int] = {}
    site_ids = {a.site_id for a in rows if a.site_id is not None}
    if site_ids:
        all_archives = (
            db.query(SiteSurveyArchive)
            .filter(SiteSurveyArchive.site_id.in_(site_ids))
            .order_by(SiteSurveyArchive.created_at.asc())
            .all()
        )
        site_round: Dict[int, int] = {}
        for arc in all_archives:
            sid = arc.site_id
            if sid is None:
                continue
            current_round = site_round.get(sid, 0) + 1
            site_round[sid] = current_round
            survey_round_map[arc.id] = current_round

    items = []
    for a in rows:
        survey_round = survey_round_map.get(a.id, 1)
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
            "updated_at": a.updated_at,
            # 勘察轮次：1 为初勘，>1 为复勘
            "survey_round": survey_round,
            "is_resurvey": survey_round > 1,
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

    # 计算该档案在其站点内的勘察轮次（按创建时间升序）
    survey_round = 1
    if a.site_id is not None:
        archives = (
            db.query(SiteSurveyArchive)
            .filter(SiteSurveyArchive.site_id == a.site_id)
            .order_by(SiteSurveyArchive.created_at.asc())
            .all()
        )
        for idx, arc in enumerate(archives, start=1):
            if arc.id == a.id:
                survey_round = idx
                break

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
        "survey_round": survey_round,
        "is_resurvey": survey_round > 1,
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


@router.get("/{archive_id}/export")
async def export_archive_zip(
    archive_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    a = db.query(SiteSurveyArchive).options(
        joinedload(SiteSurveyArchive.site),
        joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.inspector),
        joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.reviewer),
    ).filter(SiteSurveyArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")

    mem_zip = io.BytesIO()
    with zipfile.ZipFile(mem_zip, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 概览与内容
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
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
        }
        import json as _json
        zf.writestr("overview.json", _json.dumps(overview, ensure_ascii=False, indent=2))
        zf.writestr("content.json", _json.dumps(a.content or {}, ensure_ascii=False, indent=2))

        # CSV总览
        csv_buf = io.StringIO()
        w = csv.writer(csv_buf)
        w.writerow(["key", "value"])
        for k, v in overview.items():
            w.writerow([k, v])
        zf.writestr("overview.csv", csv_buf.getvalue())

        # 写入照片与清单
        files_csv = io.StringIO()
        fw = csv.writer(files_csv)
        fw.writerow(["category","item","file_name","zip_path","mime_type","file_size"])
        cats = (a.content or {}).get("check_categories") or []
        for cat in cats:
            cat_name = cat.get("category_name") or cat.get("category_id")
            for it in (cat.get("items") or []):
                item_name = it.get("item_name") or it.get("item_id")
                for p in (it.get("photos") or []):
                    fp = p.get("file_path")
                    if not fp or not os.path.exists(fp):
                        continue
                    base = os.path.basename(fp)
                    subdir = f"photos/{cat_name}/{item_name}"
                    arcname = f"{subdir}/{base}"
                    try:
                        zf.write(fp, arcname=arcname)
                    except Exception:
                        continue
                    fw.writerow([cat_name, item_name, base, arcname, p.get("mime_type"), (os.path.getsize(fp) if os.path.exists(fp) else None)])
        zf.writestr("files.csv", files_csv.getvalue())

    mem_zip.seek(0)
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
    human_base = f"勘察档案_{site_code or ''}_{site_name or ''}_v{ver}_{ts}".strip('_')
    from urllib.parse import quote
    headers = {
        "Content-Disposition": f"attachment; filename={ascii_base}.zip; filename*=UTF-8''{quote(human_base + '.zip')}"
    }
    return StreamingResponse(mem_zip, media_type="application/zip", headers=headers)


@router.get("/{archive_id}/export-pdf")
async def export_archive_pdf(
    archive_id: str,
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

    a = db.query(SiteSurveyArchive).options(
        joinedload(SiteSurveyArchive.site),
        joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.inspector),
        joinedload(SiteSurveyArchive.inspection).joinedload(SiteInspection.reviewer),
    ).filter(SiteSurveyArchive.id == archive_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="档案不存在")

    # 字体
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
        try:
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
            return "STSong-Light", "STSong-Light"
        except Exception:
            return "Helvetica", "Helvetica-Bold"

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

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitleCN", fontName=FONT_BOLD, fontSize=24, leading=30, textColor=primary, spaceAfter=10))
    styles.add(ParagraphStyle(name="H2CN", fontName=FONT_BOLD, fontSize=16, leading=22, textColor=primary, spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name="BodyCN", fontName=FONT_MAIN, fontSize=11, leading=16, textColor=text_color))
    styles.add(ParagraphStyle(name="MetaCN", fontName=FONT_MAIN, fontSize=10, leading=14, textColor=colors.HexColor('#555555')))
    styles.add(ParagraphStyle(name="CaptionCN", fontName=FONT_MAIN, fontSize=9, leading=12, textColor=colors.HexColor('#666666'), alignment=1))

    # 页眉/页脚
    def draw_page_frame(canvas, doc_):
        canvas.saveState()
        # header bar
        canvas.setFillColor(primary)
        canvas.rect(0, A4[1]-1.2*cm, A4[0], 1.2*cm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont(FONT_BOLD, 12)
        canvas.drawString(2*cm, A4[1]-0.85*cm, "勘察档案报告 Site Survey Archive")
        # footer
        canvas.setStrokeColor(primary)
        canvas.setLineWidth(0.6)
        canvas.line(2*cm, 1.5*cm, A4[0]-2*cm, 1.5*cm)
        canvas.setFont(FONT_MAIN, 9)
        canvas.setFillColor(colors.HexColor('#888888'))
        canvas.drawRightString(A4[0]-2*cm, 1.1*cm, f"第 {doc_.page} 页")
        canvas.restoreState()

    story = []
    # 封面标题
    story.append(Paragraph("勘察档案报告", styles["TitleCN"]))

    # Meta 卡片（两列表格）
    meta_rows = [
        ["站点", f"{a.site.site_name if a.site else '-'} ({a.site.site_code if a.site else '-'})"],
        ["版本", str(a.current_version or '-')],
        ["勘察人", str(getattr(getattr(a.inspection, 'inspector', None), 'full_name', '-') or '-')],
        ["审核人", str(getattr(getattr(a.inspection, 'reviewer', None), 'full_name', '-') or '-')],
        ["更新时间", (a.updated_at.strftime('%Y-%m-%d %H:%M') if a.updated_at else '-')],
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

    # 内容概览表（字段值）
    def decimals_from_step(step_val) -> int:
        try:
            s = str(step_val)
            if '.' in s:
                return len(s.split('.', 1)[1].rstrip('0'))
            return 0
        except Exception:
            return 0

    def opt_label(options, v):
        try:
            for o in (options or []):
                if str(o.get('value')) == str(v):
                    return o.get('label') or v
        except Exception:
            pass
        return v

    def fmt_value_by_field(fd: dict, v):
        if v is None or v == '':
            return '-'
        try:
            t = str((fd or {}).get('type') or '').lower()
            cons = (fd or {}).get('constraints') or {}
            unit = cons.get('unit') or cons.get('suffix') or ''
            # boolean
            if t == 'boolean' or isinstance(v, bool):
                return ('是' if (v is True or str(v).lower() in ('1','true','yes','y')) else '否') + (f" {unit}" if unit else '')
            # number
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
            # select single/multi
            if t == 'select_single':
                return str(opt_label((fd or {}).get('options'), v))
            if t == 'select_multi':
                arr = v if isinstance(v, list) else ([v] if v not in (None, '') else [])
                labeled = [str(opt_label((fd or {}).get('options'), x)) for x in arr]
                return '、'.join(labeled) if labeled else '-'
            # dates
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
            # objects/arrays
            if isinstance(v, (dict, list)):
                import json as _json
                return _json.dumps(v, ensure_ascii=False)
            # default
            return str(v)
        except Exception:
            return str(v)
    cats = (a.content or {}).get("check_categories") or []
    # 照片网格辅助
    def make_photo_grid(photo_list, cols=2):
        cells = []
        row = []
        for p in photo_list:
            fp = p.get('file_path')
            if not fp or not os.path.exists(fp):
                continue
            try:
                im = Image(fp, width=7.2*cm if cols==2 else 5.0*cm, height=5.4*cm if cols==2 else 3.8*cm)
                caption = Paragraph(os.path.basename(fp), styles['CaptionCN'])
                row.append([im, caption])
                if len(row) == cols:
                    cells.append(row)
                    row = []
            except Exception:
                continue
        if row:
            # 填充空白单元格以齐列
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

    for cat in cats:
        story.append(Paragraph(cat.get("category_name") or str(cat.get("category_id")), styles["H2CN"]))
        for it in (cat.get("items") or []):
            title = f"{it.get('item_name') or it.get('item_id')}"
            story.append(Paragraph(title, styles["BodyCN"]))
            tbl_data = [["字段", "值"]]
            fields = it.get("fields") or []
            values = it.get("values") or {}
            for fd in fields:
                label = fd.get("label") or fd.get("field_id")
                raw = values.get(fd.get("field_id"))
                val = fmt_value_by_field(fd, raw)
                tbl_data.append([label, val])
            if len(tbl_data) > 1:
                t = Table(tbl_data, colWidths=[5*cm, 9*cm])
                t.setStyle(TableStyle([
                    ('FONTNAME', (0,0), (-1,-1), FONT_MAIN),
                    ('FONTSIZE', (0,0), (-1,-1), 10),
                    ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
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
            # 照片缩略表格
            if with_thumbs:
                grid = make_photo_grid((it.get("photos") or []), cols=2)
                if grid:
                    story.append(grid)
                    story.append(Spacer(1, 6))
        story.append(PageBreak())

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
    human_base = f"勘察档案_{site_code or ''}_{site_name or ''}_v{ver}_{ts}".strip('_')
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
