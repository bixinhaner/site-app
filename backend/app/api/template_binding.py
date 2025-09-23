"""
模板绑定管理API
提供模板绑定的增删改查和解析功能
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from typing import List, Optional
from datetime import datetime
import uuid

from app.core.database import get_db
from app.models.user import User
from app.models.site import Site
from app.models.inspection import (
    InspectionTemplate, TemplateBinding
)
from app.schemas.template_binding import (
    TemplateBindingCreate, TemplateBindingUpdate, TemplateBindingResponse,
    TemplateBindingBatchUpdate, ResolveContextSchema, TemplateResolveResponse,
    TemplateMatchResultSchema, InspectionTemplateCreate, InspectionTemplateUpdate,
    InspectionTemplateResponse
)
from app.api.auth import get_current_user
from app.services.template_resolver import (
    TemplateResolver, ResolveContext, create_resolver
)

router = APIRouter()


@router.get("/templates", response_model=List[InspectionTemplateResponse])
async def get_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    site_id: Optional[int] = Query(None),
    site_type: Optional[str] = Query(None),
    task_type: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="搜索关键字"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取检查模板列表"""
    # 权限检查：管理员/经理可管理，检查员可读
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    query = db.query(InspectionTemplate).options(
        joinedload(InspectionTemplate.creator)
    )
    
    # 关键字搜索
    if q:
        query = query.filter(InspectionTemplate.template_name.contains(q))
    

    # 按更新时间排序
    query = query.order_by(desc(InspectionTemplate.updated_at))
    
    templates = query.offset(skip).limit(limit).all()
    
    # 获取绑定统计信息
    result = []
    for template in templates:
        bindings_count = db.query(TemplateBinding).filter(
            TemplateBinding.template_id == template.id
        ).count()
        
        active_bindings_count = db.query(TemplateBinding).filter(
            TemplateBinding.template_id == template.id,
            TemplateBinding.active == True
        ).count()
        
        template_response = InspectionTemplateResponse(
            id=template.id,
            template_name=template.template_name,
            template_data=template.template_data,
            created_by=template.created_by,
            created_at=template.created_at,
            updated_at=template.updated_at,
            creator_name=template.creator.full_name if template.creator else None,
            bindings_count=bindings_count,
            active_bindings_count=active_bindings_count
        )
        result.append(template_response)
    
    return result


