#!/usr/bin/env python3
"""
修复检查项，使其与模板一致
"""

import requests
import uuid

def fix_inspection_items():
    base_url = "http://localhost:8000"
    
    # 1. Admin登录获取token
    print("Step 1: Admin登录...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print("❌ Admin登录失败")
        return
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    print("✅ Admin登录成功")
    
    # 2. 获取检查记录和模板
    inspection_id = "8553c0aa-69f1-45e6-9dbc-1a1c94b9f25b"
    template_id = "266d3253-13d8-46af-9fd3-f417566428cf"
    
    print(f"\nStep 2: 获取模板 {template_id}...")
    response = requests.get(f"{base_url}/api/inspections/templates/{template_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ 获取模板失败: {response.status_code}")
        return
    
    template = response.json()
    template_data = template.get("template_data", {})
    print("✅ 模板获取成功")
    
    # 3. 使用数据库直接操作
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from app.core.database import get_db
    from app.models.inspection import InspectionCheckItem, CheckItemStatusEnum, SiteInspection
    from sqlalchemy.orm import Session
    
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # 4. 删除现有的错误检查项
        print("\nStep 3: 删除现有检查项...")
        existing_items = db.query(InspectionCheckItem).filter(
            InspectionCheckItem.inspection_id == inspection_id
        ).all()
        
        for item in existing_items:
            db.delete(item)
        print(f"✅ 删除了 {len(existing_items)} 个旧检查项")
        
        # 5. 根据真实模板创建检查项
        print("\nStep 4: 根据模板创建正确的检查项...")
        total_items = 0
        
        for category in template_data.get("check_categories", []):
            for item in category.get("items", []):
                # 如果是扇区级检查，为每个扇区创建检查项
                if category.get("sector_specific", False):
                    # 假设3个扇区
                    for sector_num in range(1, 4):
                        check_item = InspectionCheckItem(
                            id=str(uuid.uuid4()),
                            inspection_id=inspection_id,
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
                        print(f"  ✓ 创建扇区{sector_num}检查项: {item['item_name']}")
                else:
                    # 站点级检查项
                    check_item = InspectionCheckItem(
                        id=str(uuid.uuid4()),
                        inspection_id=inspection_id,
                        item_id=item["item_id"],
                        item_name=item["item_name"],
                        category_id=category["category_id"],
                        category_name=category["category_name"],
                        required_type=item["required_type"],
                        status=CheckItemStatusEnum.PENDING
                    )
                    db.add(check_item)
                    total_items += 1
                    print(f"  ✓ 创建站点检查项: {item['item_name']}")
        
        # 6. 更新检查记录的总检查项数
        inspection_record = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
        if inspection_record:
            inspection_record.total_items = total_items
            inspection_record.completed_items = 0
            inspection_record.failed_items = 0
            inspection_record.completion_rate = 0.0
        
        db.commit()
        print(f"✅ 成功创建 {total_items} 个检查项")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 操作失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    # 7. 验证结果
    print("\nStep 5: 验证结果...")
    response = requests.get(f"{base_url}/api/inspections/detail/{inspection_id}/items", headers=headers)
    if response.status_code == 200:
        items = response.json()
        print(f"✅ 检查记录现在有 {len(items)} 个检查项（与模板一致）")
        for i, item in enumerate(items, 1):
            sector_info = f" - 扇区{item['sector_id']}" if item.get('sector_id') else ""
            print(f"  {i}. {item['item_name']}{sector_info} ({item['required_type']}) - {item['status']}")
    else:
        print(f"❌ 验证失败: {response.status_code}")

if __name__ == "__main__":
    fix_inspection_items()