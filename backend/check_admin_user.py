#!/usr/bin/env python3
"""
检查admin用户信息
"""

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.core.security import verify_password

def check_admin_user():
    """检查admin用户"""
    print("正在检查admin用户...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 查找admin用户
        admin_user = db.query(User).filter(User.username == "admin").first()
        
        if admin_user:
            print("✅ admin用户存在")
            print(f"   用户名: {admin_user.username}")
            print(f"   全名: {admin_user.full_name}")
            print(f"   角色: {admin_user.role}")
            print(f"   邮箱: {admin_user.email}")
            print(f"   活跃状态: {admin_user.is_active}")
            print(f"   密码哈希: {admin_user.hashed_password[:50]}...")
            
            # 测试不同的密码
            passwords_to_test = ["admin123456", "admin", "123456"]
            
            for password in passwords_to_test:
                is_valid = verify_password(password, admin_user.hashed_password)
                print(f"密码 '{password}': {'✅ 正确' if is_valid else '❌ 错误'}")
                
            return admin_user
        else:
            print("❌ admin用户不存在")
            return None
            
    except Exception as e:
        print(f"❌ 检查用户失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_admin_user()