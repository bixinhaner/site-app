#!/usr/bin/env python3
"""
启动后端服务的脚本
"""

import os
import sys
import subprocess

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8或更高版本是必需的")
        sys.exit(1)
    print(f"✅ Python版本: {sys.version.split()[0]}")

def create_virtual_env():
    """创建虚拟环境（如果不存在）"""
    venv_path = "venv"
    if not os.path.exists(venv_path):
        print("📦 创建虚拟环境...")
        subprocess.run([sys.executable, "-m", "venv", venv_path], check=True)
        print("✅ 虚拟环境创建成功")
    else:
        print("✅ 虚拟环境已存在")

def get_activate_command():
    """获取激活虚拟环境的命令"""
    if os.name == 'nt':  # Windows
        return os.path.join("venv", "Scripts", "activate")
    else:  # Unix/Linux/MacOS
        return "source venv/bin/activate"

def install_dependencies():
    """安装依赖"""
    print("📦 安装依赖包...")
    pip_path = "venv/bin/pip" if os.name != 'nt' else "venv\\Scripts\\pip.exe"
    
    if not os.path.exists(pip_path):
        print("❌ 找不到pip，请确保虚拟环境创建成功")
        sys.exit(1)
    
    subprocess.run([pip_path, "install", "-r", "backend/requirements.txt"], check=True)
    print("✅ 依赖安装完成")

def setup_database():
    """设置数据库"""
    print("🗃️ 初始化数据库...")
    
    # 切换到backend目录
    os.chdir("backend")
    
    # 创建uploads目录
    os.makedirs("uploads", exist_ok=True)
    
    # 复制环境配置文件
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            import shutil
            shutil.copy(".env.example", ".env")
            print("✅ 环境配置文件已创建，请根据需要修改 .env 文件")
        else:
            print("⚠️ 找不到 .env.example 文件")
    
    print("✅ 数据库初始化完成")

def create_default_user():
    """创建默认用户"""
    print("👤 创建默认管理员用户...")
    
    python_path = "../venv/bin/python" if os.name != 'nt' else "..\\venv\\Scripts\\python.exe"
    
    # 创建默认用户脚本
    script = """
from app.core.database import SessionLocal, engine, Base
from app.models.user import User
from app.core.security import get_password_hash

# 创建数据库表
Base.metadata.create_all(bind=engine)

db = SessionLocal()

# 检查是否已存在管理员用户
admin_user = db.query(User).filter(User.username == "admin").first()

if not admin_user:
    # 创建默认管理员
    admin = User(
        username="admin",
        email="admin@example.com",
        full_name="系统管理员",
        hashed_password=get_password_hash("admin123"),
        role="admin",
        department="技术部",
        position="系统管理员"
    )
    db.add(admin)
    
    # 创建inspector用户
    inspector = User(
        username="inspector",
        email="inspector@example.com",
        full_name="安装施工人员",
        hashed_password=get_password_hash("inspector123"),
        role="inspector",
        department="工程部",
        position="安装施工人员"
    )
    db.add(inspector)
    
    # 创建Tom用户
    tom = User(
        username="tom",
        email="tom@example.com",
        full_name="Tom",
        hashed_password=get_password_hash("tom123456"),
        role="inspector",
        department="工程部",
        position="安装施工人员"
    )
    db.add(tom)
    
    # 创建测试用户
    user = User(
        username="test_user",
        email="user@example.com", 
        full_name="测试用户",
        hashed_password=get_password_hash("user123"),
        role="user",
        department="工程部",
        position="现场工程师"
    )
    db.add(user)
    
    db.commit()
    print("✅ 默认用户创建成功:")
    print("   管理员 - 用户名: admin, 密码: admin123")
    print("   检查员 - 用户名: inspector, 密码: inspector123")
    print("   Tom用户 - 用户名: tom, 密码: tom123456")
    print("   普通用户 - 用户名: test_user, 密码: user123")
else:
    print("ℹ️ 管理员用户已存在")

db.close()
"""
    
    with open("create_users.py", "w", encoding="utf-8") as f:
        f.write(script)
    
    try:
        subprocess.run([python_path, "create_users.py"], check=True)
        os.remove("create_users.py")
    except subprocess.CalledProcessError as e:
        print(f"❌ 创建用户失败: {e}")
        if os.path.exists("create_users.py"):
            os.remove("create_users.py")

def start_server():
    """启动服务器"""
    print("🚀 启动后端服务...")
    python_path = "../venv/bin/python" if os.name != 'nt' else "..\\venv\\Scripts\\python.exe"
    
    print("=" * 50)
    print("🎉 站点信息管理系统后端服务启动中...")
    print("📍 服务地址: http://localhost:8000")
    print("📖 API文档: http://localhost:8000/docs")
    print("🔄 自动重载: 已启用")
    print("=" * 50)
    
    # 启动服务
    subprocess.run([python_path, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"])

def main():
    """主函数"""
    print("🏗️ 站点信息管理系统 - 后端服务启动器")
    print("=" * 50)
    
    try:
        # 检查Python版本
        check_python_version()
        
        # 创建虚拟环境
        create_virtual_env()
        
        # 安装依赖
        install_dependencies()
        
        # 设置数据库
        setup_database()
        
        # 创建默认用户
        create_default_user()
        
        # 启动服务器
        start_server()
        
    except subprocess.CalledProcessError as e:
        print(f"❌ 启动失败: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 意外错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()