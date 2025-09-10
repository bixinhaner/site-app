#!/usr/bin/env python3
"""
测试任务API返回的数据
"""

import requests
import json

def test_task_api():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 登录管理员账户
    print("正在登录管理员账户...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    print(f"登录响应状态: {response.status_code}")
    print(f"登录响应内容: {response.text}")
    
    if response.status_code != 200:
        print("登录失败，无法继续测试")
        return
    
    login_result = response.json()
    access_token = login_result.get("access_token")
    
    if not access_token:
        print("未获取到access_token")
        return
    
    # 2. 获取任务列表
    print("\n正在获取任务列表...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{base_url}/api/tasks/?skip=0&limit=20", headers=headers)
    print(f"任务列表响应状态: {response.status_code}")
    
    if response.status_code == 200:
        tasks = response.json()
        print(f"\n获取到 {len(tasks)} 个任务:")
        for i, task in enumerate(tasks, 1):
            print(f"\n任务 {i}:")
            print(f"  ID: {task.get('id')}")
            print(f"  标题: {task.get('task_title')}")
            print(f"  站点ID: {task.get('site_id')}")
            print(f"  站点名称: {task.get('site_name', '未设置')}")
            print(f"  站点编码: {task.get('site_code', '未设置')}")
            print(f"  分配人: {task.get('assigner_name', '未设置')}")
            print(f"  被分配人: {task.get('assignee_name', '未设置')}")
            print(f"  状态: {task.get('status')}")
    else:
        print(f"获取任务列表失败: {response.text}")

if __name__ == "__main__":
    test_task_api()