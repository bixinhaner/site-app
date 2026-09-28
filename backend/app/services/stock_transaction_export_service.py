"""出入库记录导出（盘库用 Excel）。

只负责把已组装好的行数据渲染为多 Sheet 工作簿，不访问数据库：
- 出入库明细：一行一台设备（SN）/一种辅料，单据信息逐行冗余，便于筛选与透视
- 单据汇总：一张单据一行
- 物料进出汇总：按 仓库 + 物料 统计期间进出与净变化
- 盘点表：当前账面库存 + 实盘数（手填）+ 差异（公式）

所有固定文案均为 (中文, English, Bahasa Indonesia) 三元组，按 locale 输出。
"""

from __future__ import annotations

import io
from typing import Dict, List, Optional, Sequence, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.utils.archive_pdf import localized_text

Label = Tuple[str, str, str]

HEADER_FILL = PatternFill("solid", fgColor="F97316")
HEADER_FONT = Font(bold=True, color="FFFFFF")
MISMATCH_FILL = PatternFill("solid", fgColor="FFF3BF")
VOIDED_FONT = Font(color="999999", strike=True)
INPUT_FILL = PatternFill("solid", fgColor="EAF4FF")


def tr(label: Label, locale: str) -> str:
    zh, en, id_text = label
    return localized_text(zh, locale, en, id_text)


DETAIL_COLUMNS: Sequence[Tuple[str, Label]] = (
    ("document_number", ("单据号", "Document No.", "No. Dokumen")),
    ("type_label", ("类型", "Type", "Jenis")),
    ("source_label", ("出库方式", "Stock-out Method", "Metode Keluar")),
    ("operation_time", ("时间", "Time", "Waktu")),
    ("warehouse_name", ("仓库", "Warehouse", "Gudang")),
    ("equipment_code", ("物料编码", "Material Code", "Kode Material")),
    ("equipment_name", ("物料名称", "Material Name", "Nama Material")),
    ("category_label", ("物料类别", "Category", "Kategori")),
    ("serial_number", ("SN", "SN", "SN")),
    ("quantity", ("数量", "Qty", "Jumlah")),
    ("unit", ("单位", "Unit", "Satuan")),
    ("batch_number", ("批次号", "Batch No.", "No. Batch")),
    ("receiver_name", ("领料人/退库人", "Receiver / Returner", "Penerima / Pengembali")),
    ("approver_name", ("审批人", "Approver", "Penyetuju")),
    ("approved_at", ("审批时间", "Approved At", "Waktu Disetujui")),
    ("operator_name", ("经办人（仓管）", "Handled By (Warehouse)", "Petugas Gudang")),
    ("planned_site", ("目标站点（计划）", "Target Site (Planned)", "Site Tujuan (Rencana)")),
    ("actual_site", ("实际安装站点", "Actual Installed Site", "Site Terpasang Aktual")),
    ("actual_cell", ("安装小区", "Installed Cell", "Sel Terpasang")),
    ("site_check", ("站点核对", "Site Check", "Cek Site")),
    ("material_request_no", ("申请单号", "Material Request No.", "No. Permintaan Material")),
    ("issue_draft_no", ("领料单号", "Issue Draft No.", "No. Draf Pengambilan")),
    ("out_document_number", ("关联出库单", "Related Stock-out", "Dokumen Keluar Terkait")),
    ("status_label", ("单据状态", "Document Status", "Status Dokumen")),
    ("notes", ("备注", "Notes", "Catatan")),
)

DOCUMENT_COLUMNS: Sequence[Tuple[str, Label]] = (
    ("document_number", ("单据号", "Document No.", "No. Dokumen")),
    ("type_label", ("类型", "Type", "Jenis")),
    ("source_label", ("出库方式", "Stock-out Method", "Metode Keluar")),
    ("operation_time", ("时间", "Time", "Waktu")),
    ("warehouse_name", ("仓库", "Warehouse", "Gudang")),
    ("total_quantity", ("总数量", "Total Qty", "Total Jumlah")),
    ("main_count", ("主设备（台）", "Main Devices", "Perangkat Utama")),
    ("aux_count", ("辅料（件）", "Auxiliary Items", "Material Bantu")),
    ("receiver_name", ("领料人/退库人", "Receiver / Returner", "Penerima / Pengembali")),
    ("approver_name", ("审批人", "Approver", "Penyetuju")),
    ("approved_at", ("审批时间", "Approved At", "Waktu Disetujui")),
    ("operator_name", ("经办人（仓管）", "Handled By (Warehouse)", "Petugas Gudang")),
    ("planned_site", ("目标站点（计划）", "Target Site (Planned)", "Site Tujuan (Rencana)")),
    ("material_request_no", ("申请单号", "Material Request No.", "No. Permintaan Material")),
    ("issue_draft_no", ("领料单号", "Issue Draft No.", "No. Draf Pengambilan")),
    ("out_document_number", ("关联出库单", "Related Stock-out", "Dokumen Keluar Terkait")),
    ("status_label", ("单据状态", "Document Status", "Status Dokumen")),
    ("notes", ("备注", "Notes", "Catatan")),
)

