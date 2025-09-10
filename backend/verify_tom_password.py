#!/usr/bin/env python3
"""
验证Tom用户密码
"""

from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.user import User
from app.core.security import verify_password

def verify_tom_password():
    """验证Tom用户密码"""
    print("正在验证Tom用户密码...")
    
    # 创建数据库会话
    db = next(get_db())
    
    try:
        # 查找Tom用户
        tom_user = db.query(User).filter(User.username == "tom").first()
        
        if not tom_user:
            print("❌ Tom用户不存在")
            return
        
        # 测试不同的密码
        passwords_to_test = ["tom123456", "Tom", "tom", "123456"]
        
        for password in passwords_to_test:
            is_valid = verify_password(password, tom_user.hashed_password)
            print(f"密码 '{password}': {'✅ 正确' if is_valid else '❌ 错误'}")
            
    except Exception as e:
        print(f"❌ 验证密码失败: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_tom_password()