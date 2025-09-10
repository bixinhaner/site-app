#!/usr/bin/env python3
"""
检查Tom的深圳南山任务状态
"""

import requests

def check_shenzhen_task():
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
    
    # 2. 获取Tom的所有任务，寻找深圳南山任务
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
            print("Tom的所有任务:")
            for task in tasks:
                print(f"  - {task.get('site_name', '未知站点')}: {task['task_title']} ({task['status']})")
            return
        
        task_id = shenzhen_task["id"]
        print(f"✅ 找到深圳南山任务:")
        print(f"   任务ID: {task_id}")
        print(f"   标题: {shenzhen_task['task_title']}")
        print(f"   状态: {shenzhen_task['status']}")
        print(f"   站点: {shenzhen_task['site_name']}")
        print(f"   创建时间: {shenzhen_task['created_at']}")
        
        # 3. 查看该任务的详细信息
        print(f"\nStep 3: 查看任务详细信息...")
        response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=headers)
        if response.status_code == 200:
            task_detail = response.json()
            print("✅ 任务详细信息:")
            for key, value in task_detail.items():
                if key not in ['id', 'task_title', 'status', 'site_name', 'created_at']:
                    print(f"   {key}: {value}")
        else:
            print(f"❌ 获取任务详情失败: {response.status_code}")
        
        # 4. 查看关联的检查记录
        print(f"\nStep 4: 查看检查记录...")
        response = requests.get(f"{base_url}/api/inspections/?task_id={task_id}", headers=headers)
        if response.status_code == 200:
            inspections = response.json()
            print(f"✅ 找到 {len(inspections)} 条检查记录:")
            
            for i, inspection in enumerate(inspections, 1):
                print(f"\n--- 检查记录 {i} ---")
                print(f"ID: {inspection['id']}")
                print(f"类型: {inspection.get('inspection_type', 'unknown')}")
                print(f"状态: {inspection.get('status', 'unknown')}")
                print(f"完成率: {inspection.get('completion_rate', 0)}%")
                print(f"开始时间: {inspection.get('start_time', 'N/A')}")
                print(f"结束时间: {inspection.get('end_time', 'N/A')}")
                
                # 获取检查项
                inspection_id = inspection['id']
                items_response = requests.get(
                    f"{base_url}/api/inspections/detail/{inspection_id}/items",
                    headers=headers
                )
                if items_response.status_code == 200:
                    check_items = items_response.json()
                    print(f"检查项: {len(check_items)} 项")
                    for j, item in enumerate(check_items[:3]):  # 只显示前3项
                        print(f"  {j+1}. {item['item_name']} - {item['status']}")
                    if len(check_items) > 3:
                        print(f"  ... 还有 {len(check_items)-3} 项")
                else:
                    print(f"检查项查询失败: {items_response.status_code}")
                    
        else:
            print(f"❌ 获取检查记录失败: {response.status_code}")
            
        return shenzhen_task
    else:
        print(f"❌ 获取任务失败: {response.status_code}")
        return None

if __name__ == "__main__":
    check_shenzhen_task()