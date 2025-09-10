#!/usr/bin/env python3
"""
直接测试登录功能，不启动服务器
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal
from app.core.security import verify_password, create_access_token
from app.models.user import User
from datetime import timedelta

def test_direct_login():
    """直接测试登录逻辑"""
    
    print("=== 直接登录测试 ===")
    
    db = SessionLocal()
    
    try:
        # 测试用户凭据
        test_users = [
            {"username": "admin", "password": "admin123"},
            {"username": "test_user", "password": "password123"},
            {"username": "admin", "password": "wrong_password"}  # 错误密码测试
        ]
        
        for i, creds in enumerate(test_users, 1):
            print(f"\n测试 {i}: 用户名={creds['username']}, 密码={creds['password']}")
            
            # 查找用户
            user = db.query(User).filter(User.username == creds['username']).first()
            
            if not user:
                print(f"❌ 用户不存在: {creds['username']}")
                continue
            
            print(f"✅ 用户存在: {user.full_name} ({user.email})")
            
            # 验证密码
            is_password_valid = verify_password(creds['password'], user.hashed_password)
            
            if is_password_valid:
                print(f"✅ 密码验证通过")
                
                # 生成token
                access_token = create_access_token(subject=user.username, expires_delta=timedelta(minutes=30))
                print(f"✅ Token生成成功: {access_token[:50]}...")
                
                # 模拟返回数据
                login_response = {
                    "access_token": access_token,
                    "token_type": "bearer",
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "full_name": user.full_name,
                        "role": user.role
                    }
                }
                print(f"✅ 登录成功，用户信息: {login_response['user']}")
            else:
                print(f"❌ 密码验证失败")
        
    finally:
        db.close()

def simulate_frontend_request():
    """模拟前端请求"""
    
    print("\n=== 模拟前端登录请求 ===")
    
    import requests
    import json
    
    # 测试服务器连接
    test_urls = [
        "http://localhost:8000",
        "http://localhost:8001", 
        "http://localhost:8002"
    ]
    
    working_url = None
    
    for url in test_urls:
        try:
            response = requests.get(f"{url}/health", timeout=2)
            if response.status_code == 200:
                working_url = url
                print(f"✅ 找到工作中的服务器: {url}")
                break
        except:
            continue
    
    if not working_url:
        print("❌ 没有找到工作中的服务器")
        print("请先启动服务器:")
        print("python start_minimal.py")
        return False
    
    # 测试登录请求
    login_data = {"username": "admin", "password": "admin123"}
    
    try:
        response = requests.post(
            f"{working_url}/api/auth/login",
            json=login_data,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"请求URL: {working_url}/api/auth/login")
        print(f"请求数据: {login_data}")
        print(f"响应状态: {response.status_code}")
        print(f"响应数据: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            if "access_token" in data:
                print("✅ 登录API测试成功！")
                print(f"获得Token: {data['access_token'][:50]}...")
                print(f"用户信息: {data.get('user', {})}")
                return True
            else:
                print("❌ 响应格式错误")
        else:
            print(f"❌ 登录失败: {response.json().get('detail', '未知错误')}")
    
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")
    
    return False

def check_database_users():
    """检查数据库用户信息"""
    
    print("\n=== 检查数据库用户 ===")
    
    db = SessionLocal()
    
    try:
        users = db.query(User).all()
        
        print(f"数据库中共有 {len(users)} 个用户:")
        
        for user in users:
            print(f"- ID: {user.id}")
            print(f"  用户名: {user.username}")
            print(f"  邮箱: {user.email}")
            print(f"  姓名: {user.full_name}")
            print(f"  角色: {user.role}")
            print(f"  密码哈希: {user.hashed_password[:50]}...")
            print()
            
            # 测试admin123密码
            if user.username == "admin":
                is_valid = verify_password("admin123", user.hashed_password)
                print(f"  admin123密码验证: {'✅ 正确' if is_valid else '❌ 错误'}")
                
                if not is_valid:
                    # 重置admin密码
                    from app.core.security import get_password_hash
                    user.hashed_password = get_password_hash("admin123")
                    db.commit()
                    print("  ✅ admin密码已重置为 admin123")
    
    finally:
        db.close()

def main():
    """主函数"""
    
    print("登录问题诊断和修复工具")
    print("=" * 50)
    
    # 1. 检查数据库用户
    check_database_users()
    
    # 2. 直接测试登录逻辑
    test_direct_login()
    
    # 3. 模拟前端请求（如果服务器在运行）
    api_working = simulate_frontend_request()
    
    print("\n" + "=" * 50)
    print("诊断总结:")
    
    if api_working:
        print("✅ 后端API正常工作")
        print("✅ 登录功能正常")
        print("\n前端配置检查:")
        print("1. 确保前端请求URL正确")
        print("2. 检查网络连接")
        print("3. 检查浏览器控制台错误")
        
        # 检查前端配置
        print("\n=== 前端配置检查 ===")
        frontend_path = "../uniapp-site-manager/stores/user.js"
        
        if os.path.exists(frontend_path):
            with open(frontend_path, 'r') as f:
                content = f.read()
                
            # 检查API地址
            if "localhost:8000" in content:
                print("⚠️  前端仍然配置为 localhost:8000")
                print("   请确保后端服务器在该端口运行")
            elif "localhost:8002" in content:
                print("前端配置为 localhost:8002")
            else:
                print("前端API地址配置可能有问题")
        else:
            print("❌ 找不到前端用户store文件")
    else:
        print("❌ 后端API无法访问")
        print("请检查:")
        print("1. 服务器是否启动")
        print("2. 端口是否被占用")
        print("3. 防火墙设置")

if __name__ == "__main__":
    main()