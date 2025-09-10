#!/usr/bin/env python3
"""
API测试脚本 - 验证站点管理系统的核心功能
"""

import requests
import json

BASE_URL = "http://localhost:8000"
TOKEN = None

def test_api_endpoint(name, method, url, data=None, headers=None):
    """测试API端点"""
    try:
        if method.upper() == 'GET':
            response = requests.get(url, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, headers=headers)
        else:
            print(f"❌ {name}: 不支持的方法 {method}")
            return None
            
        if response.status_code in [200, 201]:
            print(f"✅ {name}: 成功 ({response.status_code})")
            return response.json()
        else:
            print(f"❌ {name}: 失败 ({response.status_code}) - {response.text[:100]}")
            return None
    except Exception as e:
        print(f"❌ {name}: 连接错误 - {str(e)}")
        return None

def main():
    global TOKEN
    
    print("🚀 开始测试站点管理系统 API")
    print("=" * 50)
    
    # 1. 测试根端点
    print("📍 测试基本连接...")
    root_response = test_api_endpoint(
        "根端点", "GET", f"{BASE_URL}/"
    )
    
    # 2. 测试健康检查
    test_api_endpoint(
        "健康检查", "GET", f"{BASE_URL}/health"
    )
    
    # 3. 测试管理员登录
    print("\n👤 测试用户认证...")
    login_response = test_api_endpoint(
        "管理员登录", "POST", f"{BASE_URL}/api/auth/login",
        {"username": "admin", "password": "admin123"}
    )
    
    if login_response:
        TOKEN = login_response.get("access_token")
        user_info = login_response.get("user", {})
        print(f"   用户: {user_info.get('full_name')} ({user_info.get('role')})")
    
    # 4. 测试普通用户登录
    test_user_response = test_api_endpoint(
        "普通用户登录", "POST", f"{BASE_URL}/api/auth/login",
        {"username": "test_user", "password": "user123"}
    )
    
    if test_user_response:
        test_user_info = test_user_response.get("user", {})
        print(f"   用户: {test_user_info.get('full_name')} ({test_user_info.get('role')})")
    
    if not TOKEN:
        print("❌ 无法获取访问令牌，跳过后续测试")
        return
    
    # 5. 测试用户信息获取
    headers = {"Authorization": f"Bearer {TOKEN}"}
    test_api_endpoint(
        "获取当前用户信息", "GET", f"{BASE_URL}/api/auth/me",
        headers=headers
    )
    
    # 6. 测试站点管理
    print("\n📍 测试站点管理...")
    
    # 创建测试站点
    site_data = {
        "site_code": "TEST001",
        "site_name": "测试站点1号",
        "site_type": "base_station",
        "address": "测试地址123号",
        "latitude": 39.9042,
        "longitude": 116.4074,
        "contact_person": "张工程师",
        "contact_phone": "13800138000",
        "description": "这是一个API测试站点"
    }
    
    create_site_response = test_api_endpoint(
        "创建站点", "POST", f"{BASE_URL}/api/sites/",
        site_data, headers
    )
    
    site_id = None
    if create_site_response:
        site_id = create_site_response.get("id")
        print(f"   创建的站点ID: {site_id}")
    
    # 获取站点列表
    sites_response = test_api_endpoint(
        "获取站点列表", "GET", f"{BASE_URL}/api/sites/",
        headers=headers
    )
    
    if sites_response:
        print(f"   站点总数: {len(sites_response)}")
    
    # 7. 测试检查管理
    if site_id:
        print("\n🔍 测试检查管理...")
        
        # 创建检查记录
        inspection_data = {
            "site_id": site_id,
            "inspection_type": "routine",
            "location": "站点主机房",
            "weather": "晴天",
            "temperature": "25°C",
            "notes": "API测试检查记录"
        }
        
        inspection_response = test_api_endpoint(
            "创建检查记录", "POST", f"{BASE_URL}/api/inspections/",
            inspection_data, headers
        )
        
        # 获取检查列表
        test_api_endpoint(
            "获取检查列表", "GET", f"{BASE_URL}/api/inspections/",
            headers=headers
        )
    
    print("\n" + "=" * 50)
    print("🎉 API 测试完成！")
    print(f"📖 API 文档地址: {BASE_URL}/docs")
    print(f"🔗 ReDoc 文档: {BASE_URL}/redoc")
    print("\n🔑 测试账户:")
    print("   管理员: admin / admin123")
    print("   普通用户: test_user / user123")

if __name__ == "__main__":
    main()