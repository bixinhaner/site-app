from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional, Dict, Any
from datetime import datetime
import io
import pandas as pd

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.planning import (
    SitePlanning,
    SitePlanningSector,
    SiteAntennaPort,
    SiteSwitchPort,
    PlanningChangeLog,
    SitePlanningCell,
)
from app.schemas.planning import (
    SitePlanningResponse,
    SitePlanningUpdate,
    SitePlanningVersion,
    PlanningImportReport,
    SitePlanningBase,
    PlanningChangeLogItem,
    BatchImportReport,
    BatchPlanningResult,
    PlanningCell,
    SitePlanningLldResponse,
    SitePlanningLldSummary,
    PlanningCellUpdate,
    PlanningCellCreate,
)


router = APIRouter()


def _get_current_planning(db: Session, site_id: int) -> Optional[SitePlanning]:
    return (
        db.query(SitePlanning)
        .filter(SitePlanning.site_id == site_id)
        .filter(SitePlanning.is_current == True)
        .first()
    )


def _max_version(db: Session, site_id: int) -> int:
    version = db.query(func.max(SitePlanning.version)).filter(SitePlanning.site_id == site_id).scalar()
    return int(version or 0)


def _snapshot(planning: Optional[SitePlanning]) -> Optional[dict]:
    if not planning:
        return None
    return {
        "planning": {
            "bands": planning.bands or [],
            "sector_count": planning.sector_count or 0,
            "notes": planning.notes or "",
        },
        "sectors": [
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (planning.sectors or [])
        ],
        "antenna_ports": [
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in (planning.antenna_ports or [])
        ],
        "switch_ports": [
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in (planning.switch_ports or [])
        ],
    }


def _compute_diff(before: Optional[dict], after: Optional[dict]) -> dict:
    """
    生成规划变更的简要 diff 信息。

    当前前端只使用 diff.changed_fields 在“日志”Tab 中展示发生变更的模块，
    因此这里主要关注哪些大类发生了变化：planning / sectors / antenna_ports / switch_ports。
    """
    keys = ["planning", "sectors", "antenna_ports", "switch_ports"]

    if before is None and after is None:
        return {}

    # 首次创建或被删除时，也补充 changed_fields，便于前端展示
    if before is None:
        return {"action": "created", "changed_fields": keys}
    if after is None:
        return {"action": "deleted", "changed_fields": keys}

    diff: Dict[str, Any] = {"changed_fields": []}
    for key in keys:
        if (before or {}).get(key) != (after or {}).get(key):
            diff["changed_fields"].append(key)
    return diff


def _compute_lld_cells_diff(
    old_cells: List[SitePlanningCell],
    new_cells: List[dict],
) -> Dict[str, Any]:
    """
    针对 LLD 导入场景，比较导入前后的 Cell 明细差异。

    返回结构示例：
    {
      "changed_fields": ["cells", "cells.tac", "cells.pci"],
      "cell_changes": [
         {
           "key": {"rat": "LTE", "band_code": "B3", "local_cell_id": 1},
           "change_type": "updated",
           "changes": [
              {"field": "tac", "old": "12345", "new": "23456"},
              ...
           ]
         },
         ...
      ]
    }
    """

    def make_key(obj) -> tuple:
        rat = getattr(obj, "rat", None) if isinstance(obj, SitePlanningCell) else obj.get("rat")
        band = getattr(obj, "band_code", None) if isinstance(obj, SitePlanningCell) else obj.get("band_code")
        lcid = getattr(obj, "local_cell_id", None) if isinstance(obj, SitePlanningCell) else obj.get("local_cell_id")
        return (
            str(rat) if rat is not None else None,
            str(band) if band is not None else None,
            int(lcid) if lcid is not None else None,
        )

    # 需要比较的字段：排除 id/planning_id/site_id/timestamps 等
    exclude = {"id", "planning_id", "site_id", "created_at"}
    compare_fields = [
        c.name
        for c in SitePlanningCell.__table__.columns
        if c.name not in exclude
    ]

    old_map: Dict[tuple, SitePlanningCell] = {}
    for c in old_cells:
        k = make_key(c)
        old_map[k] = c

    new_map: Dict[tuple, dict] = {}
    for d in new_cells:
        k = make_key(d)
        if k[0] is None or k[2] is None:
            # 缺少关键信息的行（如没有 RAT 或 LOCAL CELL ID）跳过
            continue
        new_map[k] = d

    all_keys = set(old_map.keys()) | set(new_map.keys())
    changed_fields: set = set()
    cell_changes: List[Dict[str, Any]] = []

    for key in all_keys:
        old = old_map.get(key)
        new = new_map.get(key)

        if old is None and new is not None:
            # 新增的 Cell
            changes = []
            for field in compare_fields:
                new_val = new.get(field)
                if new_val not in (None, ""):
                    changes.append({"field": field, "old": None, "new": new_val})
                    changed_fields.add(f"cells.{field}")
            if changes:
                cell_changes.append(
                    {
                        "key": {
                            "rat": key[0],
                            "band_code": key[1],
                            "local_cell_id": key[2],
                        },
                        "change_type": "created",
                        "changes": changes,
                    }
                )
            continue

        if old is not None and new is None:
            # 删除的 Cell
            changes = []
            for field in compare_fields:
                old_val = getattr(old, field, None)
                if old_val not in (None, ""):
                    changes.append({"field": field, "old": old_val, "new": None})
                    changed_fields.add(f"cells.{field}")
            if changes:
                cell_changes.append(
                    {
                        "key": {
                            "rat": key[0],
                            "band_code": key[1],
                            "local_cell_id": key[2],
                        },
                        "change_type": "deleted",
                        "changes": changes,
                    }
                )
            continue

        # 更新的 Cell：逐字段对比
        per_cell_changes = []
        for field in compare_fields:
            old_val = getattr(old, field, None)
            new_val = new.get(field)
            if old_val != new_val:
                per_cell_changes.append({"field": field, "old": old_val, "new": new_val})
                changed_fields.add(f"cells.{field}")

        if per_cell_changes:
            cell_changes.append(
                {
                    "key": {
                        "rat": key[0],
                        "band_code": key[1],
                        "local_cell_id": key[2],
                    },
                    "change_type": "updated",
                    "changes": per_cell_changes,
                }
            )

    result: Dict[str, Any] = {}
    if changed_fields:
        # 始终包含顶层 cells 标记，方便前端快速识别“有小区变更”
        changed_fields.add("cells")
        result["changed_fields"] = sorted(changed_fields)
    if cell_changes:
        result["cell_changes"] = cell_changes
    return result


def _ensure_site_plannable(site: Site):
    """业务门禁：仅允许在勘察完成后的状态进行规划。

    规则：当站点状态为 survey_pending（勘察前/进行中）时，禁止录入/导入规划。
    允许状态示例：planning, construction, operational, maintenance 等。
    """
    status = getattr(site, 'status', None)
    if status == 'survey_pending':
        raise HTTPException(status_code=409, detail="站点尚处于勘察阶段（survey_pending），暂不允许录入规划信息。请完成勘察后再试。")


def _normalize_tower_id(value) -> Optional[str]:
    """将 Excel 中的 TOWER ID 规范化为用于匹配站点的 SITE ID（site_code）。"""
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _first_not_null(row: dict, candidates) -> Optional[object]:
    """从多列候选中取第一个非空值（排除 NaN 和空字符串）。"""
    for name in candidates:
        if name in row:
            v = row.get(name)
            if pd.isna(v):
                continue
            if isinstance(v, str) and not v.strip():
                continue
            return v
    return None


def _to_str(v) -> Optional[str]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(v).strip()
    return s if s else None


def _to_int(v) -> Optional[int]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(str(v).split('.')[0])
    except Exception:
        return None


