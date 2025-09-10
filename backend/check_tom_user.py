#!/usr/bin/env python3
"""
检查Tom用户是否存在
"""

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User

def check_tom_user():
    """检查Tom用户"""
    print("正在检查Tom用户...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 查找Tom用户
        tom_user = db.query(User).filter(User.username == "tom").first()
        
        if tom_user:
            print("✅ Tom用户存在")
            print(f"   用户名: {tom_user.username}")
            print(f"   全名: {tom_user.full_name}")
            print(f"   角色: {tom_user.role}")
            print(f"   邮箱: {tom_user.email}")
            print(f"   活跃状态: {tom_user.is_active}")
            print(f"   密码哈希: {tom_user.hashed_password[:50]}...")
            return tom_user
        else:
            print("❌ Tom用户不存在")
            return None
            
    except Exception as e:
        print(f"❌ 检查用户失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_tom_user()