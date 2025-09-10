#!/usr/bin/env python3
"""
测试数据实时更新功能
模拟管理员审核任务，检查前端是否能实时更新状态
"""

import requests
import time

def test_data_refresh():
    base_url = "http://192.168.31.101:8000"
    
    print("=== 数据实时更新功能测试 ===\n")
    
    # 1. 管理员登录
    print("Step 1: 管理员登录...")
    admin_login_data = {
        "username": "admin",
        "password": "admin123456"
    }
    
    response = requests.post(f"{base_url}/api/auth/login", json=admin_login_data)
    if response.status_code != 200:
        print("❌ 管理员登录失败")
        return
    
    admin_token = response.json().get("access_token")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("✅ 管理员登录成功")
    
    # 2. Tom登录（用于验证数据更新）
    print("\nStep 2: Tom登录...")
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
    
    # 3. 获取待审核的任务
    print("\nStep 3: 查找待审核任务...")
    response = requests.get(f"{base_url}/api/tasks/", headers=admin_headers)
    if response.status_code == 200:
        tasks = response.json()
        submitted_task = None
        
        for task in tasks:
            if task.get('status') == 'submitted':
                submitted_task = task
                break
        
        if not submitted_task:
            print("❌ 没有找到待审核任务")
            print("提示：可以先让Tom提交一个任务供测试")
            return
        
        task_id = submitted_task["id"]
        print(f"✅ 找到待审核任务: {submitted_task['task_title']}")
        print(f"   任务ID: {task_id}")
        print(f"   当前状态: {submitted_task['status']}")
        
        # 4. Tom查询自己的任务状态（审核前）
        print(f"\nStep 4: Tom查询任务状态（审核前）...")
        response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=tom_headers)
        if response.status_code == 200:
            task_before = response.json()
            print(f"✅ Tom看到的任务状态: {task_before['status']}")
        
        # 5. 管理员审核任务（批准）
        print(f"\nStep 5: 管理员批准任务...")
        review_data = {
            "action": "approve",
            "comments": "测试批准：任务执行良好"
        }
        
        response = requests.post(
            f"{base_url}/api/tasks/{task_id}/review",
            json=review_data,
            headers=admin_headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 任务批准成功")
            print(f"   新状态: {result['status']}")
            print(f"   审核意见: {result.get('review_comments', '无')}")
            
            # 等待一秒让数据更新
            time.sleep(1)
            
            # 6. Tom再次查询任务状态（审核后）
            print(f"\nStep 6: Tom查询任务状态（审核后）...")
            response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=tom_headers)
            if response.status_code == 200:
                task_after = response.json()
                print(f"✅ Tom看到的任务状态: {task_after['status']}")
                
                if task_after['status'] != task_before['status']:
                    print("🎉 数据更新成功！前端应该能看到状态变化")
                else:
                    print("⚠️  任务状态没有变化，可能需要前端手动刷新")
            
            # 7. 验证任务列表中的状态更新
            print(f"\nStep 7: 验证任务列表状态更新...")
            response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=tom_headers)
            if response.status_code == 200:
                tasks_list = response.json()
                updated_task = None
                
                for task in tasks_list:
                    if task['id'] == task_id:
                        updated_task = task
                        break
                
                if updated_task:
                    print(f"✅ 任务列表中的状态: {updated_task['status']}")
                    print("📱 前端页面刷新机制测试完成")
                    print("\n测试说明：")
                    print("1. 当管理员审核任务后，任务状态从 'submitted' 变为 'approved'")
                    print("2. 前端页面应该通过以下机制自动更新：")
                    print("   - onShow() 生命周期：页面显示时刷新")
                    print("   - 事件监听：操作完成后发送事件通知")
                    print("   - 页面可见性管理：应用切换时智能刷新")
                    print("3. 用户应该能立即看到状态变化，无需手动刷新")
                else:
                    print("❌ 在任务列表中没有找到更新的任务")
        else:
            print(f"❌ 任务审核失败: {response.status_code}")
            if response.text:
                print(f"   错误: {response.text}")
    else:
        print(f"❌ 获取任务列表失败: {response.status_code}")

if __name__ == "__main__":
    test_data_refresh()