@router.post("/templates", response_model=InspectionTemplateResponse)
async def create_template(
    template_data: InspectionTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建检查模板"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 创建模板
    template = InspectionTemplate(
        id=str(uuid.uuid4()),
        template_name=template_data.template_name,
        template_data=template_data.template_data,
        created_by=current_user.id
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=current_user.full_name,
        bindings_count=0,
        active_bindings_count=0
    )


@router.get("/templates/{template_id}", response_model=InspectionTemplateResponse)
async def get_template(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取模板详情"""
    # 权限检查
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    template = db.query(InspectionTemplate).options(
        joinedload(InspectionTemplate.creator)
    ).filter(InspectionTemplate.id == template_id).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 获取绑定统计信息
    bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id
    ).count()
    
    active_bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id,
        TemplateBinding.active == True
    ).count()
    
    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=template.creator.full_name if template.creator else None,
        bindings_count=bindings_count,
        active_bindings_count=active_bindings_count
    )


@router.put("/templates/{template_id}", response_model=InspectionTemplateResponse)
async def update_template(
    template_id: str,
    template_update: InspectionTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新检查模板"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 更新字段
    update_fields = template_update.dict(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(template, field, value)
    
    template.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(template)
    
    # 获取绑定统计信息
    bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id
    ).count()
    
    active_bindings_count = db.query(TemplateBinding).filter(
        TemplateBinding.template_id == template.id,
        TemplateBinding.active == True
    ).count()
    
    return InspectionTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        template_data=template.template_data,
        created_by=template.created_by,
        created_at=template.created_at,
        updated_at=template.updated_at,
        creator_name=template.creator.full_name if template.creator else None,
        bindings_count=bindings_count,
        active_bindings_count=active_bindings_count
    )


@router.get("/templates/{template_id}/bindings", response_model=List[TemplateBindingResponse])
async def get_template_bindings(
    template_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=1000),
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取模板绑定列表"""
    # 权限检查
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    query = db.query(TemplateBinding).options(
        joinedload(TemplateBinding.site),
        joinedload(TemplateBinding.creator)
    ).filter(TemplateBinding.template_id == template_id)
    
    if active_only:
        query = query.filter(TemplateBinding.active == True)
    
    # 按优先级降序、更新时间降序排序
    query = query.order_by(desc(TemplateBinding.priority), desc(TemplateBinding.updated_at))
    
    bindings = query.offset(skip).limit(limit).all()
    
    result = []
    for binding in bindings:
        binding_response = TemplateBindingResponse(
            id=binding.id,
            template_id=binding.template_id,
            site_id=binding.site_id,
            site_type=binding.site_type,
            task_type=None,
            region=binding.region,
            customer=binding.customer,
            tags=binding.tags,
            priority=binding.priority,
            active=binding.active,
            valid_from=binding.valid_from,
            valid_to=binding.valid_to,
            notes=binding.notes,
            created_by=binding.created_by,
            created_at=binding.created_at,
            updated_at=binding.updated_at,
            template_name=template.template_name,
            site_name=binding.site.site_name if binding.site else None,
            creator_name=binding.creator.full_name if binding.creator else None
        )
        result.append(binding_response)
    
    return result


@router.post("/templates/{template_id}/bindings", response_model=TemplateBindingResponse)
async def create_template_binding(
    template_id: str,
    binding_data: TemplateBindingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建模板绑定"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 验证绑定条件
    resolver = create_resolver(db)
    errors = resolver.validate_binding_conditions(binding_data.dict())
    if errors:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"绑定条件验证失败: {'; '.join(errors)}"
        )
    
    # 创建绑定
    binding = TemplateBinding(
        template_id=template_id,
        site_id=binding_data.site_id,
        site_type=binding_data.site_type,
        task_type=binding_data.task_type,
        region=binding_data.region,
        customer=binding_data.customer,
        tags=binding_data.tags,
        priority=binding_data.priority,
        active=binding_data.active,
        valid_from=binding_data.valid_from,
        valid_to=binding_data.valid_to,
        notes=binding_data.notes,
        created_by=current_user.id
    )
    
    db.add(binding)
    db.commit()
    db.refresh(binding)
    
    # 获取关联信息
    site = None
    if binding.site_id:
        site = db.query(Site).filter(Site.id == binding.site_id).first()
    
    return TemplateBindingResponse(
        id=binding.id,
        template_id=binding.template_id,
        site_id=binding.site_id,
        site_type=binding.site_type,
        task_type=binding.task_type,
        region=binding.region,
        customer=binding.customer,
        tags=binding.tags,
        priority=binding.priority,
        active=binding.active,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        notes=binding.notes,
        created_by=binding.created_by,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
        template_name=template.template_name,
        site_name=site.site_name if site else None,
        creator_name=current_user.full_name
    )


@router.put("/templates/{template_id}/bindings/{binding_id}", response_model=TemplateBindingResponse)
async def update_template_binding(
    template_id: str,
    binding_id: int,
    binding_update: TemplateBindingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新模板绑定"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    binding = db.query(TemplateBinding).filter(
        TemplateBinding.id == binding_id,
        TemplateBinding.template_id == template_id
    ).first()
    
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="绑定不存在"
        )
    
    # 验证绑定条件
    update_data = binding_update.dict(exclude_unset=True)
    if update_data:
        # 合并现有数据和更新数据进行验证
        current_data = {
            'site_id': binding.site_id,
            'site_type': binding.site_type,
            'task_type': binding.task_type.value if binding.task_type else None,
            'region': binding.region,
            'customer': binding.customer,
            'tags': binding.tags,
            'priority': binding.priority
        }
        current_data.update(update_data)
        
        resolver = create_resolver(db)
        errors = resolver.validate_binding_conditions(current_data)
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"绑定条件验证失败: {'; '.join(errors)}"
            )
    
    # 更新字段
    for field, value in update_data.items():
        setattr(binding, field, value)
    
    binding.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(binding)
    
    # 获取关联信息
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    site = None
    if binding.site_id:
        site = db.query(Site).filter(Site.id == binding.site_id).first()
    
    creator = db.query(User).filter(User.id == binding.created_by).first()
    
    return TemplateBindingResponse(
        id=binding.id,
        template_id=binding.template_id,
        site_id=binding.site_id,
        site_type=binding.site_type,
        task_type=binding.task_type,
        region=binding.region,
        customer=binding.customer,
        tags=binding.tags,
        priority=binding.priority,
        active=binding.active,
        valid_from=binding.valid_from,
        valid_to=binding.valid_to,
        notes=binding.notes,
        created_by=binding.created_by,
        created_at=binding.created_at,
        updated_at=binding.updated_at,
        template_name=template.template_name if template else None,
        site_name=site.site_name if site else None,
        creator_name=creator.full_name if creator else None
    )


