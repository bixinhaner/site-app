#!/usr/bin/env python3
"""
测试页面加载功能是否正常
"""

import requests

def test_page_loading():
    base_url = "http://192.168.31.101:8000"
    
    print("=== 页面加载测试 ===\n")
    
    # 1. Tom登录
    print("Step 1: Tom登录...")
    tom_login_data = {
        "username": "tom",
        "password": "tom123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=tom_login_data)
    if response.status_code != 200:
        print("❌ Tom登录失败")
        return
    
    tom_token = response.json().get("access_token")
    tom_headers = {"Authorization": f"Bearer {tom_token}"}
    print("✅ Tom登录成功")
    
    # 2. 测试任务列表API
    print("\nStep 2: 测试任务列表API...")
    response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=tom_headers)
    if response.status_code == 200:
        tasks = response.json()
        print(f"✅ 任务列表加载成功，共 {len(tasks)} 个任务")
        
        for task in tasks[:3]:  # 显示前3个任务
            print(f"   - {task['task_title']} ({task['status']})")
    else:
        print(f"❌ 任务列表加载失败: {response.status_code}")
        return
    
    # 3. 测试任务详情API
    if tasks:
        print(f"\nStep 3: 测试任务详情API...")
        first_task_id = tasks[0]['id']
        response = requests.get(f"{base_url}/api/tasks/{first_task_id}", headers=tom_headers)
        if response.status_code == 200:
            task_detail = response.json()
            print(f"✅ 任务详情加载成功")
            print(f"   任务ID: {task_detail['id']}")
            print(f"   标题: {task_detail['task_title']}")
            print(f"   状态: {task_detail['status']}")
            print(f"   站点: {task_detail.get('site_name', '未知')}")
        else:
            print(f"❌ 任务详情加载失败: {response.status_code}")
    
    # 4. 测试用户信息API
    print(f"\nStep 4: 测试用户信息API...")
    response = requests.get(f"{base_url}/api/users/me", headers=tom_headers)
    if response.status_code == 200:
        user_info = response.json()
        print(f"✅ 用户信息加载成功")
        print(f"   用户名: {user_info['username']}")
        print(f"   角色: {user_info['role']}")
        print(f"   姓名: {user_info.get('full_name', '未设置')}")
    else:
        print(f"❌ 用户信息加载失败: {response.status_code}")
    
    print(f"\n🎉 API测试完成！前端页面应该能正常显示数据")
    print("现在可以尝试访问前端任务列表页面了")

if __name__ == "__main__":
    test_page_loading()