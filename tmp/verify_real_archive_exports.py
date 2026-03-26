from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import sys
import uuid
from pathlib import Path

import fitz
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
SRC_DB = BACKEND / "site_manager.db"
TMP_DIR = ROOT / "tmp" / "real_archive_verify"
TMP_DIR.mkdir(parents=True, exist_ok=True)
TMP_DB = TMP_DIR / "site_manager_verify.db"

if not SRC_DB.exists():
    raise SystemExit(f"source db missing: {SRC_DB}")

shutil.copy2(SRC_DB, TMP_DB)

conn = sqlite3.connect(TMP_DB)
conn.row_factory = sqlite3.Row


def load_json(value):
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def score_content(content):
    cats = (content or {}).get("check_categories") or []
    items = sum(len(c.get("items") or []) for c in cats)
    photos = 0
    atts = len((content or {}).get("attachments") or [])
    for c in cats:
        for it in c.get("items") or []:
            photos += len(it.get("photos") or [])
            for sec in it.get("sectors") or []:
                photos += len(sec.get("photos") or [])
            for cell in it.get("cells") or []:
                photos += len(cell.get("photos") or [])
    return items * 10 + photos * 3 + atts * 5 + len(cats)


def best_row(table_name):
    rows = conn.execute(f"SELECT * FROM {table_name}").fetchall()
    if not rows:
        return None
    ranked = sorted(
        rows,
        key=lambda r: (
            score_content(load_json(r["content"])),
            int(r["current_version"] or 0),
            int(r["id"] is not None),
        ),
    )
    return ranked[-1]


opening_row = best_row("site_opening_archives")
if not opening_row:
    raise SystemExit("missing opening archive rows in local db")

user_row = conn.execute("SELECT * FROM users ORDER BY id ASC LIMIT 1").fetchone()
if not user_row:
    raise SystemExit("missing users table rows")