@router.delete("/templates/{template_id}/bindings/{binding_id}")
async def delete_template_binding(
    template_id: str,
    binding_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """删除模板绑定"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    binding = db.query(TemplateBinding).filter(
        TemplateBinding.id == binding_id,
        TemplateBinding.template_id == template_id
    ).first()
    
    if not binding:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="绑定不存在"
        )
    
    db.delete(binding)
    db.commit()
    
    return {"message": "绑定已删除"}


@router.post("/templates/{template_id}/bindings/batch-update")
async def batch_update_binding_priority(
    template_id: str,
    batch_update: TemplateBindingBatchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """批量更新绑定优先级（用于拖拽排序）"""
    # 权限检查
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 验证模板存在
    template = db.query(InspectionTemplate).filter(
        InspectionTemplate.id == template_id
    ).first()
    
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="模板不存在"
        )
    
    # 批量更新
    updated_count = 0
    for update_data in batch_update.binding_updates:
        binding = db.query(TemplateBinding).filter(
            TemplateBinding.id == update_data['id'],
            TemplateBinding.template_id == template_id
        ).first()
        
        if binding:
            binding.priority = update_data['priority']
            binding.updated_at = datetime.utcnow()
            updated_count += 1
    
    db.commit()
    
    return {
        "message": f"成功更新 {updated_count} 个绑定的优先级",
        "updated_count": updated_count
    }


@router.post("/templates/resolve", response_model=TemplateResolveResponse)
async def resolve_template(
    context: ResolveContextSchema,
    show_all: bool = Query(False, description="是否显示所有匹配结果"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """解析最匹配的模板"""
    # 权限检查
    if current_user.role not in ["admin", "manager", "inspector"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="权限不足"
        )
    
    # 创建解析上下文
    resolve_context = ResolveContext(
        site_id=context.site_id,
        site_type=context.site_type,
        task_id=context.task_id,
        task_type=context.task_type,
        region=context.region,
        customer=context.customer,
        tags=context.tags
    )
    
    # 创建解析器
    resolver = create_resolver(db)
    
    if show_all:
        # 获取所有匹配结果
        all_matches = resolver.get_matching_bindings(resolve_context)
        
        all_match_schemas = []
        for match in all_matches:
            # 获取绑定详情
            binding_response = TemplateBindingResponse(
                id=match.binding.id,
                template_id=match.binding.template_id,
                site_id=match.binding.site_id,
                site_type=match.binding.site_type,
                task_type=match.binding.task_type,
                region=match.binding.region,
                customer=match.binding.customer,
                tags=match.binding.tags,
                priority=match.binding.priority,
                active=match.binding.active,
                valid_from=match.binding.valid_from,
                valid_to=match.binding.valid_to,
                notes=match.binding.notes,
                created_by=match.binding.created_by,
                created_at=match.binding.created_at,
                updated_at=match.binding.updated_at
            )
            
            match_schema = TemplateMatchResultSchema(
                template_id=match.template_id,
                binding_id=match.binding_id,
                match_score=match.match_score,
                priority=match.priority,
                explain=match.explain,
                template_name=match.template.template_name,
                template_data=match.template.template_data,
                binding_details=binding_response
            )
            all_match_schemas.append(match_schema)
        
        return TemplateResolveResponse(
            success=True,
            result=all_match_schemas[0] if all_match_schemas else None,
            message=f"找到 {len(all_match_schemas)} 个匹配结果" if all_match_schemas else "未找到匹配的模板",
            all_matches=all_match_schemas
        )
    else:
        # 只获取最佳匹配
        result = resolver.resolve_template(resolve_context)
        
        if result:
            # 获取绑定详情
            binding_response = TemplateBindingResponse(
                id=result.binding.id,
                template_id=result.binding.template_id,
                site_id=result.binding.site_id,
                site_type=result.binding.site_type,
                task_type=result.binding.task_type,
                region=result.binding.region,
                customer=result.binding.customer,
                tags=result.binding.tags,
                priority=result.binding.priority,
                active=result.binding.active,
                valid_from=result.binding.valid_from,
                valid_to=result.binding.valid_to,
                notes=result.binding.notes,
                created_by=result.binding.created_by,
                created_at=result.binding.created_at,
                updated_at=result.binding.updated_at
            )
            
            result_schema = TemplateMatchResultSchema(
                template_id=result.template_id,
                binding_id=result.binding_id,
                match_score=result.match_score,
                priority=result.priority,
                explain=result.explain,
                template_name=result.template.template_name,
                template_data=result.template.template_data,
                binding_details=binding_response
            )
            
            return TemplateResolveResponse(
                success=True,
                result=result_schema,
                message="成功找到匹配的模板"
            )
        else:
            return TemplateResolveResponse(
                success=False,
                message="未找到匹配的模板，将使用默认模板"
            )
