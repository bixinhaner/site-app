from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import io
import pandas as pd

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.planning import (
    SitePlanning, SitePlanningSector, SiteAntennaPort, SiteSwitchPort, PlanningChangeLog
)
from app.schemas.planning import (
    SitePlanningResponse, SitePlanningUpdate, SitePlanningVersion,
    PlanningImportReport, SitePlanningBase, PlanningChangeLogItem,
    BatchImportReport, BatchPlanningResult
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
    if before is None and after is None:
        return {}
    if before is None:
        return {"action": "created"}
    if after is None:
        return {"action": "deleted"}
    diff = {"changed_fields": []}
    for key in ["planning", "sectors", "antenna_ports", "switch_ports"]:
        if (before or {}).get(key) != (after or {}).get(key):
            diff["changed_fields"].append(key)
    return diff


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
    _create_new_version(db, site_id, data, current_user.id, operation="restore", summary=f"Restore to v{version}")
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
async def get_change_logs(site_id: int, skip: int = 0, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    logs = (
        db.query(PlanningChangeLog)
        .filter(PlanningChangeLog.site_id == site_id)
        .order_by(PlanningChangeLog.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [
        PlanningChangeLogItem(
            id=l.id,
            operation=l.operation,
            actor_id=l.actor_id,
            summary=l.summary,
            created_at=l.created_at.isoformat() if l.created_at else "",
            diff=l.diff,
        )
        for l in logs
    ]


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
                if dry_run:
                    # report as would-create
                    warnings.append("站点不存在，将自动创建")
                else:
                    # create new site from Sites sheet
                    try:
                        srow = sites_df[sites_df["SiteCode"].astype(str) == code].iloc[0].to_dict()
                    except Exception:
                        errors.append("Sites 工作表缺少该站点行: " + code)
                        results.append(BatchPlanningResult(site_code=code, success=False, errors=errors))
                        failed_count += 1
                        continue
                    site_name = srow.get("SiteName")
                    if not site_name:
                        errors.append("缺少 SiteName，无法创建站点: " + code)
                        results.append(BatchPlanningResult(site_code=code, success=False, errors=errors))
                        failed_count += 1
                        continue
                    site = Site(
                        site_code=code,
                        site_name=site_name,
                        site_type=srow.get("SiteType"),
                        address=srow.get("Address"),
                        province=srow.get("Province"),
                        city=srow.get("City"),
                        district=srow.get("District"),
                        priority=srow.get("Priority") or "normal",
                        contact_person=srow.get("ContactPerson"),
                        contact_phone=srow.get("ContactPhone"),
                        created_by=current_user.id
                    )
                    db.add(site)
                    db.commit()
                    db.refresh(site)
                    warnings.append("已新建站点")

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