def _to_float(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _create_new_version(
    db: Session,
    site_id: int,
    data: SitePlanningBase,
    actor_id: int,
    operation: str,
    summary: Optional[str] = None,
) -> SitePlanning:
    current = _get_current_planning(db, site_id)
    before_snapshot = _snapshot(current)

    # mark previous current to False
    if current:
        current.is_current = False
        db.flush()

    # 确保站点状态从 planning 切换为 planned（仅在第一次形成规划基线时）
    site = db.query(Site).filter(Site.id == site_id).first()
    if site and site.status == "planning":
        site.status = "planned"

    new_version = _max_version(db, site_id) + 1
    planning = SitePlanning(
        site_id=site_id,
        version=new_version,
        bands=data.bands,
        sector_count=data.sector_count,
        notes=data.notes,
        is_current=True,
        created_by=actor_id,
    )
    db.add(planning)
    db.flush()

    # child rows
    for s in data.sectors:
        db.add(
            SitePlanningSector(
                planning_id=planning.id,
                sector_index=s.sector_index,
                azimuth_deg=s.azimuth_deg,
                downtilt_deg=s.downtilt_deg,
                bands=s.bands,
            )
        )
    for p in data.antenna_ports:
        db.add(
            SiteAntennaPort(
                planning_id=planning.id,
                port_label=p.port_label,
                sector_index=p.sector_index,
                band=p.band,
                mimo_chain=p.mimo_chain,
                remarks=p.remarks,
            )
        )
    for sp in data.switch_ports:
        db.add(
            SiteSwitchPort(
                planning_id=planning.id,
                port_no=sp.port_no,
                vlan_ids=sp.vlan_ids,
                is_uplink=sp.is_uplink,
                poe=sp.poe,
                description=sp.description,
            )
        )

    db.commit()
    db.refresh(planning)

    after_snapshot = _snapshot(planning)
    diff = _compute_diff(before_snapshot, after_snapshot)

    # 对 LLD 相关操作，标记 cells 发生变化，便于前端在“日志”Tab 中区分
    if operation.startswith("lld"):
        changed = diff.setdefault("changed_fields", [])
        if "cells" not in changed:
            changed.append("cells")

    log = PlanningChangeLog(
        site_id=site_id,
        planning_id=planning.id,
        operation=operation,
        actor_id=actor_id,
        summary=summary,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        diff=diff,
    )
    db.add(log)
    db.commit()

    return planning


def _collect_lld_rows_by_tower(excel: pd.ExcelFile) -> dict:
    """
    按 TOWER ID 聚合 LLD 行数据。

    返回结构:
        {
          "TOWER_ID": [
              {"rat": "LTE"|"NR", "band_code": "B28"/"N41", "sheet_name": "B28", "row": {...}},
              ...
          ],
          ...
        }
    """
    rows_by_tower = {}
    for sheet_name in excel.sheet_names:
        if not sheet_name:
            continue
        sname = str(sheet_name).strip()
        upper = sname.upper()
        if not (upper.startswith("B") or upper.startswith("N")):
            # 仅处理 B*/N* 这些 4G/5G 规划 sheet
            continue
        rat = "LTE" if upper.startswith("B") else "NR"
        band_code = sname

        df = excel.parse(sheet_name)
        if df.empty:
            continue
        # 去除列名空格，便于字段匹配
        df.rename(columns=lambda c: str(c).strip(), inplace=True)

        for _, r in df.iterrows():
            row_dict = r.to_dict()
            tower_raw = row_dict.get("TOWER ID")
            tower_id = _normalize_tower_id(tower_raw)
            local_cell_val = _first_not_null(row_dict, ["LOCAL CELL ID"])
            if not tower_id or local_cell_val is None:
                # 没有 SITE ID 或 LOCAL CELL ID 的行视为无效
                continue
            rows_by_tower.setdefault(tower_id, []).append(
                {
                    "rat": rat,
                    "band_code": band_code,
                    "sheet_name": sname,
                    "row": row_dict,
                }
            )
    return rows_by_tower


def _build_cell_dict_from_row(
    site_id: int,
    tower_id: str,
    meta: dict,
) -> dict:
    """将 LLD 行解析为 SitePlanningCell 可用的字段字典（不含 planning_id）。"""
    rat = meta["rat"]
    band_code = meta["band_code"]
    sheet_name = meta["sheet_name"]
    row = meta["row"]

    cell = {
        "site_id": site_id,
        "rat": rat,
        "band_code": band_code,
        "sheet_name": sheet_name,
        "tower_id": tower_id,
        "site_information": _to_str(_first_not_null(row, ["SITE INFORMATION"])),
        "site_name": _to_str(_first_not_null(row, ["SITE NAME"])),
        "local_cell_id": _to_int(_first_not_null(row, ["LOCAL CELL ID"])),
        "cell_name": _to_str(_first_not_null(row, ["CELL NAME"])),
        "enb_id": _to_int(_first_not_null(row, ["ENB ID"])),
        "eci": _to_int(_first_not_null(row, ["ECI"])),
        "plmn": _to_str(_first_not_null(row, ["PLMN"])),
        "tac": _to_str(_first_not_null(row, ["TAC"])),
        "pci": _to_int(_first_not_null(row, ["PCI"])),
        "zc_root_index": _to_int(_first_not_null(row, ["ZC Root Index"])),
        "longitude": _to_float(_first_not_null(row, ["Longitude"])),
        "latitude": _to_float(_first_not_null(row, ["Latitude"])),
        "power_dbm": _to_float(_first_not_null(row, ["功率（dbm）", "功率"])),
        "pa": _to_str(_first_not_null(row, ["PA"])),
        "pb": _to_str(_first_not_null(row, ["PB"])),
        "cover_type": _to_str(_first_not_null(row, ["Cover Type"])),
        "band_in_file": _to_str(_first_not_null(row, ["BAND"])),
        "frequency": _to_int(_first_not_null(row, ["Frequency"])),
        "bandwidth": _to_str(_first_not_null(row, ["带宽", "Bandwidth"])),
        "mechanical_downtilt_deg": _to_float(_first_not_null(row, ["机械下倾"])),
        "electrical_downtilt_deg": _to_float(_first_not_null(row, ["电子下倾"])),
        "azimuth_deg": _to_float(_first_not_null(row, ["Azimuth"])),
        "tower_height": _to_float(_first_not_null(row, ["Tower Height"])),
        "antenna_height": _to_float(_first_not_null(row, ["Antenna Height"])),
        "tower_merchants": _to_str(_first_not_null(row, ["Tower Merchants"])),
        "band_combination": _to_str(_first_not_null(row, ["Band Combination"])),
        "antenna_ports": _to_int(_first_not_null(row, ["天线端口"])),
        "cell_allocation": _to_str(_first_not_null(row, ["Cell Allocation"])),
        "tower_name": _to_str(_first_not_null(row, ["TOWER NAME"])),
        "town": _to_str(_first_not_null(row, ["Town"])),
        "region": _to_str(_first_not_null(row, ["Region"])),
        "coverage_area": _to_str(_first_not_null(row, ["覆盖区域"])),
        "coverage_weight": _to_str(_first_not_null(row, ["区域权重"])),
        "scenario": _to_str(_first_not_null(row, ["覆盖场景"])),
        "scenario_weight": _to_str(_first_not_null(row, ["场景权重"])),
        "weight": _to_str(_first_not_null(row, ["综合权重"])),
        "remark": _to_str(_first_not_null(row, ["备注列：调整日期"])),
        # 5G 字段（如果列不存在或为 NaN，会自动为 None）
        "gnb_id": _to_int(_first_not_null(row, ["gNB ID"])),
        "gnb_length": _to_int(_first_not_null(row, ["Gnb length"])),
        "nci": _to_int(_first_not_null(row, ["NCI"])),
        "gnb_wan_ip": _to_str(_first_not_null(row, ["gNB WAN IP"])),
        "master_5gc_ip1": _to_str(_first_not_null(row, ["MASTER 5GC IP1"])),
        "master_5gc_ip2": _to_str(_first_not_null(row, ["MASTER 5GC IP2"])),
        "master_5gc_ip3": _to_str(_first_not_null(row, ["MASTER 5GC IP3"])),
        "backup_5gc_ip1": _to_str(_first_not_null(row, ["BACKUP 5GC IP1"])),
        "backup_5gc_ip2": _to_str(_first_not_null(row, ["BACKUP 5GC IP2"])),
        "backup_5gc_ip3": _to_str(_first_not_null(row, ["BACKUP 5GC IP3"])),
        "master_omc_ip": _to_str(_first_not_null(row, ["MASTER OMC IP"])),
        "backup_omc_ip": _to_str(_first_not_null(row, ["BACKUP OMC IP"])),
        "ntp_ip1": _to_str(_first_not_null(row, ["NTP IP1"])),
        "ntp_ip2": _to_str(_first_not_null(row, ["NTP IP2"])),
        "kssb": _to_float(_first_not_null(row, ["Kssb"])),
        "offset_to_point_a": _to_str(_first_not_null(row, ["Offset to PointA"])),
        "slot_config": _to_str(_first_not_null(row, ["Slot config"])),
        "slot_config_dl_ul": _to_str(_first_not_null(row, ["Slot config DL/UL"])),
        "symbol_config_dl_ul": _to_str(_first_not_null(row, ["Symbol config DL/UL"])),
        "extra_params": None,
    }
    return cell


def _build_planning_from_cells(site_id: int, cells: List[dict]) -> SitePlanningBase:
    """根据 Cell 明细聚合生成 SitePlanningBase（bands + sectors）。"""
    # bands: 使用 band_code 去重
    bands = sorted(
        {c["band_code"] for c in cells if c.get("band_code")}
    )

    # sectors: 以 LOCAL CELL ID 作为扇区号
    sector_ids = sorted(
        {c["local_cell_id"] for c in cells if c.get("local_cell_id") is not None}
    )
    sectors = []
    for sid in sector_ids:
        sec_cells = [c for c in cells if c.get("local_cell_id") == sid]
        # 取第一个有方位角/下倾角的 Cell
        az = None
        mech = None
        elec = None
        for c in sec_cells:
            if az is None and c.get("azimuth_deg") is not None:
                az = c["azimuth_deg"]
            if mech is None and c.get("mechanical_downtilt_deg") is not None:
                mech = c["mechanical_downtilt_deg"]
            if elec is None and c.get("electrical_downtilt_deg") is not None:
                elec = c["electrical_downtilt_deg"]
        downtilt = (mech or 0.0) + (elec or 0.0)
        sector_bands = sorted(
            {c["band_code"] for c in sec_cells if c.get("band_code")}
        )
        sectors.append(
            {
                "sector_index": int(sid),
                "azimuth_deg": float(az or 0.0),
                "downtilt_deg": float(downtilt),
                "bands": sector_bands,
            }
        )

    sector_count = len(sector_ids)

    return SitePlanningBase(
        bands=bands,
        sector_count=sector_count,
        notes=None,
        sectors=sectors,
        antenna_ports=[],
        switch_ports=[],
    )


def _build_lld_summary_from_cells(planning: SitePlanning, cells: List[SitePlanningCell]) -> SitePlanningLldSummary:
    """根据当前规划版本与 Cell 明细构建概要统计。"""
    bands = sorted({c.band_code for c in cells if c.band_code})
    lte_cell_count = sum(1 for c in cells if c.rat == "LTE")
    nr_cell_count = sum(1 for c in cells if c.rat == "NR")

    mech_vals = [c.mechanical_downtilt_deg for c in cells if c.mechanical_downtilt_deg is not None]
    elec_vals = [c.electrical_downtilt_deg for c in cells if c.electrical_downtilt_deg is not None]

    return SitePlanningLldSummary(
        bands=bands,
        sector_count=planning.sector_count or 0,
        lte_cell_count=lte_cell_count,
        nr_cell_count=nr_cell_count,
        mechanical_downtilt_min=min(mech_vals) if mech_vals else None,
        mechanical_downtilt_max=max(mech_vals) if mech_vals else None,
        electrical_downtilt_min=min(elec_vals) if elec_vals else None,
        electrical_downtilt_max=max(elec_vals) if elec_vals else None,
    )


def _sync_planning_from_cells(db: Session, planning: SitePlanning, cells: List[SitePlanningCell]):
    """根据 Cell 明细同步更新基础规划数据，确保数据一致性。"""
    if not cells:
        return planning

    # 从 Cells 聚合基础规划数据
    bands = sorted({c.band_code for c in cells if c.band_code})

    # 获取唯一的扇区ID（基于LOCAL CELL ID）
    sector_ids = sorted({c.local_cell_id for c in cells if c.local_cell_id is not None})

    # 构建或更新扇区数据
    sectors = []
    for sector_id in sector_ids:
        sector_cells = [c for c in cells if c.local_cell_id == sector_id]

        # 从该扇区的Cell中获取方位角和下倾角
        azimuth = 0.0
        mechanical_downtilt = 0.0
        electrical_downtilt = 0.0
        sector_bands = []

        for cell in sector_cells:
            if cell.azimuth_deg is not None:
                azimuth = float(cell.azimuth_deg)
            if cell.mechanical_downtilt_deg is not None:
                mechanical_downtilt = float(cell.mechanical_downtilt_deg)
            if cell.electrical_downtilt_deg is not None:
                electrical_downtilt = float(cell.electrical_downtilt_deg)
            if cell.band_code:
                sector_bands.append(cell.band_code)

        total_downtilt = mechanical_downtilt + electrical_downtilt

        sectors.append({
            "sector_index": int(sector_id),
            "azimuth_deg": azimuth,
            "downtilt_deg": total_downtilt,
            "bands": sorted(set(sector_bands)),
        })

    # 更新基础规划数据
    planning.bands = bands
    planning.sector_count = len(sector_ids)

    # 删除旧的扇区数据并重新创建
    for sector in planning.sectors or []:
        db.delete(sector)

    for sector_data in sectors:
        db.add(SitePlanningSector(
            planning_id=planning.id,
            sector_index=sector_data["sector_index"],
            azimuth_deg=sector_data["azimuth_deg"],
            downtilt_deg=sector_data["downtilt_deg"],
            bands=sector_data["bands"],
        ))

    db.flush()
    return planning


def _validate_cell_data(cell_data: dict, operation: str = "create") -> List[str]:
    """验证Cell数据的业务规则，返回错误信息列表。"""
    errors = []

    # RAT 验证（如果是更新且RAT不在更新数据中，则跳过）
    rat = cell_data.get("rat")
    if rat is not None and rat not in ["LTE", "NR"]:
        errors.append("RAT必须是LTE或NR")

    # 频段验证（如果是更新且band_code不在更新数据中，则跳过）
    band_code = cell_data.get("band_code")
    if band_code is not None and not band_code:
        errors.append("频段代码不能为空")

    # PCI验证 (如果提供)
    pci = cell_data.get("pci")
    if pci is not None:
        if not isinstance(pci, int) or pci < 0 or pci > 503:
            errors.append("PCI必须是0-503之间的整数")

    # 经纬度验证
    longitude = cell_data.get("longitude")
    if longitude is not None and (longitude < -180 or longitude > 180):
        errors.append("经度必须在-180到180之间")

    latitude = cell_data.get("latitude")
    if latitude is not None and (latitude < -90 or latitude > 90):
        errors.append("纬度必须在-90到90之间")

    # 功率验证
    power_dbm = cell_data.get("power_dbm")
    if power_dbm is not None and (power_dbm < -50 or power_dbm > 80):
        errors.append("功率必须在-50到80dBm之间")

    # 角度验证
    azimuth_deg = cell_data.get("azimuth_deg")
    if azimuth_deg is not None and (azimuth_deg < 0 or azimuth_deg > 360):
        errors.append("方位角必须在0到360度之间")

    mechanical_downtilt_deg = cell_data.get("mechanical_downtilt_deg")
    if mechanical_downtilt_deg is not None and (mechanical_downtilt_deg < 0 or mechanical_downtilt_deg > 90):
        errors.append("机械下倾角必须在0到90度之间")

    electrical_downtilt_deg = cell_data.get("electrical_downtilt_deg")
    if electrical_downtilt_deg is not None and (electrical_downtilt_deg < 0 or electrical_downtilt_deg > 90):
        errors.append("电子下倾角必须在0到90度之间")

    # Local Cell ID验证
    local_cell_id = cell_data.get("local_cell_id")
    if local_cell_id is not None:
        if not isinstance(local_cell_id, int) or local_cell_id < 1 or local_cell_id > 65535:
            errors.append("Local Cell ID必须是1-65535之间的整数")

    return errors


def _check_cell_conflicts(db: Session, site_id: int, cell_data: dict, exclude_cell_id: Optional[int] = None) -> List[str]:
    """检查Cell冲突（相同频段和扇区的重复Cell）。"""
    conflicts = []

    local_cell_id = cell_data.get("local_cell_id")
    band_code = cell_data.get("band_code")
    rat = cell_data.get("rat")

    if local_cell_id is None or band_code is None or rat is None:
        return conflicts

    # 查找当前规划版本
    current_planning = _get_current_planning(db, site_id)
    if not current_planning:
        return conflicts

    # 查找冲突的Cell
    conflict_cells = (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.planning_id == current_planning.id,
            SitePlanningCell.site_id == site_id,
            SitePlanningCell.local_cell_id == local_cell_id,
            SitePlanningCell.band_code == band_code,
            SitePlanningCell.rat == rat,
        )
    )

    if exclude_cell_id:
        conflict_cells = conflict_cells.filter(SitePlanningCell.id != exclude_cell_id)

    conflict_cells = conflict_cells.all()

    if conflict_cells:
        conflicts.append(f"已存在相同的Cell: 扇区{local_cell_id} - {rat} {band_code}")

    return conflicts


