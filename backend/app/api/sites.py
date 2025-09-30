from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.schemas.site import SiteCreate, SiteUpdate, SiteResponse
from app.api.auth import get_current_user

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