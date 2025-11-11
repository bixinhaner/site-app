from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
import io
import pandas as pd
from datetime import datetime

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.schemas.site import (
    SiteCreate, SiteUpdate, SiteResponse,
    BasicBatchImportReport, BasicImportRowResult, BasicImportHistoryItem,
)
from app.api.auth import get_current_user
from sqlalchemy import func
from pydantic import BaseModel
from app.models.work_order import AuditEvent

router = APIRouter()

@router.post("/", response_model=SiteResponse)
async def create_site(
    site_data: SiteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 检查站点编码是否已存在
    existing_site = db.query(Site).filter(Site.site_code == site_data.site_code).first()
    if existing_site:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Site code already exists"
        )
    
    # 创建新站点
    db_site = Site(
        **site_data.dict(),
        created_by=current_user.id
    )
    db.add(db_site)
    db.commit()
    db.refresh(db_site)
    
    return SiteResponse.from_orm(db_site)

@router.get("/", response_model=List[SiteResponse])
async def get_sites(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = Query(None),
    site_type: Optional[str] = Query(None),
    assigned_to: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Site)

    # 权限控制：inspector和admin/manager都可以查看所有站点（只读）
    # 只有普通user需要过滤assigned_to
    if current_user.role == "user":
        query = query.filter(Site.assigned_to == current_user.id)

    # 应用过滤条件
    if status:
        query = query.filter(Site.status == status)
    if site_type:
        query = query.filter(Site.site_type == site_type)
    if assigned_to:
        query = query.filter(Site.assigned_to == assigned_to)

    sites = query.offset(skip).limit(limit).all()
    return [SiteResponse.from_orm(site) for site in sites]


# ===== 基础信息批量导入（模板/上传/历史） =====
@router.get("/basic/batch-template")
async def download_basic_template():
    """下载基础信息批量导入模板（仅 Sites 表）。"""
    sites_df = pd.DataFrame([
        {
            "site_code": "SITE001",
            "site_name": "样例站点A",
            "site_type": "macro",
            "province": "北京",
            "city": "北京",
            "district": "朝阳区",
            "address": "某路1号",
            "latitude": 39.9,
            "longitude": 116.3,
            "priority": "normal",
            "contact_person": "张三",
            "contact_phone": "13800000000",
            "description": "示例备注",
        }
    ])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sites_df.to_excel(writer, sheet_name="Sites", index=False)
    output.seek(0)
    headers = {"Content-Disposition": "attachment; filename=site_basic_template.xlsx"}
    return StreamingResponse(output, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers=headers)


