from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
import os
import uuid
import hashlib
import json

from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.site import Site
# 统一使用增强版本的模型
from app.models.inspection import (
    InspectionTemplate, SiteInspection, InspectionCheckItem, 
    InspectionPhoto, InspectionAuditLog, OfflineInspectionData,
    InspectionStatusEnum, CheckItemStatusEnum, InspectionTypeEnum
)
from app.schemas.inspection_enhanced import (
    InspectionTemplateCreate, InspectionTemplateResponse,
    SiteInspectionCreate, SiteInspectionUpdate, SiteInspectionResponse,
    InspectionCheckItemUpdate, InspectionCheckItemResponse,
    InspectionPhotoCreate, InspectionPhotoResponse,
    InspectionReviewRequest, InspectionAuditLogResponse,
    CheckItemReviewRequest, PhotoReviewRequest, InspectionReviewSummary,
    OfflineInspectionDataCreate, InspectionStatistics,
    InspectionSummary, SiteInspectionProgress
)
from app.api.auth import get_current_user
from app.utils.file_handler import save_uploaded_file, generate_watermark
from app.utils.gps_utils import reverse_geocode, validate_gps_accuracy
from app.services.template_resolver import create_resolver, ResolveContext

router = APIRouter()

# 新增工具函数
async def create_default_template(db: Session, site_id: int, inspection_type: str) -> InspectionTemplate:
    """创建默认检查模板"""
    import uuid
    from app.schemas.inspection_enhanced import InspectionTemplateData, CheckCategoryTemplate, CheckItemTemplate
    
    # 根据检查类型创建不同的默认检查项
    template_data = {
        "site_id": str(site_id),
        "site_name": f"站点_{site_id}",
        "template_version": "1.0",
        "check_categories": []
    }
    
    if inspection_type in ['opening', 'OPENING']:
        # 新站点设备安装模板
        template_data["check_categories"] = [
            {
                "category_id": "basic_info",
                "category_name": "基本信息检查",
                "description": "站点基本信息核实",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "tower_id",
                        "item_name": "铁塔编号确认",
                        "description": "核实并拍照记录铁塔编号",
                        "required_type": "photo",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "site_coordinates",
                        "item_name": "站点坐标确认",
                        "description": "使用GPS确认站点实际坐标",
                        "required_type": "data",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            },
            {
                "category_id": "equipment_check",
                "category_name": "设备检查",
                "description": "基站设备状态检查",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "antenna_installation",
                        "item_name": "天线安装检查",
                        "description": "检查天线安装情况和方向角",
                        "required_type": "both",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "cabinet_environment",
                        "item_name": "机柜环境检查",
                        "description": "检查机柜周围环境和安全状况",
                        "required_type": "photo",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            }
        ]
    else:
        # 维护检查模板
        template_data["check_categories"] = [
            {
                "category_id": "maintenance_check",
                "category_name": "维护检查",
                "description": "设备维护状况检查",
                "sector_specific": False,
                "items": [
                    {
                        "item_id": "equipment_status",
                        "item_name": "设备状态检查",
                        "description": "检查设备运行状态",
                        "required_type": "both",
                        "assigned_role": "inspector",
                        "status": "pending"
                    },
                    {
                        "item_id": "signal_quality",
                        "item_name": "信号质量测试",
                        "description": "测试并记录信号质量参数",
                        "required_type": "data",
                        "assigned_role": "inspector",
                        "status": "pending"
                    }
                ]
            }
        ]
    
    # 创建模板记录
    template = InspectionTemplate(
        id=str(uuid.uuid4()),
        site_id=site_id,
        template_name=f"默认{inspection_type}检查模板",
        template_version="1.0",
        template_data=template_data,
        status="approved"
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return template

def calculate_file_hash(file_path: str) -> str:
    """计算文件哈希值"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

@router.post("/", response_model=SiteInspectionResponse)
async def create_inspection(
    inspection_data: SiteInspectionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建站点检查 - 统一接口"""
    template = None
    
    # 获取站点信息用于解析上下文
    site = db.query(Site).filter(Site.id == inspection_data.site_id).first()
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="站点不存在"
        )
    
    # 获取或解析检查模板
    if inspection_data.template_id:
        # 使用指定的模板
        template = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == inspection_data.template_id
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="检查模板不存在"
            )
    else:
        # 使用模板解析器自动匹配模板
        resolver = create_resolver(db)
        
        # 创建解析上下文
        resolve_context = ResolveContext(
            site_id=inspection_data.site_id,
            site_type=getattr(site, 'site_type', None),  # 如果站点有类型字段
            task_id=inspection_data.task_id,
            task_type=inspection_data.inspection_type,
            region=getattr(site, 'region', None),  # 如果站点有区域字段
            customer=getattr(site, 'customer', None),  # 如果站点有客户字段
            tags=[]  # 可以根据需要添加标签
        )
        
        # 解析最匹配的模板
        match_result = resolver.resolve_template(resolve_context)
        
        if match_result:
            template = match_result.template
        else:
            # 兜底：自动创建默认模板
            template = await create_default_template(db, inspection_data.site_id, inspection_data.inspection_type)
    
    # 创建检查记录
    inspection = SiteInspection(
        id=str(uuid.uuid4()),
        site_id=inspection_data.site_id,
        task_id=inspection_data.task_id,
        template_id=template.id,
        inspector_id=current_user.id,
        inspection_type=inspection_data.inspection_type,
        start_time=datetime.utcnow(),
        location=inspection_data.location,
        weather=inspection_data.weather,
        temperature=inspection_data.temperature,
        notes=inspection_data.notes
    )
    
    # 设置GPS信息
    if inspection_data.gps_info:
        inspection.latitude = inspection_data.gps_info.latitude
        inspection.longitude = inspection_data.gps_info.longitude
        inspection.gps_accuracy = inspection_data.gps_info.accuracy
        inspection.address = inspection_data.gps_info.address or await reverse_geocode(
            inspection_data.gps_info.latitude, 
            inspection_data.gps_info.longitude
        )
    
    db.add(inspection)
    db.flush()
    
    # 根据模板创建检查项
    template_data = template.template_data
    total_items = 0
    
    for category in template_data.get("check_categories", []):
        for item in category.get("items", []):
            # 如果是扇区级检查，为每个扇区创建检查项
            if category.get("sector_specific", False):
                # 假设3个扇区，实际应该根据站点配置
                for sector_num in range(1, 4):
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=f"{item['item_id']}_sector_{sector_num}",
                        item_name=f"{item['item_name']} - Sector {sector_num}",
                        category_id=category["category_id"],
                        category_name=category["category_name"],
                        sector_id=str(sector_num),
                        required_type=item["required_type"],
                        status=CheckItemStatusEnum.PENDING
                    )
                    db.add(check_item)
                    total_items += 1
            else:
                # 站点级检查项
                check_item = InspectionCheckItem(
                    id=str(uuid.uuid4()),
                    inspection_id=inspection.id,
                    item_id=item["item_id"],
                    item_name=item["item_name"],
                    category_id=category["category_id"],
                    category_name=category["category_name"],
                    required_type=item["required_type"],
                    status=CheckItemStatusEnum.PENDING
                )
                db.add(check_item)
                total_items += 1
    
    # 更新总检查项数
    inspection.total_items = total_items
    
    db.commit()
    db.refresh(inspection)
    
    # 记录审核日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection.id,
        action="create",
        to_status="draft",
        operator_id=current_user.id,
        comments="创建检查记录"
    )
    db.add(audit_log)
    db.commit()
    
    return inspection

