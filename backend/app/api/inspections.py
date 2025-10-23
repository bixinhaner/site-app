from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Request
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
from app.services.cell_generator import CellGenerator
from app.utils.field_validator import FieldValidator
from app.schemas.inspection_enhanced import FieldDefinition

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
    
    # 根据模板和站点规划创建检查项
    template_data = template.template_data
    total_items = 0
    
    # 基于站点规划数据生成小区配置
    print(f"DEBUG: 开始为站点 {inspection_data.site_id} 生成小区配置")
    cells = CellGenerator.generate_cells_from_planning(db, inspection_data.site_id)
    cells_summary = CellGenerator.get_cells_summary(cells)
    print(f"DEBUG: 生成了 {len(cells)} 个小区: {[cell.to_dict() for cell in cells]}")
    print(f"DEBUG: 小区摘要: {cells_summary}")
    
    print(f"DEBUG: 模板数据类型: {type(template_data)}")
    print(f"DEBUG: 检查分类数量: {len(template_data.get('check_categories', []))}")
    
    for i, category in enumerate(template_data.get("check_categories", [])):
        category_name = category.get("category_name", "未知分类")
        category_id = category.get("category_id", "unknown")
        print(f"DEBUG: === 处理分类 {i+1}: {category_name} (ID: {category_id}) ===")
        print(f"DEBUG:   cell_specific: {category.get('cell_specific')}")
        print(f"DEBUG:   sector_specific: {category.get('sector_specific')}")
        print(f"DEBUG:   level_type: {category.get('level_type')}")
        
        items = category.get("items", [])
        print(f"DEBUG:   该分类有 {len(items)} 个检查项")
        
        for j, item in enumerate(items):
            item_name = item.get("item_name", "未知检查项")
            item_id = item.get("item_id", "unknown")
            item_description = item.get("description", "")  # 获取检查项描述
            item_fields = item.get("fields", [])  # 获取字段配置
            required_type = item.get("required_type", "unknown")
            print(f"DEBUG:   --- 处理检查项 {j+1}: {item_name} (ID: {item_id}) ---")
            print(f"DEBUG:     required_type: {required_type}")
            
            # 检查是否是小区级检查
            is_cell_specific = category.get("cell_specific", False)
            is_sector_specific = category.get("sector_specific", False)
            
            print(f"DEBUG:     判断检查级别:")
            print(f"DEBUG:       is_cell_specific: {is_cell_specific} (type: {type(is_cell_specific)})")
            print(f"DEBUG:       is_sector_specific: {is_sector_specific} (type: {type(is_sector_specific)})")
            print(f"DEBUG:       cells数量: {len(cells)}")
            
            # 如果是小区级检查，为每个小区创建检查项
            if is_cell_specific:
                print(f"DEBUG:     ✅ 进入小区级检查分支，准备为 {len(cells)} 个小区创建检查项")
                cell_items_created = 0
                for k, cell in enumerate(cells):
                    cell_item_id = f"{item_id}_cell_{cell.cell_id}"
                    cell_item_name = f"{item_name} - 小区 {cell.cell_id}"
                    print(f"DEBUG:       创建小区检查项 {k+1}: {cell_item_name} (ID: {cell_item_id})")
                    print(f"DEBUG:         扇区: {cell.sector_id}, 频段: {cell.band}, 小区: {cell.cell_id}")
                    
                    try:
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=cell_item_id,
                            item_name=cell_item_name,
                            description=item_description,
                            category_id=category_id,
                            category_name=category_name,
                            sector_id=cell.sector_id,
                            band=cell.band,
                            cell_id=cell.cell_id,
                            required_type=required_type,
                            fields=item_fields,
                            status=CheckItemStatusEnum.PENDING
                        )
                        db.add(check_item)
                        cell_items_created += 1
                        total_items += 1
                        print(f"DEBUG:         ✅ 成功创建小区检查项: {cell_item_id}")
                    except Exception as e:
                        print(f"DEBUG:         ❌ 创建小区检查项失败: {e}")
                        
                print(f"DEBUG:     小区级检查项创建完成，共创建 {cell_items_created} 个")
                
            # 如果是扇区级检查（向后兼容）
            elif is_sector_specific:
                print(f"DEBUG:     ✅ 进入扇区级检查分支")
                sectors = set(cell.sector_id for cell in cells)
                print(f"DEBUG:       发现 {len(sectors)} 个扇区: {list(sectors)}")
                sector_items_created = 0
                for sector_id in sectors:
                    sector_item_id = f"{item_id}_sector_{sector_id}"
                    sector_item_name = f"{item_name} - 扇区 {sector_id}"
                    print(f"DEBUG:       创建扇区检查项: {sector_item_name} (ID: {sector_item_id})")
                    
                    try:
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection.id,
                            item_id=sector_item_id,
                            item_name=sector_item_name,
                            description=item_description,
                            category_id=category_id,
                            category_name=category_name,
                            sector_id=sector_id,
                            required_type=required_type,
                            fields=item_fields,
                            status=CheckItemStatusEnum.PENDING
                        )
                        db.add(check_item)
                        sector_items_created += 1
                        total_items += 1
                        print(f"DEBUG:         ✅ 成功创建扇区检查项: {sector_item_id}")
                    except Exception as e:
                        print(f"DEBUG:         ❌ 创建扇区检查项失败: {e}")
                        
                print(f"DEBUG:     扇区级检查项创建完成，共创建 {sector_items_created} 个")
                
            else:
                # 站点级检查项
                print(f"DEBUG:     ✅ 进入站点级检查分支")
                site_item_id = item_id
                site_item_name = item_name
                print(f"DEBUG:       创建站点检查项: {site_item_name} (ID: {site_item_id})")
                
                try:
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection.id,
                        item_id=site_item_id,
                        item_name=site_item_name,
                        description=item_description,
                        category_id=category_id,
                        category_name=category_name,
                        required_type=required_type,
                        fields=item_fields,
                        status=CheckItemStatusEnum.PENDING
                    )
                    db.add(check_item)
                    total_items += 1
                    print(f"DEBUG:         ✅ 成功创建站点检查项: {site_item_id}")
                except Exception as e:
                    print(f"DEBUG:         ❌ 创建站点检查项失败: {e}")
                    
            print(f"DEBUG:     检查项 {item_name} 处理完成，当前总数: {total_items}")
            
    print(f"DEBUG: === 检查项创建汇总 ===")
    print(f"DEBUG: 总共创建了 {total_items} 个检查项")
    
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
    
    # 如果检查关联了工单，在照片列表中包含工单照片，并获取驳回意见
    if inspection.work_order_id:
        from app.models.work_order import WorkOrder, WorkOrderPhoto
        
        # 获取工单信息（包括驳回意见）
        work_order = db.query(WorkOrder).filter(WorkOrder.id == inspection.work_order_id).first()
        if work_order and work_order.status.value == "REJECTED" and work_order.review_comments:
            # 如果工单被驳回且有驳回意见，将其添加到检查的review_comments字段
            inspection.review_comments = work_order.review_comments
        
        work_order_photos = db.query(WorkOrderPhoto).filter(
            WorkOrderPhoto.work_order_id == inspection.work_order_id
        ).all()
        
        # 将工单照片转换为检查照片格式并添加到检查的照片列表中
        for wo_photo in work_order_photos:
            # 创建一个临时的检查照片对象用于显示
            inspection_photo = InspectionPhoto(
                id=f"wo_{wo_photo.id}",  # 使用前缀标识这是工单照片
                inspection_id=inspection_id,
                check_item_id=wo_photo.item_id,
                original_name=wo_photo.original_name,
                file_path=wo_photo.file_path,
                file_size=wo_photo.file_size,
                mime_type=wo_photo.mime_type,
                latitude=wo_photo.latitude,
                longitude=wo_photo.longitude,
                gps_accuracy=wo_photo.gps_accuracy,
                address=wo_photo.address,
                taken_at=wo_photo.taken_at,
                has_watermark=wo_photo.has_watermark,
                watermark_data=wo_photo.watermark_data,
                hash_value=wo_photo.hash_value,
                uploaded_by=wo_photo.uploaded_by,
                created_at=wo_photo.created_at,
                updated_at=wo_photo.updated_at
            )
            # 不要添加到数据库，只是临时用于响应
            inspection.photos.append(inspection_photo)
    
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
    print(f"DEBUG: update_inspection调用 - 检查ID: {inspection.id}, 旧状态: {old_status}, 更新字段: {list(update_fields.keys())}, 请求数据: {inspection_update.dict()}")

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
    
    # 如果从驳回状态重新提交，清除旧的审核结果
    is_resubmit = (old_status == InspectionStatusEnum.REJECTED and 
                   "status" in update_fields and 
                   inspection.status == InspectionStatusEnum.SUBMITTED)
    
    if is_resubmit:
        print(f"[重新提交] 检查 {inspection_id} 从驳回状态重新提交，清除旧审核结果")
        
        # 1. 清除检查级别的审核信息
        inspection.review_comments = None
        inspection.reviewed_by = None
        inspection.reviewed_at = None
        
        # 2. 清除所有检查项的审核结果
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).all()
        
        cleared_count = 0
        for item in check_items:
            if item.review_status or item.review_comments:
                item.review_status = None
                item.review_comments = None
                item.reviewed_by = None
                item.reviewed_at = None
                cleared_count += 1
        
        print(f"[重新提交] 已清除 {cleared_count} 个检查项的审核结果")
    
    # 如果状态变更为submitted，且没有设置submitted_at，自动设置
    if "status" in update_fields and inspection.status == InspectionStatusEnum.SUBMITTED:
        if not inspection.submitted_at:
            inspection.submitted_at = datetime.utcnow()
    
    # 记录状态变更日志
    audit_log_to_add = None
    if "status" in update_fields and old_status != inspection.status:
        # 区分首次提交和重新提交
        action = "resubmit" if is_resubmit else "update_status"
        comments = "重新提交检查（已清除旧审核结果）" if is_resubmit else "更新检查状态"
        
        audit_log_to_add = InspectionAuditLog(
            id=str(uuid.uuid4()),
            inspection_id=inspection.id,
            action=action,
            from_status=old_status.value,
            to_status=inspection.status.value,
            operator_id=current_user.id,
            comments=comments
        )
        db.add(audit_log_to_add)
    
    # 如果检查状态变更为submitted，同步工单状态（在提交前）
    should_sync = False
    if "status" in update_fields and inspection.work_order_id:
        # 检查是否更新为submitted状态
        status_check = (inspection.status == InspectionStatusEnum.SUBMITTED or 
                       str(inspection.status).upper() == "SUBMITTED" or
                       getattr(inspection.status, 'value', None) == 'submitted')
        should_sync = status_check
        print(f"DEBUG: 同步检查条件 - status字段存在: True, work_order_id存在: {bool(inspection.work_order_id)}, 状态检查: {status_check}")
        print(f"DEBUG: 检查状态值: {inspection.status}, 类型: {type(inspection.status)}")
        
    if should_sync:
        print(f"DEBUG: 开始同步工单状态 - 检查ID: {inspection.id}, 工单ID: {inspection.work_order_id}")
        from app.services.work_order_sync import get_work_order_sync_service
        sync_service = get_work_order_sync_service(db)
        sync_service.sync_inspection_to_work_order_status(inspection)
    else:
        if "status" in update_fields:
            print(f"DEBUG: 未触发同步 - 检查状态: {inspection.status}, work_order_id: {inspection.work_order_id}")
    
    # 统一提交所有更改
    db.commit()
    db.refresh(inspection)
    
    return inspection

