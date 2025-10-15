#!/usr/bin/env python3
"""
测试检查项描述API返回
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import requests
import json

# 配置
API_BASE_URL = "http://127.0.0.1:8000"

def test_description_api():
    """测试描述信息是否正确返回"""
    
    print("=" * 60)
    print("测试检查项描述API返回")
    print("=" * 60)
    
    # 1. 登录获取token
    print("\n1️⃣  登录获取token...")
    login_response = requests.post(
        f"{API_BASE_URL}/api/auth/login",
        data={
            "username": "inspector",
            "password": "inspector123"
        }
    )
    
    if login_response.status_code != 200:
        print(f"❌ 登录失败: {login_response.status_code}")
        return False
    
    token = login_response.json()["access_token"]
    print(f"✅ 登录成功，token: {token[:20]}...")
    
    # 2. 获取检查列表
    print("\n2️⃣  获取检查列表...")
    headers = {"Authorization": f"Bearer {token}"}
    
    inspections_response = requests.get(
        f"{API_BASE_URL}/api/inspections",
        headers=headers
    )
    
    if inspections_response.status_code != 200:
        print(f"❌ 获取检查列表失败: {inspections_response.status_code}")
        return False
    
    inspections = inspections_response.json()
    if not inspections:
        print("❌ 没有找到检查记录")
        return False
    
    inspection_id = inspections[0]["id"]
    print(f"✅ 找到检查记录: {inspection_id}")
    
    # 3. 获取检查项列表
    print("\n3️⃣  获取检查项列表...")
    items_response = requests.get(
        f"{API_BASE_URL}/api/inspections/detail/{inspection_id}/items",
        headers=headers
    )
    
    if items_response.status_code != 200:
        print(f"❌ 获取检查项失败: {items_response.status_code}")
        return False
    
    items = items_response.json()
    print(f"✅ 获取到 {len(items)} 个检查项")
    
    # 4. 检查description字段
    print("\n4️⃣  检查description字段...")
    items_with_desc = []
    items_without_desc = []
    
    for item in items:
        if "description" in item and item["description"]:
            items_with_desc.append(item)
        else:
            items_without_desc.append(item)
    
    print(f"\n📊 统计结果:")
    print(f"   总检查项数: {len(items)}")
    print(f"   有描述的: {len(items_with_desc)}")
    print(f"   无描述的: {len(items_without_desc)}")
    
    # 5. 显示有描述的检查项示例
    if items_with_desc:
        print(f"\n✅ 成功！以下是有描述的检查项示例：")
        print("-" * 60)
        for i, item in enumerate(items_with_desc[:3], 1):
            print(f"\n示例 {i}:")
            print(f"  ID: {item['id']}")
            print(f"  名称: {item['item_name']}")
            print(f"  描述: {item['description'][:100]}{'...' if len(item['description']) > 100 else ''}")
        print("-" * 60)
        return True
    else:
        print("\n❌ 失败：所有检查项都没有描述信息")
        print("\n请检查：")
        print("  1. 数据库中是否有description数据")
        print("  2. API Schema是否包含description字段")
        print("  3. 是否重启了后端服务")
        return False

if __name__ == "__main__":
    try:
        success = test_description_api()
        print("\n" + "=" * 60)
        if success:
            print("✅ 测试通过！API正确返回了description字段")
            print("\n现在可以在App端查看描述信息了！")
        else:
            print("❌ 测试失败！需要进一步检查")
        print("=" * 60)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
