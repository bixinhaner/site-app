"""
更新检查项的description字段
从检查记录关联的模板中读取description，更新到检查项
"""

from app.core.database import SessionLocal
from app.models.inspection import SiteInspection, InspectionCheckItem, InspectionTemplate

def update_inspection_descriptions(inspection_id: str = None):
    """
    更新检查项的description字段
    
    Args:
        inspection_id: 指定检查记录ID，如果不指定则更新所有description为None的检查项
    """
    db = SessionLocal()
    
    try:
        # 查询需要更新的检查记录
        if inspection_id:
            inspections = db.query(SiteInspection).filter(
                SiteInspection.id == inspection_id
            ).all()
        else:
            # 查询所有有检查项description为None的检查记录
            inspections = db.query(SiteInspection).join(
                InspectionCheckItem,
                SiteInspection.id == InspectionCheckItem.inspection_id
            ).filter(
                InspectionCheckItem.description.is_(None)
            ).distinct().all()
        
        print(f'找到 {len(inspections)} 个需要更新的检查记录')
        
        updated_count = 0
        
        for inspection in inspections:
            print(f'\n处理检查记录: {inspection.id}')
            print(f'  站点: {inspection.site.site_name if inspection.site else "未知"}')
            print(f'  模板ID: {inspection.template_id}')
            
            # 获取模板
            template = db.query(InspectionTemplate).filter(
                InspectionTemplate.id == inspection.template_id
            ).first()
            
            if not template:
                print(f'  ⚠️  未找到模板')
                continue
            
            template_data = template.template_data
            
            # 构建item_id到description的映射
            description_map = {}
            
            for category in template_data.get('check_categories', []):
                for item in category.get('items', []):
                    item_id = item.get('item_id')
                    description = item.get('description', '')
                    if item_id and description:
                        description_map[item_id] = description
            
            print(f'  模板中有 {len(description_map)} 个检查项包含描述')
            
            # 更新检查项
            check_items = db.query(InspectionCheckItem).filter(
                InspectionCheckItem.inspection_id == inspection.id,
                InspectionCheckItem.description.is_(None)
            ).all()
            
            items_updated = 0
            for check_item in check_items:
                # 尝试从item_id中提取原始的item_id
                # 格式可能是: "item_xxx" 或 "item_xxx_cell_1_n41" 或 "item_xxx_sector_1"
                original_item_id = check_item.item_id
                
                # 移除后缀
                if '_cell_' in original_item_id:
                    original_item_id = original_item_id.split('_cell_')[0]
                elif '_sector_' in original_item_id:
                    original_item_id = original_item_id.split('_sector_')[0]
                
                # 查找描述
                description = description_map.get(original_item_id)
                
                if description:
                    check_item.description = description
                    items_updated += 1
                    print(f'    ✅ 更新: {check_item.item_name} -> "{description[:30]}..."')
            
            if items_updated > 0:
                db.commit()
                updated_count += items_updated
                print(f'  已更新 {items_updated} 个检查项')
            else:
                print(f'  无需更新')
        
        print(f'\n总计更新了 {updated_count} 个检查项')
        return updated_count
        
    except Exception as e:
        db.rollback()
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    import sys
    
    # 从命令行参数获取inspection_id
    inspection_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if inspection_id:
        print(f'更新指定检查记录: {inspection_id}')
    else:
        print('更新所有description为None的检查项')
    
    count = update_inspection_descriptions(inspection_id)
    print(f'\n完成！共更新 {count} 个检查项')
