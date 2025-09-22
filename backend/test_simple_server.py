#!/usr/bin/env python3
"""
简单的后端测试服务器
用于测试基本的API功能
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI(title="简单测试服务器")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "服务器运行正常"}

@app.get("/")
async def root():
    return {"message": "简单测试服务器", "version": "1.0.0"}

@app.post("/api/auth/login")
async def test_login(credentials: dict):
    # 简单的测试登录
    print(f"收到登录请求: {credentials}")
    username = credentials.get("username", "")
    password = credentials.get("password", "")
    print(f"用户名: '{username}', 密码: '{password}'")
    
    if (username == "tom" and password == "tom123456") or (username == "admin" and password == "admin123"):
        print("登录成功")
        
        # 根据用户名返回不同的用户信息
        if username == "admin":
            user_info = {
                "id": 2,
                "username": "admin",
                "full_name": "Admin User",
                "role": "admin"
            }
        else:  # tom
            user_info = {
                "id": 1,
                "username": "tom", 
                "full_name": "Tom User",
                "role": "admin"
            }
            
        return {
            "access_token": "test_token_123456",
            "user": user_info
        }
    else:
        print(f"登录失败: username='{username}', password='{password}'")
        raise HTTPException(status_code=401, detail="用户名或密码错误")

@app.post("/api/logs")
async def create_log(log_data: dict):
    print(f"收到日志: {log_data}")
    return {"success": True, "log_id": 12345}

@app.post("/api/logs/batch")
async def create_logs_batch(batch_data: dict):
    logs = batch_data.get("logs", [])
    print(f"收到批量日志: {len(logs)} 条")
    for i, log in enumerate(logs):
        print(f"  日志 {i+1}: {log.get('action', 'unknown')} - {log.get('timestamp', 'no time')}")
    
    return {
        "success": True,
        "created_count": len(logs),
        "total_count": len(logs)
    }

# 添加模拟的业务API端点

@app.get("/api/equipment/")
async def get_equipment(skip: int = 0, limit: int = 20):
    # 模拟设备数据
    return {
        "items": [
            {
                "id": 1,
                "name": "基站设备A",
                "type": "eNodeB",
                "model": "5G-2000",
                "status": "active",
                "location": "站点001"
            },
            {
                "id": 2,
                "name": "传输设备B", 
                "type": "Transport",
                "model": "TX-1000",
                "status": "maintenance",
                "location": "站点002"
            }
        ],
        "total": 2,
        "skip": skip,
        "limit": limit
    }

@app.get("/api/stock/inventory/dashboard")
async def get_inventory_dashboard():
    # 模拟库存仪表板数据
    return {
        "total_items": 150,
        "low_stock_items": 5,
        "out_of_stock_items": 2,
        "pending_orders": 8,
        "recent_activities": [
            {
                "id": 1,
                "action": "入库",
                "item": "5G模块",
                "quantity": 10,
                "date": "2025-09-22"
            }
        ]
    }

@app.get("/api/inspections/")
async def get_inspections(skip: int = 0, limit: int = 20):
    # 模拟检查数据
    return {
        "items": [
            {
                "id": 1,
                "site_name": "站点001",
                "inspector": "张工程师",
                "status": "completed",
                "created_at": "2025-09-22T10:00:00Z",
                "score": 95
            },
            {
                "id": 2,
                "site_name": "站点002", 
                "inspector": "李工程师",
                "status": "in_progress",
                "created_at": "2025-09-22T09:30:00Z",
                "score": null
            }
        ],
        "total": 2,
        "skip": skip,
        "limit": limit
    }

@app.get("/api/work-orders")
async def get_work_orders(skip: int = 0, limit: int = 20):
    # 模拟工单数据
    return {
        "items": [
            {
                "id": 1,
                "title": "站点001设备检查",
                "type": "inspection",
                "status": "pending",
                "priority": "high",
                "assignee": "张工程师",
                "created_at": "2025-09-22T10:00:00Z",
                "due_date": "2025-09-23T18:00:00Z"
            },
            {
                "id": 2,
                "title": "站点002故障维修",
                "type": "maintenance", 
                "status": "in_progress",
                "priority": "urgent",
                "assignee": "李工程师",
                "created_at": "2025-09-21T14:30:00Z",
                "due_date": "2025-09-22T20:00:00Z"
            }
        ],
        "total": 2,
        "skip": skip,
        "limit": limit
    }

if __name__ == "__main__":
    print("启动简单测试服务器...")
    print("服务器地址: http://0.0.0.0:8000")
    print("本地访问: http://localhost:8000")
    print("网络访问: http://192.168.x.x:8000")
    print("健康检查: http://0.0.0.0:8000/health")
    uvicorn.run(app, host="0.0.0.0", port=8000)