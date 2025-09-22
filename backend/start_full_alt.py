#!/usr/bin/env python3
"""
完整服务启动脚本 - 使用备用端口8001
"""

if __name__ == "__main__":
    import uvicorn
    
    print("启动完整服务器（端口8001）...")
    print("访问 http://localhost:8001 查看状态")
    print("访问 http://localhost:8001/docs 查看API文档")
    
    # 使用不同端口避免冲突
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)