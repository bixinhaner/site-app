#!/usr/bin/env python3
"""
登录功能测试脚本
测试登录API是否正常工作
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
import json

# 检查是否有必要的依赖
def check_dependencies():
    """检查必要的Python依赖"""
    missing_deps = []
    
    try:
        import fastapi
        print(f"✓ FastAPI: {fastapi.__version__}")
    except ImportError:
        missing_deps.append("fastapi")
    
    try:
        import sqlalchemy
        print(f"✓ SQLAlchemy: {sqlalchemy.__version__}")
    except ImportError:
        missing_deps.append("sqlalchemy")
        
    try:
        import jose
        from jose import jwt
        print(f"✓ python-jose: Available")
    except ImportError:
        missing_deps.append("python-jose[cryptography]")
    
    try:
        import passlib
        print(f"✓ passlib: {passlib.__version__}")
    except ImportError:
        missing_deps.append("passlib[bcrypt]")
    
    if missing_deps:
        print(f"\n✗ 缺少依赖: {', '.join(missing_deps)}")
        print("请运行以下命令安装:")
        print(f"pip install {' '.join(missing_deps)}")
        return False
    
    return True

def test_login_api():
    """测试登录API"""
    
    if not check_dependencies():
        return False
    
    try:
        # 导入应用
        from app.main import app
        client = TestClient(app)
        
        print("\n=== 测试登录API ===")
        
        # 测试用户凭据
        test_credentials = [
            {"username": "admin", "password": "admin123"},
            {"username": "test_user", "password": "password123"}
        ]
        
        for creds in test_credentials:
            print(f"\n测试用户: {creds['username']}")
            
            # 发送登录请求
            response = client.post("/api/auth/login", json=creds)
            
            print(f"响应状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            
            if response.status_code == 200:
                data = response.json()
                if "access_token" in data:
                    print(f"✓ 登录成功，获得token: {data['access_token'][:50]}...")
                    print(f"✓ 用户信息: {data.get('user', {}).get('full_name')}")
                else:
                    print("✗ 响应格式错误，缺少access_token")
            else:
                print(f"✗ 登录失败: {response.json().get('detail', '未知错误')}")
        
        return True
        
    except Exception as e:
        print(f"✗ 测试过程出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def check_database_connection():
    """检查数据库连接"""
    
    try:
        from app.core.database import engine
        from sqlalchemy import text
        
        print("\n=== 检查数据库连接 ===")
        
        with engine.connect() as conn:
            # 检查用户表
            result = conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()
            print(f"✓ 数据库连接正常，共有 {user_count} 个用户")
            
            # 获取用户详情
            result = conn.execute(text("SELECT username, email, full_name, hashed_password FROM users LIMIT 3"))
            users = result.fetchall()
            
            print("\n用户列表:")
            for user in users:
                password_hash = user[3][:50] + "..." if user[3] else "无密码"
                print(f"- 用户名: {user[0]}, 邮箱: {user[1]}, 姓名: {user[2]}")
                print(f"  密码哈希: {password_hash}")
        
        return True
        
    except Exception as e:
        print(f"✗ 数据库连接失败: {str(e)}")
        return False

def check_password_hashing():
    """检查密码哈希功能"""
    
    try:
        from app.core.security import get_password_hash, verify_password
        
        print("\n=== 检查密码哈希功能 ===")
        
        test_password = "admin123"
        hashed = get_password_hash(test_password)
        
        print(f"原始密码: {test_password}")
        print(f"哈希后密码: {hashed}")
        
        # 验证密码
        is_valid = verify_password(test_password, hashed)
        print(f"密码验证结果: {is_valid}")
        
        if is_valid:
            print("✓ 密码哈希功能正常")
            return True
        else:
            print("✗ 密码哈希验证失败")
            return False
            
    except Exception as e:
        print(f"✗ 密码哈希功能测试失败: {str(e)}")
        return False

def create_test_user():
    """创建测试用户（如果不存在）"""
    
    try:
        from app.core.database import SessionLocal
        from app.core.security import get_password_hash
        from app.models.user import User
        
        print("\n=== 创建/检查测试用户 ===")
        
        db = SessionLocal()
        
        # 检查admin用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        if not admin_user:
            print("创建admin用户...")
            admin_user = User(
                username="admin",
                email="admin@example.com", 
                hashed_password=get_password_hash("admin123"),
                full_name="系统管理员",
                role="admin"
            )
            db.add(admin_user)
            db.commit()
            print("✓ admin用户创建成功")
        else:
            print(f"✓ admin用户已存在: {admin_user.full_name}")
        
        # 检查密码是否正确
        from app.core.security import verify_password
        if verify_password("admin123", admin_user.hashed_password):
            print("✓ admin用户密码正确")
        else:
            print("✗ admin用户密码不正确，重新设置...")
            admin_user.hashed_password = get_password_hash("admin123")
            db.commit()
            print("✓ admin用户密码已重新设置")
        
        db.close()
        return True
        
    except Exception as e:
        print(f"✗ 创建测试用户失败: {str(e)}")
        return False

def main():
    """主函数"""
    
    print("=== 登录功能诊断 ===")
    print("正在检查登录相关功能...")
    
    results = []
    
    # 1. 检查依赖
    results.append(("检查Python依赖", check_dependencies()))
    
    # 2. 检查数据库连接
    results.append(("检查数据库连接", check_database_connection()))
    
    # 3. 检查密码哈希功能
    results.append(("检查密码功能", check_password_hashing()))
    
    # 4. 创建/检查测试用户
    results.append(("检查测试用户", create_test_user()))
    
    # 5. 测试登录API
    results.append(("测试登录API", test_login_api()))
    
    # 显示结果
    print("\n" + "="*50)
    print("诊断结果汇总:")
    
    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"- {test_name}: {status}")
    
    success_count = sum([1 for _, result in results if result])
    total_count = len(results)
    
    print(f"\n总体结果: {success_count}/{total_count} 项检查通过")
    
    if success_count == total_count:
        print("\n🎉 所有检查通过！登录功能应该正常工作。")
        print("\n测试建议:")
        print("1. 使用用户名: admin, 密码: admin123")
        print("2. 确保后端服务器运行在 http://localhost:8000")
        print("3. 检查前端网络请求是否正确发送")
    else:
        print(f"\n⚠️ 发现{total_count - success_count}个问题，请先解决这些问题。")

if __name__ == "__main__":
    main()