SUMMARY_COLUMNS: Sequence[Tuple[str, Label]] = (
    ("warehouse_name", ("仓库", "Warehouse", "Gudang")),
    ("equipment_code", ("物料编码", "Material Code", "Kode Material")),
    ("equipment_name", ("物料名称", "Material Name", "Nama Material")),
    ("unit", ("单位", "Unit", "Satuan")),
    ("stock_in", ("入库", "Stock In", "Masuk")),
    ("stock_out", ("出库", "Stock Out", "Keluar")),
    ("return_in", ("退库收货", "Returns Received", "Retur Diterima")),
    ("adjustment", ("调整", "Adjustment", "Penyesuaian")),
    ("damage", ("报损", "Damage", "Rusak")),
    ("net", ("期间净变化", "Net Change", "Perubahan Bersih")),
)

STOCKTAKE_COLUMNS: Sequence[Tuple[str, Label]] = (
    ("warehouse_name", ("仓库", "Warehouse", "Gudang")),
    ("equipment_code", ("物料编码", "Material Code", "Kode Material")),
    ("equipment_name", ("物料名称", "Material Name", "Nama Material")),
    ("category_label", ("物料类别", "Category", "Kategori")),
    ("unit", ("单位", "Unit", "Satuan")),
    ("book_qty", ("账面库存", "Book Qty", "Stok Buku")),
    ("actual_qty", ("实盘数（手填）", "Counted Qty (fill in)", "Hitung Fisik (isi)")),
    ("diff", ("差异（实盘-账面）", "Difference (Counted - Book)", "Selisih (Fisik - Buku)")),
    ("remark", ("盘点备注", "Stocktake Notes", "Catatan Opname")),
)

SHEET_DETAIL: Label = ("出入库明细", "Transaction Details", "Detail Transaksi")
SHEET_DOCUMENTS: Label = ("单据汇总", "Documents", "Ringkasan Dokumen")
SHEET_SUMMARY: Label = ("物料进出汇总", "Material Flow", "Mutasi Material")
SHEET_STOCKTAKE: Label = ("盘点表", "Stocktake", "Stock Opname")
SHEET_INFO: Label = ("导出说明", "About This Export", "Keterangan Ekspor")

EXPORT_NOTES: Sequence[Tuple[Label, Label]] = (
    (
        ("审批人", "Approver", "Penyetuju"),
        (
            "出库取物料申请单的审批人；快速出库无审批流程，标记为“快速出库（无审批）”；退库取收货人。",
            "Stock-outs use the approver of the material request; quick stock-outs have no approval step and are marked "
            "\"Quick stock-out (no approval)\"; returns use the person who received them.",
            "Barang keluar memakai penyetuju permintaan material; keluar cepat tanpa persetujuan ditandai "
            "\"Keluar cepat (tanpa persetujuan)\"; retur memakai penerima retur.",
        ),
    ),
    (
        ("目标站点（计划）", "Target Site (Planned)", "Site Tujuan (Rencana)"),
        (
            "领料/快速出库时选择的目标站点（选填），历史单据为空。",
            "Target site chosen when requesting or quick-issuing materials (optional); empty for older documents.",
            "Site tujuan yang dipilih saat permintaan/keluar cepat (opsional); kosong untuk dokumen lama.",
        ),
    ),
    (
        ("实际安装站点", "Actual Installed Site", "Site Terpasang Aktual"),
        (
            "主设备按 SN 查询最新绑定记录得到；辅料及未安装设备为空。",
            "Looked up from the latest binding record of each main-device SN; empty for auxiliary items and uninstalled devices.",
            "Diambil dari data pemasangan terbaru per SN perangkat utama; kosong untuk material bantu dan perangkat belum terpasang.",
        ),
    ),
    (
        ("站点核对", "Site Check", "Cek Site"),
        (
            "计划与实际站点不一致的行标黄，需重点核查。",
            "Rows where the planned and actual site differ are highlighted in yellow and should be checked.",
            "Baris dengan site rencana dan aktual berbeda ditandai kuning dan perlu diperiksa.",
        ),
    ),
    (
        ("物料进出汇总", "Material Flow", "Mutasi Material"),
        (
            "入库/退库收货/调整为正向，出库/报损为负向；调拨不计入净变化。",
            "Stock in, returns received and adjustments add; stock out and damage subtract; transfers are excluded from net change.",
            "Masuk, retur diterima, dan penyesuaian menambah; keluar dan rusak mengurangi; transfer tidak dihitung.",
        ),
    ),
    (
        ("盘点表", "Stocktake", "Stock Opname"),
        (
            "账面库存为导出时刻的实时数据（仅列出账面不为 0 的物料）；填写“实盘数”后自动计算差异。",
            "Book quantity is live at export time (only items with non-zero book stock); the difference is calculated once the counted quantity is filled in.",
            "Stok buku adalah data saat ekspor (hanya material dengan stok buku tidak nol); selisih dihitung otomatis setelah hitung fisik diisi.",
        ),
    ),
)


