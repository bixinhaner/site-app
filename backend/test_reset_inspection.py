#!/usr/bin/env python3
"""
测试重置被驳回任务的检查记录功能
"""

import requests

def test_reset_inspection():
    base_url = "http://192.168.31.101:8000"
    
    # 1. Tom登录
    print("Step 1: Tom登录...")
    login_data = {
        "username": "tom",
        "password": "tom123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print("❌ Tom登录失败")
        return
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    print("✅ Tom登录成功")
    
    # 2. 查找深圳南山任务
    print("\nStep 2: 查找深圳南山任务...")
    response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        shenzhen_task = None
        
        for task in tasks:
            site_name = task.get('site_name', '')
            if "深圳" in site_name or "南山" in site_name:
                shenzhen_task = task
                break
        
        if not shenzhen_task:
            print("❌ 未找到深圳南山任务")
            return
        
        task_id = shenzhen_task["id"]
        print(f"✅ 找到深圳南山任务: {shenzhen_task['task_title']}")
        print(f"   任务状态: {shenzhen_task['status']}")
        
        # 3. 获取检查记录
        print(f"\nStep 3: 获取检查记录...")
        response = requests.get(f"{base_url}/api/inspections/?task_id={task_id}", headers=headers)
        if response.status_code == 200:
            inspections = response.json()
            if not inspections:
                print("❌ 没有找到检查记录")
                return
            
            inspection = inspections[0]
            inspection_id = inspection['id']
            
            print(f"✅ 找到检查记录:")
            print(f"   检查记录ID: {inspection_id}")
            print(f"   检查状态: {inspection['status']}")
            print(f"   完成率: {inspection.get('completion_rate', 0)}%")
            
            # 4. 尝试重置检查记录
            print(f"\nStep 4: 重置检查记录...")
            response = requests.post(
                f"{base_url}/api/inspections/detail/{inspection_id}/reset",
                headers=headers
            )
            
            if response.status_code == 200:
                result = response.json()
                print("✅ 检查记录重置成功")
                print(f"   消息: {result['message']}")
                
                # 验证重置结果
                updated_inspection = result.get('inspection')
                if updated_inspection:
                    print(f"   新状态: {updated_inspection['status']}")
                    print(f"   新完成率: {updated_inspection.get('completion_rate', 0)}%")
                
                # 5. 查看检查项状态
                print(f"\nStep 5: 查看检查项状态...")
                response = requests.get(
                    f"{base_url}/api/inspections/detail/{inspection_id}/items",
                    headers=headers
                )
                
                if response.status_code == 200:
                    items = response.json()
                    print(f"✅ 检查项状态:")
                    for item in items:
                        print(f"   - {item['item_name']}: {item['status']}")
                        
                    pending_count = len([item for item in items if item['status'] == 'pending'])
                    print(f"   待处理检查项: {pending_count}/{len(items)}")
                    
            else:
                print(f"❌ 重置检查记录失败: {response.status_code}")
                if response.text:
                    print(f"   错误: {response.text}")
                    
        else:
            print(f"❌ 获取检查记录失败: {response.status_code}")
    else:
        print(f"❌ 获取任务失败: {response.status_code}")

if __name__ == "__main__":
    test_reset_inspection()