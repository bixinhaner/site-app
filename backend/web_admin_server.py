#!/usr/bin/env python3
"""
简单的Web Admin后端服务器
专门为web admin提供必要的API服务
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn
import sqlite3
import os

app = FastAPI(title="Web Admin Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]

class Site(BaseModel):
    id: int
    site_name: str
    site_code: str
    status: str
    longitude: Optional[float] = None
    latitude: Optional[float] = None
    address: Optional[str] = None

class Inspection(BaseModel):
    id: str
    site_id: int
    status: str
    created_at: str
    completion_rate: Optional[float] = 0

class Task(BaseModel):
    id: str
    title: str
    status: str
    assigned_to: Optional[int] = None
    created_at: str

# Database setup
DB_PATH = "web_admin.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            full_name TEXT,
            role TEXT
        )
    """)
    
    # 创建站点表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY,
            site_name TEXT,
            site_code TEXT UNIQUE,
            status TEXT,
            longitude REAL,
            latitude REAL,
            address TEXT
        )
    """)
    
    # 插入测试用户
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, full_name, role)
            VALUES ('admin', 'admin123', 'Administrator', 'admin')
        """)
        cursor.execute("""
            INSERT OR IGNORE INTO users (username, password_hash, full_name, role)
            VALUES ('tom', 'tom123456', 'Tom Manager', 'manager')
        """)
    except:
        pass
    
    # 插入测试站点
    sites_data = [
        (1, "北京站点1", "BJ001", "operational", 116.4074, 39.9042, "北京市朝阳区"),
        (2, "上海站点1", "SH001", "construction", 121.4737, 31.2304, "上海市浦东新区"),
        (3, "广州站点1", "GZ001", "planning", 113.2644, 23.1291, "广州市天河区"),
    ]
    
    for site in sites_data:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO sites (id, site_name, site_code, status, longitude, latitude, address)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, site)
        except:
            pass
    
    conn.commit()
    conn.close()

# API路由
@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Web Admin Backend is running"}

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """用户登录"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT id, username, full_name, role FROM users WHERE username = ? AND password_hash = ?",
        (credentials.username, credentials.password)
    )
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user_id, username, full_name, role = user_data
    
    return LoginResponse(
        access_token=f"token_{username}_{user_id}",
        user={
            "id": user_id,
            "username": username,
            "full_name": full_name,
            "role": role
        }
    )

@app.get("/api/sites", response_model=List[Site])
async def get_sites():
    """获取站点列表"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT id, site_name, site_code, status, longitude, latitude, address FROM sites")
    sites_data = cursor.fetchall()
    conn.close()
    
    sites = []
    for row in sites_data:
        sites.append(Site(
            id=row[0],
            site_name=row[1],
            site_code=row[2],
            status=row[3],
            longitude=row[4],
            latitude=row[5],
            address=row[6]
        ))
    
    return sites

@app.get("/api/inspections", response_model=List[Inspection])
async def get_inspections():
    """获取检查列表"""
    # 模拟检查数据
    return [
        Inspection(
            id="insp_001",
            site_id=1,
            status="completed",
            created_at="2024-01-15T10:30:00Z",
            completion_rate=95.0
        ),
        Inspection(
            id="insp_002", 
            site_id=2,
            status="in_progress",
            created_at="2024-01-16T14:20:00Z",
            completion_rate=60.0
        )
    ]

@app.get("/api/tasks", response_model=List[Task])
async def get_tasks():
    """获取任务列表"""
    # 模拟任务数据
    return [
        Task(
            id="task_001",
            title="站点设备安装",
            status="in_progress",
            assigned_to=1,
            created_at="2024-01-15T09:00:00Z"
        ),
        Task(
            id="task_002",
            title="设备维护检查",
            status="pending",
            assigned_to=2,
            created_at="2024-01-16T11:00:00Z"
        )
    ]

@app.get("/api/statistics/overview")
async def get_statistics():
    """获取统计数据"""
    return {
        "sites": {
            "total": 3,
            "operational": 1,
            "construction": 1,
            "planning": 1
        },
        "inspections": {
            "total": 15,
            "completed": 10,
            "in_progress": 3,
            "pending": 2
        },
        "tasks": {
            "total": 20,
            "completed": 12,
            "in_progress": 5,
            "pending": 3
        }
    }

if __name__ == "__main__":
    print("正在启动Web Admin后端服务器...")
    print("初始化数据库...")
    init_db()
    print("数据库初始化完成")
    print("服务器地址: http://localhost:8000")
    print("API文档: http://localhost:8000/docs")
    print("健康检查: http://localhost:8000/health")
    print()
    print("可用的测试账户:")
    print("- admin/admin123 (管理员)")
    print("- tom/tom123456 (项目经理)")
    
    uvicorn.run(app, host="127.0.0.1", port=8000)