@router.post("/detail/{inspection_id}/photos", response_model=InspectionPhotoResponse)
async def upload_inspection_photo(
    request: Request,
    inspection_id: str,
    file: UploadFile = File(...),
    check_item_id: Optional[str] = Form(None),
    gps_latitude: float = Form(0),
    gps_longitude: float = Form(0),
    gps_accuracy: Optional[float] = Form(None),
    has_watermark: bool = Form(False),
    replace_existing: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传检查照片 - 统一接口"""
    
    # 详细调试日志
    print(f"DEBUG: 照片上传接口调用")
    print(f"  inspection_id: {inspection_id}")
    print(f"  check_item_id: {check_item_id} (type: {type(check_item_id)})")
    print(f"  gps_latitude: {gps_latitude} (type: {type(gps_latitude)})")
    print(f"  gps_longitude: {gps_longitude} (type: {type(gps_longitude)})")
    print(f"  gps_accuracy: {gps_accuracy} (type: {type(gps_accuracy)})")
    print(f"  has_watermark: {has_watermark} (type: {type(has_watermark)})")
    print(f"  file.filename: {file.filename}")
    print(f"  file.content_type: {file.content_type}")
    print(f"  current_user: {current_user.username}")
    
    # 尝试从request中获取原始表单数据
    try:
        form = await request.form()
        print(f"  原始表单数据: {dict(form)}")
    except Exception as e:
        print(f"  无法获取原始表单数据: {e}")
    
    # 验证必需参数
    if not check_item_id or check_item_id.strip() == "":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="check_item_id 不能为空，照片必须关联到具体的检查项"
        )
    
    # 验证GPS坐标（拍照时必须有有效GPS坐标）
    if gps_latitude == 0 and gps_longitude == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GPS坐标无效，现场拍照必须包含有效的位置信息"
        )
    
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
    
    # 照片逻辑：只在明确指定replace_existing=True时才替换
    import os
    
    # 注意：前端现在会主动调用删除API删除不需要的照片
    # 因此这里只在明确指定时才启用替换模式，避免误删其他照片
    should_replace = replace_existing
    
    # 执行照片替换逻辑（仅在明确指定时）
    if should_replace and check_item_id:
        # 删除同一检查项的已有照片
        existing_photos = db.query(InspectionPhoto).filter(
            InspectionPhoto.inspection_id == inspection_id,
            InspectionPhoto.check_item_id == check_item_id
        ).all()
        
        # 删除旧照片文件和数据库记录
        for old_photo in existing_photos:
            try:
                # 删除物理文件
                if old_photo.file_path and os.path.exists(old_photo.file_path):
                    os.remove(old_photo.file_path)
                # 删除数据库记录
                db.delete(old_photo)
                print(f"替换模式：删除旧检查照片 {old_photo.id}")
            except Exception as e:
                print(f"替换模式：删除旧检查照片失败 {old_photo.id}: {e}")
        
        print(f"检查照片替换模式：should_replace={should_replace}，已清理旧照片")
    else:
        print(f"检查照片添加模式：should_replace={should_replace}，直接添加新照片")

    # 保存文件
    file_path = await save_uploaded_file(file, "inspections", inspection_id)
    
    # 根据是否已有水印决定是否添加水印
    watermarked_path = file_path
    watermark_data = None
    
    if not has_watermark:
        # 前端没有水印，后端添加水印
        print(f"DEBUG: 前端无水印，后端添加水印")
        watermark_data = {
            "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username,
            "accuracy": f"{gps_accuracy}m" if gps_accuracy else "N/A"
        }
        watermarked_path = await generate_watermark(file_path, watermark_data)
    else:
        # 前端已有水印，跳过后端水印处理
        print(f"DEBUG: 前端已有水印，跳过后端水印处理")
        watermark_data = {
            "source": "frontend_watermark",
            "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username
        }
    
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
        has_watermark=has_watermark or watermark_data is not None,
        watermark_data=watermark_data,
        hash_value=file_hash,
        uploaded_by=current_user.id
    )
    
    db.add(photo)
    db.commit()
    db.refresh(photo)
    
    return photo


@router.delete("/photos/{photo_id}")
async def delete_inspection_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定检查照片"""
    import os
    
    photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查关联的检查记录权限
    inspection = db.query(SiteInspection).filter(SiteInspection.id == photo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
        
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该照片")
    
    # 检查检查状态是否允许删除照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许删除照片")
    
    # 删除物理文件
    try:
        if photo.file_path and os.path.exists(photo.file_path):
            os.remove(photo.file_path)
            print(f"已删除检查照片文件: {photo.file_path}")
    except Exception as e:
        print(f"删除检查照片文件失败: {e}")
    
    # 删除数据库记录
    db.delete(photo)
    db.commit()
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=photo.inspection_id,
        action="delete_photo",
        operator_id=current_user.id,
        details={"photo_id": photo_id, "check_item_id": photo.check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return {"message": "照片删除成功"}


@router.put("/photos/{photo_id}", response_model=InspectionPhotoResponse)
async def replace_inspection_photo(
    photo_id: str,
    file: UploadFile = File(...),
    gps_latitude: Optional[float] = Form(None),
    gps_longitude: Optional[float] = Form(None),
    gps_accuracy: Optional[float] = Form(None),
    has_watermark: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """替换指定检查照片"""
    import os
    
    existing_photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
    if not existing_photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查关联的检查记录权限
    inspection = db.query(SiteInspection).filter(SiteInspection.id == existing_photo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
        
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限替换该照片")
    
    # 检查检查状态是否允许替换照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许替换照片")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")
    
    # 使用传入的GPS坐标，如果没有则使用原照片的坐标
    latitude = gps_latitude if gps_latitude is not None else existing_photo.latitude
    longitude = gps_longitude if gps_longitude is not None else existing_photo.longitude
    accuracy = gps_accuracy if gps_accuracy is not None else existing_photo.gps_accuracy
    
    # 保存新文件
    file_path = await save_uploaded_file(file, "inspections", existing_photo.inspection_id)
    
    # 根据是否已有水印决定是否添加水印
    watermarked_path = file_path
    watermark_data = None
    
    if not has_watermark:
        # 前端没有水印，后端添加水印
        watermark_data = {
            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username,
            "accuracy": f"{accuracy}m" if accuracy else "N/A"
        }
        watermarked_path = await generate_watermark(file_path, watermark_data)
    else:
        # 前端已有水印，跳过后端水印处理
        watermark_data = {
            "source": "frontend_watermark",
            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "inspector": current_user.full_name or current_user.username
        }
    
    file_hash = calculate_file_hash(watermarked_path)
    address = await reverse_geocode(latitude, longitude)
    
    # 删除旧文件
    try:
        if existing_photo.file_path and os.path.exists(existing_photo.file_path):
            os.remove(existing_photo.file_path)
            print(f"已删除旧检查照片文件: {existing_photo.file_path}")
    except Exception as e:
        print(f"删除旧检查照片文件失败: {e}")
    
    # 更新照片记录
    existing_photo.original_name = file.filename
    existing_photo.file_path = watermarked_path
    existing_photo.file_size = file.size
    existing_photo.mime_type = file.content_type
    existing_photo.latitude = latitude
    existing_photo.longitude = longitude
    existing_photo.gps_accuracy = accuracy
    existing_photo.address = address
    existing_photo.taken_at = datetime.utcnow()
    existing_photo.has_watermark = has_watermark or watermark_data is not None
    existing_photo.watermark_data = watermark_data
    existing_photo.hash_value = file_hash
    existing_photo.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(existing_photo)
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=existing_photo.inspection_id,
        action="replace_photo",
        operator_id=current_user.id,
        details={"photo_id": photo_id, "check_item_id": existing_photo.check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return existing_photo


@router.post("/detail/{inspection_id}/photos/batch")
async def batch_inspection_photo_operations(
    inspection_id: str,
    operations: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量检查照片操作：删除、更新、添加照片
    
    operations: 操作列表，每个操作包含:
    - action: "delete" | "replace" | "add"
    - photo_id: 照片ID (delete/replace时必需)
    - file_data: base64编码的文件数据 (replace/add时必需)
    - filename: 文件名 (replace/add时必需)
    - check_item_id: 检查项ID (add时必需)
    - gps_latitude, gps_longitude, gps_accuracy: GPS信息 (replace/add时可选)
    - has_watermark: 是否已有水印 (replace/add时可选)
    """
    import os
    import base64
    import tempfile
    from fastapi import UploadFile
    from io import BytesIO
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="检查记录不存在")
        
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该检查照片")
    
    # 检查检查状态是否允许操作照片
    if inspection.status not in [InspectionStatusEnum.DRAFT, InspectionStatusEnum.IN_PROGRESS, InspectionStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"检查状态 {inspection.status} 下不允许操作照片")
    
    results = []
    
    for i, operation in enumerate(operations):
        try:
            action = operation.get("action")
            photo_id = operation.get("photo_id")
            
            if action == "delete":
                if not photo_id:
                    results.append({"index": i, "action": "delete", "success": False, "error": "缺少photo_id"})
                    continue
                
                # 删除照片
                photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
                if not photo:
                    results.append({"index": i, "action": "delete", "success": False, "error": "照片不存在"})
                    continue
                
                # 删除物理文件
                try:
                    if photo.file_path and os.path.exists(photo.file_path):
                        os.remove(photo.file_path)
                except Exception as e:
                    print(f"批量操作：删除检查照片文件失败: {e}")
                
                # 删除数据库记录
                db.delete(photo)
                results.append({"index": i, "action": "delete", "success": True, "photo_id": photo_id})
                
            elif action == "replace":
                if not photo_id or not operation.get("file_data"):
                    results.append({"index": i, "action": "replace", "success": False, "error": "缺少photo_id或file_data"})
                    continue
                
                # 获取现有照片
                existing_photo = db.query(InspectionPhoto).filter(InspectionPhoto.id == photo_id).first()
                if not existing_photo:
                    results.append({"index": i, "action": "replace", "success": False, "error": "照片不存在"})
                    continue
                
                # 处理文件数据
                try:
                    file_data = base64.b64decode(operation["file_data"])
                    filename = operation.get("filename", "replaced_photo.jpg")
                    
                    # 创建临时UploadFile对象
                    temp_file = BytesIO(file_data)
                    upload_file = UploadFile(
                        filename=filename,
                        file=temp_file,
                        size=len(file_data),
                        headers={"content-type": "image/jpeg"}
                    )
                    
                    # 使用GPS坐标
                    latitude = operation.get("gps_latitude", existing_photo.latitude)
                    longitude = operation.get("gps_longitude", existing_photo.longitude)
                    accuracy = operation.get("gps_accuracy", existing_photo.gps_accuracy)
                    has_watermark = operation.get("has_watermark", False)
                    
                    # 保存新文件
                    file_path = await save_uploaded_file(upload_file, "inspections", inspection_id)
                    
                    # 根据是否已有水印决定是否添加水印
                    watermarked_path = file_path
                    watermark_data = None
                    
                    if not has_watermark:
                        # 前端没有水印，后端添加水印
                        watermark_data = {
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username,
                            "accuracy": f"{accuracy}m" if accuracy else "N/A"
                        }
                        watermarked_path = await generate_watermark(file_path, watermark_data)
                    else:
                        # 前端已有水印，跳过后端水印处理
                        watermark_data = {
                            "source": "frontend_watermark",
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username
                        }
                    
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 删除旧文件
                    try:
                        if existing_photo.file_path and os.path.exists(existing_photo.file_path):
                            os.remove(existing_photo.file_path)
                    except Exception as e:
                        print(f"批量操作：删除旧检查照片文件失败: {e}")
                    
                    # 更新照片记录
                    existing_photo.original_name = filename
                    existing_photo.file_path = watermarked_path
                    existing_photo.file_size = len(file_data)
                    existing_photo.mime_type = "image/jpeg"
                    existing_photo.latitude = latitude
                    existing_photo.longitude = longitude
                    existing_photo.gps_accuracy = accuracy
                    existing_photo.address = address
                    existing_photo.taken_at = datetime.utcnow()
                    existing_photo.has_watermark = has_watermark or watermark_data is not None
                    existing_photo.watermark_data = watermark_data
                    existing_photo.hash_value = file_hash
                    existing_photo.updated_at = datetime.utcnow()
                    
                    results.append({"index": i, "action": "replace", "success": True, "photo_id": photo_id})
                    
                except Exception as e:
                    results.append({"index": i, "action": "replace", "success": False, "error": str(e)})
                    
            elif action == "add":
                if not operation.get("file_data") or not operation.get("check_item_id"):
                    results.append({"index": i, "action": "add", "success": False, "error": "缺少file_data或check_item_id"})
                    continue
                
                # 处理文件数据
                try:
                    file_data = base64.b64decode(operation["file_data"])
                    filename = operation.get("filename", "new_photo.jpg")
                    
                    # 创建临时UploadFile对象
                    temp_file = BytesIO(file_data)
                    upload_file = UploadFile(
                        filename=filename,
                        file=temp_file,
                        size=len(file_data),
                        headers={"content-type": "image/jpeg"}
                    )
                    
                    # GPS坐标
                    latitude = operation.get("gps_latitude", 0)
                    longitude = operation.get("gps_longitude", 0)
                    accuracy = operation.get("gps_accuracy")
                    has_watermark = operation.get("has_watermark", False)
                    
                    # 保存文件
                    file_path = await save_uploaded_file(upload_file, "inspections", inspection_id)
                    
                    # 根据是否已有水印决定是否添加水印
                    watermarked_path = file_path
                    watermark_data = None
                    
                    if not has_watermark:
                        # 前端没有水印，后端添加水印
                        watermark_data = {
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username,
                            "accuracy": f"{accuracy}m" if accuracy else "N/A"
                        }
                        watermarked_path = await generate_watermark(file_path, watermark_data)
                    else:
                        # 前端已有水印，跳过后端水印处理
                        watermark_data = {
                            "source": "frontend_watermark",
                            "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                            "inspector": current_user.full_name or current_user.username
                        }
                    
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 创建新照片记录
                    new_photo = InspectionPhoto(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection_id,
                        check_item_id=operation["check_item_id"],
                        original_name=filename,
                        file_path=watermarked_path,
                        file_size=len(file_data),
                        mime_type="image/jpeg",
                        latitude=latitude,
                        longitude=longitude,
                        gps_accuracy=accuracy,
                        address=address,
                        taken_at=datetime.utcnow(),
                        has_watermark=has_watermark or watermark_data is not None,
                        watermark_data=watermark_data,
                        hash_value=file_hash,
                        uploaded_by=current_user.id
                    )
                    db.add(new_photo)
                    
                    results.append({"index": i, "action": "add", "success": True, "photo_id": new_photo.id})
                    
                except Exception as e:
                    results.append({"index": i, "action": "add", "success": False, "error": str(e)})
            
            else:
                results.append({"index": i, "action": action, "success": False, "error": "无效的操作类型"})
                
        except Exception as e:
            results.append({"index": i, "action": operation.get("action", "unknown"), "success": False, "error": str(e)})
    
    # 提交所有更改
    db.commit()
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        action="batch_photo_operations",
        operator_id=current_user.id,
        details={"operations_count": len(operations), "results": results}
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": "批量检查照片操作完成",
        "total_operations": len(operations),
        "results": results
    }


@router.post("/detail/{inspection_id}/photos/cleanup")
async def cleanup_duplicate_inspection_photos(
    inspection_id: str,
    check_item_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理重复和累积的检查照片，只保留最新的照片"""
    import os
    from collections import defaultdict
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="检查记录不存在")
        
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该检查照片")
    
    # 构建查询条件
    query = db.query(InspectionPhoto).filter(InspectionPhoto.inspection_id == inspection_id)
    if check_item_id:
        query = query.filter(InspectionPhoto.check_item_id == check_item_id)
    
    # 获取所有照片，按检查项分组
    photos = query.order_by(InspectionPhoto.created_at.desc()).all()
    
    # 按检查项分组
    photos_by_item = defaultdict(list)
    for photo in photos:
        key = photo.check_item_id or "inspection_level"
        photos_by_item[key].append(photo)
    
    deleted_count = 0
    kept_count = 0
    
    for item_key, item_photos in photos_by_item.items():
        if len(item_photos) <= 1:
            kept_count += len(item_photos)
            continue
        
        # 保留最新的照片，删除其他的
        latest_photo = item_photos[0]  # 已按created_at倒序排列
        photos_to_delete = item_photos[1:]
        
        for old_photo in photos_to_delete:
            try:
                # 删除物理文件
                if old_photo.file_path and os.path.exists(old_photo.file_path):
                    os.remove(old_photo.file_path)
                # 删除数据库记录
                db.delete(old_photo)
                deleted_count += 1
                print(f"清理累积检查照片: {old_photo.id} (检查项: {item_key})")
            except Exception as e:
                print(f"清理检查照片失败 {old_photo.id}: {e}")
        
        kept_count += 1  # 保留的最新照片
    
    db.commit()
    
    # 记录审计日志
    audit_log = InspectionAuditLog(
        id=str(uuid.uuid4()),
        inspection_id=inspection_id,
        action="cleanup_duplicate_photos",
        operator_id=current_user.id,
        details={"deleted_count": deleted_count, "kept_count": kept_count, "check_item_id": check_item_id}
    )
    db.add(audit_log)
    db.commit()
    
    return {
        "message": "检查照片清理完成",
        "deleted_count": deleted_count,
        "kept_count": kept_count,
        "details": f"已删除 {deleted_count} 张重复照片，保留 {kept_count} 张最新照片"
    }


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
    equipment_sn: Optional[str] = None,
    has_equipment: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取检查项列表
    
    Args:
        inspection_id: 检查记录ID
        equipment_sn: 设备SN筛选（模糊查询）
        has_equipment: 绑定状态筛选（True=已绑定，False=未绑定）
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        检查项列表
    """
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
    
    # 获取检查项，包括照片
    from sqlalchemy.orm import joinedload
    
    query = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.photos)
    ).filter(
        InspectionCheckItem.inspection_id == inspection_id
    )
    
    # 设备SN筛选（模糊查询）
    if equipment_sn:
        query = query.filter(InspectionCheckItem.equipment_sn.like(f"%{equipment_sn}%"))
    
    # 绑定状态筛选
    if has_equipment is True:
        query = query.filter(InspectionCheckItem.equipment_sn.isnot(None))
    elif has_equipment is False:
        # 仅筛选小区级检查项中未绑定的
        query = query.filter(
            InspectionCheckItem.equipment_sn.is_(None),
            InspectionCheckItem.sector_id.isnot(None),
            InspectionCheckItem.band.isnot(None)
        )
    
    check_items = query.all()
    
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
    
    # 如果更新包含data_value且检查项有字段定义，执行字段验证
    if 'data_value' in update_fields and check_item.fields:
        try:
            # 将check_item.fields转换为FieldDefinition对象列表
            field_definitions = []
            if isinstance(check_item.fields, list):
                for field_dict in check_item.fields:
                    try:
                        field_def = FieldDefinition(**field_dict)
                        field_definitions.append(field_def)
                    except Exception as e:
                        print(f"WARNING: 无法解析字段定义: {field_dict}, 错误: {e}")
            
            # 执行验证（非严格模式，允许部分填写）
            if field_definitions and update_fields['data_value']:
                # 将CheckItemDataValue对象列表转换为字典列表
                data_values_dict = []
                for dv in update_fields['data_value']:
                    if hasattr(dv, 'dict'):
                        data_values_dict.append(dv.dict())
                    elif isinstance(dv, dict):
                        data_values_dict.append(dv)
                
                validation_result = FieldValidator.validate_check_item_data(
                    field_definitions,
                    data_values_dict,
                    strict=False  # 非严格模式，允许部分填写
                )
                
                # 存储验证结果
                check_item.validation_result = validation_result
                
                # 如果有验证错误，记录但不阻止保存（允许保存草稿）
                if not validation_result['valid']:
                    print(f"INFO: 检查项 {item_id} 存在字段验证错误: {validation_result['errors']}")
                    # 可以选择在检查项状态为COMPLETED时才强制验证通过
                    if 'status' in update_fields and update_fields['status'] == CheckItemStatusEnum.COMPLETED:
                        if validation_result['errors']:
                            error_messages = '; '.join([f"{k}: {v}" for k, v in validation_result['errors'].items()])
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail=f"字段验证失败，无法标记为完成: {error_messages}"
                            )
        except HTTPException:
            raise  # 重新抛出HTTP异常
        except Exception as e:
            print(f"WARNING: 字段验证过程出错: {e}")
            # 验证出错不阻止保存，但记录错误
    
    for field, value in update_fields.items():
        setattr(check_item, field, value)
    
    # 更新检查人员和时间
    check_item.checked_by = current_user.id
    check_item.checked_at = datetime.utcnow()
    check_item.updated_at = datetime.utcnow()
    
    # 如果检查项已完成且绑定了设备，更新设备状态为"已检查"
    if (check_item.status == CheckItemStatusEnum.COMPLETED and 
        check_item.equipment_sn):
        from app.models.equipment import EquipmentInstance, InventoryStatusEnum
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == check_item.equipment_sn
        ).first()
        
        if equipment_instance:
            equipment_instance.status = InventoryStatusEnum.INSPECTED
            equipment_instance.updated_at = datetime.utcnow()
    
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
    
    # 检查是否所有项都已完成，如果是则自动更新检查状态并同步工单状态
    if inspection.completion_rate == 100.0:
        from app.services.work_order_sync import get_work_order_sync_service
        from datetime import datetime as dt
        
        print(f"DEBUG: 检查项更新完成100% - 检查ID: {inspection.id}, 当前状态: {inspection.status}, submitted_at: {inspection.submitted_at}")
        
        # 如果检查状态还是进行中，更新为已提交
        if inspection.status == InspectionStatusEnum.IN_PROGRESS:
            inspection.status = InspectionStatusEnum.SUBMITTED
            inspection.end_time = dt.utcnow()
            print(f"DEBUG: 状态从IN_PROGRESS更新为SUBMITTED: {inspection.id}")
        
        # 如果检查状态是SUBMITTED但没有submitted_at，设置它
        if inspection.status == InspectionStatusEnum.SUBMITTED and not inspection.submitted_at:
            inspection.submitted_at = dt.utcnow()
            print(f"DEBUG: 设置submitted_at时间戳: {inspection.id}, 时间: {inspection.submitted_at}")
        
        # 如果检查关联了工单，同步工单状态（无论检查当前状态如何）
        if inspection.work_order_id:
            print(f"DEBUG: 开始同步工单状态 - 检查ID: {inspection.id}, 工单ID: {inspection.work_order_id}")
            sync_service = get_work_order_sync_service(db)
            sync_service.sync_inspection_to_work_order_status(inspection)
    
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
    if inspection.work_order_id:
        from app.models.work_order import WorkOrder
        work_order = db.query(WorkOrder).filter(
            WorkOrder.id == inspection.work_order_id
        ).first()
        
        if not work_order or work_order.status.value != "REJECTED":
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


# 新增：设备验证和绑定接口
@router.get("/equipment/check-pickup/{sn}")
async def check_equipment_pickup_status(
    sn: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """验证设备是否已被当前用户领料。

    放宽校验：支持已出库(ISSUED)与待检查(PENDING_INSPECTION)两种状态，
    以兼容已完成首次绑定但再次扫描校验的场景。
    """
    from app.models.equipment import EquipmentInstance, InventoryStatusEnum

    equipment_instance = db.query(EquipmentInstance).filter(
        EquipmentInstance.serial_number == sn
    ).first()

    if not equipment_instance:
        raise HTTPException(status_code=404, detail=f"设备序列号 {sn} 不存在")

    # 允许以下状态进入检查流程：已出库、待检查、已检查（便于复核/返检）
    allowed_status = {
        InventoryStatusEnum.ISSUED,
        InventoryStatusEnum.PENDING_INSPECTION,
        InventoryStatusEnum.INSPECTED,
    }
    if equipment_instance.status not in allowed_status:
        raise HTTPException(status_code=400, detail="设备未出库，无法进行检查")

    if equipment_instance.issued_to != current_user.id:
        raise HTTPException(status_code=403, detail="设备未被当前用户领料，无法进行检查")

    return {
        "success": True,
        "equipment_sn": sn,
        "equipment_name": equipment_instance.equipment.equipment_name if equipment_instance.equipment else "未知设备",
        "issued_date": equipment_instance.issued_date,
        "message": "设备验证通过，可以进行检查"
    }


@router.post("/detail/{inspection_id}/bind-equipment")
async def bind_equipment_to_sector(
    inspection_id: str,
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """绑定设备到小区检查项"""
    equipment_sn = request_data.get("equipment_sn")
    sector_id = request_data.get("sector_id")
    band = request_data.get("band")
    
    if not sector_id:
        raise HTTPException(
            status_code=400,
            detail="扇区ID不能为空"
        )
    
    # 如果设备SN为空或空字符串，表示解绑操作
    is_unbind = not equipment_sn or equipment_sn.strip() == ""
    
    # 验证检查记录存在且属于当前用户
    inspection = db.query(SiteInspection).filter(
        SiteInspection.id == inspection_id,
        SiteInspection.inspector_id == current_user.id
    ).first()
    
    if not inspection:
        raise HTTPException(
            status_code=404,
            detail="检查记录不存在或无权限操作"
        )
    
    # 验证设备状态（仅在绑定操作时验证）
    equipment_instance = None
    if not is_unbind:
        from app.models.equipment import EquipmentInstance, InventoryStatusEnum
        # 允许以下状态进行绑定（同一领料人）：已出库、待检查、已检查
        equipment_instance = db.query(EquipmentInstance).filter(
            EquipmentInstance.serial_number == equipment_sn,
            EquipmentInstance.status.in_([
                InventoryStatusEnum.ISSUED,
                InventoryStatusEnum.PENDING_INSPECTION,
                InventoryStatusEnum.INSPECTED,
            ]),
            EquipmentInstance.issued_to == current_user.id
        ).first()
        
        if not equipment_instance:
            raise HTTPException(
                status_code=400,
                detail="设备序列号无效或未被当前用户领料"
            )
    
    # 构造cell_id
    cell_id = f"{sector_id}_{band}" if band else sector_id
    
    # 查找该小区的检查项
    check_items = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.inspection_id == inspection_id,
        InspectionCheckItem.sector_id == sector_id
    )
    
    if band:
        check_items = check_items.filter(InspectionCheckItem.band == band)
    
    check_items = check_items.all()
    
    if not check_items:
        raise HTTPException(
            status_code=404,
            detail=f"未找到扇区 {sector_id} 的检查项"
        )
    
    # 仅在绑定操作时检查是否已有其他设备绑定到该小区
    if not is_unbind:
        existing_binding = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id,
            InspectionCheckItem.sector_id == sector_id,
            InspectionCheckItem.equipment_sn.isnot(None),
            InspectionCheckItem.equipment_sn != equipment_sn
        ).first()
        
        if existing_binding:
            raise HTTPException(
                status_code=409,
                detail=f"扇区 {sector_id} 已绑定其他设备: {existing_binding.equipment_sn}"
            )

        # 新增：阻止同一设备SN绑定到其他小区（跨检查记录全局唯一小区）
        from sqlalchemy import or_, func
        from sqlalchemy.orm import joinedload
        conflict = db.query(InspectionCheckItem).options(
            joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.site),
            joinedload(InspectionCheckItem.inspection).joinedload(SiteInspection.inspector)
        ).filter(
            InspectionCheckItem.equipment_sn == equipment_sn,
            or_(
                InspectionCheckItem.sector_id != sector_id,
                func.coalesce(InspectionCheckItem.band, "") != func.coalesce(band, "")
            )
        ).first()

        if conflict:
            conflict_cell = conflict.sector_id
            conflict_band = getattr(conflict, 'band', None)
            conflict_cell_str = f"{conflict_cell}_{conflict_band}" if conflict_band else f"{conflict_cell}"
            
            # 获取站点信息
            conflict_inspection = conflict.inspection
            site_name = conflict_inspection.site.site_name if conflict_inspection and conflict_inspection.site else "未知站点"
            site_id = conflict_inspection.site_id if conflict_inspection else "N/A"
            
            # 获取绑定人信息（优先使用检查项的checked_by，否则使用检查记录的inspector）
            binder_id = conflict.checked_by if conflict.checked_by else (conflict_inspection.inspector_id if conflict_inspection else None)
            binder_name = "未知用户"
            if binder_id:
                binder = db.query(User).filter(User.id == binder_id).first()
                if binder:
                    binder_name = binder.full_name or binder.username
            
            # 构造丰富的错误提示
            detail_msg = (
                f"设备 {equipment_sn} 已被使用，无法绑定！\n"
                f"已绑定站点：{site_name} (ID: {site_id})\n"
                f"已绑定小区：扇区{conflict_cell}{'的' + conflict_band + '频段' if conflict_band else ''} (小区ID: {conflict_cell_str})\n"
                f"绑定操作人：{binder_name}\n"
                f"请先解绑该设备后再进行绑定操作"
            )
            
            raise HTTPException(
                status_code=409,
                detail=detail_msg
            )
    
    # 绑定或解绑设备到所有相关检查项
    try:
        # 导入历史记录模型
        from app.models.equipment_binding_history import EquipmentBindingHistory, BindingActionEnum
        
        for item in check_items:
            # 记录之前的设备SN（用于历史记录）
            previous_sn = item.equipment_sn
            
            # 更新设备绑定
            item.equipment_sn = equipment_sn if not is_unbind else None
            item.updated_at = datetime.utcnow()
            
            # 创建历史记录
            if not is_unbind or previous_sn:  # 绑定操作或有之前设备的解绑操作才记录
                history = EquipmentBindingHistory(
                    inspection_id=inspection_id,
                    check_item_id=item.id,
                    site_id=inspection.site_id,
                    sector_id=sector_id,
                    band=band or "",
                    cell_id=cell_id,
                    equipment_sn=equipment_sn if not is_unbind else previous_sn,
                    action=BindingActionEnum.UNBIND if is_unbind else (
                        BindingActionEnum.REBIND if previous_sn else BindingActionEnum.BIND
                    ),
                    operator_id=current_user.id,
                    previous_equipment_sn=previous_sn if not is_unbind and previous_sn else None,
                    latitude=request_data.get("latitude"),
                    longitude=request_data.get("longitude"),
                    gps_accuracy=request_data.get("gps_accuracy"),
                    notes=request_data.get("notes")
                )
                db.add(history)
        
        # 更新设备状态
        if not is_unbind and equipment_instance:
            # 绑定时，设备状态更新为"待检查"
            from app.models.equipment import InventoryStatusEnum
            equipment_instance.status = InventoryStatusEnum.PENDING_INSPECTION
            equipment_instance.updated_at = datetime.utcnow()
        
        db.commit()
        
        if is_unbind:
            return {
                "success": True,
                "message": f"成功解绑扇区 {sector_id} 的设备",
                "action": "unbind",
                "sector_id": sector_id,
                "band": band,
                "cell_id": cell_id,
                "affected_items_count": len(check_items)
            }
        else:
            return {
                "success": True,
                "message": f"成功绑定设备 {equipment_sn} 到扇区 {sector_id}，设备状态已更新为待检查",
                "action": "bind",
                "equipment_sn": equipment_sn,
                "sector_id": sector_id,
                "band": band,
                "cell_id": cell_id,
                "bound_items_count": len(check_items),
                "equipment_name": equipment_instance.equipment.equipment_name if equipment_instance and equipment_instance.equipment else "未知设备",
                "equipment_status": "pending_inspection"
            }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"绑定设备失败: {str(e)}"
        )


@router.get("/binding-history/{check_item_id}")
async def get_binding_history(
    check_item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取检查项的设备绑定历史记录
    
    Args:
        check_item_id: 检查项ID
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        设备绑定历史记录列表
    """
    from app.models.equipment_binding_history import EquipmentBindingHistory
    from sqlalchemy.orm import joinedload
    
    # 验证检查项存在且有权限查看
    check_item = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.inspection)
    ).filter(InspectionCheckItem.id == check_item_id).first()
    
    if not check_item:
        raise HTTPException(
            status_code=404,
            detail="检查项不存在"
        )
    
    # 权限检查
    inspection = check_item.inspection
    if current_user.role == "inspector" and inspection.inspector_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="没有权限查看此检查项的历史记录"
        )
    
    # 查询历史记录
    history_records = db.query(EquipmentBindingHistory).options(
        joinedload(EquipmentBindingHistory.operator)
    ).filter(
        EquipmentBindingHistory.check_item_id == check_item_id
    ).order_by(
        EquipmentBindingHistory.operated_at.desc()
    ).all()
    
    # 格式化返回数据
    result = []
    for record in history_records:
        result.append({
            "id": record.id,
            "action": record.action.value,
            "equipment_sn": record.equipment_sn,
            "previous_equipment_sn": record.previous_equipment_sn,
            "operator": {
                "id": record.operator.id,
                "name": record.operator.full_name or record.operator.username
            },
            "operated_at": record.operated_at.isoformat() if record.operated_at else None,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "gps_accuracy": record.gps_accuracy,
            "notes": record.notes,
            "cell_info": {
                "sector_id": record.sector_id,
                "band": record.band,
                "cell_id": record.cell_id
            }
        })
    
    return {
        "check_item_id": check_item_id,
        "check_item_name": check_item.item_name,
        "history": result
    }


@router.get("/equipment-history/{equipment_sn}")
async def get_equipment_binding_history(
    equipment_sn: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    获取设备的完整绑定历史记录（用于设备追踪）
    
    Args:
        equipment_sn: 设备序列号
        db: 数据库会话
        current_user: 当前用户
    
    Returns:
        设备的完整绑定历史
    """
    from app.models.equipment_binding_history import EquipmentBindingHistory
    from sqlalchemy.orm import joinedload
    
    # 查询该设备的所有绑定历史
    history_records = db.query(EquipmentBindingHistory).options(
        joinedload(EquipmentBindingHistory.operator),
        joinedload(EquipmentBindingHistory.site),
        joinedload(EquipmentBindingHistory.inspection)
    ).filter(
        EquipmentBindingHistory.equipment_sn == equipment_sn
    ).order_by(
        EquipmentBindingHistory.operated_at.desc()
    ).all()
    
    if not history_records:
        return {
            "equipment_sn": equipment_sn,
            "history": [],
            "message": "该设备尚无绑定历史记录"
        }
    
    # 格式化返回数据
    result = []
    for record in history_records:
        result.append({
            "id": record.id,
            "action": record.action.value,
            "site": {
                "id": record.site_id,
                "name": record.site.site_name if record.site else "未知站点"
            },
            "cell_info": {
                "sector_id": record.sector_id,
                "band": record.band,
                "cell_id": record.cell_id
            },
            "operator": {
                "id": record.operator.id,
                "name": record.operator.full_name or record.operator.username
            },
            "operated_at": record.operated_at.isoformat() if record.operated_at else None,
            "previous_equipment_sn": record.previous_equipment_sn,
            "latitude": record.latitude,
            "longitude": record.longitude,
            "gps_accuracy": record.gps_accuracy,
            "notes": record.notes,
            "inspection_id": record.inspection_id
        })
    
    return {
        "equipment_sn": equipment_sn,
        "total_records": len(result),
        "history": result
    }


# === 统计汇总 ===
from sqlalchemy import func
from app.models.inspection import SiteInspection, InspectionStatusEnum


@router.get("/stats/summary", response_model=InspectionStatistics)
async def get_inspection_stats_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """检查记录统计（管理员/经理）"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )

    total = db.query(func.count(SiteInspection.id)).scalar() or 0

    completed = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.COMPLETED
    ).scalar() or 0

    approved = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.APPROVED
    ).scalar() or 0

    rejected = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status == InspectionStatusEnum.REJECTED
    ).scalar() or 0

    pending = db.query(func.count(SiteInspection.id)).filter(
        SiteInspection.status.in_([
            InspectionStatusEnum.DRAFT,
            InspectionStatusEnum.IN_PROGRESS,
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW
        ])
    ).scalar() or 0

    avg_score = db.query(func.avg(SiteInspection.score)).scalar()
    avg_score = float(avg_score) if avg_score is not None else None

    avg_completion_rate = db.query(func.avg(SiteInspection.completion_rate)).scalar() or 0.0

    return InspectionStatistics(
        total_inspections=int(total),
        completed_inspections=int(completed),
        pending_inspections=int(pending),
        approved_inspections=int(approved),
        rejected_inspections=int(rejected),
        average_score=avg_score,
        completion_rate=float(avg_completion_rate or 0.0)
    )
