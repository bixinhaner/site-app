#!/usr/bin/env python3
"""
更新现有检查项的description字段
从对应的模板中提取description信息并填充到已有的检查项中
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import json
from sqlalchemy import create_engine, text
from app.core.config import settings

def update_check_items_description():
    """更新现有检查项的description"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # 1. 获取所有检查记录及其对应的模板
            query_inspections = text("""
                SELECT 
                    si.id as inspection_id,
                    si.template_id,
                    it.template_data
                FROM site_inspections si
                JOIN inspection_templates it ON si.template_id = it.id
            """)
            
            inspections = conn.execute(query_inspections).fetchall()
            
            if not inspections:
                print("没有找到检查记录")
                return True
            
            print(f"找到 {len(inspections)} 个检查记录")
            
            total_updated = 0
            
            # 2. 遍历每个检查记录
            for inspection in inspections:
                inspection_id = inspection[0]
                template_id = inspection[1]
                template_data_str = inspection[2]
                
                try:
                    template_data = json.loads(template_data_str)
                except:
                    print(f"⚠️  检查 {inspection_id} 的模板数据解析失败")
                    continue
                
                print(f"\n处理检查记录: {inspection_id}")
                
                # 3. 构建item_id到description的映射
                item_descriptions = {}
                
                check_categories = template_data.get('check_categories', [])
                for category in check_categories:
                    items = category.get('items', [])
                    for item in items:
                        item_id = item.get('item_id', '')
                        description = item.get('description', '')
                        if item_id and description:
                            item_descriptions[item_id] = description
                
                print(f"  从模板中提取了 {len(item_descriptions)} 个检查项描述")
                
                # 4. 获取该检查记录的所有检查项
                query_items = text("""
                    SELECT id, item_id
                    FROM inspection_check_items
                    WHERE inspection_id = :inspection_id
                """)
                
                check_items = conn.execute(
                    query_items,
                    {"inspection_id": inspection_id}
                ).fetchall()
                
                print(f"  找到 {len(check_items)} 个检查项")
                
                # 5. 更新每个检查项的description
                updated_count = 0
                for check_item in check_items:
                    item_db_id = check_item[0]
                    item_id = check_item[1]
                    
                    # 提取基础item_id（去除_cell_xxx或_sector_xxx后缀）
                    base_item_id = item_id
                    if '_cell_' in item_id:
                        base_item_id = item_id.split('_cell_')[0]
                    elif '_sector_' in item_id:
                        base_item_id = item_id.split('_sector_')[0]
                    
                    # 查找对应的description
                    description = item_descriptions.get(base_item_id, '')
                    
                    if description:
                        update_sql = text("""
                            UPDATE inspection_check_items
                            SET description = :description
                            WHERE id = :id
                        """)
                        
                        conn.execute(
                            update_sql,
                            {
                                "description": description,
                                "id": item_db_id
                            }
                        )
                        updated_count += 1
                
                conn.commit()
                print(f"  ✅ 更新了 {updated_count} 个检查项的描述")
                total_updated += updated_count
            
            print(f"\n总计更新了 {total_updated} 个检查项的描述")
            return True
            
    except Exception as e:
        print(f"❌ 更新失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("开始更新现有检查项的描述信息...")
    success = update_check_items_description()
    
    if success:
        print("\n✅ 更新完成！")
        print("现在app端应该能看到检查项的描述信息了")
    else:
        print("\n❌ 更新失败！")
        sys.exit(1)
