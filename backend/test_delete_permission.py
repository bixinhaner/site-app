#!/usr/bin/env python3
"""
测试删除任务的权限控制
"""

import requests

def test_delete_permission():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 使用Tom用户（inspector角色）登录
    print("正在使用Tom用户登录...")
    login_data = {
        "username": "tom",
        "password": "tom123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    print(f"登录响应状态: {response.status_code}")
    
    if response.status_code != 200:
        print("登录失败，无法继续测试")
        return
    
    login_result = response.json()
    access_token = login_result.get("access_token")
    user_info = login_result.get("user")
    print(f"用户角色: {user_info.get('role')}")
    
    # 2. 先获取管理员创建的任务ID
    print("\n使用管理员获取任务列表...")
    admin_login = requests.post(f"{base_url}/api/auth/login", json={"username": "admin", "password": "admin123"})
    admin_token = admin_login.json().get("access_token")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    tasks_response = requests.get(f"{base_url}/api/tasks/?skip=0&limit=20", headers=admin_headers)
    tasks = tasks_response.json()
    
    if tasks:
        task_id = tasks[0]["id"]
        print(f"选择任务ID: {task_id}")
        
        # 3. 尝试使用Tom用户删除任务
        print(f"\n尝试使用Tom用户删除任务...")
        headers = {"Authorization": f"Bearer {access_token}"}
        
        response = requests.delete(f"{base_url}/api/tasks/{task_id}", headers=headers)
        print(f"删除响应状态: {response.status_code}")
        print(f"删除响应内容: {response.text}")
        
        if response.status_code == 403:
            result = response.json()
            print(f"✅ 权限控制正常: {result.get('detail')}")
        else:
            print("❌ 权限控制有问题")
    else:
        print("没有任务可测试")

if __name__ == "__main__":
    test_delete_permission()