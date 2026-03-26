from __future__ import annotations

import html
import json
import os
import re
import shutil
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph


def normalize_locale(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("_", "-")
    if not raw:
        return "zh-CN"
    if raw.startswith("en"):
        return "en-US"
    if raw.startswith("id") or raw.startswith("in"):
        return "id-ID"
    if raw.startswith("zh"):
        return "zh-CN"
    return "zh-CN"


def _locale_key(locale: Any) -> str:
    normalized = normalize_locale(locale)
    if normalized.startswith("en"):
        return "en"
    if normalized.startswith("id"):
        return "id"
    return "zh"


def _i18n_candidates(locale: Any) -> List[str]:
    normalized = normalize_locale(locale)
    key = _locale_key(locale)
    if key == "en":
        return ["en", "en-US", "en_GB", normalized]
    if key == "id":
        return ["id", "id-ID", "in", "in-ID", normalized]
    return ["zh", "zh-CN", "zh-Hans", normalized]


def pick_localized_text(base: Any, i18n_map: Any, locale: Any = "zh-CN") -> str:
    base_text = "" if base is None else str(base)
    if _locale_key(locale) == "zh":
        return base_text
    if not isinstance(i18n_map, dict):
        return base_text

    for key in _i18n_candidates(locale):
        value = i18n_map.get(key)
        if value is None:
            continue
        if str(value).strip() != "":
            return str(value)

    return base_text


def localized_text(zh: str, locale: Any, en: Optional[str] = None, id_text: Optional[str] = None) -> str:
    key = _locale_key(locale)
    if key == "en" and en is not None and str(en).strip() != "":
        return str(en)
    if key == "id" and id_text is not None and str(id_text).strip() != "":
        return str(id_text)
    return str(zh)


def _candidate_font_paths() -> Iterable[str]:
    seen = set()
    module_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(module_dir, "..", ".."))
    project_font_dir = os.path.join(backend_dir, "fonts")

    project_fonts = [
        "NotoSansSC-Regular.ttf",
        "NotoSansSC-Medium.ttf",
        "NotoSansCJKsc-Regular.otf",
        "NotoSansCJKSC-Regular.otf",
        "SourceHanSansSC-Regular.otf",
        "SourceHanSansCN-Regular.otf",
        "wqy-microhei.ttc",
    ]
    for name in project_fonts:
        path = os.path.join(project_font_dir, name)
        if os.path.exists(path) and path not in seen:
            seen.add(path)
            yield path

    explicit_paths = [
        "/System/Library/Fonts/Supplemental/Songti.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKSC-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansSC-Regular.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttf",
        "/usr/share/fonts/truetype/arphic/ukai.ttc",
        "C:\\Windows\\Fonts\\msyh.ttc",
        "C:\\Windows\\Fonts\\simhei.ttf",
        "C:\\Windows\\Fonts\\simsun.ttc",
        "C:\\Windows\\Fonts\\arialuni.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode MS.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode MS.ttf",
        "/System/Library/Fonts/Supplemental/Verdana.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Tahoma.ttf",
    ]
    for path in explicit_paths:
        if os.path.exists(path) and path not in seen:
            seen.add(path)
            yield path

    if shutil.which("fc-match"):
        families = [
            "Noto Sans CJK SC",
            "Source Han Sans SC",
            "WenQuanYi Micro Hei",
            "Microsoft YaHei",
            "Songti SC",
            "Noto Sans SC",
            "Arial Unicode MS",
        ]
        for family in families:
            try:
                result = subprocess.run(
                    ["fc-match", "-f", "%{file}\n", family],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                path = (result.stdout or "").strip().splitlines()[0]
            except Exception:
                continue
            if path and os.path.exists(path) and path not in seen:
                seen.add(path)
                yield path


def _register_ttf_font(font_path: str) -> Optional[str]:
    base_name = re.sub(r"[^A-Za-z0-9_]+", "_", os.path.splitext(os.path.basename(font_path))[0]).strip("_")
    if not base_name:
        base_name = "ArchivePDF"
    font_name = f"{base_name}_ArchivePDF"

    try:
        pdfmetrics.getFont(font_name)
        return font_name
    except Exception:
        pass

    try:
        font_obj = TTFont(font_name, font_path)
        face = getattr(font_obj, "face", None)
        cmap = getattr(face, "charToGlyph", None)
        if not isinstance(cmap, dict):
            return None
        # 同时要求基础拉丁和常见中文可覆盖，避免误选仅拉丁字体导致跨平台替换异常
        required = ("A", "a", "0", "中", "测")
        if any(ord(ch) not in cmap for ch in required):
            return None
        pdfmetrics.registerFont(font_obj)
        return font_name
    except Exception:
        return None


def register_pdf_fonts() -> Tuple[str, str]:
    """
    注册可同时覆盖英文和中文的字体。

    优先选择可嵌入的 TrueType 字体，避免回退到 CID 字体后出现英文字符排版异常。
    """

    for path in _candidate_font_paths():
        font_name = _register_ttf_font(path)
        if font_name:
            return font_name, font_name

    try:
        pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        return "STSong-Light", "STSong-Light"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


def build_pdf_styles(font_main: str, font_bold: Optional[str] = None) -> Dict[str, ParagraphStyle]:
    font_bold = font_bold or font_main
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ArchivePdfTitle",
            fontName=font_bold,
            fontSize=24,
            leading=30,
            textColor=colors.HexColor("#F56C3A"),
            alignment=TA_CENTER,
            spaceAfter=10,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfH2",
            fontName=font_bold,
            fontSize=16,
            leading=22,
            textColor=colors.HexColor("#F56C3A"),
            spaceBefore=10,
            spaceAfter=6,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfH3",
            fontName=font_bold,
            fontSize=13,
            leading=18,
            textColor=colors.HexColor("#333333"),
            spaceBefore=6,
            spaceAfter=4,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfH4",
            fontName=font_bold,
            fontSize=11,
            leading=16,
            textColor=colors.HexColor("#555555"),
            spaceBefore=4,
            spaceAfter=2,
            leftIndent=6,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfBody",
            fontName=font_main,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#333333"),
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfHeader",
            fontName=font_bold,
            fontSize=10,
            leading=14,
            textColor=colors.white,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfBadge",
            fontName=font_bold,
            fontSize=10,
            leading=14,
            textColor=colors.white,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfMeta",
            fontName=font_main,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#555555"),
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ArchivePdfCaption",
            fontName=font_main,
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#666666"),
            alignment=TA_CENTER,
            wordWrap="CJK",
            splitLongWords=1,
        )
    )
    return styles


