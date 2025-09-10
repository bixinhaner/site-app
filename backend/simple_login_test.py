#!/usr/bin/env python3
"""
简单登录测试 - 直接测试登录功能和前端配置
"""

import requests
import json
import os
import time

def test_login_with_curl():
    """使用curl测试登录"""
    
    print("=== 使用curl测试登录 ===")
    
    # 准备测试数据
    login_data = {
        "username": "admin", 
        "password": "admin123"
    }
    
    # 尝试不同端口
    test_ports = [8000, 8001, 8002, 8003]
    
    for port in test_ports:
        print(f"\n测试端口 {port}...")
        
        url = f"http://localhost:{port}/api/auth/login"
        
        try:
            import subprocess
            import json
            
            # 使用curl命令
            curl_cmd = [
                'curl', '-X', 'POST',
                '-H', 'Content-Type: application/json',
                '-d', json.dumps(login_data),
                url
            ]
            
            result = subprocess.run(curl_cmd, capture_output=True, text=True, timeout=5)
            
            print(f"状态码: {result.returncode}")
            print(f"响应: {result.stdout}")
            
            if result.returncode == 0 and "access_token" in result.stdout:
                print(f"✅ 端口 {port} 登录成功！")
                return port
            elif "Connection refused" in result.stderr:
                print(f"❌ 端口 {port} 连接被拒绝（服务器未运行）")
            else:
                print(f"❌ 端口 {port} 其他错误: {result.stderr}")
                
        except Exception as e:
            print(f"❌ 端口 {port} 测试失败: {str(e)}")
    
    return None

def fix_frontend_config():
    """修复前端配置"""
    
    print("\n=== 检查和修复前端配置 ===")
    
    user_store_path = "../uniapp-site-manager/stores/user.js"
    
    if not os.path.exists(user_store_path):
        print("❌ 找不到前端用户store文件")
        return False
    
    # 读取当前配置
    with open(user_store_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("当前API配置:")
    
    # 找出所有API地址
    api_urls = []
    for line in content.split('\n'):
        if 'http://localhost:' in line and 'api' in line:
            api_urls.append(line.strip())
    
    for url in api_urls:
        print(f"  {url}")
    
    # 检查是否需要修复
    if "localhost:8000" not in content:
        print("⚠️  前端API地址不是 localhost:8000")
        print("建议修改为 localhost:8000")
        
        # 备份原文件
        backup_path = user_store_path + ".backup"
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ 已备份到 {backup_path}")
        
        # 修复配置
        fixed_content = content.replace('localhost:8001', 'localhost:8000')
        fixed_content = fixed_content.replace('localhost:8002', 'localhost:8000')
        fixed_content = fixed_content.replace('localhost:8003', 'localhost:8000')
        
        with open(user_store_path, 'w', encoding='utf-8') as f:
            f.write(fixed_content)
        print("✅ 前端API地址已修复为 localhost:8000")
        
        return True
    else:
        print("✅ 前端API地址配置正确")
        return True

def start_simple_server():
    """启动简单服务器"""
    
    print("\n=== 启动简单服务器 ===")
    
    try:
        import subprocess
        import time
        
        # 终止可能占用端口的进程
        subprocess.run(['pkill', '-f', 'uvicorn'], capture_output=True)
        subprocess.run(['pkill', '-f', 'python.*main'], capture_output=True)
        
        time.sleep(2)
        
        # 启动服务器
        server_cmd = ['python', 'start_minimal.py']
        
        print("正在启动服务器...")
        process = subprocess.Popen(server_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # 等待服务器启动
        time.sleep(5)
        
        # 检查服务器是否运行
        try:
            response = requests.get('http://localhost:8002/health', timeout=2)
            if response.status_code == 200:
                print("✅ 服务器启动成功 (端口 8002)")
                return 8002
        except:
            pass
        
        try:
            response = requests.get('http://localhost:8000/health', timeout=2)
            if response.status_code == 200:
                print("✅ 服务器启动成功 (端口 8000)")
                return 8000
        except:
            pass
        
        print("❌ 服务器启动失败")
        return None
        
    except Exception as e:
        print(f"❌ 启动服务器时出错: {str(e)}")
        return None

def provide_manual_steps():
    """提供手动解决步骤"""
    
    print("\n" + "="*60)
    print("手动解决登录问题的步骤:")
    print("="*60)
    
    print("\n1. 启动后端服务器:")
    print("   cd backend")
    print("   python start_minimal.py")
    print("   # 或者")
    print("   python -m app.main_simple")
    
    print("\n2. 检查服务器是否运行:")
    print("   打开浏览器访问: http://localhost:8002")
    print("   应该看到服务器状态信息")
    
    print("\n3. 测试登录API:")
    print("   curl -X POST http://localhost:8002/api/auth/login \\")
    print("        -H 'Content-Type: application/json' \\")
    print("        -d '{\"username\":\"admin\",\"password\":\"admin123\"}'")
    
    print("\n4. 检查前端配置:")
    frontend_path = "../uniapp-site-manager/stores/user.js"
    print(f"   打开文件: {frontend_path}")
    print("   确保API地址为: http://localhost:8002/api/auth/login")
    
    print("\n5. 测试账户:")
    print("   用户名: admin")
    print("   密码: admin123")
    print("   用户名: test_user")  
    print("   密码: password123")
    
    print("\n6. 如果仍然有问题:")
    print("   - 检查浏览器控制台错误")
    print("   - 检查网络连接")
    print("   - 确认没有被防火墙阻挡")
    
    print("\n7. 前端调试:")
    print("   在浏览器开发者工具Network选项卡中")
    print("   观察登录请求是否发送成功")

def main():
    """主函数"""
    
    print("登录问题解决方案")
    print("=" * 50)
    
    # 1. 修复前端配置
    fix_frontend_config()
    
    # 2. 测试现有服务器
    working_port = test_login_with_curl()
    
    if working_port:
        print(f"\n✅ 找到工作的服务器端口: {working_port}")
        print("登录功能应该正常工作")
    else:
        print("\n❌ 没有找到工作的服务器")
        
        # 3. 尝试启动服务器
        server_port = start_simple_server()
        
        if server_port:
            time.sleep(2)
            working_port = test_login_with_curl()
    
    # 4. 提供手动步骤
    provide_manual_steps()
    
    print(f"\n{'='*60}")
    if working_port:
        print("✅ 登录功能已修复！")
        print(f"后端服务器运行在: http://localhost:{working_port}")
        print("请重新尝试登录APP")
    else:
        print("⚠️  需要手动启动服务器")
        print("请按照上面的步骤操作")

if __name__ == "__main__":
    main()