from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.api.auth import get_current_user
from app.models.user import User
from app.models.site import Site
from app.models.work_order import (
    WorkOrder, WorkOrderItem, WorkOrderPhoto,
    WorkOrderStatusEnum, WorkOrderTypeEnum, WorkOrderPriorityEnum,
    ItemStatusEnum, AuditEvent
)
from app.models.inspection import SiteInspection, InspectionStatusEnum, InspectionTypeEnum, InspectionTemplate, InspectionCheckItem, CheckItemStatusEnum
from app.schemas.work_order import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse,
    WorkOrderItemUpdate, WorkOrderItemResponse,
    WorkOrderStatusChangeRequest, WorkOrderReviewRequest,
    ItemReviewRequest, PhotoReviewRequest, WorkOrderPhotoResponse,
    ReviewSummary, WorkOrderBatchOperation, WorkOrderSearchParams, WorkOrderListResponse
)
from app.services.template_resolver import create_resolver, ResolveContext
from app.services.work_order_sync import get_work_order_sync_service
from app.utils.file_handler import save_uploaded_file, generate_watermark
from app.utils.gps_utils import reverse_geocode

router = APIRouter()


@router.get("/search", response_model=WorkOrderListResponse)
async def search_work_orders(
    keyword: Optional[str] = None,
    status: Optional[WorkOrderStatusEnum] = None,
    type: Optional[WorkOrderTypeEnum] = None,
    assigned_to: Optional[int] = None,
    priority: Optional[WorkOrderPriorityEnum] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """搜索工单（带分页和筛选）"""
    from sqlalchemy import or_, and_
    import math
    
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    query = db.query(WorkOrder)
    
    # 关键词搜索
    if keyword:
        query = query.join(Site, WorkOrder.site_id == Site.id, isouter=True).filter(
            or_(
                WorkOrder.title.contains(keyword),
                WorkOrder.description.contains(keyword),
                Site.site_name.contains(keyword),
                Site.site_code.contains(keyword)
            )
        )
    
    # 状态筛选
    if status:
        query = query.filter(WorkOrder.status == status)
    
    # 类型筛选
    if type:
        query = query.filter(WorkOrder.type == type)
    
    # 分配人筛选
    if assigned_to:
        query = query.filter(WorkOrder.assigned_to == assigned_to)
    
    # 优先级筛选
    if priority:
        query = query.filter(WorkOrder.priority == priority)
    
    # 计算总数
    total = query.count()
    
    # 分页查询
    work_orders = query.order_by(WorkOrder.assigned_at.desc()).offset(skip).limit(limit).all()
    
    # 计算分页信息
    page = (skip // limit) + 1
    pages = math.ceil(total / limit)
    
    return WorkOrderListResponse(
        work_orders=[_enrich_work_order_response(db, wo) for wo in work_orders],
        total=total,
        page=page,
        size=limit,
        pages=pages
    )


def _enrich_work_order_response(db: Session, wo: WorkOrder) -> dict:
    from datetime import datetime
    
    # Build the response manually to avoid validation issues
    current_time = datetime.utcnow()
    data = {
        "id": wo.id,
        "site_id": wo.site_id,
        "inspection_id": wo.inspection_id,
        "title": wo.title,
        "type": wo.type,
        "description": wo.description,
        "priority": wo.priority,
        "status": wo.status,
        "assigned_by": wo.assigned_by,
        "assigned_to": wo.assigned_to,
        "reviewer_id": wo.reviewer_id,
        "assigned_at": wo.assigned_at or current_time,
        "accepted_at": wo.accepted_at,
        "submitted_at": wo.submitted_at,
        "reviewed_at": wo.reviewed_at,
        "completed_at": wo.completed_at,
        "due_date": wo.due_date,
        "extra_data": wo.extra_data or {},
        "created_at": wo.created_at or current_time,
        "updated_at": wo.updated_at or current_time,
    }
    
    # Add enriched fields
    # site fields
    if wo.site_id:
        site = db.query(Site).filter(Site.id == wo.site_id).first()
        if site:
            data["site_name"] = getattr(site, "site_name", None)
            data["site_code"] = getattr(site, "site_code", None)
    
    # users
    if wo.assigned_by:
        u = db.query(User).filter(User.id == wo.assigned_by).first()
        if u:
            data["assigner_name"] = u.full_name or u.username
    if wo.assigned_to:
        u = db.query(User).filter(User.id == wo.assigned_to).first()
        if u:
            data["assignee_name"] = u.full_name or u.username
    if wo.reviewer_id:
        u = db.query(User).filter(User.id == wo.reviewer_id).first()
        if u:
            data["reviewer_name"] = u.full_name or u.username
    
    return data


def _audit(db: Session, resource_type: str, resource_id: str, action: str, operator_id: int,
           from_status: Optional[str] = None, to_status: Optional[str] = None,
           comments: Optional[str] = None, details: Optional[dict] = None):
    ev = AuditEvent(
        id=str(uuid.uuid4()),
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        operator_id=operator_id,
        comments=comments,
        details=details or {}
    )
    db.add(ev)
    db.commit()


@router.post("", response_model=WorkOrderResponse)
@router.post("/", response_model=WorkOrderResponse)
async def create_work_order(
    data: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(status_code=403, detail="无权限创建工单")

    site = db.query(Site).filter(Site.id == data.site_id).first()
    if not site:
        raise HTTPException(status_code=404, detail="站点不存在")

    wo = WorkOrder(
        id=str(uuid.uuid4()),
        site_id=data.site_id,
        title=data.title,
        type=data.type,
        description=data.description,
        priority=data.priority,
        assigned_by=current_user.id,
        assigned_to=data.assigned_to,
        due_date=data.due_date,
        status=WorkOrderStatusEnum.PENDING,
        extra_data={"template_id": data.template_id} if data.template_id else {}
    )
    db.add(wo)
    db.flush()

    # 工单创建成功，检查实例将在接受时创建

    db.commit()
    db.refresh(wo)
    _audit(db, "work_order", wo.id, "create", current_user.id, to_status=wo.status.value)
    return _enrich_work_order_response(db, wo)


@router.get("", response_model=List[WorkOrderResponse])
@router.get("/", response_model=List[WorkOrderResponse])
async def list_work_orders(
    status_filter: Optional[WorkOrderStatusEnum] = None,
    assigned_to: Optional[int] = None,
    type_filter: Optional[WorkOrderTypeEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    q = db.query(WorkOrder)
    if status_filter:
        q = q.filter(WorkOrder.status == status_filter)
    if assigned_to:
        q = q.filter(WorkOrder.assigned_to == assigned_to)
    if type_filter:
        q = q.filter(WorkOrder.type == type_filter)

    if current_user.role == "inspector":
        q = q.filter(WorkOrder.assigned_to == current_user.id)

    orders = q.order_by(WorkOrder.assigned_at.desc()).offset(skip).limit(limit).all()
    return [_enrich_work_order_response(db, o) for o in orders]


@router.get("/{work_order_id}", response_model=WorkOrderResponse)
async def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    return _enrich_work_order_response(db, wo)


@router.put("/{work_order_id}", response_model=WorkOrderResponse)
async def update_work_order(
    work_order_id: str,
    data: WorkOrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role not in ["admin", "manager"] and current_user.id != wo.assigned_by:
        raise HTTPException(status_code=403, detail="无权限修改工单")

    update = data.dict(exclude_unset=True)
    for k, v in update.items():
        setattr(wo, k, v)
    db.commit()
    db.refresh(wo)
    return _enrich_work_order_response(db, wo)


@router.delete("/{work_order_id}")
async def delete_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除工单"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有管理员或创建者可以删除
    if current_user.role not in ["admin", "manager"] and current_user.id != wo.assigned_by:
        raise HTTPException(status_code=403, detail="无权限删除工单")
    
    # 检查工单状态：只能删除待分配或已分配状态的工单
    if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
        raise HTTPException(status_code=400, detail=f"无法删除{wo.status}状态的工单")
    
    # 如果有关联的检查记录，需要同时删除
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if inspection:
            # 删除检查记录及其相关数据
            db.delete(inspection)
    
    # 删除工单
    db.delete(wo)
    db.commit()
    
    # 记录审计日志
    _audit(db, "work_order", work_order_id, "delete", current_user.id,
           from_status=wo.status.value, to_status="deleted")
    
    return {"message": "工单删除成功"}


@router.post("/{work_order_id}/accept")
async def accept_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """接受工单并创建关联检查实例"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有被分配人才能接受
    if wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="只有被分配人才能接受工单")
    
    if wo.status != WorkOrderStatusEnum.PENDING:
        raise HTTPException(status_code=400, detail=f"只能接受待处理状态的工单，当前状态：{wo.status}")

    # 更新工单状态
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.ACTIVE
    wo.accepted_at = datetime.utcnow()
    
    # 创建关联的检查实例
    inspection = SiteInspection(
        id=str(uuid.uuid4()),
        site_id=wo.site_id,
        inspector_id=wo.assigned_to,
        inspection_type=InspectionTypeEnum.OPENING if wo.type.value == "opening_inspection" else InspectionTypeEnum.MAINTENANCE,
        work_order_id=wo.id,  # 关联工单ID
        status=InspectionStatusEnum.DRAFT,
        template_id=wo.extra_data.get("template_id") if wo.extra_data else "266d3253-13d8-46af-9fd3-f417566428cf"
    )
    db.add(inspection)
    db.flush()
    
    # 根据模板创建检查项
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == inspection.template_id
    ).first()
    
    if template and template.template_data:
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
    
    # 更新工单的inspection_id
    wo.inspection_id = inspection.id
    
    # 同步工单状态到检查
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    
    db.commit()
    db.refresh(wo)
    db.refresh(inspection)
    
    _audit(db, "work_order", wo.id, "accept", current_user.id, 
           from_status=old_status.value, to_status=wo.status.value)
    
    return {
        "message": "工单接受成功",
        "work_order": _enrich_work_order_response(db, wo),
        "inspection_id": inspection.id
    }


@router.get("/{work_order_id}/inspection")
async def get_work_order_inspection(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单关联的检查实例"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    if not wo.inspection_id:
        raise HTTPException(status_code=404, detail="工单尚未创建关联检查")
    
    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
    if not inspection:
        raise HTTPException(status_code=404, detail="关联检查不存在")
    
    # 如果工单被驳回，将检查状态设置为已驳回状态
    if wo.status == WorkOrderStatusEnum.REJECTED and inspection.status != InspectionStatusEnum.REJECTED:
        inspection.status = InspectionStatusEnum.REJECTED
        db.commit()
    
    return {"inspection_id": inspection.id, "status": inspection.status.value}


@router.post("/{work_order_id}/complete")
async def complete_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """完成工单（当关联检查完成后调用）"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.assigned_to != current_user.id and current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限完成此工单")
    
    if wo.status != WorkOrderStatusEnum.ACTIVE:
        raise HTTPException(status_code=400, detail="只能完成执行中的工单")
    
    # 检查关联的检查是否已完成
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if inspection and inspection.status not in [InspectionStatusEnum.APPROVED, InspectionStatusEnum.COMPLETED]:
            raise HTTPException(status_code=400, detail="关联检查尚未完成")
    
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()
    
    db.commit()
    _audit(db, "work_order", wo.id, "complete", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {"message": "工单完成"}


@router.get("/{work_order_id}/items", response_model=List[WorkOrderItemResponse])
async def list_items(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    # 完全使用关联检查的检查项，不再使用工单自己的检查项
    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")
    
    from sqlalchemy.orm import joinedload
    
    inspection_items = db.query(InspectionCheckItem).options(
        joinedload(InspectionCheckItem.photos)
    ).filter(
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).all()
    
    # 将检查项转换为工单检查项格式返回
    result = []
    for item in inspection_items:
        # 构建符合WorkOrderItemResponse格式的数据
        item_data = {
            "id": item.id,
            "work_order_id": work_order_id,
            "item_id": item.item_id,
            "item_name": item.item_name,
            "category_id": item.category_id,
            "category_name": item.category_name,
            "sector_id": item.sector_id,
            "required_type": item.required_type,
            "status": item.status.value if hasattr(item.status, 'value') else str(item.status),
            "data_value": item.data_value if item.data_value else [],
            "validation_result": None,
            "review_status": item.review_status,
            "review_comments": item.review_comments,
            "reviewed_at": item.reviewed_at if hasattr(item, 'reviewed_at') else None,
            "photos": item.photos,  # Include photos
            "created_at": item.created_at,
            "updated_at": item.updated_at
        }
        result.append(WorkOrderItemResponse(**item_data))
    
    return result


@router.put("/{work_order_id}/items/{item_id}", response_model=WorkOrderItemResponse)
async def update_item(
    work_order_id: str,
    item_id: str,
    data: WorkOrderItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限修改此工单")
    
    # 完全使用关联检查的检查项，不再使用工单自己的检查项
    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")
    
    inspection_item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id,
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).first()
    
    if not inspection_item:
        raise HTTPException(status_code=404, detail="检查项不存在")
    
    # 检查工单状态是否允许编辑（驳回后应该可以编辑）
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许编辑检查项")
    
    # 更新检查项
    upd = data.dict(exclude_unset=True)
    if 'data_value' in upd:
        inspection_item.data_value = upd['data_value']
    if 'status' in upd:
        # 将字符串状态转换为枚举
        status_str = upd['status']
        if status_str == 'completed':
            inspection_item.status = CheckItemStatusEnum.COMPLETED
            inspection_item.checked_at = datetime.utcnow()
        elif status_str == 'pending':
            inspection_item.status = CheckItemStatusEnum.PENDING
            inspection_item.checked_at = None
    
    inspection_item.updated_at = datetime.utcnow()
    
    # 检查是否应该更新工单的检查状态
    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
    if inspection and (wo.status == WorkOrderStatusEnum.REJECTED or inspection.status == InspectionStatusEnum.REJECTED):
        # 当工单被驳回或检查被驳回时，任何编辑操作都应该将检查状态改为进行中
        inspection.status = InspectionStatusEnum.IN_PROGRESS
        # 同步工单状态
        sync_service = get_work_order_sync_service(db)
        sync_service.sync_inspection_to_work_order_status(inspection)
    
    db.commit()
    db.refresh(inspection_item)
    
    # 返回格式化的响应
    item_data = {
        "id": inspection_item.id,
        "work_order_id": work_order_id,
        "item_id": inspection_item.item_id,
        "item_name": inspection_item.item_name,
        "category_id": inspection_item.category_id,
        "category_name": inspection_item.category_name,
        "sector_id": inspection_item.sector_id,
        "required_type": inspection_item.required_type,
        "status": inspection_item.status.value if hasattr(inspection_item.status, 'value') else str(inspection_item.status),
        "data_value": inspection_item.data_value if inspection_item.data_value else [],
        "validation_result": None,
        "review_status": inspection_item.review_status,
        "review_comments": inspection_item.review_comments,
        "reviewed_at": inspection_item.reviewed_at if hasattr(inspection_item, 'reviewed_at') else None,
        "created_at": inspection_item.created_at,
        "updated_at": inspection_item.updated_at
    }
    return WorkOrderItemResponse(**item_data)


@router.post("/{work_order_id}/photos", response_model=WorkOrderPhotoResponse)
async def upload_photo(
    work_order_id: str,
    file: UploadFile = File(...),
    item_id: Optional[str] = None,
    gps_latitude: float = 0,
    gps_longitude: float = 0,
    gps_accuracy: Optional[float] = None,
    replace_existing: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限上传该工单照片")
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")

    # 照片逻辑：驳回状态默认替换，其他情况明确指定才替换
    import os
    
    # 默认逻辑：如果工单是驳回状态且该检查项已有照片，则自动启用替换模式
    should_replace = replace_existing
    if not should_replace and wo.status == WorkOrderStatusEnum.REJECTED and item_id:
        existing_count = db.query(WorkOrderPhoto).filter(
            WorkOrderPhoto.work_order_id == work_order_id,
            WorkOrderPhoto.item_id == item_id
        ).count()
        if existing_count > 0:
            should_replace = True
            print(f"工单驳回状态，检查项 {item_id} 已有 {existing_count} 张照片，自动启用替换模式")
    
    # 执行照片替换逻辑
    if should_replace:
        if item_id:
            # 删除同一检查项的已有照片
            existing_photos = db.query(WorkOrderPhoto).filter(
                WorkOrderPhoto.work_order_id == work_order_id,
                WorkOrderPhoto.item_id == item_id
            ).all()
        else:
            # 删除工单级别的照片
            existing_photos = db.query(WorkOrderPhoto).filter(
                WorkOrderPhoto.work_order_id == work_order_id,
                WorkOrderPhoto.item_id.is_(None)
            ).all()
        
        # 删除旧照片文件和数据库记录
        for old_photo in existing_photos:
            try:
                # 删除物理文件
                if old_photo.file_path and os.path.exists(old_photo.file_path):
                    os.remove(old_photo.file_path)
                # 删除数据库记录
                db.delete(old_photo)
                print(f"替换模式：删除旧照片 {old_photo.id}")
            except Exception as e:
                print(f"替换模式：删除旧照片失败 {old_photo.id}: {e}")
        
        print(f"照片替换模式：should_replace={should_replace}，已清理旧照片")
    else:
        print(f"照片添加模式：should_replace={should_replace}，直接添加新照片")

    file_path = await save_uploaded_file(file, "work_orders", work_order_id)
    watermark_data = {
        "gps_coordinates": f"{gps_latitude:.6f}, {gps_longitude:.6f}",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "inspector": current_user.full_name or current_user.username,
        "accuracy": f"{gps_accuracy}m" if gps_accuracy else "N/A"
    }
    watermarked_path = await generate_watermark(file_path, watermark_data)
    from app.api.inspections import calculate_file_hash
    file_hash = calculate_file_hash(watermarked_path)
    address = await reverse_geocode(gps_latitude, gps_longitude)

    photo = WorkOrderPhoto(
        id=str(uuid.uuid4()),
        work_order_id=work_order_id,
        item_id=item_id,
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
        uploaded_by=current_user.id,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return WorkOrderPhotoResponse.from_orm(photo)


@router.get("/{work_order_id}/photos", response_model=List[WorkOrderPhotoResponse])
async def list_photos(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该工单照片")
    photos = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.work_order_id == work_order_id).order_by(WorkOrderPhoto.created_at.desc()).all()
    return [WorkOrderPhotoResponse.from_orm(p) for p in photos]


@router.delete("/photos/{photo_id}")
async def delete_photo(
    photo_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除指定照片"""
    import os
    
    photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查工单权限
    wo = db.query(WorkOrder).filter(WorkOrder.id == photo.work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="关联工单不存在")
        
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限删除该照片")
    
    # 检查工单状态是否允许删除照片
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许删除照片")
    
    # 删除物理文件
    try:
        if photo.file_path and os.path.exists(photo.file_path):
            os.remove(photo.file_path)
            print(f"已删除照片文件: {photo.file_path}")
    except Exception as e:
        print(f"删除照片文件失败: {e}")
    
    # 删除数据库记录
    db.delete(photo)
    db.commit()
    
    _audit(db, "photo", photo_id, "delete", current_user.id, 
           details={"work_order_id": photo.work_order_id, "item_id": photo.item_id})
    
    return {"message": "照片删除成功"}


@router.put("/photos/{photo_id}", response_model=WorkOrderPhotoResponse)
async def replace_photo(
    photo_id: str,
    file: UploadFile = File(...),
    gps_latitude: Optional[float] = None,
    gps_longitude: Optional[float] = None,
    gps_accuracy: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """替换指定照片"""
    import os
    
    existing_photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
    if not existing_photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    
    # 检查权限：检查工单权限
    wo = db.query(WorkOrder).filter(WorkOrder.id == existing_photo.work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="关联工单不存在")
        
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限替换该照片")
    
    # 检查工单状态是否允许替换照片
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许替换照片")
    
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="只支持图片文件")
    
    # 使用传入的GPS坐标，如果没有则使用原照片的坐标
    latitude = gps_latitude if gps_latitude is not None else existing_photo.latitude
    longitude = gps_longitude if gps_longitude is not None else existing_photo.longitude
    accuracy = gps_accuracy if gps_accuracy is not None else existing_photo.gps_accuracy
    
    # 保存新文件
    file_path = await save_uploaded_file(file, "work_orders", existing_photo.work_order_id)
    watermark_data = {
        "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "inspector": current_user.full_name or current_user.username,
        "accuracy": f"{accuracy}m" if accuracy else "N/A"
    }
    watermarked_path = await generate_watermark(file_path, watermark_data)
    from app.api.inspections import calculate_file_hash
    file_hash = calculate_file_hash(watermarked_path)
    address = await reverse_geocode(latitude, longitude)
    
    # 删除旧文件
    try:
        if existing_photo.file_path and os.path.exists(existing_photo.file_path):
            os.remove(existing_photo.file_path)
            print(f"已删除旧照片文件: {existing_photo.file_path}")
    except Exception as e:
        print(f"删除旧照片文件失败: {e}")
    
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
    existing_photo.has_watermark = True
    existing_photo.watermark_data = watermark_data
    existing_photo.hash_value = file_hash
    existing_photo.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(existing_photo)
    
    _audit(db, "photo", photo_id, "replace", current_user.id,
           details={"work_order_id": existing_photo.work_order_id, "item_id": existing_photo.item_id})
    
    return WorkOrderPhotoResponse.from_orm(existing_photo)


@router.post("/{work_order_id}/photos/batch")
async def batch_photo_operations(
    work_order_id: str,
    operations: List[dict],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量照片操作：删除、更新、添加照片
    
    operations: 操作列表，每个操作包含:
    - action: "delete" | "replace" | "add"
    - photo_id: 照片ID (delete/replace时必需)
    - file_data: base64编码的文件数据 (replace/add时必需)
    - filename: 文件名 (replace/add时必需)
    - item_id: 检查项ID (add时必需)
    - gps_latitude, gps_longitude, gps_accuracy: GPS信息 (replace/add时可选)
    """
    import os
    import base64
    import tempfile
    from fastapi import UploadFile
    from io import BytesIO
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该工单照片")
    
    # 检查工单状态是否允许操作照片
    if wo.status not in [WorkOrderStatusEnum.ACTIVE, WorkOrderStatusEnum.REJECTED]:
        raise HTTPException(status_code=400, detail=f"工单状态 {wo.status} 下不允许操作照片")
    
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
                photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
                if not photo:
                    results.append({"index": i, "action": "delete", "success": False, "error": "照片不存在"})
                    continue
                
                # 删除物理文件
                try:
                    if photo.file_path and os.path.exists(photo.file_path):
                        os.remove(photo.file_path)
                except Exception as e:
                    print(f"批量操作：删除照片文件失败: {e}")
                
                # 删除数据库记录
                db.delete(photo)
                results.append({"index": i, "action": "delete", "success": True, "photo_id": photo_id})
                
            elif action == "replace":
                if not photo_id or not operation.get("file_data"):
                    results.append({"index": i, "action": "replace", "success": False, "error": "缺少photo_id或file_data"})
                    continue
                
                # 获取现有照片
                existing_photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id).first()
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
                    
                    # 保存新文件
                    file_path = await save_uploaded_file(upload_file, "work_orders", work_order_id)
                    watermark_data = {
                        "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "inspector": current_user.full_name or current_user.username,
                        "accuracy": f"{accuracy}m" if accuracy else "N/A"
                    }
                    watermarked_path = await generate_watermark(file_path, watermark_data)
                    from app.api.inspections import calculate_file_hash
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 删除旧文件
                    try:
                        if existing_photo.file_path and os.path.exists(existing_photo.file_path):
                            os.remove(existing_photo.file_path)
                    except Exception as e:
                        print(f"批量操作：删除旧照片文件失败: {e}")
                    
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
                    existing_photo.has_watermark = True
                    existing_photo.watermark_data = watermark_data
                    existing_photo.hash_value = file_hash
                    existing_photo.updated_at = datetime.utcnow()
                    
                    results.append({"index": i, "action": "replace", "success": True, "photo_id": photo_id})
                    
                except Exception as e:
                    results.append({"index": i, "action": "replace", "success": False, "error": str(e)})
                    
            elif action == "add":
                if not operation.get("file_data") or not operation.get("item_id"):
                    results.append({"index": i, "action": "add", "success": False, "error": "缺少file_data或item_id"})
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
                    
                    # 保存文件
                    file_path = await save_uploaded_file(upload_file, "work_orders", work_order_id)
                    watermark_data = {
                        "gps_coordinates": f"{latitude:.6f}, {longitude:.6f}",
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        "inspector": current_user.full_name or current_user.username,
                        "accuracy": f"{accuracy}m" if accuracy else "N/A"
                    }
                    watermarked_path = await generate_watermark(file_path, watermark_data)
                    from app.api.inspections import calculate_file_hash
                    file_hash = calculate_file_hash(watermarked_path)
                    address = await reverse_geocode(latitude, longitude)
                    
                    # 创建新照片记录
                    new_photo = WorkOrderPhoto(
                        id=str(uuid.uuid4()),
                        work_order_id=work_order_id,
                        item_id=operation["item_id"],
                        original_name=filename,
                        file_path=watermarked_path,
                        file_size=len(file_data),
                        mime_type="image/jpeg",
                        latitude=latitude,
                        longitude=longitude,
                        gps_accuracy=accuracy,
                        address=address,
                        taken_at=datetime.utcnow(),
                        has_watermark=True,
                        watermark_data=watermark_data,
                        hash_value=file_hash,
                        uploaded_by=current_user.id,
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
    _audit(db, "photos", work_order_id, "batch_operations", current_user.id,
           details={"operations_count": len(operations), "results": results})
    
    return {
        "message": "批量照片操作完成",
        "total_operations": len(operations),
        "results": results
    }


@router.post("/{work_order_id}/photos/cleanup")
async def cleanup_duplicate_photos(
    work_order_id: str,
    item_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """清理重复和累积的照片，只保留最新的照片"""
    import os
    from collections import defaultdict
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限操作该工单照片")
    
    # 构建查询条件
    query = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.work_order_id == work_order_id)
    if item_id:
        query = query.filter(WorkOrderPhoto.item_id == item_id)
    
    # 获取所有照片，按检查项分组
    photos = query.order_by(WorkOrderPhoto.created_at.desc()).all()
    
    # 按检查项分组
    photos_by_item = defaultdict(list)
    for photo in photos:
        key = photo.item_id or "work_order_level"
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
                print(f"清理累积照片: {old_photo.id} (检查项: {item_key})")
            except Exception as e:
                print(f"清理照片失败 {old_photo.id}: {e}")
        
        kept_count += 1  # 保留的最新照片
    
    db.commit()
    
    # 记录审计日志
    _audit(db, "photos", work_order_id, "cleanup_duplicates", current_user.id,
           details={"deleted_count": deleted_count, "kept_count": kept_count, "item_id": item_id})
    
    return {
        "message": "照片清理完成",
        "deleted_count": deleted_count,
        "kept_count": kept_count,
        "details": f"已删除 {deleted_count} 张重复照片，保留 {kept_count} 张最新照片"
    }


@router.post("/{work_order_id}/review/start")
async def start_review(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限认领审核")
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.status != WorkOrderStatusEnum.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"只能从 submitted 认领，当前：{wo.status}")
    old = wo.status
    wo.status = WorkOrderStatusEnum.UNDER_REVIEW
    db.commit()
    _audit(db, "work_order", work_order_id, "review_start", current_user.id, from_status=old.value, to_status=wo.status.value)
    return {"message": "已进入审核中"}


@router.post("/{work_order_id}/items/{item_id}/review")
async def review_item(
    work_order_id: str,
    item_id: str,
    req: ItemReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限执行检查项审核")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or not wo.inspection_id:
        raise HTTPException(status_code=404, detail="工单或关联检查不存在")
    
    item = db.query(InspectionCheckItem).filter(
        InspectionCheckItem.id == item_id, 
        InspectionCheckItem.inspection_id == wo.inspection_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="检查项不存在")
    
    item.review_status = req.action
    item.review_comments = req.comments
    item.reviewed_at = datetime.utcnow()
    db.commit()
    _audit(db, "item", item_id, "item_review", current_user.id, comments=req.comments, details={"result": req.action})
    _update_work_order_result(db, work_order_id)
    return {"message": "检查项审核成功"}


@router.post("/{work_order_id}/photos/{photo_id}/review")
async def review_photo(
    work_order_id: str,
    photo_id: str,
    req: PhotoReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限执行照片审核")
    photo = db.query(WorkOrderPhoto).filter(WorkOrderPhoto.id == photo_id, WorkOrderPhoto.work_order_id == work_order_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="照片不存在")
    photo.review_status = req.action
    photo.review_comments = req.comments
    db.commit()
    _audit(db, "photo", photo_id, "photo_review", current_user.id, comments=req.comments, details={"result": req.action})
    return {"message": "照片审核成功"}


@router.get("/{work_order_id}/review-summary", response_model=ReviewSummary)
async def review_summary(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if not wo.inspection_id:
        return ReviewSummary(total_items=0, pass_count=0, fail_count=0, warning_count=0, pending_count=0)
    
    total = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).count()
    p = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "pass").count()
    f = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "fail").count()
    w = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id, InspectionCheckItem.review_status == "warning").count()
    pending = total - p - f - w
    return ReviewSummary(total_items=total, pass_count=p, fail_count=f, warning_count=w, pending_count=pending)


@router.post("/{work_order_id}/review")
async def final_review(
    work_order_id: str,
    req: WorkOrderReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in ["admin", "manager", "reviewer"]:
        raise HTTPException(status_code=403, detail="没有权限审核工单")
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if wo.status not in [WorkOrderStatusEnum.SUBMITTED, WorkOrderStatusEnum.UNDER_REVIEW]:
        raise HTTPException(status_code=400, detail=f"当前状态不允许审核：{wo.status}")

    # 检查是否有不合格的检查项，如果有则不能通过
    if req.action == "approve" and wo.inspection_id:
        failed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == wo.inspection_id,
            InspectionCheckItem.review_status == "fail"
        ).all()
        
        if failed_items:
            failed_names = [item.item_name for item in failed_items]
            raise HTTPException(
                status_code=400, 
                detail=f"不能通过工单审核，存在不合格的检查项：{', '.join(failed_names)}"
            )

    old = wo.status
    wo.status = WorkOrderStatusEnum.APPROVED if req.action == "approve" else WorkOrderStatusEnum.REJECTED
    wo.reviewed_by = current_user.id
    wo.reviewed_at = datetime.utcnow()
    wo.review_comments = req.comments
    if req.score is not None:
        wo.score = req.score
    db.commit()
    _audit(db, "work_order", work_order_id, "final_review", current_user.id, from_status=old.value, to_status=wo.status.value, comments=req.comments)
    return {"message": "审核完成"}


def _update_work_order_result(db: Session, work_order_id: str):
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo or not wo.inspection_id:
        return
    
    items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).all()
    result = None
    if any(i.review_status == "fail" for i in items):
        result = "fail"
    elif any(i.review_status == "warning" for i in items):
        result = "warning"
    elif items and all(i.review_status == "pass" for i in items if i.review_status is not None):
        result = "pass"
    
    wo.result = result
    db.commit()


def _resolve_template_for_work_order(db: Session, wo: WorkOrder):
    site = db.query(Site).filter(Site.id == wo.site_id).first()
    resolver = create_resolver(db)
    ctx = ResolveContext(
        site_id=wo.site_id,
        site_type=getattr(site, 'site_type', None),
        task_type=wo.type.value,
        region=getattr(site, 'region', None),
        customer=getattr(site, 'customer', None),
        tags=[]
    )
    match = resolver.resolve_template(ctx)
    return match.template if match else None


@router.get("/{work_order_id}/items/field-schema")
async def get_item_field_schema(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """返回每个检查项的字段定义（若模板未定义，返回通用字段）"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问该工单")

    if not wo.inspection_id:
        raise HTTPException(status_code=400, detail="工单尚未关联检查实例")

    template = _resolve_template_for_work_order(db, wo)
    items = db.query(InspectionCheckItem).filter(InspectionCheckItem.inspection_id == wo.inspection_id).all()

    # 构建模板 items 索引（按基础 item_id）
    tpl_index = {}
    if template:
        for cat in template.template_data.get("check_categories", []):
            for it in cat.get("items", []):
                base_id = it.get("item_id")
                if base_id:
                    tpl_index[base_id] = it

    def default_fields(required_type: str):
        fields = []
        # 提供一个通用备注字段
        fields.append({
            "field_id": "note",
            "label": "备注",
            "type": "text",
            "required": False,
        })
        # 可扩展更多默认字段
        return fields

    result = []
    for it in items:
        base_id = it.item_id.split("_sector_")[0] if "_sector_" in it.item_id else it.item_id
        tpl_item = tpl_index.get(base_id)
        fields = []
        if tpl_item and isinstance(tpl_item, dict) and tpl_item.get("fields"):
            fields = tpl_item.get("fields")
        else:
            fields = default_fields(it.required_type)
        result.append({
            "item_id": it.id,
            "base_item_id": base_id,
            "fields": fields
        })

    return result


@router.post("/{work_order_id}/submit")
async def submit_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """提交工单等待审核"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有被分配人才能提交
    if wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="只有被分配人才能提交工单")
    
    if wo.status != WorkOrderStatusEnum.ACTIVE:
        raise HTTPException(status_code=400, detail=f"只能提交活跃状态的工单，当前状态：{wo.status}")
    
    # 检查关联的检查是否完成
    if wo.inspection_id:
        inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
        if not inspection:
            raise HTTPException(status_code=400, detail="未找到关联的检查实例")
        
        # 检查所有检查项是否完成
        total_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id
        ).count()
        
        completed_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id,
            InspectionCheckItem.status == CheckItemStatusEnum.COMPLETED
        ).count()
        
        if completed_items < total_items:
            raise HTTPException(
                status_code=400, 
                detail=f"检查未完成，已完成 {completed_items}/{total_items} 项"
            )
        
        # 同步检查状态
        inspection.status = InspectionStatusEnum.SUBMITTED
        inspection.submitted_at = datetime.utcnow()
    
    # 更新工单状态
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.SUBMITTED
    wo.submitted_at = datetime.utcnow()
    
    # 分配审核人（默认分配给分配人，即管理员）
    wo.reviewer_id = wo.assigned_by
    
    # 同步状态
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    sync_service.sync_work_order_review_info(wo)
    
    db.commit()
    
    _audit(db, "work_order", wo.id, "submit", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {
        "message": "工单提交成功",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/{work_order_id}/review")
async def review_work_order(
    work_order_id: str,
    review_data: WorkOrderReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """审核工单"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    # 权限检查：只有管理员、项目经理或指定审核人才能审核
    if (current_user.role not in ["admin", "manager"] and 
        wo.reviewer_id != current_user.id):
        raise HTTPException(status_code=403, detail="无权限审核此工单")
    
    if wo.status != WorkOrderStatusEnum.SUBMITTED:
        raise HTTPException(status_code=400, detail=f"只能审核已提交的工单，当前状态：{wo.status}")
    
    # 更新工单状态
    old_status = wo.status
    
    if review_data.action == "approve":
        wo.status = WorkOrderStatusEnum.COMPLETED
        wo.completed_at = datetime.utcnow()
        
        # 同步检查状态
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.APPROVED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = review_data.comments
                if review_data.score:
                    inspection.score = review_data.score
                    inspection.result = "pass" if review_data.score >= 60 else "fail"
        
    elif review_data.action == "reject":
        wo.status = WorkOrderStatusEnum.REJECTED  # 驳回状态
        
        # 同步检查状态
        if wo.inspection_id:
            inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
            if inspection:
                inspection.status = InspectionStatusEnum.REJECTED
                inspection.reviewed_by = current_user.id
                inspection.reviewed_at = datetime.utcnow()
                inspection.review_comments = review_data.comments
                inspection.result = "fail"
    
    # 更新审核信息
    wo.reviewed_at = datetime.utcnow()
    wo.review_comments = review_data.comments
    
    # 同步状态
    sync_service = get_work_order_sync_service(db)
    sync_service.sync_work_order_to_inspection_status(wo)
    sync_service.sync_work_order_review_info(wo)
    
    db.commit()
    
    _audit(db, "work_order", wo.id, f"review_{review_data.action}", current_user.id,
           from_status=old_status.value, to_status=wo.status.value,
           comments=review_data.comments)
    
    return {
        "message": f"工单{review_data.action}成功",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.post("/batch-operation")
async def batch_work_order_operation(
    operation: WorkOrderBatchOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量工单操作"""
    # 只有admin和manager可以批量操作
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin and manager can perform batch operations"
        )
    
    if not operation.work_order_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No work order IDs provided"
        )
    
    work_orders = db.query(WorkOrder).filter(WorkOrder.id.in_(operation.work_order_ids)).all()
    
    if len(work_orders) != len(operation.work_order_ids):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Some work orders not found"
        )
    
    # 执行批量操作
    updated_count = 0
    error_count = 0
    errors = []
    
    for wo in work_orders:
        try:
            if operation.operation == "delete":
                # 检查工单状态：只能删除待分配或已分配状态的工单
                if wo.status not in [WorkOrderStatusEnum.PENDING, WorkOrderStatusEnum.ACTIVE]:
                    errors.append(f"工单 {wo.id} 状态不允许删除: {wo.status}")
                    error_count += 1
                    continue
                
                # 如果有关联的检查记录，需要同时删除
                if wo.inspection_id:
                    inspection = db.query(SiteInspection).filter(SiteInspection.id == wo.inspection_id).first()
                    if inspection:
                        db.delete(inspection)
                
                # 删除工单
                db.delete(wo)
                _audit(db, "work_order", wo.id, "batch_delete", current_user.id,
                       from_status=wo.status.value, to_status="deleted")
                updated_count += 1
                
            elif operation.operation == "change_status" and operation.value:
                try:
                    new_status = WorkOrderStatusEnum(operation.value)
                    old_status = wo.status
                    wo.status = new_status
                    _audit(db, "work_order", wo.id, "batch_status_change", current_user.id,
                           from_status=old_status.value, to_status=new_status.value)
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效状态: {operation.value}")
                    error_count += 1
                    
            elif operation.operation == "change_assignee" and operation.value:
                try:
                    new_assignee_id = int(operation.value)
                    # 检查用户是否存在
                    assignee = db.query(User).filter(User.id == new_assignee_id).first()
                    if not assignee:
                        errors.append(f"工单 {wo.id} 分配人不存在: {new_assignee_id}")
                        error_count += 1
                        continue
                    
                    wo.assigned_to = new_assignee_id
                    _audit(db, "work_order", wo.id, "batch_assignee_change", current_user.id,
                           details={"new_assignee": new_assignee_id})
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效分配人ID: {operation.value}")
                    error_count += 1
                    
            elif operation.operation == "change_priority" and operation.value:
                try:
                    new_priority = WorkOrderPriorityEnum(operation.value)
                    wo.priority = new_priority
                    _audit(db, "work_order", wo.id, "batch_priority_change", current_user.id,
                           details={"new_priority": new_priority.value})
                    updated_count += 1
                except ValueError:
                    errors.append(f"工单 {wo.id} 无效优先级: {operation.value}")
                    error_count += 1
                    
        except Exception as e:
            errors.append(f"工单 {wo.id} 操作失败: {str(e)}")
            error_count += 1
    
    db.commit()
    
    result = {
        "message": f"批量操作完成，成功 {updated_count} 个，失败 {error_count} 个",
        "updated_count": updated_count,
        "error_count": error_count
    }
    
    if errors:
        result["errors"] = errors
    
    return result


@router.get("/stats/summary")
async def get_work_order_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单统计信息"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    
    total_work_orders = db.query(WorkOrder).count()
    
    # 按状态统计
    status_stats = {}
    for status_enum in WorkOrderStatusEnum:
        count = db.query(WorkOrder).filter(WorkOrder.status == status_enum).count()
        status_stats[status_enum.value] = count
    
    # 按类型统计
    type_stats = {}
    for type_enum in WorkOrderTypeEnum:
        count = db.query(WorkOrder).filter(WorkOrder.type == type_enum).count()
        type_stats[type_enum.value] = count
    
    # 按优先级统计
    priority_stats = {}
    for priority_enum in WorkOrderPriorityEnum:
        count = db.query(WorkOrder).filter(WorkOrder.priority == priority_enum).count()
        priority_stats[priority_enum.value] = count
    
    return {
        "total_work_orders": total_work_orders,
        "status_stats": status_stats,
        "type_stats": type_stats,
        "priority_stats": priority_stats
    }


@router.post("/{work_order_id}/check-activation")
async def check_equipment_activation(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """手动触发设备开通检测"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限执行设备开通检测")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.status != WorkOrderStatusEnum.APPROVED:
        raise HTTPException(
            status_code=400, 
            detail=f"只有审核通过的工单才能进行设备开通检测，当前状态：{wo.status}"
        )
    
    from app.services.equipment_activation_service import EquipmentActivationService
    
    service = EquipmentActivationService(db)
    result = await service.trigger_equipment_activation_check(work_order_id)
    
    return result


@router.get("/{work_order_id}/activation-status")
async def get_activation_status(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单设备开通状态"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    activation_check = wo.extra_data.get("activation_check") if wo.extra_data else None
    
    return {
        "work_order_id": work_order_id,
        "status": wo.status.value,
        "activation_check": activation_check,
        "last_check_time": wo.extra_data.get("activation_check_time") if wo.extra_data else None,
        "activated_at": wo.activated_at.isoformat() if wo.activated_at else None
    }


@router.post("/{work_order_id}/mark-completed")
async def mark_work_order_completed(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """将已开通的工单标记为完成"""
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(status_code=403, detail="无权限完成工单")
    
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if wo.status != WorkOrderStatusEnum.ACTIVATED:
        raise HTTPException(
            status_code=400,
            detail=f"只有已开通的工单才能标记为完成，当前状态：{wo.status}"
        )
    
    old_status = wo.status
    wo.status = WorkOrderStatusEnum.COMPLETED
    wo.completed_at = datetime.utcnow()
    
    db.commit()
    
    _audit(db, "work_order", work_order_id, "mark_completed", current_user.id,
           from_status=old_status.value, to_status=wo.status.value)
    
    return {
        "message": "工单已标记为完成",
        "work_order": _enrich_work_order_response(db, wo)
    }


@router.get("/{work_order_id}/progress")
async def get_work_order_progress(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取工单进度信息"""
    wo = db.query(WorkOrder).filter(WorkOrder.id == work_order_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="工单不存在")
    
    if current_user.role == "inspector" and wo.assigned_to != current_user.id:
        raise HTTPException(status_code=403, detail="无权限访问此工单")
    
    from app.utils.work_order_progress import WorkOrderProgressCalculator
    
    progress_info = WorkOrderProgressCalculator.calculate_progress(db, wo)
    
    return {
        "work_order_id": work_order_id,
        "status": wo.status.value,
        "stage_name": WorkOrderProgressCalculator.get_stage_name(wo.status),
        "next_action": WorkOrderProgressCalculator.get_next_action(wo.status),
        "progress_color": WorkOrderProgressCalculator.get_progress_color(progress_info["progress"]),
        **progress_info
    }
