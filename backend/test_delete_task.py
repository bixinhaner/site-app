#!/usr/bin/env python3
"""
测试删除任务API
"""

import requests
import json

def test_delete_task():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 登录管理员账户
    print("正在登录管理员账户...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    print(f"登录响应状态: {response.status_code}")
    
    if response.status_code != 200:
        print("登录失败，无法继续测试")
        return
    
    login_result = response.json()
    access_token = login_result.get("access_token")
    
    # 2. 获取任务列表
    print("\n正在获取任务列表...")
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }
    
    response = requests.get(f"{base_url}/api/tasks/?skip=0&limit=20", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        print(f"获取到 {len(tasks)} 个任务")
        
        if tasks:
            # 选择第一个任务进行删除测试
            task_to_delete = tasks[0]
            task_id = task_to_delete["id"]
            task_title = task_to_delete["task_title"]
            task_status = task_to_delete["status"]
            
            print(f"\n准备删除任务:")
            print(f"  ID: {task_id}")
            print(f"  标题: {task_title}")
            print(f"  状态: {task_status}")
            
            # 3. 删除任务
            print(f"\n正在删除任务 {task_id}...")
            response = requests.delete(f"{base_url}/api/tasks/{task_id}", headers=headers)
            print(f"删除响应状态: {response.status_code}")
            print(f"删除响应内容: {response.text}")
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ 删除成功: {result.get('message')}")
                
                # 4. 验证任务已被删除
                print(f"\n验证任务是否已被删除...")
                response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=headers)
                if response.status_code == 404:
                    print("✅ 验证成功：任务已被删除")
                else:
                    print("❌ 验证失败：任务仍然存在")
            else:
                error_detail = response.json().get('detail') if response.status_code != 500 else response.text
                print(f"❌ 删除失败: {error_detail}")
        else:
            print("没有任务可以删除")
    else:
        print(f"获取任务列表失败: {response.text}")

if __name__ == "__main__":
    test_delete_task()