#!/usr/bin/env python3
"""测试Token刷新功能"""
import requests
import time
import sys

# 配置
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def test_token_refresh():
    """测试Token刷新流程"""
    print("=" * 60)
    print("测试Token刷新功能")
    print("=" * 60)
    
    # 1. 登录获取token
    print("\n1. 登录获取token...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    
    if login_response.status_code != 200:
        print(f"❌ 登录失败: {login_response.status_code}")
        print(login_response.text)
        return False
    
    login_data = login_response.json()
    token = login_data.get("access_token")
    user = login_data.get("user")
    
    print(f"✅ 登录成功")
    print(f"   用户: {user.get('username')}")
    print(f"   角色: {user.get('role')}")
    print(f"   Token前缀: {token[:20]}...")
    
    # 2. 使用token访问受保护接口
    print("\n2. 使用token访问用户信息...")
    headers = {"Authorization": f"Bearer {token}"}
    me_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    
    if me_response.status_code != 200:
        print(f"❌ 获取用户信息失败: {me_response.status_code}")
        return False
    
    print(f"✅ 成功访问用户信息")
    
    # 3. 刷新token
    print("\n3. 刷新token...")
    refresh_response = requests.post(
        f"{BASE_URL}/api/auth/refresh",
        headers=headers
    )
    
    if refresh_response.status_code != 200:
        print(f"❌ 刷新token失败: {refresh_response.status_code}")
        print(refresh_response.text)
        return False
    
    refresh_data = refresh_response.json()
    new_token = refresh_data.get("access_token")
    
    print(f"✅ Token刷新成功")
    print(f"   新Token前缀: {new_token[:20]}...")
    print(f"   Token已更新: {token != new_token}")
    
    # 4. 使用新token访问接口
    print("\n4. 使用新token访问接口...")
    new_headers = {"Authorization": f"Bearer {new_token}"}
    verify_response = requests.get(f"{BASE_URL}/api/auth/me", headers=new_headers)
    
    if verify_response.status_code != 200:
        print(f"❌ 使用新token失败: {verify_response.status_code}")
        return False
    
    print(f"✅ 新token验证成功")
    
    # 5. 测试旧token是否仍然有效
    print("\n5. 测试旧token是否仍然有效...")
    old_response = requests.get(f"{BASE_URL}/api/auth/me", headers=headers)
    
    if old_response.status_code == 200:
        print(f"⚠️  旧token仍然有效（符合预期，JWT在过期前都有效）")
    else:
        print(f"❌ 旧token已失效: {old_response.status_code}")
    
    print("\n" + "=" * 60)
    print("✅ Token刷新功能测试通过")
    print("=" * 60)
    return True

if __name__ == "__main__":
    try:
        success = test_token_refresh()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