@router.post("/basic/batch-upload", response_model=BasicBatchImportReport)
async def basic_batch_upload(
    file: UploadFile = File(...),
    dry_run: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    content = await file.read()
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 Excel(.xlsx/.xls)")

    excel = pd.ExcelFile(io.BytesIO(content))
    if "Sites" not in excel.sheet_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少工作表: Sites")

    df = excel.parse("Sites")
    results: List[BasicImportRowResult] = []
    success_count = 0
    failed_count = 0
    total_rows = int(len(df.index))
    batch_id = uuid.uuid4().hex

    # 预取所有已存在的 site_code，便于快速校验
    existing_codes = set([s.site_code for s in db.query(Site.site_code).all()])
    seen_in_file = set()

    for i, row in enumerate(df.itertuples(index=False), start=2):  # 从第2行开始（表头占第1行）
        row_dict = row._asdict() if hasattr(row, "_asdict") else dict(zip(df.columns.tolist(), list(row)))
        site_code = str(row_dict.get("site_code") or "").strip()
        site_name = str(row_dict.get("site_name") or "").strip()
        errors: List[str] = []
        warnings: List[str] = []

        if not site_code:
            errors.append("缺少必填列: site_code")
        if not site_name:
            errors.append("缺少必填列: site_name")
        # 文件内重复
        if site_code:
            if site_code in seen_in_file:
                errors.append(f"文件内重复的站点编码: {site_code}")
            else:
                seen_in_file.add(site_code)

        # DB 冲突策略：存在即报错，不更新
        if site_code and site_code in existing_codes:
            errors.append(f"站点编码已存在: {site_code}")

        # 经纬度范围
        lat = row_dict.get("latitude")
        lon = row_dict.get("longitude")
        try:
            if lat is not None and str(lat).strip() != "":
                latf = float(lat)
                if not (-90 <= latf <= 90):
                    errors.append("纬度超出范围[-90,90]")
        except Exception:
            errors.append("纬度格式错误")
        try:
            if lon is not None and str(lon).strip() != "":
                lonf = float(lon)
                if not (-180 <= lonf <= 180):
                    errors.append("经度超出范围[-180,180]")
        except Exception:
            errors.append("经度格式错误")

        if errors:
            results.append(BasicImportRowResult(row_index=i, site_code=site_code or None, success=False, action=None, warnings=warnings, errors=errors))
            failed_count += 1
            continue

        # 构造站点对象（不持久化于 dry_run）
        payload = dict(
            site_code=site_code,
            site_name=site_name,
            site_type=(str(row_dict.get("site_type")) if row_dict.get("site_type") is not None else None),
            address=(str(row_dict.get("address")) if row_dict.get("address") is not None else None),
            latitude=(float(row_dict.get("latitude")) if row_dict.get("latitude") not in (None, "") else None),
            longitude=(float(row_dict.get("longitude")) if row_dict.get("longitude") not in (None, "") else None),
            province=(str(row_dict.get("province")) if row_dict.get("province") is not None else None),
            city=(str(row_dict.get("city")) if row_dict.get("city") is not None else None),
            district=(str(row_dict.get("district")) if row_dict.get("district") is not None else None),
            priority=(str(row_dict.get("priority")) if row_dict.get("priority") is not None else "normal"),
            description=(str(row_dict.get("description")) if row_dict.get("description") is not None else None),
            contact_person=(str(row_dict.get("contact_person")) if row_dict.get("contact_person") is not None else None),
            contact_phone=(str(row_dict.get("contact_phone")) if row_dict.get("contact_phone") is not None else None),
        )

        site_id: Optional[int] = None
        if not dry_run:
            site = Site(
                **payload,
                status="survey_pending",
                created_by=current_user.id,
            )
            db.add(site)
            db.flush()  # 获取自增ID
            site_id = site.id
        results.append(BasicImportRowResult(row_index=i, site_code=site_code, success=True, action="created", site_id=site_id, warnings=warnings, errors=[]))
        success_count += 1

    if not dry_run:
        db.commit()

    # 写审计
    try:
        evt = AuditEvent(
            id=batch_id,
            resource_type="site_basic_import",
            resource_id=batch_id,
            action=("dry_run" if dry_run else "import"),
            operator_id=current_user.id,
            comments=f"{file.filename}",
            details={
                "file_name": file.filename,
                "total_rows": total_rows,
                "success_count": success_count,
                "failed_count": failed_count,
            },
        )
        db.add(evt)
        db.commit()
    except Exception:
        db.rollback()

    return BasicBatchImportReport(
        batch_id=batch_id,
        dry_run=dry_run,
        total_rows=total_rows,
        success_count=success_count,
        failed_count=failed_count,
        results=results,
    )


@router.get("/basic/import-history")
async def list_basic_import_history(
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")

    query = db.query(AuditEvent).filter(AuditEvent.resource_type == "site_basic_import")
    total = query.count()
    rows = (
        query.order_by(AuditEvent.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items: List[BasicImportHistoryItem] = []
    for e in rows:
        details = e.details or {}
        items.append(
            BasicImportHistoryItem(
                batch_id=e.id,
                action=e.action,
                operator_id=e.operator_id,
                operator_name=getattr(e.operator, "username", None) if getattr(e, "operator", None) else None,
                file_name=details.get("file_name"),
                created_at=e.created_at,
                total_rows=details.get("total_rows"),
                success_count=details.get("success_count"),
                failed_count=details.get("failed_count"),
            )
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/basic/import-history/{batch_id}")
async def get_basic_import_history_detail(
    batch_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    e = db.query(AuditEvent).filter(AuditEvent.id == batch_id, AuditEvent.resource_type == "site_basic_import").first()
    if not e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="批次不存在")
    return {
        "batch_id": e.id,
        "action": e.action,
        "operator_id": e.operator_id,
        "operator_name": getattr(e.operator, "username", None) if getattr(e, "operator", None) else None,
        "file_name": (e.details or {}).get("file_name"),
        "created_at": e.created_at,
        "summary": e.details or {},
        # 目前仅存汇总，若后期需要详细逐行结果，可扩展单独持久化
    }

@router.get("/{site_id}", response_model=SiteResponse)
async def get_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )

    # 权限控制：inspector可以查看所有站点详情（只读）
    # 只有普通user需要检查assigned_to权限
    if (current_user.role == "user" and
        site.assigned_to != current_user.id and
        site.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    return SiteResponse.from_orm(site)

@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    site_update: SiteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    # 检查权限
    if (current_user.role in ["user", "inspector"] and 
        site.created_by != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    update_data = site_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(site, field, value)
    
    db.commit()
    db.refresh(site)
    
    return SiteResponse.from_orm(site)

@router.delete("/{site_id}")
async def delete_site(
    site_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    site = db.query(Site).filter(Site.id == site_id).first()
    if site is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Site not found"
        )
    
    db.delete(site)
    db.commit()
    
    return {"message": "Site deleted successfully"}


class SiteStatsSummary(BaseModel):
    total_sites: int
    status_stats: dict
    type_stats: dict


@router.get("/stats/summary", response_model=SiteStatsSummary)
async def get_site_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """站点统计信息（管理员/经理）"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    total_sites = db.query(func.count(Site.id)).scalar() or 0

    # 按状态统计
    status_rows = db.query(Site.status, func.count(Site.id)).group_by(Site.status).all()
    status_stats = {str(s or "unknown"): int(c) for s, c in status_rows}

    # 按类型统计
    type_rows = db.query(Site.site_type, func.count(Site.id)).group_by(Site.site_type).all()
    type_stats = {str(t or "unknown"): int(c) for t, c in type_rows}

    return SiteStatsSummary(
        total_sites=total_sites,
        status_stats=status_stats,
        type_stats=type_stats,
    )
