"""
模板变更验证器
用于验证模板更新时是否包含禁止的结构性变更
"""

from typing import Dict, List, Optional


def validate_template_changes(old_data: Dict, new_data: Dict) -> Dict:
    """
    后端验证：确保没有禁止的结构性变更
    这是防止前端绕过的最后防线
    
    Args:
        old_data: 旧模板数据
        new_data: 新模板数据
    
    Returns:
        验证结果字典，包含 valid 和 violations
    """
    
    violations = []
    
    old_categories = {cat['category_id']: cat for cat in old_data.get('check_categories', [])}
    new_categories = {cat['category_id']: cat for cat in new_data.get('check_categories', [])}
    
    # 1. 检查分类结构
    for cat_id in new_categories:
        if cat_id not in old_categories:
            violations.append(f"禁止添加新分类: {cat_id}")
    
    for cat_id in old_categories:
        if cat_id not in new_categories:
            violations.append(f"禁止删除分类: {cat_id}")
    
    # 2. 检查分类属性
    for cat_id in old_categories:
        if cat_id in new_categories:
            old_cat = old_categories[cat_id]
            new_cat = new_categories[cat_id]
            
            # sector_specific 变更是结构性的
            if old_cat.get('sector_specific') != new_cat.get('sector_specific'):
                violations.append(f"禁止修改分类的 sector_specific 属性: {cat_id}")
            
            # cell_specific 变更是结构性的
            if old_cat.get('cell_specific') != new_cat.get('cell_specific'):
                violations.append(f"禁止修改分类的 cell_specific 属性: {cat_id}")
            
            # 3. 检查检查项结构
            old_items = {item['item_id']: item for item in old_cat.get('items', [])}
            new_items = {item['item_id']: item for item in new_cat.get('items', [])}
            
            for item_id in new_items:
                if item_id not in old_items:
                    violations.append(f"禁止添加新检查项: {cat_id}.{item_id}")
            
            for item_id in old_items:
                if item_id not in new_items:
                    violations.append(f"禁止删除检查项: {cat_id}.{item_id}")
                else:
                    # 4. 检查检查项属性
                    old_item = old_items[item_id]
                    new_item = new_items[item_id]
                    
                    # required_type 变更是结构性的
                    if old_item.get('required_type') != new_item.get('required_type'):
                        violations.append(
                            f"禁止修改检查类型: {cat_id}.{item_id} "
                            f"({old_item.get('required_type')} -> {new_item.get('required_type')})"
                        )
                    
                    # 5. 检查字段结构
                    old_fields = {f['field_id']: f for f in old_item.get('fields', [])}
                    new_fields = {f['field_id']: f for f in new_item.get('fields', [])}
                    
                    for field_id in new_fields:
                        if field_id not in old_fields:
                            violations.append(f"禁止添加新字段: {cat_id}.{item_id}.{field_id}")
                    
                    for field_id in old_fields:
                        if field_id not in new_fields:
                            violations.append(f"禁止删除字段: {cat_id}.{item_id}.{field_id}")
                        else:
                            # 6. 检查字段属性
                            old_field = old_fields[field_id]
                            new_field = new_fields[field_id]
                            
                            # 字段类型变更是结构性的
                            if old_field.get('type') != new_field.get('type'):
                                violations.append(
                                    f"禁止修改字段类型: {cat_id}.{item_id}.{field_id} "
                                    f"({old_field.get('type')} -> {new_field.get('type')})"
                                )
                            
                            # required 从 false 改为 true 是结构性的
                            old_required = old_field.get('required', False)
                            new_required = new_field.get('required', False)
                            if not old_required and new_required:
                                violations.append(
                                    f"禁止将字段改为必填: {cat_id}.{item_id}.{field_id}"
                                )
    
    return {
        'valid': len(violations) == 0,
        'violations': violations
    }


