#!/usr/bin/env python3
"""
检查Tom用户的任务状态
"""

import requests

def check_tom_task():
    base_url = "http://192.168.31.101:8000"
    
    # 使用Tom用户登录
    login_data = {
        "username": "tom",
        "password": "tom123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print("Tom登录失败")
        return
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 获取Tom的任务
    print("获取Tom的任务列表...")
    response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        print(f"Tom有 {len(tasks)} 个任务:")
        
        for task in tasks:
            print(f"\n任务详情:")
            print(f"  ID: {task['id']}")
            print(f"  标题: {task['task_title']}")
            print(f"  类型: {task['task_type']}")
            print(f"  状态: {task['status']}")
            print(f"  站点: {task.get('site_name', '未知')}")
            print(f"  创建时间: {task['created_at']}")
            if task.get('due_date'):
                print(f"  截止时间: {task['due_date']}")
                
            # 检查是否有相关检查记录
            print(f"\n检查该任务的检查记录...")
            insp_response = requests.get(f"{base_url}/api/inspections/?task_id={task['id']}", headers=headers)
            if insp_response.status_code == 200:
                inspections = insp_response.json()
                print(f"  检查记录: {len(inspections)} 条")
                for insp in inspections:
                    print(f"    - {insp.get('inspection_type', 'unknown')} ({insp.get('status', 'unknown')})")
            else:
                print(f"  检查记录查询失败: {insp_response.status_code}")
                
        return tasks
    else:
        print(f"获取任务失败: {response.status_code} - {response.text}")
        return []

if __name__ == "__main__":
    check_tom_task()