def _escape_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, indent=2)
    text = str(value)
    text = html.escape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "<br/>")


def create_pdf_cell(value: Any, style: ParagraphStyle):
    if isinstance(value, Paragraph):
        return value
    if value is None:
        return ""
    text = str(value)
    if text.strip() == "":
        return ""
    return Paragraph(_escape_text(text), style)


def _decimals_from_step(step_val: Any) -> int:
    try:
        s = str(step_val)
        if "." in s:
            return len(s.split(".", 1)[1].rstrip("0"))
        return 0
    except Exception:
        return 0


def _is_blank_raw(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def format_archive_value(field_def: Dict[str, Any], raw_value: Any, locale: Any = "zh-CN") -> Optional[str]:
    if _is_blank_raw(raw_value):
        return None

    try:
        field_type = str((field_def or {}).get("type") or "").lower()
        constraints = (field_def or {}).get("constraints") or {}
        unit = constraints.get("unit") or constraints.get("suffix") or ""

        if field_type == "rich_text":
            import html as _html
            import re as _re

            text = str(raw_value)
            text = _re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", text)
            text = _re.sub(r"(?is)<[^>]+>", "", text)
            text = _html.unescape(text).strip()
            return f"{text}{f' {unit}' if unit else ''}" if text else None

        if field_type == "boolean" or isinstance(raw_value, bool):
            yes = localized_text("是", locale, "Yes", "Ya")
            no = localized_text("否", locale, "No", "Tidak")
            return (yes if (raw_value is True or str(raw_value).lower() in ("1", "true", "yes", "y")) else no) + (f" {unit}" if unit else "")

        if field_type == "number" or isinstance(raw_value, (int, float)):
            precision = constraints.get("precision")
            if precision is None:
                precision = _decimals_from_step(constraints.get("step"))
            try:
                num = float(raw_value)
                if isinstance(precision, int) and precision >= 0:
                    if precision > 0:
                        text = f"{num:.{precision}f}"
                    else:
                        text = f"{int(round(num))}"
                else:
                    text = str(num)
            except Exception:
                text = str(raw_value)
            return text + (f" {unit}" if unit else "")

        if field_type == "select_single":
            options = (field_def or {}).get("options") or []
            for option in options:
                if str(option.get("value")) == str(raw_value):
                    return pick_localized_text(option.get("label") or raw_value, option.get("label_i18n"), locale)
            return str(raw_value)

        if field_type == "select_multi":
            options = (field_def or {}).get("options") or []
            arr = raw_value if isinstance(raw_value, list) else ([raw_value] if raw_value not in (None, "") else [])
            labels: List[str] = []
            for item in arr:
                label = None
                for option in options:
                    if str(option.get("value")) == str(item):
                        label = pick_localized_text(option.get("label") or item, option.get("label_i18n"), locale)
                        break
                labels.append(str(label if label is not None else item))
            if not labels:
                return None
            return ("、" if _locale_key(locale) == "zh" else ", ").join(labels)

        if field_type in ("date", "time", "datetime"):
            from datetime import datetime as _dt

            text = str(raw_value)
            dt = None
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ):
                try:
                    dt = _dt.strptime(text, fmt)
                    break
                except Exception:
                    continue
            if not dt:
                return text
            if field_type == "date":
                return dt.strftime("%Y-%m-%d")
            if field_type == "time":
                return dt.strftime("%H:%M:%S")
            return dt.strftime("%Y-%m-%d %H:%M")

        if isinstance(raw_value, (dict, list)):
            return json.dumps(raw_value, ensure_ascii=False, indent=2)

        return str(raw_value)
    except Exception:
        return str(raw_value)