def _write_sheet(ws, columns: Sequence[Tuple[str, Label]], rows: List[dict], locale: str) -> None:
    labels = [tr(label, locale) for _, label in columns]
    ws.append(labels)
    for cell in ws[1]:
        cell.fill = HEADER_FILL
        cell.font = HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for row in rows:
        ws.append([_cell_value(row.get(key)) for key, _ in columns])

    ws.freeze_panes = "A2"
    if rows:
        ws.auto_filter.ref = f"A1:{get_column_letter(len(columns))}{len(rows) + 1}"

    widths = [_text_width(label) + 2 for label in labels]
    for row in rows[:2000]:  # 采样计算列宽，避免大数据量时过慢
        for idx, (key, _) in enumerate(columns):
            width = _text_width(str(row.get(key) if row.get(key) is not None else "")) + 2
            if width > widths[idx]:
                widths[idx] = width
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = min(max(width, 8), 48)


def _text_width(text: str) -> int:
    return sum(2 if ord(ch) > 127 else 1 for ch in text)


def _cell_value(value):
    if value is None:
        return ""
    return value


def build_stock_transactions_workbook(
    *,
    detail_rows: List[dict],
    document_rows: List[dict],
    summary_rows: List[dict],
    stocktake_rows: Optional[List[dict]],
    filter_desc: List[Tuple[str, str]],
    locale: str = "zh-CN",
) -> bytes:
    wb = Workbook()

    ws_detail = wb.active
    ws_detail.title = tr(SHEET_DETAIL, locale)
    _write_sheet(ws_detail, DETAIL_COLUMNS, detail_rows, locale)
    sn_col = [key for key, _ in DETAIL_COLUMNS].index("serial_number") + 1
    for r_idx, row in enumerate(detail_rows, start=2):
        if row.get("site_mismatch"):
            for c_idx in range(1, len(DETAIL_COLUMNS) + 1):
                ws_detail.cell(row=r_idx, column=c_idx).fill = MISMATCH_FILL
        if row.get("instance_is_voided"):
            ws_detail.cell(row=r_idx, column=sn_col).font = VOIDED_FONT

    ws_docs = wb.create_sheet(tr(SHEET_DOCUMENTS, locale))
    _write_sheet(ws_docs, DOCUMENT_COLUMNS, document_rows, locale)

    ws_summary = wb.create_sheet(tr(SHEET_SUMMARY, locale))
    _write_sheet(ws_summary, SUMMARY_COLUMNS, summary_rows, locale)

    if stocktake_rows is not None:
        ws_take = wb.create_sheet(tr(SHEET_STOCKTAKE, locale))
        _write_sheet(ws_take, STOCKTAKE_COLUMNS, stocktake_rows, locale)
        keys = [k for k, _ in STOCKTAKE_COLUMNS]
        book_col = get_column_letter(keys.index("book_qty") + 1)
        actual_col = get_column_letter(keys.index("actual_qty") + 1)
        diff_idx = keys.index("diff") + 1
        actual_idx = keys.index("actual_qty") + 1
        for r_idx in range(2, len(stocktake_rows) + 2):
            ws_take.cell(row=r_idx, column=actual_idx).fill = INPUT_FILL
            ws_take.cell(
                row=r_idx,
                column=diff_idx,
                value=f'=IF({actual_col}{r_idx}="","",{actual_col}{r_idx}-{book_col}{r_idx})',
            )

    ws_info = wb.create_sheet(tr(SHEET_INFO, locale))
    ws_info.column_dimensions["A"].width = 24
    ws_info.column_dimensions["B"].width = 90
    for label, value in filter_desc:
        ws_info.append([label, value])
        ws_info.cell(row=ws_info.max_row, column=1).font = Font(bold=True)
    ws_info.append([])
    for label, value in EXPORT_NOTES:
        ws_info.append([tr(label, locale), tr(value, locale)])
        ws_info.cell(row=ws_info.max_row, column=1).font = Font(bold=True)
        ws_info.cell(row=ws_info.max_row, column=2).alignment = Alignment(wrap_text=True)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def summarize_material_flow(detail_rows: List[dict]) -> List[dict]:
    """根据明细行按 仓库 + 物料 汇总期间进出。"""
    buckets: Dict[Tuple[str, str], dict] = {}
    for row in detail_rows:
        key = (row.get("warehouse_name") or "", row.get("equipment_code") or "")
        bucket = buckets.get(key)
        if bucket is None:
            bucket = {
                "warehouse_name": row.get("warehouse_name"),
                "equipment_code": row.get("equipment_code"),
                "equipment_name": row.get("equipment_name"),
                "unit": row.get("unit"),
                "stock_in": 0,
                "stock_out": 0,
                "return_in": 0,
                "adjustment": 0,
                "damage": 0,
            }
            buckets[key] = bucket
        flow_key = row.get("flow_key")
        if flow_key in bucket:
            bucket[flow_key] += int(row.get("flow_qty") or 0)

    result = []
    for bucket in buckets.values():
        bucket["net"] = (
            bucket["stock_in"] + bucket["return_in"] + bucket["adjustment"] - bucket["stock_out"] - bucket["damage"]
        )
        result.append(bucket)
    result.sort(key=lambda x: (x.get("warehouse_name") or "", x.get("equipment_code") or ""))
    return result
