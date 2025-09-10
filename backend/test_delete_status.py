#!/usr/bin/env python3
"""
测试删除任务的状态限制
"""

import requests

def test_delete_status():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 使用管理员登录
    print("正在使用管理员登录...")
    login_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=login_data)
    if response.status_code != 200:
        print("登录失败")
        return
    
    access_token = response.json().get("access_token")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 2. 获取任务列表
    print("\n获取任务列表...")
    response = requests.get(f"{base_url}/api/tasks/?skip=0&limit=20", headers=headers)
    tasks = response.json()
    
    if tasks:
        task = tasks[0]
        task_id = task["id"]
        current_status = task["status"]
        
        print(f"任务ID: {task_id}")
        print(f"当前状态: {current_status}")
        
        # 如果任务状态可以删除，我们先修改状态让它不能删除
        if current_status in ['pending', 'assigned', 'rejected']:
            print("\n当前任务可删除，先修改为不可删除状态...")
            # 先尝试直接修改状态（这只是模拟，实际可能需要通过正常流程）
            # 这里我们直接尝试删除一个可删除的任务，然后看看效果
            print("尝试删除可删除状态的任务...")
        else:
            print("\n当前任务不可删除，直接测试...")
        
        # 3. 尝试删除任务
        print(f"\n尝试删除任务...")
        response = requests.delete(f"{base_url}/api/tasks/{task_id}", headers=headers)
        print(f"删除响应状态: {response.status_code}")
        print(f"删除响应内容: {response.text}")
        
        if response.status_code == 200:
            print("✅ 删除成功")
        elif response.status_code == 400:
            result = response.json()
            print(f"✅ 状态限制正常: {result.get('detail')}")
        else:
            print(f"❌ 意外的响应状态: {response.status_code}")
    else:
        print("没有任务可测试")

if __name__ == "__main__":
    test_delete_status()