ssv_row = conn.execute("SELECT * FROM site_ssv_archives ORDER BY updated_at DESC LIMIT 1").fetchone()
if ssv_row is None:
    new_ssv_id = uuid.uuid4().hex
    content = load_json(opening_row["content"])
    conn.execute(
        """
        INSERT INTO site_ssv_archives
        (id, site_id, work_order_id, inspection_id, template_id, template_version,
         current_version, content, status, created_by, created_at, updated_by, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_ssv_id,
            opening_row["site_id"],
            opening_row["work_order_id"],
            opening_row["inspection_id"],
            opening_row["template_id"],
            opening_row["template_version"],
            opening_row["current_version"] or 1,
            json.dumps(content, ensure_ascii=False),
            "active",
            user_row["id"],
            opening_row["created_at"],
            user_row["id"],
            opening_row["updated_at"],
        ),
    )
    conn.commit()
    ssv_row = conn.execute("SELECT * FROM site_ssv_archives WHERE id = ?", (new_ssv_id,)).fetchone()

conn.close()

os.environ["DATABASE_URL"] = f"sqlite:///{TMP_DB}"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.database import SessionLocal  # noqa: E402
from app.api.auth import get_current_user  # noqa: E402
from app.api.opening_archives import export_archive_pdf as export_opening_pdf  # noqa: E402
from app.api.site_surveys import export_survey_pdf  # noqa: E402
from app.api.ssv_archives import export_archive_pdf as export_ssv_pdf  # noqa: E402
from app.models.survey import SiteSurvey  # noqa: E402
from app.models.user import User  # noqa: E402
from sqlalchemy.orm import joinedload  # noqa: E402


async def extract_response_bytes(response):
    chunks = []
    iterator = response.body_iterator
    if hasattr(iterator, "__aiter__"):
        async for chunk in iterator:
            chunks.append(chunk)
    else:
        for chunk in iterator:
            chunks.append(chunk)
    return b"".join(chunks)


def render_preview(pdf_path: Path, png_path: Path, page_number: int = 1):
    doc = fitz.open(pdf_path)
    page_index = min(max(page_number, 0), max(0, len(doc) - 1))
    page = doc.load_page(page_index)
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(str(png_path))
    doc.close()


def build_contact_sheet(items, out_path: Path):
    thumbs = []
    widths = []
    heights = []
    for label, png in items:
        img = Image.open(png).convert("RGB")
        scale = min(520 / img.width, 700 / img.height, 1.0)
        size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
        thumb = img.resize(size, Image.LANCZOS)
        canvas = Image.new("RGB", (thumb.width + 20, thumb.height + 60), "white")
        draw = ImageDraw.Draw(canvas)
        draw.text((10, 10), label, fill="black")
        canvas.paste(thumb, (10, 40))
        thumbs.append(canvas)
        widths.append(canvas.width)
        heights.append(canvas.height)

    margin = 20
    total_width = max(widths) + margin * 2
    total_height = sum(heights) + margin * (len(thumbs) + 1)
    sheet = Image.new("RGB", (total_width, total_height), "#eaeaea")
    y = margin
    for thumb in thumbs:
        x = (total_width - thumb.width) // 2
        sheet.paste(thumb, (x, y))
        y += thumb.height + margin
    sheet.save(out_path)


async def generate_pdf_and_preview(label, fn, resource_id, param_name="archive_id", locale="en-US"):
    db = SessionLocal()
    try:
        current_user = db.query(User).order_by(User.id.asc()).first()
        kwargs = {
            param_name: resource_id,
            "locale": locale,
            "db": db,
            "current_user": current_user,
        }
        response = await fn(**kwargs)
        pdf_bytes = await extract_response_bytes(response)
        pdf_path = TMP_DIR / f"{label}.pdf"
        pdf_path.write_bytes(pdf_bytes)
        png_path = TMP_DIR / f"{label}_page2.png"
        render_preview(pdf_path, png_path, page_number=1)
        return pdf_path, png_path
    finally:
        db.close()


async def main():
    db = SessionLocal()
    try:
        survey_rows = (
            db.query(SiteSurvey)
            .options(joinedload(SiteSurvey.site), joinedload(SiteSurvey.photos))
            .all()
        )
        if not survey_rows:
            raise SystemExit("missing site survey rows in local db")

        def score_survey(row: SiteSurvey) -> tuple[int, int, int]:
            fields = [
                row.survey_date,
                row.surveyor_name,
                row.surveyor_phone,
                row.latitude,
                row.longitude,
                row.address,
                row.gps_accuracy,
                row.site_type,
                row.tower_type,
                row.available_height_m,
                row.load_capacity_kg,
                row.power_available,
                row.power_distance_m,
                row.power_capacity_kw,
                row.earthing_feasible,
                row.fiber_available,
                row.fiber_distance_m,
                row.duct_notes,
                row.microwave_los,
                row.los_azimuth_deg,
                row.los_distance_km,
                row.sensitive_points,
                row.safety_notes,
                row.permits_constraints,
                row.owner_name,
                row.owner_phone,
                row.access_time_window,
                row.entry_constraints,
                row.feasibility,
                row.risks,
                row.recommendations,
            ]
            non_null = sum(v is not None and v != "" for v in fields)
            photo_count = len(row.photos or [])
            has_site = 1 if row.site else 0
            return (non_null, photo_count, has_site)

        survey_row = max(survey_rows, key=score_survey)
    finally:
        db.close()

    results = []
    results.append(await generate_pdf_and_preview("survey_real", export_survey_pdf, survey_row.id, param_name="survey_id"))
    results.append(await generate_pdf_and_preview("opening_real", export_opening_pdf, opening_row["id"]))
    results.append(await generate_pdf_and_preview("ssv_temp_real_content", export_ssv_pdf, ssv_row["id"]))
    for pdf_path, png_path in results:
        print(pdf_path)
        print(png_path)
    build_contact_sheet(
        [
            ("Survey archive", results[0][1]),
            ("Opening archive", results[1][1]),
            ("SSV archive", results[2][1]),
        ],
        TMP_DIR / "contact_sheet.png",
    )
    print(TMP_DIR / "contact_sheet.png")


if __name__ == "__main__":
    asyncio.run(main())
