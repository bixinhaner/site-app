# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

- 如果需要关闭、启动、重启后台服务，请告诉使用者，让使用者自己操作。
- github推送信息用中文。

# 站点信息管理系统

现代化的**通信站点信息管理系统**，采用 **UniApp + FastAPI + Vue Web Admin** 三端架构，为运营商工程建网项目提供从物料管理到规划、安装、验收的全链路闭环管控。

## 技术架构

### 后端 (FastAPI)
- **框架**: Python FastAPI 0.104.1 + SQLAlchemy 2.0.23
- **数据库**: SQLite (开发) / MySQL (生产) 
- **认证**: JWT Token + RBAC权限模型，30分钟过期
- **服务器**: Uvicorn

### 前端 (三端架构)
1. **UniApp移动端**: Vue 3 + Pinia，支持Android原生应用
2. **Web管理端**: Vue 3 + Element Plus + Vite，设备货物管理
3. **主题设计**: 现代化橙色主题 (#f97316)

## 开发环境设置

### 后端服务启动
```bash
# 一键启动（推荐）- 自动创建venv、安装依赖、初始化数据库
python start_backend.py

# 手动启动
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 网络访问模式（移动端开发必需）
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 终止所有后端服务
pkill -f "uvicorn.*8000"
```

### 前端启动
```bash
# UniApp移动端
cd uniapp-site-manager
npm install
npm run dev                    # 本地开发
npm run build:h5:prod         # 构建H5生产版
npm run build:prod            # 构建App生产版

# Web管理端
cd web-admin  
npm install
npm run dev                    # 开发服务器 (通常在5173端口)
npm run build                  # 生产构建
```

### 测试验证
```bash
# 后端API测试
python backend/test_login.py
python backend/test_task_api.py

# 健康检查
curl http://localhost:8000/health
```

## 核心业务架构

### 用户权限体系
- **admin**: 系统管理员 (全权限)
- **manager**: 项目经理 (站点和人员管理)  
- **inspector**: 现场工程师 (检查和数据录入)
- **user**: 普通用户

**默认测试账户**:
- admin/admin123, inspector/inspector123, tom/tom123456, test_user/user123

### 工作流状态机
```
工单流程: PENDING → ASSIGNED → ACCEPTED → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED/REJECTED → COMPLETED
站点状态: planning → construction → operational → maintenance  
设备状态: offline → online → activated
```

### 📡 基站层级结构说明

  🏢 站点级 (Site Level)

  - 定义: 一个物理站点位置
  - 包含: 多个方向（扇区）+ 多个频段的基站设备
  - 例子: "北京朝阳01站"

  📍 扇区级 (Sector Level)

  - 定义: 一个特定方向（通常120°覆盖范围）
  - 包含: 该方向上的多个频段基站设备
  - 标识: sector_id (如: 1, 2, 3)
  - 例子: "扇区1" 包含 n41、n78、n3 三个频段

  📱 小区级 (Cell Level)

  - 定义: 具体方向 + 具体频段的唯一基站设备
  - 标识: cell_id = sector_id + "_" + band (如: 1_n41, 2_n78)
  - 对应关系: 一个小区 = 一台物理设备
  - 例子: "1_n41" 是扇区1上的n41频段设备

### 检查系统核心设计
采用**模板+实例**模式:
1. **InspectionTemplate**: JSON格式检查模板，支持站点级和扇区级检查项
2. **SiteInspection**: 检查实例，关联特定站点和检查员
3. **InspectionCheckItem**: 具体检查项，支持多频段扇区细分
4. **InspectionPhoto**: GPS水印照片，包含防篡改机制

## 关键技术特性

### 离线优先架构 
- **存储策略**: IndexedDB主存储 + localStorage备用
- **同步机制**: 三层状态同步 (本地状态 ↔ 离线存储 ↔ 服务器)
- **智能队列**: 网络恢复后自动批量同步，冲突检测与解决

### GPS和位置服务
- **高精度定位**: GPS accuracy验证，现场位置与站点坐标匹配
- **水印技术**: 自动添加经纬度、时间戳、检查员信息到照片
- **防篡改**: 文件哈希值验证 + 数字签名

### 用户行为日志系统
- **全链路追踪**: `stores/logger.js` + `utils/api-interceptor.js`
- **会话管理**: 自动生成session ID，记录完整用户轨迹  
- **API拦截**: 自动记录所有请求响应，支持离线日志同步

### 数据验证规则
- **天线参数**: 方位角(0-360°)，挂高(0-100m)，下倾角(0-20°)，驻波比(1.0-2.0)
- **审核工作流**: 多级审批，完整审计追踪，0-100分质量评分

## 项目结构要点

### 后端核心
```
backend/app/
├── api/                    # 路由层
│   ├── auth.py            # JWT认证 (/api/auth/login,register,me)
│   ├── work_orders.py     # 工单管理（核心业务API）
│   ├── inspections.py     # 检查系统API  
│   ├── logs.py            # 用户行为日志API
│   └── equipment.py       # 设备物料管理
├── models/                # SQLAlchemy模型
│   ├── inspection.py      # 复杂检查系统模型
│   ├── work_order.py      # 工单流程模型
│   └── user_log.py        # 日志模型
├── core/
│   ├── config.py          # 环境配置 (JWT, 文件上传, CORS)
│   ├── database.py        # 数据库连接
│   └── security.py        # 安全组件
└── utils/
    └── file_handler.py    # 文件上传和水印处理
```

### 前端核心  
```
uniapp-site-manager/
├── stores/                # Pinia状态管理
│   ├── user.js           # 用户认证和权限控制
│   ├── offline.js        # 离线数据管理（核心）
│   ├── logger.js         # 用户行为日志
│   └── inspection.js     # 检查状态管理
├── config/
│   ├── env.js            # 环境配置（API_BASE_URL动态配置）
│   └── api.js            # API端点定义
├── utils/
│   ├── api-interceptor.js # API请求拦截器
│   └── watermark.js      # GPS水印处理
└── pages/
    ├── login/            # 登录认证
    ├── workorder/        # 工单管理（核心功能）
    └── inspection/       # 现场检查系统
```

## API端点概览

### 核心业务API
- `POST /api/auth/login` - 用户登录
- `GET /api/work-orders` - 工单列表
- `GET /api/work-orders/{id}` - 工单详情  
- `POST /api/work-orders/{id}/items/{item_id}` - 更新检查项
- `POST /api/work-orders/{id}/photos` - 上传检查照片
- `POST /api/work-orders/{id}/complete` - 完成工单
- `GET /api/inspections/detail/{id}` - 检查详情
- `POST /api/logs` - 创建用户日志
- `POST /api/logs/batch` - 批量同步日志

### 管理API
- `GET /health` - 健康检查
- `GET /docs` - Swagger API文档  
- `GET /redoc` - ReDoc API文档

## 网络配置要点

### 开发环境网络设置
```javascript
// uniapp-site-manager/config/env.js
// 根据实际网络环境动态配置
config.API_BASE_URL = 'http://192.168.31.184:8000'  // 局域网IP
config.API_BASE_URL = 'http://127.0.0.1:8000'       // 本地开发
```

### 后端CORS配置
```python
# backend/app/core/config.py
ALLOWED_HOSTS_STR: str = "*"  # 开发环境允许所有来源
```

## 重要业务规则

### 检查系统业务逻辑
1. **强制GPS验证**: 确保现场作业真实性，照片必须包含位置信息
2. **模板版本控制**: 检查模板支持版本管理，向下兼容
3. **状态机管理**: 严格的状态转换控制，防止非法状态切换
4. **权限隔离**: 用户只能操作分配给自己的工单和站点

### 数据同步策略
1. **优先本地**: 离线环境下优先使用本地存储
2. **增量同步**: 网络恢复后仅同步变更数据，减少带宽消耗
3. **冲突解决**: 基于时间戳的冲突检测和解决机制

## 文件和目录约定

### 上传文件管理
- **路径**: `backend/uploads/` (自动创建)
- **权限**: 确保写入权限，生产环境注意安全配置
- **格式**: 支持 jpg,jpeg,png,pdf，最大10MB
- **命名**: UUID格式防止冲突，支持水印后缀

### 环境配置
- **后端**: `backend/.env` (从.env.example复制)
- **前端**: `uniapp-site-manager/config/env.js` (动态环境配置)
- **数据库**: SQLite开发环境，生产环境迁移MySQL

## 调试和故障排除

### 常见问题解决
1. **登录连接失败**: 检查API_BASE_URL配置，确认后端服务运行在0.0.0.0
2. **端口冲突**: 使用 `lsof -i :8000` 检查端口占用
3. **数据库初始化**: 运行 `python start_backend.py` 自动创建默认数据
4. **权限问题**: 检查uploads目录权限，确保可写入

### 调试工具
- **后端日志**: Uvicorn控制台输出
- **前端调试**: 浏览器开发者工具，HBuilderX控制台
- **API测试**: 使用 `/docs` Swagger界面进行API测试
- **数据库**: SQLite Browser查看数据表结构

这是一个功能完整、架构合理的企业级移动应用，特别适合通信行业的现场作业管理场景。系统采用离线优先设计，支持断网环境下的数据采集和同步，具备GPS防伪技术和完整的审核工作流。