def build_archive_value_rows(
    fields: Optional[Iterable[Dict[str, Any]]],
    values: Optional[Dict[str, Any]],
    *,
    locale: Any,
    label_style: ParagraphStyle,
    value_style: ParagraphStyle,
) -> List[List[Any]]:
    rows: List[List[Any]] = []
    used = set()

    for field_def in fields or []:
        field_id = field_def.get("field_id")
        if field_id is None:
            continue
        label = pick_localized_text(field_def.get("label") or field_id, field_def.get("label_i18n"), locale) or field_id
        raw = (values or {}).get(field_id)
        formatted = format_archive_value(field_def, raw, locale)
        if formatted is None:
            continue
        rows.append([create_pdf_cell(label, label_style), create_pdf_cell(formatted, value_style)])
        used.add(str(field_id))

    for key, raw in (values or {}).items():
        if str(key) in used or _is_blank_raw(raw):
            continue
        rows.append([create_pdf_cell(str(key), label_style), create_pdf_cell(str(raw), value_style)])

    return rows


_ARCHIVE_UNBOUND_PHOTO_FIELD = "__archive_unbound_photo_field__"


def _normalize_photo_field_key(photo_obj: Any) -> str:
    if not isinstance(photo_obj, dict):
        return _ARCHIVE_UNBOUND_PHOTO_FIELD
    raw = photo_obj.get("field_id")
    if raw is None:
        return _ARCHIVE_UNBOUND_PHOTO_FIELD
    key = str(raw).strip()
    if key == "":
        return _ARCHIVE_UNBOUND_PHOTO_FIELD
    return key


def build_archive_value_photo_blocks(
    fields: Optional[Iterable[Dict[str, Any]]],
    values: Optional[Dict[str, Any]],
    photos: Optional[Iterable[Dict[str, Any]]],
    *,
    locale: Any,
    label_style: ParagraphStyle,
    value_style: ParagraphStyle,
    unbound_label: Optional[str] = None,
    unbound_value: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    构建“字段值 + 对应照片”的顺序块：
    1) 优先按模板字段顺序；
    2) 再补充 values 中模板外字段；
    3) 再补充仅有 field_id 但无字段定义/无值的照片组；
    4) 最后兜底未绑定字段的照片组。
    """
    blocks: List[Dict[str, Any]] = []
    used = set()
    grouped_photos: Dict[str, List[Dict[str, Any]]] = {}

    for photo in photos or []:
        if not isinstance(photo, dict):
            continue
        key = _normalize_photo_field_key(photo)
        grouped_photos.setdefault(key, []).append(photo)

    for field_def in fields or []:
        field_id = field_def.get("field_id")
        if field_id is None:
            continue
        field_key = str(field_id)
        label = pick_localized_text(field_def.get("label") or field_id, field_def.get("label_i18n"), locale) or field_key
        raw = (values or {}).get(field_id)
        formatted = format_archive_value(field_def, raw, locale)
        field_photos = grouped_photos.pop(field_key, [])
        if formatted is None and not field_photos:
            continue
        blocks.append(
            {
                "field_id": field_key,
                "label_cell": create_pdf_cell(label, label_style),
                "value_cell": create_pdf_cell("" if formatted is None else formatted, value_style),
                "photos": field_photos,
                "has_value": formatted is not None,
            }
        )
        used.add(field_key)

    for key, raw in (values or {}).items():
        key_str = str(key)
        if key_str in used:
            continue
        field_photos = grouped_photos.pop(key_str, [])
        if _is_blank_raw(raw) and not field_photos:
            continue
        blocks.append(
            {
                "field_id": key_str,
                "label_cell": create_pdf_cell(key_str, label_style),
                "value_cell": create_pdf_cell("" if _is_blank_raw(raw) else str(raw), value_style),
                "photos": field_photos,
                "has_value": not _is_blank_raw(raw),
            }
        )
        used.add(key_str)

    for key in list(grouped_photos.keys()):
        if key == _ARCHIVE_UNBOUND_PHOTO_FIELD:
            continue
        field_photos = grouped_photos.pop(key) or []
        if not field_photos:
            continue
        blocks.append(
            {
                "field_id": key,
                "label_cell": create_pdf_cell(key, label_style),
                "value_cell": create_pdf_cell("", value_style),
                "photos": field_photos,
                "has_value": False,
            }
        )

    unbound_photos = grouped_photos.get(_ARCHIVE_UNBOUND_PHOTO_FIELD) or []
    if unbound_photos:
        blocks.append(
            {
                "field_id": _ARCHIVE_UNBOUND_PHOTO_FIELD,
                "label_cell": create_pdf_cell(
                    unbound_label or localized_text("照片", locale, "Photo", "Foto"),
                    label_style,
                ),
                "value_cell": create_pdf_cell(
                    unbound_value or localized_text("未关联字段", locale, "Unassigned to Field", "Tidak terkait field"),
                    value_style,
                ),
                "photos": unbound_photos,
                "has_value": False,
            }
        )

    return blocks
