#!/usr/bin/env python3
"""
检查已提交的任务，供管理员审核
"""

import requests

def check_submitted_tasks():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 管理员登录
    print("Step 1: 管理员登录...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print("❌ 管理员登录失败")
        return
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    print("✅ 管理员登录成功")
    
    # 2. 获取所有已提交的任务
    print("\nStep 2: 查看所有已提交的任务...")
    response = requests.get(f"{base_url}/api/tasks/?status=submitted", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        print(f"✅ 找到 {len(tasks)} 个已提交的任务")
        
        for i, task in enumerate(tasks, 1):
            print(f"\n--- 任务 {i} ---")
            print(f"ID: {task['id']}")
            print(f"标题: {task['task_title']}")
            print(f"类型: {task['task_type']}")
            print(f"站点: {task.get('site_name', '未知站点')}")
            print(f"分配给: {task.get('assignee_name', '未知')}")
            print(f"状态: {task['status']}")
            print(f"创建时间: {task['created_at']}")
            
            # 获取关联的检查记录
            task_id = task['id']
            insp_response = requests.get(f"{base_url}/api/inspections/?task_id={task_id}", headers=headers)
            if insp_response.status_code == 200:
                inspections = insp_response.json()
                print(f"关联检查记录: {len(inspections)} 条")
                for j, inspection in enumerate(inspections):
                    print(f"  检查记录 {j+1}: {inspection.get('inspection_type', 'unknown')} - {inspection.get('status', 'unknown')}")
                    if inspection.get('completion_rate'):
                        print(f"    完成率: {inspection['completion_rate']}%")
            else:
                print("关联检查记录: 查询失败")
                
        return tasks
    else:
        print(f"❌ 获取任务失败: {response.status_code}")
        return []

if __name__ == "__main__":
    check_submitted_tasks()