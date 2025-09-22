#!/usr/bin/env python3
"""
为现有的空检查记录补充检查项
"""

import requests
import uuid

def populate_inspection_items():
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
    
    # 2. 获取需要处理的检查记录
    inspection_id = "8553c0aa-69f1-45e6-9dbc-1a1c94b9f25b"
    print(f"\nStep 2: 检查记录 {inspection_id}...")
    
    # 检查是否已有检查项
    response = requests.get(f"{base_url}/api/inspections/detail/{inspection_id}/items", headers=headers)
    if response.status_code == 200:
        items = response.json()
        if len(items) > 0:
            print(f"✅ 检查记录已有 {len(items)} 个检查项，无需处理")
            return
        else:
            print("📝 检查记录没有检查项，需要创建")
    else:
        print(f"❌ 获取检查项失败: {response.status_code}")
        return
    
    # 3. 获取检查记录详情
    response = requests.get(f"{base_url}/api/inspections/detail/{inspection_id}", headers=headers)
    if response.status_code != 200:
        print(f"❌ 获取检查详情失败: {response.status_code}")
        return
    
    inspection = response.json()
    template_id = inspection.get("template_id")
    print(f"✅ 检查记录使用模板: {template_id}")
    
    # 4. 直接创建基本检查项（简化版本）
    print("\nStep 3: 创建基本检查项...")
    
    basic_items = [
        {
            "item_id": "site_basic_001",
            "item_name": "站点环境检查",
            "category_id": "basic",
            "category_name": "基础检查",
            "required_type": "VISUAL"
        },
        {
            "item_id": "equipment_001", 
            "item_name": "设备状态检查",
            "category_id": "equipment",
            "category_name": "设备检查", 
            "required_type": "VISUAL"
        },
        {
            "item_id": "antenna_001",
            "item_name": "天线安装检查",
            "category_id": "antenna",
            "category_name": "天线检查",
            "required_type": "MEASUREMENT"
        }
    ]
    
    # 为3个扇区创建天线检查项
    for sector in range(1, 4):
        basic_items.append({
            "item_id": f"antenna_sector_{sector}",
            "item_name": f"扇区{sector}天线参数检查", 
            "category_id": "antenna",
            "category_name": "天线检查",
            "required_type": "MEASUREMENT",
            "sector_id": str(sector)
        })
    
    # 5. 通过数据库直接插入（使用FastAPI的数据库连接）
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    
    from app.core.database import get_db
    from app.models.inspection import InspectionCheckItem, CheckItemStatusEnum
    from sqlalchemy.orm import Session
    
    # 获取数据库会话
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        created_count = 0
        for item_data in basic_items:
            check_item = InspectionCheckItem(
                id=str(uuid.uuid4()),
                inspection_id=inspection_id,
                item_id=item_data["item_id"],
                item_name=item_data["item_name"],
                category_id=item_data["category_id"],
                category_name=item_data["category_name"],
                sector_id=item_data.get("sector_id"),
                required_type=item_data["required_type"],
                status=CheckItemStatusEnum.PENDING
            )
            db.add(check_item)
            created_count += 1
        
        # 更新检查记录的总检查项数
        from app.models.inspection import SiteInspection
        inspection_record = db.query(SiteInspection).filter(SiteInspection.id == inspection_id).first()
        if inspection_record:
            inspection_record.total_items = created_count
        
        db.commit()
        print(f"✅ 成功创建 {created_count} 个检查项")
        
    except Exception as e:
        db.rollback()
        print(f"❌ 创建检查项失败: {e}")
    finally:
        db.close()
    
    # 6. 验证结果
    print("\nStep 4: 验证结果...")
    response = requests.get(f"{base_url}/api/inspections/detail/{inspection_id}/items", headers=headers)
    if response.status_code == 200:
        items = response.json()
        print(f"✅ 检查记录现在有 {len(items)} 个检查项")
        for i, item in enumerate(items[:3], 1):
            print(f"  {i}. {item['item_name']} - {item['status']}")
        if len(items) > 3:
            print(f"  ... 还有 {len(items)-3} 个检查项")
    else:
        print(f"❌ 验证失败: {response.status_code}")

if __name__ == "__main__":
    populate_inspection_items()