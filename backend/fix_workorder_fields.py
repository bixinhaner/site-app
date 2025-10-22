"""
修复工单检查项的字段配置
从模板中读取fields配置并更新到检查项中
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.inspection import SiteInspection, InspectionCheckItem, InspectionTemplate

def fix_inspection_check_items(inspection_id: str):
    """修复指定检查记录的所有检查项字段配置"""
    db: Session = SessionLocal()
    
    try:
        # 获取检查记录
        inspection = db.query(SiteInspection).filter(
            SiteInspection.id == inspection_id
        ).first()
        
        if not inspection:
            print(f"❌ 检查记录不存在: {inspection_id}")
            return False
        
        print(f"✅ 找到检查记录: {inspection.id}")
        print(f"   模板ID: {inspection.template_id}")
        
        # 获取模板
        template = db.query(InspectionTemplate).filter(
            InspectionTemplate.id == inspection.template_id
        ).first()
        
        if not template:
            print(f"❌ 模板不存在: {inspection.template_id}")
            return False
        
        print(f"✅ 找到模板: {template.template_name}")
        
        # 构建模板检查项索引 (item_id -> item配置)
        template_items = {}
        for category in template.template_data.get("check_categories", []):
            for item in category.get("items", []):
                base_item_id = item.get("item_id")
                if base_item_id:
                    template_items[base_item_id] = item
        
        print(f"✅ 模板中有 {len(template_items)} 个检查项配置")
        
        # 获取所有检查项
        check_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).all()
        
        print(f"✅ 检查记录有 {len(check_items)} 个检查项")
        print()
        
        updated_count = 0
        skipped_count = 0
        
        for check_item in check_items:
            # 提取基础item_id（去掉_sector_X或_cell_X后缀）
            item_id = check_item.item_id
            base_item_id = item_id
            
            # 处理扇区级后缀
            if "_sector_" in item_id:
                base_item_id = item_id.split("_sector_")[0]
            # 处理小区级后缀
            elif "_cell_" in item_id:
                base_item_id = item_id.split("_cell_")[0]
            
            # 查找模板中的配置
            template_item = template_items.get(base_item_id)
            
            if not template_item:
                print(f"⚠️  未找到模板配置: {check_item.item_name} (item_id: {item_id})")
                skipped_count += 1
                continue
            
            # 获取字段配置
            fields = template_item.get("fields")
            description = template_item.get("description")
            
            if not fields:
                print(f"⚠️  模板中无字段配置: {check_item.item_name}")
                skipped_count += 1
                continue
            
            # 更新检查项
            check_item.fields = fields
            if description and not check_item.description:
                check_item.description = description
            
            print(f"✅ 更新: {check_item.item_name}")
            print(f"   - 字段数: {len(fields)}")
            for field in fields:
                field_type = field.get("type", "unknown")
                field_label = field.get("label", "unnamed")
                constraints = field.get("constraints", {})
                print(f"     • {field_label} ({field_type}) {constraints}")
            
            updated_count += 1
        
        # 提交更改
        db.commit()
        
        print()
        print("=" * 80)
        print(f"✅ 修复完成！")
        print(f"   更新: {updated_count} 个检查项")
        print(f"   跳过: {skipped_count} 个检查项")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        return False
        
    finally:
        db.close()


if __name__ == "__main__":
    # 修复指定的检查记录
    inspection_id = "733f29c3-b4d1-48bd-ace5-b0af7ed3d3a0"
    
    print("=" * 80)
    print("修复工单检查项字段配置")
    print("=" * 80)
    print(f"检查ID: {inspection_id}")
    print()
    
    success = fix_inspection_check_items(inspection_id)
    
    if success:
        print()
        print("✅ 修复成功！现在可以在App中正常填写字段了。")
        sys.exit(0)
    else:
        print()
        print("❌ 修复失败！")
        sys.exit(1)
