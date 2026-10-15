"""物料申请 / 快速出库“目标站点必填”开关 + 历史备注回填脚本。"""
import asyncio
import csv
import sqlite3
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.api.sites as sites_api
import app.api.stock as stock
from app.core.database import Base
from app.i18n.stock_messages import EXACT as STOCK_MESSAGES
from app.models.equipment import Equipment, EquipmentCategoryEnum, Warehouse
from app.models.material_request import MaterialRequest, MaterialRequestItem, MaterialRequestStatusEnum
from app.models.site import Site
from app.models.user import User
from app.models.work_order import WorkOrder, WorkOrderTypeEnum

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKFILL_SCRIPT = REPO_ROOT / "scripts" / "backfill_material_request_sites.py"

ENGINEER = SimpleNamespace(id=2, role="engineer", is_admin=False)


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            User(id=2, username="eng", email="eng@example.com", hashed_password="x", full_name="Engineer"),
            Warehouse(id=1, warehouse_code="WH1", warehouse_name="Main"),
            Equipment(id=1, equipment_code="CBL", equipment_name="Cable", category=EquipmentCategoryEnum.AUXILIARY),
            Site(id=10, site_code="33SMG_0192", site_name="TBG_PLAMONGAN_INDAH"),
            Site(id=11, site_code="34YYK_0076", site_name="DMT_BLPT_KYAI_MODJO_TEGALREJO"),
        ]
    )
    session.commit()
    # 权限：工程师不管理任何仓库、只能看到自己工单的站点
    monkeypatch.setattr(stock, "_get_managed_warehouse_ids", lambda db, user: set())
    monkeypatch.setattr(sites_api, "_can_view_all_sites", lambda user: False)
    yield session
    session.close()


def _set_flow(db, **values):
    settings = stock._get_flow_settings(db)
    settings.update(values)
    stock._save_flow_settings(db, settings)


def _draft(db, site_id=None):
    req = MaterialRequest(
        id=f"req-{site_id}",
        request_no=f"REQ-{site_id}",
        warehouse_id=1,
        requester_id=ENGINEER.id,
        site_id=site_id,
        status=MaterialRequestStatusEnum.DRAFT,
    )
    db.add(req)
    db.add(MaterialRequestItem(request_id=req.id, equipment_id=1, requested_qty=2))
    db.commit()
    return req.id


def _submit(db, request_id):
    return asyncio.run(stock.submit_material_request(request_id, db=db, current_user=ENGINEER))


def test_defaults_keep_site_optional(db):
    settings = stock._get_flow_settings(db)
    assert settings["material_request_requires_site"] is False
    assert settings["quick_stock_out_requires_site"] is False
    res = _submit(db, _draft(db))
    assert res["request"]["status"] == "submitted"


def test_switch_on_blocks_submit_without_site_but_allows_draft(db):
    _set_flow(db, material_request_requires_site=True)
    request_id = _draft(db)  # 草稿可不填
    with pytest.raises(HTTPException) as exc:
        _submit(db, request_id)
    assert exc.value.status_code == 400
    assert exc.value.detail == stock.SITE_REQUIRED_DETAIL
    assert db.get(MaterialRequest, request_id).status == MaterialRequestStatusEnum.DRAFT


def test_switch_on_allows_submit_with_site(db):
    _set_flow(db, material_request_requires_site=True)
    res = _submit(db, _draft(db, site_id=10))
    assert res["request"]["status"] == "submitted"
    assert res["request"]["site_code"] == "33SMG_0192"


def test_quick_stock_out_requires_site_when_switch_on(db, monkeypatch):
    monkeypatch.setattr(stock, "_ensure_inventory_operator", lambda *a, **k: None)
    _set_flow(db, quick_stock_out_requires_site=True)
    payload = {"warehouse_id": 1, "issued_to": 2, "aux_items": [{"equipment_id": 1, "quantity": 1}]}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(stock.manual_stock_out(payload, db=db, current_user=ENGINEER))
    assert exc.value.detail == stock.SITE_REQUIRED_DETAIL


def test_quick_stock_out_switch_independent_from_request_switch(db, monkeypatch):
    monkeypatch.setattr(stock, "_ensure_inventory_operator", lambda *a, **k: None)
    _set_flow(db, material_request_requires_site=True)
    payload = {"warehouse_id": 1, "issued_to": 2, "aux_items": [{"equipment_id": 1, "quantity": 1}]}
    with pytest.raises(HTTPException) as exc:
        asyncio.run(stock.manual_stock_out(payload, db=db, current_user=ENGINEER))
    # 不是站点必填报错（后续因库存不足等原因失败属正常）
    assert exc.value.detail != stock.SITE_REQUIRED_DETAIL