def summarize_changes(old_data: Dict, new_data: Dict) -> Dict:
    """
    分析并总结模板变更内容（用于前端展示）
    
    Args:
        old_data: 旧模板数据
        new_data: 新模板数据
    
    Returns:
        变更摘要字典
    """
    
    summary = {
        'total_changes': 0,
        'modified_names': 0,
        'modified_descriptions': 0,
        'modified_labels': 0,
        'modified_constraints': 0,
        'modified_options': 0,
        'details': []
    }
    
    old_categories = {cat['category_id']: cat for cat in old_data.get('check_categories', [])}
    new_categories = {cat['category_id']: cat for cat in new_data.get('check_categories', [])}
    
    for cat_id in old_categories:
        if cat_id in new_categories:
            old_cat = old_categories[cat_id]
            new_cat = new_categories[cat_id]
            
            # 检查分类名称
            if old_cat.get('category_name') != new_cat.get('category_name'):
                summary['modified_names'] += 1
                summary['total_changes'] += 1
                summary['details'].append({
                    'type': 'category_name',
                    'path': f"{cat_id}",
                    'old': old_cat.get('category_name'),
                    'new': new_cat.get('category_name')
                })
            
            # 检查分类描述
            if old_cat.get('description') != new_cat.get('description'):
                summary['modified_descriptions'] += 1
                summary['total_changes'] += 1
                summary['details'].append({
                    'type': 'category_description',
                    'path': f"{cat_id}",
                    'old': old_cat.get('description'),
                    'new': new_cat.get('description')
                })
            
            # 检查检查项
            old_items = {item['item_id']: item for item in old_cat.get('items', [])}
            new_items = {item['item_id']: item for item in new_cat.get('items', [])}
            
            for item_id in old_items:
                if item_id in new_items:
                    old_item = old_items[item_id]
                    new_item = new_items[item_id]
                    
                    # 检查项名称
                    if old_item.get('item_name') != new_item.get('item_name'):
                        summary['modified_names'] += 1
                        summary['total_changes'] += 1
                        summary['details'].append({
                            'type': 'item_name',
                            'path': f"{cat_id}.{item_id}",
                            'old': old_item.get('item_name'),
                            'new': new_item.get('item_name')
                        })
                    
                    # 检查项描述
                    if old_item.get('description') != new_item.get('description'):
                        summary['modified_descriptions'] += 1
                        summary['total_changes'] += 1
                        summary['details'].append({
                            'type': 'item_description',
                            'path': f"{cat_id}.{item_id}",
                            'old': old_item.get('description'),
                            'new': new_item.get('description')
                        })
                    
                    # 检查字段
                    old_fields = {f['field_id']: f for f in old_item.get('fields', [])}
                    new_fields = {f['field_id']: f for f in new_item.get('fields', [])}
                    
                    for field_id in old_fields:
                        if field_id in new_fields:
                            old_field = old_fields[field_id]
                            new_field = new_fields[field_id]
                            
                            # 字段标签
                            if old_field.get('label') != new_field.get('label'):
                                summary['modified_labels'] += 1
                                summary['total_changes'] += 1
                                summary['details'].append({
                                    'type': 'field_label',
                                    'path': f"{cat_id}.{item_id}.{field_id}",
                                    'old': old_field.get('label'),
                                    'new': new_field.get('label')
                                })
                            
                            # 字段约束
                            if old_field.get('constraints') != new_field.get('constraints'):
                                summary['modified_constraints'] += 1
                                summary['total_changes'] += 1
                                summary['details'].append({
                                    'type': 'field_constraints',
                                    'path': f"{cat_id}.{item_id}.{field_id}",
                                    'old': old_field.get('constraints'),
                                    'new': new_field.get('constraints')
                                })
                            
                            # 字段选项
                            if old_field.get('options') != new_field.get('options'):
                                summary['modified_options'] += 1
                                summary['total_changes'] += 1
                                summary['details'].append({
                                    'type': 'field_options',
                                    'path': f"{cat_id}.{item_id}.{field_id}",
                                    'old': old_field.get('options'),
                                    'new': new_field.get('options')
                                })
    
    return summary
