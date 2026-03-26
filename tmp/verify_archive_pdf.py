from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from app.utils.archive_pdf import (
    build_archive_value_rows,
    build_pdf_styles,
    create_pdf_cell,
    register_pdf_fonts,
)


def main():
    out_path = Path("tmp") / "verify_archive_pdf_output.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    font_main, font_bold = register_pdf_fonts()
    styles = build_pdf_styles(font_main, font_bold)

    fields = [
        {
            "field_id": "antenna_check",
            "label": "天线检查",
            "label_i18n": {"en": "Antenna Check"},
            "type": "text",
        }
    ]
    values = {
        "antenna_check": "Antenna Proper Installed Mounted bracket and nuts with enough room to wrap cleanly",
    }

    rows = build_archive_value_rows(
        fields,
        values,
        locale="en-US",
        label_style=styles["ArchivePdfBody"],
        value_style=styles["ArchivePdfBody"],
    )
    table = Table(
        [
            [
                create_pdf_cell("Field", styles["ArchivePdfHeader"]),
                create_pdf_cell("Value", styles["ArchivePdfHeader"]),
            ]
        ] + rows,
        colWidths=[5 * cm, 10 * cm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F56C3A")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF6F0")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    story = [
        Paragraph("SSV Archive Report", styles["ArchivePdfTitle"]),
        table,
    ]
    doc.build(story)

    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(out_path)).pages)
    assert "Antenna Proper Installed" in text
    assert "A n t e n n a" not in text
    assert "Antenna Check" in text
    print(out_path)


if __name__ == "__main__":
    main()
