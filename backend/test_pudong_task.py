#!/usr/bin/env python3
"""
测试Tom的上海浦东基站任务提交
"""

import requests

def test_pudong_task_submission():
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
    
    # 2. 获取Tom的任务，找到上海浦东基站的任务
    print("\nStep 2: 查找上海浦东基站任务...")
    response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        pudong_task = None
        
        for task in tasks:
            if "上海浦东" in task.get('site_name', ''):
                pudong_task = task
                break
        
        if not pudong_task:
            print("❌ 未找到上海浦东基站任务")
            return
        
        task_id = pudong_task["id"]
        print(f"✅ 找到上海浦东基站任务: {pudong_task['task_title']}")
        print(f"   任务ID: {task_id}")
        print(f"   当前状态: {pudong_task['status']}")
        print(f"   站点: {pudong_task['site_name']}")
        
        # 3. 查看该任务的检查记录
        print(f"\nStep 3: 查看任务检查记录...")
        response = requests.get(f"{base_url}/api/inspections/?task_id={task_id}", headers=headers)
        if response.status_code == 200:
            inspections = response.json()
            print(f"✅ 找到 {len(inspections)} 条检查记录")
            
            completed_inspections = 0
            for i, inspection in enumerate(inspections):
                status = inspection.get('status', 'unknown')
                print(f"   检查记录 {i+1}: {status}")
                if status in ['completed', 'submitted']:
                    completed_inspections += 1
            
            print(f"   已完成/已提交的检查记录: {completed_inspections}/{len(inspections)}")
            
            # 4. 尝试提交任务
            if completed_inspections > 0:
                print(f"\nStep 4: 尝试提交任务...")
                response = requests.post(
                    f"{base_url}/api/tasks/{task_id}/status",
                    json={
                        "status": "submitted",
                        "comments": "上海浦东基站任务检查完成，提交审核"
                    },
                    headers=headers
                )
                
                if response.status_code == 200:
                    print("✅ 任务提交成功!")
                    
                    # 验证任务状态
                    response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=headers)
                    if response.status_code == 200:
                        updated_task = response.json()
                        print(f"✅ 任务最终状态: {updated_task['status']}")
                else:
                    print(f"❌ 任务提交失败: {response.status_code}")
                    if response.text:
                        print(f"   错误信息: {response.text}")
            else:
                print("❌ 没有已完成的检查记录，无法提交任务")
        else:
            print(f"❌ 获取检查记录失败: {response.status_code}")
    else:
        print(f"❌ 获取任务失败: {response.status_code}")

if __name__ == "__main__":
    test_pudong_task_submission()