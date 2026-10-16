"""快速出库“出库凭证（三签单）”：PDF 上传、必传开关、补传、出入库记录展示与筛选。"""
import asyncio
import io
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.datastructures import Headers

import app.api.stock as stock
from app.core.database import Base
from app.i18n.stock_messages import EXACT
from app.models.equipment import Equipment, EquipmentCategoryEnum, Inventory, StockTransaction, Warehouse
from app.models.user import User

OPERATOR = SimpleNamespace(id=2, role="warehouse_manager", is_admin=False)
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7\x35\x81\x84\x00\x00\x00\x00IEND\xaeB`\x82"
)
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture()
def db(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # 上传文件写入临时目录
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            User(id=2, username="wh", email="wh@example.com", hashed_password="x", full_name="Warehouse"),
            Warehouse(id=1, warehouse_code="WH1", warehouse_name="Main"),
            Equipment(id=1, equipment_code="CBL", equipment_name="Cable", category=EquipmentCategoryEnum.AUXILIARY),
            Inventory(warehouse_id=1, equipment_id=1, current_stock=10, available_stock=10, allocated_stock=0),
        ]
    )
    session.commit()
    monkeypatch.setattr(stock, "_ensure_inventory_operator", lambda *a, **k: None)
    monkeypatch.setattr(stock, "_get_managed_warehouse_ids", lambda db, user: None)
    monkeypatch.setattr(stock, "_can_view_inventory_history", lambda db, user: True)
    monkeypatch.setattr(stock, "has_global_inventory_scope", lambda user: True)
    monkeypatch.setattr(stock, "validate_image_on_disk", lambda *a, **k: None)
    yield session
    session.close()


def _run(coro):
    return asyncio.run(coro)


def _upload(db, doc_id, name, content, content_type):
    file = UploadFile(file=io.BytesIO(content), filename=name, headers=Headers({"content-type": content_type}))
    return _run(stock.upload_offline_document_photo(doc_id, file=file, db=db, current_user=OPERATOR))


def _new_doc(db, remark=""):
    return _run(stock.create_offline_document({"remark": remark}, db=db, current_user=OPERATOR))["id"]


def _stock_out(db, **extra):
    payload = {"warehouse_id": 1, "issued_to": 2, "aux_items": [{"equipment_id": 1, "quantity": 1}], **extra}
    return _run(stock.manual_stock_out(payload, db=db, current_user=OPERATOR))


def _set_flow(db, **values):
    settings = stock._get_flow_settings(db)
    settings.update(values)
    stock._save_flow_settings(db, settings)


def _list(db, **filters):
    return _run(stock.get_stock_transactions(db=db, current_user=OPERATOR, **filters))


def test_pdf_and_image_upload_accepted(db):
    doc_id = _new_doc(db)
    pdf = _upload(db, doc_id, "三签单.pdf", PDF, "application/pdf")
    assert pdf["mime_type"] == "application/pdf" and pdf["file_path"].endswith(".pdf")
    img = _upload(db, doc_id, "a.png", PNG, "image/png")
    assert img["mime_type"] == "image/png"


def test_fake_pdf_and_other_types_rejected(db):
    doc_id = _new_doc(db)
    with pytest.raises(HTTPException) as exc:
        _upload(db, doc_id, "x.pdf", b"not a pdf", "application/pdf")
    assert exc.value.detail == "文件不是有效的 PDF"
    with pytest.raises(HTTPException) as exc:
        _upload(db, doc_id, "x.docx", b"PK..", "application/octet-stream")
    assert exc.value.detail == "仅支持 jpg/jpeg/png 图片或 PDF 文件"
    assert _run(stock.get_offline_document(doc_id, db=db, current_user=OPERATOR))["photo_count"] == 0


def test_voucher_optional_by_default(db):
    assert stock._get_flow_settings(db)["quick_stock_out_requires_voucher"] is False
    assert _stock_out(db)["document_number"]


def test_voucher_required_switch(db):
    _set_flow(db, quick_stock_out_requires_voucher=True)
    with pytest.raises(HTTPException) as exc:
        _stock_out(db)
    assert exc.value.detail["code"] == "VOUCHER_REQUIRED"

    empty_doc = _new_doc(db)  # 只建票据未上传文件也不行
    with pytest.raises(HTTPException) as exc:
        _stock_out(db, offline_document_id=empty_doc)
    assert exc.value.detail["code"] == "VOUCHER_REQUIRED"

    doc_id = _new_doc(db, remark="SJ-001")
    _upload(db, doc_id, "sign.pdf", PDF, "application/pdf")
    res = _stock_out(db, offline_document_id=doc_id)
    assert db.get(StockTransaction, res["transaction_id"]).offline_document_id == doc_id


def test_history_shows_voucher_and_filters_missing(db):
    without = _stock_out(db)["transaction_id"]
    doc_id = _new_doc(db, remark="SJ-002")
    _upload(db, doc_id, "a.png", PNG, "image/png")
    _upload(db, doc_id, "b.pdf", PDF, "application/pdf")
    with_doc = _stock_out(db, offline_document_id=doc_id)["transaction_id"]

    rows = {t["id"]: t for t in _list(db)["transactions"]}
    assert rows[without]["is_quick_stock_out"] is True and rows[without]["offline_document"] is None
    voucher = rows[with_doc]["offline_document"]
    assert voucher["remark"] == "SJ-002" and voucher["file_count"] == 2
    assert sorted(f["mime_type"] for f in voucher["files"]) == ["application/pdf", "image/png"]

    assert [t["id"] for t in _list(db, voucher="missing")["transactions"]] == [without]
    assert [t["id"] for t in _list(db, voucher="present")["transactions"]] == [with_doc]


def test_attach_voucher_after_stock_out(db):
    tx_id = _stock_out(db)["transaction_id"]
    doc_id = _new_doc(db)
    with pytest.raises(HTTPException) as exc:  # 空票据不能补传
        _run(stock.attach_transaction_offline_document(tx_id, {"offline_document_id": doc_id}, db=db, current_user=OPERATOR))
    assert exc.value.detail == "请先上传凭证照片或 PDF"

    _upload(db, doc_id, "late.pdf", PDF, "application/pdf")
    res = _run(stock.attach_transaction_offline_document(tx_id, {"offline_document_id": doc_id}, db=db, current_user=OPERATOR))
    assert res["offline_document"]["file_count"] == 1
    assert _list(db, voucher="missing")["transactions"] == []


def test_update_remark(db):
    doc_id = _new_doc(db)
    res = _run(stock.update_offline_document(doc_id, {"remark": " SJ-9 "}, db=db, current_user=OPERATOR))
    assert res["remark"] == "SJ-9"


def test_voucher_messages_translated():
    for text in (stock.VOUCHER_REQUIRED_DETAIL, "仅支持 jpg/jpeg/png 图片或 PDF 文件", "文件不是有效的 PDF", "请先上传凭证照片或 PDF"):
        assert text in EXACT