@router.get("/{site_id}/planning", response_model=SitePlanningResponse)
async def get_current_planning(site_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    planning = _get_current_planning(db, site_id)
    if not planning:
        # return an empty frame with version 0
        raise HTTPException(status_code=404, detail="Planning not found for this site")
    # Eager load children by access
    _ = planning.sectors, planning.antenna_ports, planning.switch_ports
    return SitePlanningResponse(
        id=planning.id,
        site_id=site_id,
        version=planning.version,
        is_current=planning.is_current,
        bands=planning.bands or [],
        sector_count=planning.sector_count or 0,
        notes=planning.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in planning.sectors
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in planning.antenna_ports
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in planning.switch_ports
        ],
    )


@router.put("/{site_id}/planning", response_model=SitePlanningResponse)
async def update_planning(
    site_id: int,
    payload: SitePlanningUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Permissions: admin/manager can write; inspectors/users read only
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    # 生命周期门禁
    _ensure_site_plannable(site)

    # optimistic lock
    current = _get_current_planning(db, site_id)
    if payload.base_version is not None and current and current.version != payload.base_version:
        raise HTTPException(status_code=409, detail=f"Version conflict: current={current.version}, base={payload.base_version}")

    planning = _create_new_version(db, site_id, payload, current_user.id, operation="update", summary="Manual update")

    return await get_current_planning(site_id, db, current_user)


@router.get("/{site_id}/planning/versions", response_model=List[SitePlanningVersion])
async def list_versions(site_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    plans = (
        db.query(SitePlanning)
        .filter(SitePlanning.site_id == site_id)
        .order_by(SitePlanning.version.desc())
        .all()
    )
    return [
        SitePlanningVersion(
            id=p.id,
            site_id=site_id,
            version=p.version,
            is_current=p.is_current,
            created_by=p.created_by,
            created_at=p.created_at.isoformat() if p.created_at else None,
            notes=p.notes,
        )
        for p in plans
    ]


@router.get("/{site_id}/planning/versions/{version}", response_model=SitePlanningResponse)
async def get_version(site_id: int, version: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    planning = (
        db.query(SitePlanning)
        .filter(SitePlanning.site_id == site_id, SitePlanning.version == version)
        .first()
    )
    if not planning:
        raise HTTPException(status_code=404, detail="Version not found")
    _ = planning.sectors, planning.antenna_ports, planning.switch_ports
    return await get_current_planning(site_id, db, current_user) if planning.is_current else SitePlanningResponse(
        id=planning.id,
        site_id=site_id,
        version=planning.version,
        is_current=planning.is_current,
        bands=planning.bands or [],
        sector_count=planning.sector_count or 0,
        notes=planning.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in planning.sectors
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in planning.antenna_ports
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in planning.switch_ports
        ],
    )


@router.post("/{site_id}/planning/versions/{version}/restore", response_model=SitePlanningResponse)
async def restore_version(site_id: int, version: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    planning = (
        db.query(SitePlanning)
        .filter(SitePlanning.site_id == site_id, SitePlanning.version == version)
        .first()
    )
    if not planning:
        raise HTTPException(status_code=404, detail="Version not found")

    # build payload from snapshot
    snap = _snapshot(planning)
    data = SitePlanningBase(
        bands=snap["planning"]["bands"],
        sector_count=snap["planning"]["sector_count"],
        notes=snap["planning"].get("notes"),
        sectors=snap["sectors"],
        antenna_ports=snap["antenna_ports"],
        switch_ports=snap["switch_ports"],
    )
    # 创建新的规划版本
    new_planning = _create_new_version(
        db,
        site_id,
        data,
        current_user.id,
        operation="restore",
        summary=f"Restore to v{version}",
    )

    # 如果被回滚的版本有 LLD Cell 明细，则将其复制到新版本
    old_cells = (
        db.query(SitePlanningCell)
        .filter(SitePlanningCell.planning_id == planning.id)
        .all()
    )
    if old_cells:
        for oc in old_cells:
            cell_kwargs = {
                "site_id": oc.site_id,
                "rat": oc.rat,
                "band_code": oc.band_code,
                "sheet_name": oc.sheet_name,
                "tower_id": oc.tower_id,
                "site_information": oc.site_information,
                "site_name": oc.site_name,
                "local_cell_id": oc.local_cell_id,
                "cell_name": oc.cell_name,
                "enb_id": oc.enb_id,
                "eci": oc.eci,
                "plmn": oc.plmn,
                "tac": oc.tac,
                "pci": oc.pci,
                "zc_root_index": oc.zc_root_index,
                "longitude": oc.longitude,
                "latitude": oc.latitude,
                "power_dbm": oc.power_dbm,
                "pa": oc.pa,
                "pb": oc.pb,
                "cover_type": oc.cover_type,
                "band_in_file": oc.band_in_file,
                "frequency": oc.frequency,
                "bandwidth": oc.bandwidth,
                "mechanical_downtilt_deg": oc.mechanical_downtilt_deg,
                "electrical_downtilt_deg": oc.electrical_downtilt_deg,
                "azimuth_deg": oc.azimuth_deg,
                "tower_height": oc.tower_height,
                "antenna_height": oc.antenna_height,
                "tower_merchants": oc.tower_merchants,
                "band_combination": oc.band_combination,
                "antenna_ports": oc.antenna_ports,
                "cell_allocation": oc.cell_allocation,
                "tower_name": oc.tower_name,
                "town": oc.town,
                "region": oc.region,
                "coverage_area": oc.coverage_area,
                "coverage_weight": oc.coverage_weight,
                "scenario": oc.scenario,
                "scenario_weight": oc.scenario_weight,
                "weight": oc.weight,
                "remark": oc.remark,
                "gnb_id": oc.gnb_id,
                "gnb_length": oc.gnb_length,
                "nci": oc.nci,
                "gnb_wan_ip": oc.gnb_wan_ip,
                "master_5gc_ip1": oc.master_5gc_ip1,
                "master_5gc_ip2": oc.master_5gc_ip2,
                "master_5gc_ip3": oc.master_5gc_ip3,
                "backup_5gc_ip1": oc.backup_5gc_ip1,
                "backup_5gc_ip2": oc.backup_5gc_ip2,
                "backup_5gc_ip3": oc.backup_5gc_ip3,
                "master_omc_ip": oc.master_omc_ip,
                "backup_omc_ip": oc.backup_omc_ip,
                "ntp_ip1": oc.ntp_ip1,
                "ntp_ip2": oc.ntp_ip2,
                "kssb": oc.kssb,
                "offset_to_point_a": oc.offset_to_point_a,
                "slot_config": oc.slot_config,
                "slot_config_dl_ul": oc.slot_config_dl_ul,
                "symbol_config_dl_ul": oc.symbol_config_dl_ul,
                "extra_params": oc.extra_params,
            }
            db.add(SitePlanningCell(planning_id=new_planning.id, **cell_kwargs))
        db.commit()

    return await get_current_planning(site_id, db, current_user)


@router.post("/{site_id}/planning/upload", response_model=PlanningImportReport)
async def upload_planning(
    site_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    # 生命周期门禁
    _ensure_site_plannable(site)

    content = await file.read()
    errors: List[str] = []
    parsed: Optional[SitePlanningBase] = None

    try:
        if file.filename.lower().endswith((".xlsx", ".xls")):
            excel = pd.ExcelFile(io.BytesIO(content))
            # expected sheets
            sheets = excel.sheet_names
            if "Summary" not in sheets:
                errors.append("缺少工作表: Summary")
            summary_df = excel.parse("Summary") if "Summary" in sheets else pd.DataFrame()
            sectors_df = excel.parse("Sectors") if "Sectors" in sheets else pd.DataFrame()
            ant_df = excel.parse("AntennaPorts") if "AntennaPorts" in sheets else pd.DataFrame()
            sw_df = excel.parse("SwitchPorts") if "SwitchPorts" in sheets else pd.DataFrame()

            # build planning
            bands = []
            sector_count = 0
            notes = None
            if not summary_df.empty:
                # assume first row
                row = summary_df.iloc[0].to_dict()
                bands_val = row.get("Bands") or ""
                bands = [b.strip() for b in str(bands_val).split(",") if str(b).strip()]
                sector_count = int(row.get("SectorCount") or 0)
                notes = row.get("Notes")

            sectors = []
            if not sectors_df.empty:
                for _, r in sectors_df.iterrows():
                    sectors.append({
                        "sector_index": int(r.get("SectorIndex") or 0),
                        "azimuth_deg": float(r.get("AzimuthDeg") or 0),
                        "downtilt_deg": float(r.get("DowntiltDeg") or 0),
                        "bands": [b.strip() for b in str(r.get("Bands") or "").split(",") if str(b).strip()],
                    })

            antenna_ports = []
            if not ant_df.empty:
                for _, r in ant_df.iterrows():
                    antenna_ports.append({
                        "port_label": str(r.get("PortLabel") or ""),
                        "sector_index": int(r.get("SectorIndex") or 0),
                        "band": (str(r.get("Band")) if not pd.isna(r.get("Band")) else None),
                        "mimo_chain": (str(r.get("MIMOChain")) if not pd.isna(r.get("MIMOChain")) else None),
                        "remarks": (str(r.get("Remarks")) if not pd.isna(r.get("Remarks")) else None),
                    })

            switch_ports = []
            if not sw_df.empty:
                for _, r in sw_df.iterrows():
                    vlans = str(r.get("VLANs") or "")
                    vlan_ids = [int(x) for x in vlans.split(",") if str(x).strip().isdigit()]
                    switch_ports.append({
                        "port_no": str(r.get("PortNo") or ""),
                        "vlan_ids": vlan_ids,
                        "is_uplink": bool(r.get("IsUplink") == True or str(r.get("IsUplink")).lower() in ("true", "1", "yes")),
                        "poe": bool(r.get("POE") == True or str(r.get("POE")).lower() in ("true", "1", "yes")),
                        "description": (str(r.get("Desc")) if not pd.isna(r.get("Desc")) else None),
                    })

            parsed = SitePlanningBase(
                bands=bands,
                sector_count=sector_count,
                notes=notes,
                sectors=sectors,
                antenna_ports=antenna_ports,
                switch_ports=switch_ports,
            )

        elif file.filename.lower().endswith(".json"):
            import json
            obj = json.loads(content.decode("utf-8"))
            parsed = SitePlanningBase(**obj)
        else:
            errors.append("仅支持 Excel(.xlsx/.xls) 或 JSON 文件")

    except Exception as e:
        errors.append(f"解析失败: {str(e)}")

    if errors:
        return PlanningImportReport(dry_run=dry_run, success=False, errors=errors, warnings=[], parsed=None)

    if dry_run:
        return PlanningImportReport(dry_run=True, success=True, errors=[], warnings=[], parsed=parsed)

    # persist as new version
    planning = _create_new_version(db, site_id, parsed, current_user.id, operation="import", summary=f"Import from {file.filename}")
    return PlanningImportReport(dry_run=False, success=True, errors=[], warnings=[], parsed=parsed)


@router.get("/planning/import-template")
async def download_import_template():
    # produce Excel with 4 sheets
    from fastapi.responses import StreamingResponse

    summary_df = pd.DataFrame([
        {"SiteCode": "SITE001", "Bands": "n41,n78", "SectorCount": 3, "Notes": "example"}
    ])
    sectors_df = pd.DataFrame([
        {"SectorIndex": 1, "AzimuthDeg": 0, "DowntiltDeg": 5, "Bands": "n41"},
        {"SectorIndex": 2, "AzimuthDeg": 120, "DowntiltDeg": 5, "Bands": "n41"},
        {"SectorIndex": 3, "AzimuthDeg": 240, "DowntiltDeg": 5, "Bands": "n41"},
    ])
    ant_df = pd.DataFrame([
        {"PortLabel": "ANT1", "SectorIndex": 1, "Band": "n41", "MIMOChain": "4x4", "Remarks": ""}
    ])
    sw_df = pd.DataFrame([
        {"PortNo": "GE1", "VLANs": "201,202", "IsUplink": True, "POE": False, "Desc": "Uplink"}
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Summary", index=False)
        sectors_df.to_excel(writer, sheet_name="Sectors", index=False)
        ant_df.to_excel(writer, sheet_name="AntennaPorts", index=False)
        sw_df.to_excel(writer, sheet_name="SwitchPorts", index=False)
    output.seek(0)

    headers = {
        "Content-Disposition": "attachment; filename=site_planning_template.xlsx"
    }
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@router.get("/{site_id}/planning/logs", response_model=List[PlanningChangeLogItem])
async def get_change_logs(
    site_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    logs = (
        db.query(PlanningChangeLog)
        .filter(PlanningChangeLog.site_id == site_id)
        .order_by(PlanningChangeLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items: List[PlanningChangeLogItem] = []

    for l in logs:
        diff: Dict[str, Any] = l.diff or {}

        # 针对 LLD 相关操作，如果当初未写入 cell_changes，则在查询时按需补齐一次，
        # 以便前端“查看详情”能看到字段级别的 Cell 差异。
        try:
            if (l.operation or "").startswith("lld") and not diff.get("cell_changes"):
                planning = l.planning
                if planning:
                    current_plan = planning
                    prev_plan = (
                        db.query(SitePlanning)
                        .filter(
                            SitePlanning.site_id == l.site_id,
                            SitePlanning.version < current_plan.version,
                        )
                        .order_by(SitePlanning.version.desc())
                        .first()
                    )

                    old_cells: List[SitePlanningCell] = []
                    if prev_plan:
                        old_cells = (
                            db.query(SitePlanningCell)
                            .filter(SitePlanningCell.planning_id == prev_plan.id)
                            .all()
                        )

                    new_cells_db = (
                        db.query(SitePlanningCell)
                        .filter(SitePlanningCell.planning_id == current_plan.id)
                        .all()
                    )
                    new_cells: List[dict] = []
                    for c in new_cells_db:
                        d = {col.name: getattr(c, col.name) for col in SitePlanningCell.__table__.columns}
                        new_cells.append(d)

                    cell_diff = _compute_lld_cells_diff(old_cells, new_cells)
                    if cell_diff:
                        existing_cf = set(diff.get("changed_fields") or [])
                        for f in cell_diff.get("changed_fields") or []:
                            existing_cf.add(f)
                        if existing_cf:
                            diff["changed_fields"] = sorted(existing_cf)

                        existing_cc = diff.get("cell_changes") or []
                        existing_cc.extend(cell_diff.get("cell_changes") or [])
                        if existing_cc:
                            diff["cell_changes"] = existing_cc
        except Exception:
            # 补充 diff 失败不应影响主流程
            pass

        items.append(
            PlanningChangeLogItem(
                id=l.id,
                operation=l.operation,
                actor_id=l.actor_id,
                actor_name=getattr(l.actor, "username", None),
                summary=l.summary,
                created_at=l.created_at.isoformat() if l.created_at else "",
                diff=diff,
            )
        )

    return items


@router.get("/planning/batch-template")
async def download_batch_template():
    from fastapi.responses import StreamingResponse
    # Multi-site sheets include SiteCode column in all detail sheets
    sites_df = pd.DataFrame([
        {
            "SiteCode": "SITE001",
            "SiteName": "样例站点A",
            "SiteType": "macro",
            "Province": "北京",
            "City": "北京",
            "District": "朝阳区",
            "Address": "某路1号",
            "Priority": "normal",
            "ContactPerson": "张三",
            "ContactPhone": "13800000000",
            "Bands": "n41,n78",
            "SectorCount": 3,
            "Notes": "示例备注A"
        },
        {
            "SiteCode": "SITE002",
            "SiteName": "样例站点B",
            "SiteType": "macro",
            "Province": "上海",
            "City": "上海",
            "District": "浦东新区",
            "Address": "某路2号",
            "Priority": "high",
            "ContactPerson": "李四",
            "ContactPhone": "13900000000",
            "Bands": "n41",
            "SectorCount": 3,
            "Notes": "示例备注B"
        },
    ])
    sectors_df = pd.DataFrame([
        {"SiteCode": "SITE001", "SectorIndex": 1, "AzimuthDeg": 0, "DowntiltDeg": 5, "Bands": "n41"},
        {"SiteCode": "SITE001", "SectorIndex": 2, "AzimuthDeg": 120, "DowntiltDeg": 5, "Bands": "n41"},
        {"SiteCode": "SITE001", "SectorIndex": 3, "AzimuthDeg": 240, "DowntiltDeg": 5, "Bands": "n41"},
        {"SiteCode": "SITE002", "SectorIndex": 1, "AzimuthDeg": 0, "DowntiltDeg": 6, "Bands": "n41"},
        {"SiteCode": "SITE002", "SectorIndex": 2, "AzimuthDeg": 120, "DowntiltDeg": 6, "Bands": "n41"},
        {"SiteCode": "SITE002", "SectorIndex": 3, "AzimuthDeg": 240, "DowntiltDeg": 6, "Bands": "n41"},
    ])
    ant_df = pd.DataFrame([
        {"SiteCode": "SITE001", "PortLabel": "ANT1", "SectorIndex": 1, "Band": "n41", "MIMOChain": "4x4", "Remarks": ""},
        {"SiteCode": "SITE002", "PortLabel": "ANT1", "SectorIndex": 1, "Band": "n41", "MIMOChain": "4x4", "Remarks": ""},
    ])
    sw_df = pd.DataFrame([
        {"SiteCode": "SITE001", "PortNo": "GE1", "VLANs": "201,202", "IsUplink": True, "POE": False, "Desc": "Uplink"},
        {"SiteCode": "SITE002", "PortNo": "GE1", "VLANs": "301,302", "IsUplink": True, "POE": False, "Desc": "Uplink"},
    ])
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="Sites", index=False)
        sectors_df.to_excel(writer, sheet_name="Sectors", index=False)
        ant_df.to_excel(writer, sheet_name="AntennaPorts", index=False)
        sw_df.to_excel(writer, sheet_name="SwitchPorts", index=False)
    output.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=site_planning_batch_template.xlsx"
    }
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@router.post("/planning/batch-upload", response_model=BatchImportReport)
async def batch_upload_planning(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 Excel(.xlsx/.xls)")

    excel = pd.ExcelFile(io.BytesIO(content))
    required = ["Sites", "Sectors", "AntennaPorts", "SwitchPorts"]
    for name in required:
        if name not in excel.sheet_names:
            raise HTTPException(status_code=400, detail=f"缺少工作表: {name}")

    sites_df = excel.parse("Sites")
    sectors_df = excel.parse("Sectors")
    ant_df = excel.parse("AntennaPorts")
    sw_df = excel.parse("SwitchPorts")

    results: List[BatchPlanningResult] = []
    success_count = 0
    failed_count = 0

    site_codes = [str(x).strip() for x in sites_df.get("SiteCode", []) if str(x).strip()]
    unique_codes = list(dict.fromkeys(site_codes))

    for code in unique_codes:
        errors: List[str] = []
        warnings: List[str] = []
        try:
            site = db.query(Site).filter(Site.site_code == code).first()
            if not site:
                errors.append("站点不存在：请先在‘站点信息导入’创建站点并完成勘察")
                results.append(BatchPlanningResult(site_code=code, success=False, errors=errors))
                failed_count += 1
                continue
            # 生命周期门禁
            try:
                _ensure_site_plannable(site)
            except HTTPException as he:
                errors.append(str(he.detail))
                results.append(BatchPlanningResult(site_code=code, site_id=site.id, success=False, errors=errors))
                failed_count += 1
                continue

            srow = sites_df[sites_df["SiteCode"].astype(str) == code].iloc[0].to_dict()
            bands_val = srow.get("Bands") or ""
            bands = [b.strip() for b in str(bands_val).split(",") if str(b).strip()]
            sector_count = int(srow.get("SectorCount") or 0)
            notes = srow.get("Notes")

            sec_rows = sectors_df[sectors_df["SiteCode"].astype(str) == code]
            sectors = []
            for _, r in sec_rows.iterrows():
                sectors.append({
                    "sector_index": int(r.get("SectorIndex") or 0),
                    "azimuth_deg": float(r.get("AzimuthDeg") or 0),
                    "downtilt_deg": float(r.get("DowntiltDeg") or 0),
                    "bands": [b.strip() for b in str(r.get("Bands") or "").split(",") if str(b).strip()],
                })

            ant_rows = ant_df[ant_df["SiteCode"].astype(str) == code]
            ants = []
            for _, r in ant_rows.iterrows():
                ants.append({
                    "port_label": str(r.get("PortLabel") or ""),
                    "sector_index": int(r.get("SectorIndex") or 0),
                    "band": (str(r.get("Band")) if pd.notna(r.get("Band")) else None),
                    "mimo_chain": (str(r.get("MIMOChain")) if pd.notna(r.get("MIMOChain")) else None),
                    "remarks": (str(r.get("Remarks")) if pd.notna(r.get("Remarks")) else None),
                })

            sw_rows = sw_df[sw_df["SiteCode"].astype(str) == code]
            sps = []
            for _, r in sw_rows.iterrows():
                vlans = str(r.get("VLANs") or "")
                vlan_ids = [int(x) for x in vlans.split(",") if str(x).strip().isdigit()]
                sps.append({
                    "port_no": str(r.get("PortNo") or ""),
                    "vlan_ids": vlan_ids,
                    "is_uplink": bool(r.get("IsUplink") == True or str(r.get("IsUplink")).lower() in ("true", "1", "yes")),
                    "poe": bool(r.get("POE") == True or str(r.get("POE")).lower() in ("true", "1", "yes")),
                    "description": (str(r.get("Desc")) if pd.notna(r.get("Desc")) else None),
                })

            parsed = SitePlanningBase(
                bands=bands,
                sector_count=sector_count,
                notes=notes,
                sectors=sectors,
                antenna_ports=ants,
                switch_ports=sps,
            )

            if not dry_run:
                newp = _create_new_version(db, site.id, parsed, current_user.id, operation="import", summary=f"Batch import: {file.filename}")
                results.append(BatchPlanningResult(site_code=code, site_id=site.id, success=True, version_created=newp.version, warnings=warnings))
            else:
                results.append(BatchPlanningResult(site_code=code, site_id=(site.id if site else None), success=True, warnings=warnings))
            success_count += 1

        except Exception as e:
            errors.append(str(e))
            results.append(BatchPlanningResult(site_code=code, success=False, errors=errors))
            failed_count += 1

    return BatchImportReport(
        dry_run=dry_run,
        total_sites=len(unique_codes),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.get("/planning/lld-batch-template")
async def download_lld_batch_template():
    """
    下载 LLD 规划导入模板。

    当前实现直接返回仓库根目录下的
    `Summary of pre planned site LLD_newplan251113V1.xlsx` 文件，
    以保证与规划团队现有模板格式完全一致。
    """
    from fastapi.responses import StreamingResponse
    from pathlib import Path

    base_dir = Path(__file__).resolve().parents[3]
    xlsx_path = base_dir / "Summary of pre planned site LLD_newplan251113V1.xlsx"
    if not xlsx_path.exists():
        raise HTTPException(
            status_code=500,
            detail="LLD 模板文件缺失：请在系统部署目录中放置 Summary of pre planned site LLD_newplan251113V1.xlsx",
        )

    data = xlsx_path.read_bytes()
    output = io.BytesIO(data)
    output.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=site_planning_lld_template.xlsx"
    }
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/planning/lld-batch-upload", response_model=BatchImportReport)
async def lld_batch_upload_planning(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    基于 LLD Excel（B28/B40/B3/N41 等 Sheet）批量导入站点规划。
    使用 TOWER ID 作为 SITE ID，匹配 sites.site_code。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 Excel(.xlsx/.xls)")

    try:
        excel = pd.ExcelFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 解析失败: {e}")

    rows_by_tower = _collect_lld_rows_by_tower(excel)
    if not rows_by_tower:
        raise HTTPException(status_code=400, detail="未在 LLD 文件中找到有效的 B*/N* 规划数据（检查 TOWER ID 与 LOCAL CELL ID 列是否存在且非空）")

    results: List[BatchPlanningResult] = []
    success_count = 0
    failed_count = 0

    for tower_id, metas in rows_by_tower.items():
        errors: List[str] = []
        warnings: List[str] = []
        try:
            site = db.query(Site).filter(Site.site_code == tower_id).first()
            if not site:
                errors.append("站点不存在：请先在‘站点信息导入’创建站点并完成勘察")
                results.append(BatchPlanningResult(site_code=tower_id, success=False, errors=errors))
                failed_count += 1
                continue

            # 生命周期门禁
            try:
                _ensure_site_plannable(site)
            except HTTPException as he:
                errors.append(str(he.detail))
                results.append(BatchPlanningResult(site_code=tower_id, site_id=site.id, success=False, errors=errors))
                failed_count += 1
                continue

            # 构造 Cell 明细
            cell_dicts: List[dict] = []
            for meta in metas:
                cell = _build_cell_dict_from_row(site.id, tower_id, meta)
                if cell.get("local_cell_id") is None:
                    # 理论上上游已经过滤过，这里再次防御
                    continue
                cell_dicts.append(cell)

            if not cell_dicts:
                errors.append("该站点在 LLD 中没有有效的小区行（LOCAL CELL ID 为空）")
                results.append(BatchPlanningResult(site_code=tower_id, site_id=site.id, success=False, errors=errors))
                failed_count += 1
                continue

            lte_cell_count = sum(1 for c in cell_dicts if c.get("rat") == "LTE")
            nr_cell_count = sum(1 for c in cell_dicts if c.get("rat") == "NR")
            bands = sorted({c.get("band_code") for c in cell_dicts if c.get("band_code")})

            if dry_run:
                # 试运行仅返回统计信息，不落库
                results.append(
                    BatchPlanningResult(
                        site_code=tower_id,
                        site_id=site.id,
                        success=True,
                        warnings=warnings,
                        lte_cell_count=lte_cell_count,
                        nr_cell_count=nr_cell_count,
                        bands=bands,
                    )
                )
                success_count += 1
                continue

            # 构造并持久化新的规划版本
            base = _build_planning_from_cells(site.id, cell_dicts)
            planning = _create_new_version(
                db,
                site.id,
                base,
                current_user.id,
                operation="lld_import",
                summary=f"LLD batch import: {file.filename}",
            )

            # 将 cells 与规划版本关联后落库
            for c in cell_dicts:
                db.add(SitePlanningCell(planning_id=planning.id, **c))
            db.commit()

            results.append(
                BatchPlanningResult(
                    site_code=tower_id,
                    site_id=site.id,
                    success=True,
                    version_created=planning.version,
                    warnings=warnings,
                    lte_cell_count=lte_cell_count,
                    nr_cell_count=nr_cell_count,
                    bands=bands,
                )
            )
            success_count += 1
        except Exception as e:
            errors.append(str(e))
            results.append(BatchPlanningResult(site_code=tower_id, success=False, errors=errors))
            failed_count += 1

    return BatchImportReport(
        dry_run=dry_run,
        total_sites=len(rows_by_tower),
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.post("/{site_id}/planning/lld-upload", response_model=BatchPlanningResult)
async def lld_upload_planning_for_site(
    site_id: int,
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    单站 LLD 导入：只处理 LLD 文件中 TOWER ID 与该站点 site_code 匹配的行。
    返回 BatchPlanningResult 以复用前端展示逻辑。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    _ensure_site_plannable(site)

    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 Excel(.xlsx/.xls)")

    try:
        excel = pd.ExcelFile(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 解析失败: {e}")

    rows_by_tower = _collect_lld_rows_by_tower(excel)
    metas = rows_by_tower.get(site.site_code) or []
    if not metas:
        raise HTTPException(status_code=400, detail=f"LLD 文件中未找到与站点编码 {site.site_code} 匹配的 TOWER ID 行")

    errors: List[str] = []
    warnings: List[str] = []

    # 记录导入前的 Cell 列表，用于后续生成 diff
    current_planning = _get_current_planning(db, site.id)
    old_cells: List[SitePlanningCell] = []
    if current_planning:
        old_cells = (
            db.query(SitePlanningCell)
            .filter(
                SitePlanningCell.site_id == site.id,
                SitePlanningCell.planning_id == current_planning.id,
            )
            .all()
        )

    cell_dicts: List[dict] = []
    for meta in metas:
        cell = _build_cell_dict_from_row(site.id, site.site_code, meta)
        if cell.get("local_cell_id") is None:
            continue
        cell_dicts.append(cell)

    if not cell_dicts:
        errors.append("该站点在 LLD 中没有有效的小区行（LOCAL CELL ID 为空）")
        return BatchPlanningResult(site_code=site.site_code, site_id=site.id, success=False, errors=errors)

    lte_cell_count = sum(1 for c in cell_dicts if c.get("rat") == "LTE")
    nr_cell_count = sum(1 for c in cell_dicts if c.get("rat") == "NR")
    bands = sorted({c.get("band_code") for c in cell_dicts if c.get("band_code")})

    if dry_run:
        return BatchPlanningResult(
            site_code=site.site_code,
            site_id=site.id,
            success=True,
            warnings=warnings,
            lte_cell_count=lte_cell_count,
            nr_cell_count=nr_cell_count,
            bands=bands,
        )

    base = _build_planning_from_cells(site.id, cell_dicts)
    planning = _create_new_version(
        db,
        site.id,
        base,
        current_user.id,
        operation="lld_import",
        summary=f"LLD single-site import: {file.filename}",
    )
    for c in cell_dicts:
        db.add(SitePlanningCell(planning_id=planning.id, **c))
    db.commit()

    # 基于导入前后的 Cell 列表，构建更细粒度的 diff（字段级别变更）
    try:
        cell_diff = _compute_lld_cells_diff(old_cells, cell_dicts)
        if cell_diff:
            log_entry = (
                db.query(PlanningChangeLog)
                .filter(PlanningChangeLog.planning_id == planning.id)
                .order_by(PlanningChangeLog.created_at.desc())
                .first()
            )
            if log_entry:
                merged = log_entry.diff or {}
                # 合并 changed_fields
                existing_cf = set(merged.get("changed_fields") or [])
                for f in cell_diff.get("changed_fields") or []:
                    existing_cf.add(f)
                if existing_cf:
                    merged["changed_fields"] = sorted(existing_cf)
                # 合并 cell_changes
                existing_cc = merged.get("cell_changes") or []
                existing_cc.extend(cell_diff.get("cell_changes") or [])
                if existing_cc:
                    merged["cell_changes"] = existing_cc
                log_entry.diff = merged
                db.add(log_entry)
                db.commit()
    except Exception:
        # diff 生成失败不影响主流程
        pass

    return BatchPlanningResult(
        site_code=site.site_code,
        site_id=site.id,
        success=True,
        version_created=planning.version,
        warnings=warnings,
        lte_cell_count=lte_cell_count,
        nr_cell_count=nr_cell_count,
        bands=bands,
    )


@router.get("/{site_id}/planning/lld", response_model=SitePlanningLldResponse)
async def get_lld_planning(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前版本的 LLD 规划数据：包括 SitePlanning 概要 + Cell 明细 + 汇总信息。
    """
    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    planning = _get_current_planning(db, site_id)
    if not planning:
        raise HTTPException(status_code=404, detail="Planning not found for this site")

    cells = (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.site_id == site_id,
            SitePlanningCell.planning_id == planning.id,
        )
        .order_by(SitePlanningCell.rat.asc(), SitePlanningCell.band_code.asc(), SitePlanningCell.local_cell_id.asc())
        .all()
    )

    summary = _build_lld_summary_from_cells(planning, cells)
    # 直接复用已有的 get_current_planning 构建概要
    planning_resp = await get_current_planning(site_id, db, current_user)

    cell_models = [PlanningCell.model_validate(c, from_attributes=True) for c in cells]

    return SitePlanningLldResponse(
        planning=planning_resp,
        cells=cell_models,
        summary=summary,
    )


@router.put("/{site_id}/planning/lld", response_model=SitePlanningLldResponse)
async def update_lld_planning(
    site_id: int,
    base_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    批量更新 LLD 规划（基于现有规划创建新版本）。
    主要用于前端编辑后保存整个规划状态，保持版本管理。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    _ensure_site_plannable(site)

    current = _get_current_planning(db, site_id)
    if not current:
        raise HTTPException(status_code=404, detail="No existing planning found for this site")

    # 乐观锁检查
    if current.version != base_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: current={current.version}, base={base_version}"
        )

    # 创建新版本（当前无变更，只是版本递增）
    old_snapshot = _snapshot(current)
    data = SitePlanningBase(
        bands=current.bands or [],
        sector_count=current.sector_count or 0,
        notes=current.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (current.sectors or [])
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in (current.antenna_ports or [])
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in (current.switch_ports or [])
        ],
    )

    new_planning = _create_new_version(
        db,
        site_id,
        data,
        current_user.id,
        operation="lld_update",
        summary="Manual LLD planning update",
    )

    return await get_lld_planning(site_id, db, current_user)


@router.post("/{site_id}/planning/lld/cells", response_model=PlanningCell)
async def create_lld_cell(
    site_id: int,
    cell_data: PlanningCellCreate,
    base_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    添加新的 LLD Cell。
    会自动创建新规划版本并更新基础规划数据。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    _ensure_site_plannable(site)

    current = _get_current_planning(db, site_id)
    if not current:
        raise HTTPException(status_code=404, detail="No existing planning found for this site")

    # 乐观锁检查
    if current.version != base_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: current={current.version}, base={base_version}"
        )

    # 验证Cell数据
    cell_dict = cell_data.model_dump()
    validation_errors = _validate_cell_data(cell_dict, "create")
    if validation_errors:
        raise HTTPException(status_code=400, detail={"errors": validation_errors})

    # 检查Cell冲突
    conflicts = _check_cell_conflicts(db, site_id, cell_dict)
    if conflicts:
        raise HTTPException(status_code=409, detail={"conflicts": conflicts})

    # 创建新规划版本
    old_snapshot = _snapshot(current)
    data = SitePlanningBase(
        bands=current.bands or [],
        sector_count=current.sector_count or 0,
        notes=current.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (current.sectors or [])
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in (current.antenna_ports or [])
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in (current.switch_ports or [])
        ],
    )

    new_planning = _create_new_version(
        db,
        site_id,
        data,
        current_user.id,
        operation="lld_add_cell",
        summary=f"Add new {cell_data.rat} cell: {cell_data.band_code}",
    )

    # 创建新的 Cell
    cell_data = cell_dict.copy()
    if 'sheet_name' not in cell_data or not cell_data['sheet_name']:
        cell_data['sheet_name'] = f"{cell_data.get('rat', 'UNKNOWN')}-{cell_data.get('band_code', 'UNKNOWN')}"

    cell = SitePlanningCell(
        planning_id=new_planning.id,
        site_id=site_id,
        tower_id=site.site_code,
        **cell_data
    )
    db.add(cell)
    db.commit()
    db.refresh(cell)

    # 同步基础规划数据
    all_cells = db.query(SitePlanningCell).filter(SitePlanningCell.planning_id == new_planning.id).all()
    _sync_planning_from_cells(db, new_planning, all_cells)
    db.commit()

    return PlanningCell.model_validate(cell, from_attributes=True)


@router.put("/{site_id}/planning/lld/cells/{cell_id}", response_model=PlanningCell)
async def update_lld_cell(
    site_id: int,
    cell_id: int,
    cell_data: PlanningCellUpdate,
    base_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新指定的 LLD Cell。
    会自动创建新规划版本并复制其他 Cell 到新版本。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    _ensure_site_plannable(site)

    current = _get_current_planning(db, site_id)
    if not current:
        raise HTTPException(status_code=404, detail="No existing planning found for this site")

    # 乐观锁检查
    if current.version != base_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: current={current.version}, base={base_version}"
        )

    # 查找要更新的 Cell
    existing_cell = (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.id == cell_id,
            SitePlanningCell.site_id == site_id,
            SitePlanningCell.planning_id == current.id,
        )
        .first()
    )
    if not existing_cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    # 验证更新数据，并预先构建 Cell 级字段差异，便于写入变更日志
    update_dict = cell_data.model_dump(exclude_unset=True)
    field_changes: List[Dict[str, Any]] = []
    if update_dict:
        validation_errors = _validate_cell_data(update_dict, "update")
        if validation_errors:
            raise HTTPException(status_code=400, detail={"errors": validation_errors})

        # 检查更新后的数据是否会造成冲突
        merged_data = existing_cell.__dict__.copy()
        merged_data.update(update_dict)
        conflicts = _check_cell_conflicts(db, site_id, merged_data, exclude_cell_id=cell_id)
        if conflicts:
            raise HTTPException(status_code=409, detail={"conflicts": conflicts})

        # 记录字段级别变更（例如 TAC 从 A 改成 B），用于后续写入 PlanningChangeLog.diff
        for field, new_value in update_dict.items():
            old_value = getattr(existing_cell, field, None)
            if old_value != new_value:
                field_changes.append(
                    {
                        "field": field,
                        "old": old_value,
                        "new": new_value,
                    }
                )

    # 创建新规划版本
    old_snapshot = _snapshot(current)
    data = SitePlanningBase(
        bands=current.bands or [],
        sector_count=current.sector_count or 0,
        notes=current.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (current.sectors or [])
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in (current.antenna_ports or [])
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in (current.switch_ports or [])
        ],
    )

    new_planning = _create_new_version(
        db,
        site_id,
        data,
        current_user.id,
        operation="lld_update_cell",
        summary=f"Update {existing_cell.rat} cell: {existing_cell.band_code}",
    )

    # 复制所有现有的 Cell 到新版本
    old_cells = (
        db.query(SitePlanningCell)
        .filter(SitePlanningCell.planning_id == current.id)
        .all()
    )
    for old_cell in old_cells:
        if old_cell.id == cell_id:
            # 更新目标 Cell
            update_data = cell_data.model_dump(exclude_unset=True)
            for key, value in update_data.items():
                setattr(old_cell, key, value)
            old_cell.planning_id = new_planning.id
            db.add(old_cell)
        else:
            # 复制其他 Cell
            cell_kwargs = {
                "site_id": old_cell.site_id,
                "rat": old_cell.rat,
                "band_code": old_cell.band_code,
                "sheet_name": old_cell.sheet_name,
                "tower_id": old_cell.tower_id,
                "site_information": old_cell.site_information,
                "site_name": old_cell.site_name,
                "local_cell_id": old_cell.local_cell_id,
                "cell_name": old_cell.cell_name,
                "enb_id": old_cell.enb_id,
                "eci": old_cell.eci,
                "plmn": old_cell.plmn,
                "tac": old_cell.tac,
                "pci": old_cell.pci,
                "zc_root_index": old_cell.zc_root_index,
                "longitude": old_cell.longitude,
                "latitude": old_cell.latitude,
                "power_dbm": old_cell.power_dbm,
                "pa": old_cell.pa,
                "pb": old_cell.pb,
                "cover_type": old_cell.cover_type,
                "band_in_file": old_cell.band_in_file,
                "frequency": old_cell.frequency,
                "bandwidth": old_cell.bandwidth,
                "mechanical_downtilt_deg": old_cell.mechanical_downtilt_deg,
                "electrical_downtilt_deg": old_cell.electrical_downtilt_deg,
                "azimuth_deg": old_cell.azimuth_deg,
                "tower_height": old_cell.tower_height,
                "antenna_height": old_cell.antenna_height,
                "tower_merchants": old_cell.tower_merchants,
                "band_combination": old_cell.band_combination,
                "antenna_ports": old_cell.antenna_ports,
                "cell_allocation": old_cell.cell_allocation,
                "tower_name": old_cell.tower_name,
                "town": old_cell.town,
                "region": old_cell.region,
                "coverage_area": old_cell.coverage_area,
                "coverage_weight": old_cell.coverage_weight,
                "scenario": old_cell.scenario,
                "scenario_weight": old_cell.scenario_weight,
                "weight": old_cell.weight,
                "remark": old_cell.remark,
                "gnb_id": old_cell.gnb_id,
                "gnb_length": old_cell.gnb_length,
                "nci": old_cell.nci,
                "gnb_wan_ip": old_cell.gnb_wan_ip,
                "master_5gc_ip1": old_cell.master_5gc_ip1,
                "master_5gc_ip2": old_cell.master_5gc_ip2,
                "master_5gc_ip3": old_cell.master_5gc_ip3,
                "backup_5gc_ip1": old_cell.backup_5gc_ip1,
                "backup_5gc_ip2": old_cell.backup_5gc_ip2,
                "backup_5gc_ip3": old_cell.backup_5gc_ip3,
                "master_omc_ip": old_cell.master_omc_ip,
                "backup_omc_ip": old_cell.backup_omc_ip,
                "ntp_ip1": old_cell.ntp_ip1,
                "ntp_ip2": old_cell.ntp_ip2,
                "kssb": old_cell.kssb,
                "offset_to_point_a": old_cell.offset_to_point_a,
                "slot_config": old_cell.slot_config,
                "slot_config_dl_ul": old_cell.slot_config_dl_ul,
                "symbol_config_dl_ul": old_cell.symbol_config_dl_ul,
                "extra_params": old_cell.extra_params,
            }
            db.add(SitePlanningCell(planning_id=new_planning.id, **cell_kwargs))

    db.commit()

    # 同步基础规划数据
    all_cells = db.query(SitePlanningCell).filter(SitePlanningCell.planning_id == new_planning.id).all()
    _sync_planning_from_cells(db, new_planning, all_cells)
    db.commit()

    # 将本次 Cell 级别字段变更补充写入规划变更日志的 diff 字段，
    # 便于前端“日志”Tab 精确展示本次修改了哪些参数（例如 TAC、PCI 等）。
    if field_changes:
        log_entry = (
            db.query(PlanningChangeLog)
            .filter(PlanningChangeLog.planning_id == new_planning.id)
            .order_by(PlanningChangeLog.created_at.desc())
            .first()
        )
        if log_entry:
            diff_obj: Dict[str, Any] = log_entry.diff or {}
            # 更新 changed_fields：统一使用 cells.<field> 的形式，便于前端直接展示
            changed_fields = set(diff_obj.get("changed_fields") or [])
            changed_fields.add("cells")
            for ch in field_changes:
                changed_fields.add(f"cells.{ch['field']}")
            diff_obj["changed_fields"] = sorted(changed_fields)

            # 追加 cell_changes 详细记录
            cell_changes = diff_obj.get("cell_changes") or []
            cell_changes.append(
                {
                    "cell_id": existing_cell.id,
                    "rat": existing_cell.rat,
                    "band_code": existing_cell.band_code,
                    "local_cell_id": existing_cell.local_cell_id,
                    "changes": field_changes,
                }
            )
            diff_obj["cell_changes"] = cell_changes

            log_entry.diff = diff_obj
            db.add(log_entry)
            db.commit()

    # 返回更新后的 Cell
    updated_cell = (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.planning_id == new_planning.id,
            SitePlanningCell.local_cell_id == existing_cell.local_cell_id,
            SitePlanningCell.band_code == existing_cell.band_code,
        )
        .first()
    )
    return PlanningCell.model_validate(updated_cell, from_attributes=True)


@router.delete("/{site_id}/planning/lld/cells/{cell_id}")
async def delete_lld_cell(
    site_id: int,
    cell_id: int,
    base_version: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除指定的 LLD Cell。
    会自动创建新规划版本并复制其他 Cell 到新版本。
    """
    if current_user.role not in ["admin", "manager", "planner"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    site = db.query(Site).filter(Site.id == site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    _ensure_site_plannable(site)

    current = _get_current_planning(db, site_id)
    if not current:
        raise HTTPException(status_code=404, detail="No existing planning found for this site")

    # 乐观锁检查
    if current.version != base_version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: current={current.version}, base={base_version}"
        )

    # 查找要删除的 Cell
    existing_cell = (
        db.query(SitePlanningCell)
        .filter(
            SitePlanningCell.id == cell_id,
            SitePlanningCell.site_id == site_id,
            SitePlanningCell.planning_id == current.id,
        )
        .first()
    )
    if not existing_cell:
        raise HTTPException(status_code=404, detail="Cell not found")

    # 创建新规划版本
    old_snapshot = _snapshot(current)
    data = SitePlanningBase(
        bands=current.bands or [],
        sector_count=current.sector_count or 0,
        notes=current.notes,
        sectors=[
            {
                "sector_index": s.sector_index,
                "azimuth_deg": s.azimuth_deg,
                "downtilt_deg": s.downtilt_deg,
                "bands": s.bands or [],
            }
            for s in (current.sectors or [])
        ],
        antenna_ports=[
            {
                "port_label": p.port_label,
                "sector_index": p.sector_index,
                "band": p.band,
                "mimo_chain": p.mimo_chain,
                "remarks": p.remarks,
            }
            for p in (current.antenna_ports or [])
        ],
        switch_ports=[
            {
                "port_no": sp.port_no,
                "vlan_ids": sp.vlan_ids or [],
                "is_uplink": sp.is_uplink,
                "poe": sp.poe,
                "description": sp.description,
            }
            for sp in (current.switch_ports or [])
        ],
    )

    new_planning = _create_new_version(
        db,
        site_id,
        data,
        current_user.id,
        operation="lld_delete_cell",
        summary=f"Delete {existing_cell.rat} cell: {existing_cell.band_code}",
    )

    # 复制除要删除的 Cell 之外的所有 Cell
    old_cells = (
        db.query(SitePlanningCell)
        .filter(SitePlanningCell.planning_id == current.id)
        .all()
    )
    for old_cell in old_cells:
        if old_cell.id != cell_id:
            cell_kwargs = {
                "site_id": old_cell.site_id,
                "rat": old_cell.rat,
                "band_code": old_cell.band_code,
                "sheet_name": old_cell.sheet_name,
                "tower_id": old_cell.tower_id,
                "site_information": old_cell.site_information,
                "site_name": old_cell.site_name,
                "local_cell_id": old_cell.local_cell_id,
                "cell_name": old_cell.cell_name,
                "enb_id": old_cell.enb_id,
                "eci": old_cell.eci,
                "plmn": old_cell.plmn,
                "tac": old_cell.tac,
                "pci": old_cell.pci,
                "zc_root_index": old_cell.zc_root_index,
                "longitude": old_cell.longitude,
                "latitude": old_cell.latitude,
                "power_dbm": old_cell.power_dbm,
                "pa": old_cell.pa,
                "pb": old_cell.pb,
                "cover_type": old_cell.cover_type,
                "band_in_file": old_cell.band_in_file,
                "frequency": old_cell.frequency,
                "bandwidth": old_cell.bandwidth,
                "mechanical_downtilt_deg": old_cell.mechanical_downtilt_deg,
                "electrical_downtilt_deg": old_cell.electrical_downtilt_deg,
                "azimuth_deg": old_cell.azimuth_deg,
                "tower_height": old_cell.tower_height,
                "antenna_height": old_cell.antenna_height,
                "tower_merchants": old_cell.tower_merchants,
                "band_combination": old_cell.band_combination,
                "antenna_ports": old_cell.antenna_ports,
                "cell_allocation": old_cell.cell_allocation,
                "tower_name": old_cell.tower_name,
                "town": old_cell.town,
                "region": old_cell.region,
                "coverage_area": old_cell.coverage_area,
                "coverage_weight": old_cell.coverage_weight,
                "scenario": old_cell.scenario,
                "scenario_weight": old_cell.scenario_weight,
                "weight": old_cell.weight,
                "remark": old_cell.remark,
                "gnb_id": old_cell.gnb_id,
                "gnb_length": old_cell.gnb_length,
                "nci": old_cell.nci,
                "gnb_wan_ip": old_cell.gnb_wan_ip,
                "master_5gc_ip1": old_cell.master_5gc_ip1,
                "master_5gc_ip2": old_cell.master_5gc_ip2,
                "master_5gc_ip3": old_cell.master_5gc_ip3,
                "backup_5gc_ip1": old_cell.backup_5gc_ip1,
                "backup_5gc_ip2": old_cell.backup_5gc_ip2,
                "backup_5gc_ip3": old_cell.backup_5gc_ip3,
                "master_omc_ip": old_cell.master_omc_ip,
                "backup_omc_ip": old_cell.backup_omc_ip,
                "ntp_ip1": old_cell.ntp_ip1,
                "ntp_ip2": old_cell.ntp_ip2,
                "kssb": old_cell.kssb,
                "offset_to_point_a": old_cell.offset_to_point_a,
                "slot_config": old_cell.slot_config,
                "slot_config_dl_ul": old_cell.slot_config_dl_ul,
                "symbol_config_dl_ul": old_cell.symbol_config_dl_ul,
                "extra_params": old_cell.extra_params,
            }
            db.add(SitePlanningCell(planning_id=new_planning.id, **cell_kwargs))

    db.commit()

    # 同步基础规划数据
    all_cells = db.query(SitePlanningCell).filter(SitePlanningCell.planning_id == new_planning.id).all()
    _sync_planning_from_cells(db, new_planning, all_cells)
    db.commit()

    return {"message": "Cell deleted successfully", "deleted_cell_id": cell_id}
