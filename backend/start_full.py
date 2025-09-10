#!/usr/bin/env python3
"""
完整版启动脚本 - 包含所有API功能
"""

if __name__ == "__main__":
    import uvicorn
    print("启动完整版服务器...")
    print("包含功能:")
    print("- 用户认证 (/api/auth/*)")
    print("- 用户管理 (/api/users/*)")
    print("- 站点管理 (/api/sites/*)")
    print("- 检查管理 (/api/inspections/*)")
    print("- 增强检查管理 (/api/inspections/*)")
    print("")
    print("访问 http://localhost:8002/docs 查看API文档")
    print("访问 http://localhost:8002/health 检查服务器状态")
    print("")
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=8002, reload=True)