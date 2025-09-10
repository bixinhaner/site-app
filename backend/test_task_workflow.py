#!/usr/bin/env python3
"""
测试完整的任务执行流程
从接受任务到完成任务
"""

import requests
import json
import time

def test_task_workflow():
    base_url = "http://192.168.31.101:8000"
    
    # 1. 使用Tom用户登录
    print("Step 1: 使用Tom用户登录...")
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
    
    # 2. 获取Tom的任务列表
    print("\nStep 2: 获取Tom的任务列表...")
    response = requests.get(f"{base_url}/api/tasks/?assigned_to=3", headers=headers)
    if response.status_code == 200:
        tasks = response.json()
        if not tasks:
            print("❌ Tom没有分配的任务")
            return
        
        task = tasks[0]  # 使用第一个任务
        task_id = task["id"]
        current_status = task["status"]
        
        print(f"✅ 找到任务: {task['task_title']} (状态: {current_status})")
        
        # 3. 如果任务状态为assigned，接受任务
        if current_status == "assigned":
            print("\nStep 3: 接受任务...")
            response = requests.post(
                f"{base_url}/api/tasks/{task_id}/status",
                json={
                    "status": "accepted",
                    "comments": "接受任务"
                },
                headers=headers
            )
            if response.status_code == 200:
                print("✅ 任务已接受")
                current_status = "accepted"
            else:
                print(f"❌ 接受任务失败: {response.status_code} - {response.text}")
                return
        
        # 4. 开始执行任务
        if current_status == "accepted":
            print("\nStep 4: 开始执行任务...")
            response = requests.post(
                f"{base_url}/api/tasks/{task_id}/status",
                json={
                    "status": "in_progress",
                    "comments": "开始执行任务"
                },
                headers=headers
            )
            if response.status_code == 200:
                print("✅ 任务已开始")
                current_status = "in_progress"
            else:
                print(f"❌ 开始任务失败: {response.status_code} - {response.text}")
                return
        
        # 5. 创建检查记录
        if current_status == "in_progress":
            print("\nStep 5: 创建检查记录...")
            inspection_data = {
                "site_id": task["site_id"],
                "task_id": task_id,
                "inspection_type": "OPENING",
                "location": "现场检查",
                "weather": "晴天",
                "temperature": "25°C",
                "notes": "开始新站点设备安装检查"
            }
            
            response = requests.post(
                f"{base_url}/api/inspections/",
                json=inspection_data,
                headers=headers
            )
            if response.status_code == 200:
                inspection = response.json()
                inspection_id = inspection["id"]
                print(f"✅ 检查记录已创建: {inspection_id}")
                
                # 6. 获取检查项
                print("\nStep 6: 获取检查项...")
                response = requests.get(
                    f"{base_url}/api/inspections/detail/{inspection_id}/items",
                    headers=headers
                )
                if response.status_code == 200:
                    check_items = response.json()
                    print(f"✅ 获取到 {len(check_items)} 个检查项")
                    
                    # 7. 完成所有检查项
                    print("\nStep 7: 完成检查项...")
                    for i, item in enumerate(check_items):
                        print(f"  - 完成检查项 {i+1}/{len(check_items)}: {item['item_name']}")
                        
                        update_data = {
                            "status": "completed",
                            "result_data": f"检查项 {item['item_name']} 完成，状态正常",
                            "notes": f"完成检查: {item['item_name']}"
                        }
                        
                        response = requests.put(
                            f"{base_url}/api/inspections/detail/{inspection_id}/items/{item['id']}",
                            json=update_data,
                            headers=headers
                        )
                        if response.status_code == 200:
                            print(f"    ✅ 检查项已完成")
                        else:
                            print(f"    ❌ 检查项完成失败: {response.status_code}")
                        
                        time.sleep(0.5)  # 稍微延迟
                    
                    # 8. 完成整个检查记录
                    print("\nStep 8: 完成检查记录...")
                    response = requests.put(
                        f"{base_url}/api/inspections/detail/{inspection_id}",
                        json={
                            "status": "completed",
                        },
                        headers=headers
                    )
                    if response.status_code == 200:
                        print("✅ 检查记录已完成")
                        
                        # 9. 提交任务
                        print("\nStep 9: 提交任务...")
                        response = requests.post(
                            f"{base_url}/api/tasks/{task_id}/status",
                            json={
                                "status": "submitted",
                                "comments": "任务检查完成，提交审核"
                            },
                            headers=headers
                        )
                        if response.status_code == 200:
                            print("✅ 任务已提交")
                            
                            # 10. 查看最终状态
                            print("\nStep 10: 查看最终状态...")
                            response = requests.get(f"{base_url}/api/tasks/{task_id}", headers=headers)
                            if response.status_code == 200:
                                final_task = response.json()
                                print(f"✅ 任务最终状态: {final_task['status']}")
                                
                                # 检查检查记录
                                response = requests.get(f"{base_url}/api/inspections/?task_id={task_id}", headers=headers)
                                if response.status_code == 200:
                                    inspections = response.json()
                                    if inspections:
                                        inspection = inspections[0]
                                        print(f"✅ 检查记录状态: {inspection['status']}")
                                        print(f"✅ 完成率: {inspection.get('completion_rate', 0)}%")
                                
                                print("\n🎉 任务工作流程测试完成！")
                            else:
                                print(f"❌ 获取最终状态失败: {response.status_code}")
                        else:
                            print(f"❌ 提交任务失败: {response.status_code} - {response.text}")
                    else:
                        print(f"❌ 完成检查记录失败: {response.status_code} - {response.text}")
                else:
                    print(f"❌ 获取检查项失败: {response.status_code} - {response.text}")
            else:
                print(f"❌ 创建检查记录失败: {response.status_code} - {response.text}")
    else:
        print(f"❌ 获取任务列表失败: {response.status_code} - {response.text}")

if __name__ == "__main__":
    test_task_workflow()