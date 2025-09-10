#!/usr/bin/env python3
"""
测试管理员任务审核功能
"""

import requests

def test_task_review():
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
    
    # 2. 获取已提交的任务
    print("\nStep 2: 获取已提交的任务...")
    response = requests.get(f"{base_url}/api/tasks/?status=submitted", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        if not tasks:
            print("❌ 没有找到已提交的任务")
            return
        
        # 选择第一个任务进行审核
        task = tasks[0]
        task_id = task["id"]
        print(f"✅ 选择任务进行审核:")
        print(f"   任务ID: {task_id}")
        print(f"   标题: {task['task_title']}")
        print(f"   站点: {task.get('site_name', '未知站点')}")
        print(f"   分配给: {task.get('assignee_name', '未知')}")
        print(f"   当前状态: {task['status']}")
        
        # 3. 审核通过任务
        print(f"\nStep 3: 审核通过任务...")
        review_data = {
            "result": "approved",
            "comments": "检查记录完整，任务执行良好，审核通过",
            "require_recheck": False
        }
        
        response = requests.post(
            f"{base_url}/api/tasks/{task_id}/review",
            json=review_data,
            headers=headers
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务审核成功")
            print(f"   审核结果: {review_data['result']}")
            print(f"   审核意见: {review_data['comments']}")
            
            # 验证任务状态
            task_data = result.get('task')
            if task_data:
                print(f"   新状态: {task_data['status']}")
            
            # 4. 获取另一个任务进行驳回测试（如果有的话）
            if len(tasks) > 1:
                print(f"\nStep 4: 测试审核驳回...")
                second_task = tasks[1]
                second_task_id = second_task["id"]
                print(f"   选择任务: {second_task['task_title']}")
                
                reject_data = {
                    "result": "rejected",
                    "comments": "检查记录不够详细，需要重新检查设备安装情况",
                    "require_recheck": True
                }
                
                response = requests.post(
                    f"{base_url}/api/tasks/{second_task_id}/review",
                    json=reject_data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✅ 任务驳回成功")
                    print(f"   驳回原因: {reject_data['comments']}")
                    print(f"   需要重新检查: {reject_data['require_recheck']}")
                    
                    task_data = result.get('task')
                    if task_data:
                        print(f"   新状态: {task_data['status']}")
                else:
                    print(f"❌ 任务驳回失败: {response.status_code}")
                    if response.text:
                        print(f"   错误: {response.text}")
        else:
            print(f"❌ 任务审核失败: {response.status_code}")
            if response.text:
                print(f"   错误: {response.text}")
    else:
        print(f"❌ 获取任务失败: {response.status_code}")

if __name__ == "__main__":
    test_task_review()