def _site_option_ids(db):
    res = asyncio.run(stock.get_stock_site_options(keyword=None, limit=30, db=db, current_user=ENGINEER))
    return {s["id"] for s in res["sites"]}


def test_site_options_scope_widens_only_when_site_required(db):
    db.add(WorkOrder(id="wo-1", title="WO", type=WorkOrderTypeEnum.MAINTENANCE, site_id=10, assigned_to=ENGINEER.id, assigned_by=ENGINEER.id))
    db.commit()
    assert _site_option_ids(db) == {10}
    _set_flow(db, material_request_requires_site=True)
    assert _site_option_ids(db) == {10, 11}


def test_site_required_message_translated():
    en, idn = STOCK_MESSAGES[stock.SITE_REQUIRED_DETAIL]
    assert "target site" in en and "situs tujuan" in idn


def _backfill_db(path):
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE sites (id INTEGER PRIMARY KEY, site_code TEXT, site_name TEXT);
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT, full_name TEXT);
        CREATE TABLE material_requests (id TEXT PRIMARY KEY, request_no TEXT, created_at TEXT, status TEXT,
                                        requester_id INTEGER, notes TEXT, site_id INTEGER);
        CREATE TABLE stock_transactions (id TEXT PRIMARY KEY, material_request_id TEXT, site_id INTEGER);
        INSERT INTO sites VALUES (10, '33SMG_0192', 'TBG_PLAMONGAN_INDAH'), (11, '34YYK_0076', 'DMT_BLPT_KYAI_MODJO_TEGALREJO'),
                                 (12, '33BBS_0062', 'DMT_BANJAR_ANYAR');
        INSERT INTO users VALUES (2, 'eng', 'Engineer');
        INSERT INTO material_requests VALUES
          ('a', 'REQ-A', '2026-09-01', 'closed', 2, '33smg 0192', NULL),
          ('b', 'REQ-B', '2026-09-02', 'closed', 2, '34YYK_0076 DMT_BLPT_KYAI_MODJO_TEGALREJO 33SMG_0192 TBG', NULL),
          ('c', 'REQ-C', '2026-09-03', 'closed', 2, '35XXX_0001 (MATERIAL LACKING)', NULL),
          ('d', 'REQ-D', '2026-09-04', 'closed', 2, 'LACKING MATRIAL KABEL POWER DC', NULL),
          ('e', 'REQ-E', '2026-09-05', 'closed', 2, 'for dmt_banjar_anyar', NULL),
          ('f', 'REQ-F', '2026-09-06', 'closed', 2, '33SMG_0192', 11);
        INSERT INTO stock_transactions VALUES ('t1', 'a', NULL), ('t2', 'a', NULL), ('t3', 'b', NULL), ('t4', 'f', 11);
        """
    )
    con.commit()
    con.close()


def _run_backfill(*args):
    return subprocess.run([sys.executable, str(BACKFILL_SCRIPT), *args], capture_output=True, text=True, check=True)


def test_backfill_preview_then_apply(tmp_path):
    db_path = tmp_path / "bf.db"
    report = tmp_path / "unresolved.csv"
    _backfill_db(db_path)

    out = _run_backfill("--db", str(db_path), "--report", str(report)).stdout
    assert "可自动回填：2（关联出入库记录 2 条）" in out
    con = sqlite3.connect(db_path)
    assert con.execute("SELECT COUNT(*) FROM material_requests WHERE site_id IS NOT NULL").fetchone()[0] == 1  # 预览不写

    with open(report, encoding="utf-8-sig") as fh:
        rows = {r["申请单号"]: r for r in csv.DictReader(fh)}
    assert rows["REQ-B"]["原因"] == "备注包含多个站点"
    assert rows["REQ-C"]["原因"] == "站点ID不在站点表"
    assert rows["REQ-D"]["原因"] == "备注中未识别到站点"

    _run_backfill("--db", str(db_path), "--apply")
    sites = dict(con.execute("SELECT id, site_id FROM material_requests").fetchall())
    assert sites == {"a": 10, "b": None, "c": None, "d": None, "e": 12, "f": 11}  # 已有站点不覆盖
    tx = dict(con.execute("SELECT id, site_id FROM stock_transactions").fetchall())
    assert tx == {"t1": 10, "t2": 10, "t3": None, "t4": 11}
    con.close()