@router.get("/", response_model=List[InspectionSummary])
async def get_inspections(
    skip: int = 0,
    limit: int = 100,
    site_id: Optional[int] = None,
    task_id: Optional[str] = None,
    status: Optional[InspectionStatusEnum] = None,
    inspector_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取站点检查列表 - 统一接口"""
    query = db.query(SiteInspection)
    
    # 权限过滤：施工员只能看到自己的检查记录
    if current_user.role == "inspector":
        query = query.filter(SiteInspection.inspector_id == current_user.id)
    
    if site_id:
        query = query.filter(SiteInspection.site_id == site_id)
    
    if task_id:
        query = query.filter(SiteInspection.task_id == task_id)
    
    if status:
        query = query.filter(SiteInspection.status == status)
    
    if inspector_id:
        query = query.filter(SiteInspection.inspector_id == inspector_id)
    
    inspections = query.offset(skip).limit(limit).all()
    
    # 转换为摘要格式
    summaries = []
    for inspection in inspections:
        summary = InspectionSummary(
            id=inspection.id,
            site_id=inspection.site_id,
            site_name=inspection.site.site_name if inspection.site else None,
            inspector_id=inspection.inspector_id,
            inspector_name=inspection.inspector.full_name if inspection.inspector else None,
            inspection_type=inspection.inspection_type,
            status=inspection.status,
            start_time=inspection.start_time,
            completion_rate=inspection.completion_rate,
            score=inspection.score,
            created_at=inspection.created_at
        )
        summaries.append(summary)
    
    return summaries

@router.get("/detail/{inspection_id}", response_model=SiteInspectionResponse)
async def get_inspection(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取站点检查详情 - 统一接口"""
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (current_user.role == "inspector" and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此检查记录"
        )
    
    return inspection

@router.put("/detail/{inspection_id}", response_model=SiteInspectionResponse)
async def update_inspection(
    inspection_id: str,
    inspection_update: SiteInspectionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新站点检查 - 统一接口"""
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (current_user.role == "inspector" and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此检查记录"
        )
    
    # 更新字段
    old_status = inspection.status
    update_fields = inspection_update.dict(exclude_unset=True)

    # 轻量权限与合法迁移校验：通过/驳回必须走审核接口
    if "status" in update_fields:
        new_status = update_fields["status"]
        if new_status in [InspectionStatusEnum.APPROVED, InspectionStatusEnum.REJECTED]:
            if current_user.role not in ["admin", "manager", "reviewer"]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="没有权限进行审核操作，请使用审核接口"
                )
            if old_status not in [InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="只能从已提交/审核中状态变更为通过/驳回"
                )
    
    for field, value in update_fields.items():
        if field == "gps_info" and value:
            inspection.latitude = value.latitude
            inspection.longitude = value.longitude
            inspection.gps_accuracy = value.accuracy
            if not value.address:
                inspection.address = await reverse_geocode(
                    value.latitude, value.longitude
                )
            else:
                inspection.address = value.address
        else:
            setattr(inspection, field, value)
    
    inspection.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(inspection)
    
    # 记录状态变更日志
    if "status" in update_fields and old_status != inspection.status:
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            action="update_status",
            from_status=old_status.value,
            to_status=inspection.status.value,
            operator_id=current_user.id,
            comments="更新检查状态"
        )
        db.add(audit_log)
        db.commit()
    
    return inspection

@router.post("/detail/{inspection_id}/photos", response_model=InspectionPhotoResponse)
async def upload_inspection_photo(
    inspection_id: str,
    file: UploadFile = File(...),
    check_item_id: Optional[str] = None,
    gps_latitude: float = 0,
    gps_longitude: float = 0,
    gps_accuracy: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传检查照片 - 统一接口"""
    # 验证检查记录存在
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 验证文件类型
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持图片文件"
        )
    
    # 保存文件
    file_path = await save_uploaded_file(file, "inspections", inspection_id)
    
    # 生成水印
    watermark_data = {
        "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "inspector": current_user.full_name or current_user.username,
        "accuracy": f"{gps_accuracy}m" if gps_accuracy else "N/A"
    }
    
    # 添加水印到照片
    watermarked_path = await generate_watermark(file_path, watermark_data)
    
    # 计算文件哈希
    file_hash = calculate_file_hash(watermarked_path)
    
    # 获取地址信息
    address = await reverse_geocode(gps_latitude, gps_longitude)
    
    # 创建照片记录
    photo = InspectionPhoto(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        check_item_id=check_item_id,
        original_name=file.filename,
        file_path=watermarked_path,
        file_size=file.size,
        mime_type=file.content_type,
        latitude=gps_latitude,
        longitude=gps_longitude,
        gps_accuracy=gps_accuracy,
        address=address,
        taken_at=datetime.utcnow(),
        has_watermark=True,
        watermark_data=watermark_data,
        hash_value=file_hash,
        uploaded_by=current_user.id
    )
    
    db.add(photo)
    db.commit()
    db.refresh(photo)
    
    return photo

# Template endpoints moved to template_binding.py
# Old template endpoint removed to avoid routing conflicts

@router.get("/statistics/overview", response_model=InspectionStatistics)
async def get_inspection_statistics(
    site_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查统计信息 - 统一接口"""
    query = db.query(SiteInspection)
    
    if site_id:
        query = query.filter(SiteInspection.site_id == site_id)
    
    if start_date:
        query = query.filter(SiteInspection.created_at >= start_date)
    
    if end_date:
        query = query.filter(SiteInspection.created_at <= end_date)
    
    # 权限过滤
    if current_user.role == "inspector":
        query = query.filter(SiteInspection.inspector_id == current_user.id)
    
    total_inspections = query.count()
    completed_inspections = query.filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.COMPLETED,
            InspectionStatusEnum.APPROVED
        ])
    ).count()
    pending_inspections = query.filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.DRAFT,
            InspectionStatusEnum.IN_PROGRESS,
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW
        ])
    ).count()
    approved_inspections = query.filter(
        SiteInspection.status == InspectionStatusEnum.APPROVED
    ).count()
    rejected_inspections = query.filter(
        SiteInspection.status == InspectionStatusEnum.REJECTED
    ).count()
    
    # 计算平均分
    avg_score_result = query.filter(
        SiteInspection.score.is_not(None)
    ).with_entities(
        func.avg(SiteInspection.score)
    ).scalar()
    
    completion_rate = (completed_inspections / total_inspections * 100) if total_inspections > 0 else 0
    
    return InspectionStatistics(
        total_inspections=total_inspections,
        completed_inspections=completed_inspections,
        pending_inspections=pending_inspections,
        approved_inspections=approved_inspections,
        rejected_inspections=rejected_inspections,
        average_score=round(avg_score_result, 2) if avg_score_result else None,
        completion_rate=round(completion_rate, 2)
    )

@router.get("/detail/{inspection_id}/items", response_model=List[InspectionCheckItemResponse])
async def get_inspection_items(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查项列表"""
    # 验证检查记录存在
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (current_user.role == "inspector" and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限访问此检查记录"
        )
    
    # 获取检查项
    check_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id
    ).all()
    
    return check_items

@router.put("/detail/{inspection_id}/items/{item_id}", response_model=InspectionCheckItemResponse)
async def update_inspection_item(
    inspection_id: str,
    item_id: str,
    item_update: InspectionCheckItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新检查项"""
    # 验证检查记录存在
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查
    if (current_user.role == "inspector" and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限修改此检查记录"
        )
    
    # 验证检查项存在
    check_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == inspection_id
    ).first()
    
    if not check_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查项不存在"
        )
    
    # 更新检查项
    update_fields = item_update.dict(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(check_item, field, value)
    
    # 更新检查人员和时间
    check_item.checked_by = current_user.id
    check_item.checked_at = datetime.utcnow()
    check_item.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(check_item)
    
    # 重新计算检查完成率
    total_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id
    ).count()
    
    completed_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
    ).count()
    
    failed_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.status == CheckItemStatusEnum.FAILED
    ).count()
    
    # 更新检查记录的统计信息
    inspection.total_items = total_items
    inspection.completed_items = completed_items
    inspection.failed_items = failed_items
    inspection.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
    
    db.commit()
    
    return check_item

@router.post("/detail/{inspection_id}/reset")
async def reset_inspection_for_rejected_task(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """为被驳回的任务重置检查记录状态，允许重新编辑"""
    # 验证检查记录存在
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="检查记录不存在"
        )
    
    # 权限检查：只有检查员本人可以重置自己的检查记录
    if (current_user.role == "inspector" and 
        inspection.inspector_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="没有权限重置此检查记录"
        )
    
    # 检查关联的任务是否被驳回
    if inspection.task_id:
        from app.models.inspection import TaskAssignment
        task = db.query(TaskAssignment).filter(
            TaskAssignment.id == inspection.task_id
        ).first()
        
        if not task or task.status.value != "rejected":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能重置被驳回任务的检查记录"
            )
    
    try:
        # 重置检查记录状态为 in_progress
        inspection.status = InspectionStatusEnum.IN_PROGRESS
        inspection.end_time = None
        inspection.submitted_at = None
        inspection.updated_at = datetime.utcnow()
        
        # 重置所有已完成的检查项为待处理状态，允许重新检查
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.status.in_([
                CheckItemStatusEnum.COMPLETED,
                CheckItemStatusEnum.FAILED
            ])
        ).all()
        
        for item in check_items:
            item.status = CheckItemStatusEnum.PENDING
            item.result_data = None
            item.notes = None
            item.checked_by = None
            item.checked_at = None
            item.updated_at = datetime.utcnow()
        
        # 重新计算完成率
        total_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).count()
        
        completed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
        ).count()
        
        inspection.completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        db.commit()
        db.refresh(inspection)
        
        return {
            "message": "检查记录已重置，可以重新编辑",
            "inspection": inspection
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"重置检查记录失败: {str(e)}"
        )

@router.post("/detail/{inspection_id}/review")
async def review_inspection(
    inspection_id: str,
    review: InspectionReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查审核：approve/reject，记录审核人与日志"""
    # 权限：admin/manager/reviewer 才能审核
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限执行检查审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    old_status = inspection.status
    if old_status not in [InspectionStatusEnum.SUBMITTED, InspectionStatusEnum.UNDER_REVIEW]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"当前状态不允许审核：{old_status}")

    try:
        now = datetime.utcnow()
        if review.action == "approve":
            inspection.status = InspectionStatusEnum.APPROVED
        else:
            inspection.status = InspectionStatusEnum.REJECTED

        # 回填审核信息
        inspection.reviewed_by = current_user.id
        inspection.reviewed_at = now
        if review.comments:
            inspection.review_comments = review.comments
        if review.score is not None:
            inspection.score = review.score

        db.commit()
        db.refresh(inspection)

        # 审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            action="approve" if review.action == "approve" else "reject",
            from_status=old_status.value if old_status else None,
            to_status=inspection.status.value,
            operator_id=current_user.id,
            comments=review.comments
        )
        db.add(audit_log)
        db.commit()

        return {
            "message": "检查审核成功",
            "inspection": inspection
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检查审核失败: {str(e)}")

@router.post("/detail/{inspection_id}/items/{item_id}/review")
async def review_inspection_item(
    inspection_id: str,
    item_id: str,
    review: CheckItemReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查项审核：pass/fail/warning"""
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限执行检查项审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    check_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == inspection_id
    ).first()
    if not check_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查项不存在")

    try:
        now = datetime.utcnow()
        check_item.review_status = review.action
        check_item.review_comments = review.comments
        check_item.reviewed_by = current_user.id
        check_item.reviewed_at = now
        check_item.updated_at = now
        db.commit()
        db.refresh(check_item)

        # 写审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection_id,
            action="item_review",
            from_status=None,
            to_status=None,
            operator_id=current_user.id,
            comments=review.comments,
            details={"item_id": item_id, "result": review.action}
        )
        db.add(audit_log)
        db.commit()

        # 更新检查结果汇总（pass/fail/warning）
        _update_inspection_result_from_item_reviews(db, inspection_id)

        return {"message": "检查项审核成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"检查项审核失败: {str(e)}")

@router.post("/detail/{inspection_id}/photos/{photo_id}/review")
async def review_inspection_photo(
    inspection_id: str,
    photo_id: str,
    review: PhotoReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """照片审核：approved/rejected"""
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限执行照片审核")

    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    photo = db.query(InspectionPhoto).filter(
        InspectionPhoto.id == photo_id,
        InspectionPhoto.inspection_id == inspection_id
    ).first()
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="照片不存在")

    try:
        photo.review_status = review.action
        photo.review_comments = review.comments
        db.commit()
        db.refresh(photo)

        # 写审核日志
        audit_log = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection_id,
            action="photo_review",
            from_status=None,
            to_status=None,
            operator_id=current_user.id,
            comments=review.comments,
            details={"photo_id": photo_id, "result": review.action}
        )
        db.add(audit_log)
        db.commit()

        return {"message": "照片审核成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"照片审核失败: {str(e)}")

@router.get("/detail/{inspection_id}/review-summary", response_model=InspectionReviewSummary)
async def get_inspection_review_summary(
    inspection_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查审核汇总（基于检查项 review_status）"""
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="检查记录不存在")

    # 权限：检查员仅可看自己，其他角色可看
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有权限访问此检查记录")

    total = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id).count()
    pass_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "pass").count()
    fail_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "fail").count()
    warning_count = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id, InspectionCheckItem.review_status == "warning").count()
    pending_count = total - pass_count - fail_count - warning_count

    return InspectionReviewSummary(
        total_items=total,
        pass_count=pass_count,
        fail_count=fail_count,
        warning_count=warning_count,
        pending_count=pending_count
    )

# 内部工具：根据检查项审核结果更新检查记录的 result 字段
def _update_inspection_result_from_item_reviews(db: Session, inspection_id: str) -> None:
    try:
        items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == inspection_id).all()
        # 确定结果优先级：fail > warning > pass > pending
        result = None
        has_fail = any(i.review_status == "fail" for i in items)
        has_warning = any(i.review_status == "warning" for i in items)
        all_pass_or_pending = all(i.review_status in (None, "pass") for i in items)
        has_pass = any(i.review_status == "pass" for i in items)

        if has_fail:
            result = "fail"
        elif has_warning:
            result = "warning"
        elif all_pass_or_pending and has_pass:
            result = "pass"
        else:
            result = None

        inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
        if inspection:
            inspection.result = result
            inspection.updated_at = datetime.utcnow()
            db.commit()
    except Exception:
        db.rollback()
        raise
