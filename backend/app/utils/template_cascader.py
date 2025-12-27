"""
模板级联更新工具
用于自动更新已有检查项的非结构性内容
"""

from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.inspection import SiteInspection, InspectionCheckItem


def cascade_update_check_items(
    db: Session,
    template_id: str,
    old_template_data: Dict,
    new_template_data: Dict
) -> int:
    """
    自动级联更新已有检查项的非结构性内容
    
    Args:
        db: 数据库会话
        template_id: 模板ID
        old_template_data: 旧模板数据
        new_template_data: 新模板数据
    
    Returns:
        更新的检查项数量
    """
    
    # 获取所有使用该模板的检查记录
    inspections = db.query(SiteInspection).filter(
        SiteInspection.template_id == template_id
    ).all()
    
    if not inspections:
        return 0
    
    print(f"[级联更新] 找到 {len(inspections)} 个使用模板 {template_id} 的检查记录")
    
    updated_count = 0
    
    for inspection in inspections:
        # 获取该检查的所有检查项
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection.id
        ).all()
        
        print(f"[级联更新] 检查记录 {inspection.id} 有 {len(check_items)} 个检查项")
        
        for check_item in check_items:
            # 根据 item_id 找到对应的模板数据
            template_item = find_template_item(new_template_data, check_item.item_id)
            
            if template_item:
                item_updated = False
                changes = []
                
                # 更新名称
                new_name = template_item.get('item_name')
                if new_name and new_name != check_item.item_name:
                    old_name = check_item.item_name
                    check_item.item_name = new_name
                    item_updated = True
                    changes.append(f"名称: {old_name} -> {new_name}")
                
                # 更新描述
                new_desc = template_item.get('description')
                if new_desc != check_item.description:
                    check_item.description = new_desc
                    item_updated = True
                    changes.append("描述已更新")
                
                # 更新字段配置（非结构性部分）
                if template_item.get('fields') and check_item.fields:
                    new_fields = update_field_configs(
                        check_item.fields,
                        template_item.get('fields')
                    )
                    if new_fields != check_item.fields:
                        check_item.fields = new_fields
                        item_updated = True
                        changes.append("字段配置已更新")
                
                if item_updated:
                    check_item.updated_at = datetime.utcnow()
                    updated_count += 1
                    print(f"[级联更新] 更新检查项 {check_item.id} ({check_item.item_id}): {', '.join(changes)}")
            else:
                print(f"[级联更新] 警告：未找到检查项 {check_item.item_id} 对应的模板数据")
    
    # 提交所有更改
    db.commit()
    
    print(f"[级联更新] 完成，共更新 {updated_count} 个检查项")
    
    return updated_count


def find_template_item(template_data: Dict, item_id: str) -> Optional[Dict]:
    """
    在模板数据中查找指定的检查项
    
    Args:
        template_data: 模板数据
        item_id: 检查项ID
    
    Returns:
        检查项数据，如果未找到则返回 None
    """
    
    for category in template_data.get('check_categories', []):
        for item in category.get('items', []):
            # 支持完整匹配和前缀匹配（兼容小区级检查项）
            template_item_id = item.get('item_id')
            
            if template_item_id == item_id:
                return item
            
            # 小区级检查项匹配：item_id 可能是 "xxx_cell_1_n41" 形式
            # 模板中存储的是基础 item_id "xxx"
            if item_id.startswith(template_item_id + '_cell_'):
                return item
    
    return None


def update_field_configs(old_fields: List[Dict], new_fields: List[Dict]) -> List[Dict]:
    """
    更新字段配置（仅非结构性部分）
    
    Args:
        old_fields: 旧字段配置列表
        new_fields: 新字段配置列表
    
    Returns:
        更新后的字段配置列表
    """
    
    updated_fields = []
    
    for old_field in old_fields:
        field_id = old_field.get('field_id')
        
        # 找到对应的新字段配置
        new_field = next((f for f in new_fields if f.get('field_id') == field_id), None)
        
        if new_field:
            # 创建更新后的字段配置（深拷贝）
            updated_field = old_field.copy()
            
            # 更新非结构性字段
            if 'label' in new_field:
                updated_field['label'] = new_field['label']
            
            if 'placeholder' in new_field:
                updated_field['placeholder'] = new_field['placeholder']
            
            if 'constraints' in new_field:
                updated_field['constraints'] = new_field['constraints']
            
            if 'options' in new_field:
                updated_field['options'] = new_field['options']
            
            if 'default_value' in new_field:
                updated_field['default_value'] = new_field['default_value']

            # 字段级照片配置（非结构性变更）
            if 'allow_photo' in new_field:
                updated_field['allow_photo'] = bool(new_field.get('allow_photo'))
                # 禁止拍照时，必拍也应一并关闭
                if not updated_field['allow_photo']:
                    updated_field['photo_required'] = False

            if 'photo_required' in new_field:
                # 仅在允许拍照时才允许必拍
                updated_field['photo_required'] = bool(new_field.get('photo_required')) if bool(updated_field.get('allow_photo')) else False
            
            # required 从 true 改为 false 允许（放宽限制）
            old_required = old_field.get('required', False)
            new_required = new_field.get('required', False)
            if old_required and not new_required:
                updated_field['required'] = False
            
            # 不更新结构性字段：
            # - type (字段类型)
            # - field_id (字段ID)
            # - required (false -> true 的情况)
            
            updated_fields.append(updated_field)
        else:
            # 字段未找到，保留原字段（不应该发生，但防御性编程）
            updated_fields.append(old_field)
    
    return updated_fields


def get_affected_inspections_count(db: Session, template_id: str) -> Dict:
    """
    获取受影响的检查记录统计
    
    Args:
        db: 数据库会话
        template_id: 模板ID
    
    Returns:
        统计信息字典
    """
    
    from app.models.inspection import InspectionStatusEnum
    
    total = db.query(SiteInspection).filter(
        SiteInspection.template_id == template_id
    ).count()
    
    active = db.query(SiteInspection).filter(
        SiteInspection.template_id == template_id,
        SiteInspection.status.in_([
            InspectionStatusEnum.DRAFT,
            InspectionStatusEnum.IN_PROGRESS,
            InspectionStatusEnum.SUBMITTED,
            InspectionStatusEnum.UNDER_REVIEW
        ])
    ).count()
    
    completed = total - active
    
    return {
        'total': total,
        'active': active,
        'completed': completed
    }
