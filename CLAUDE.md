# 站点信息管理系统 - 项目分析报告

## 项目概述

这是一个现代化的**通信站点信息管理系统**，专门为运营商工程建网项目开发，采用 **UniApp + FastAPI** 全栈架构，实现从物料管理到规划、安装、验收的全链路闭环管控。

## 技术架构

### 前端 (UniApp)
- **框架**: UniApp (Vue 3) + Pinia状态管理
- **UI设计**: 现代化橙色主题设计 (#f97316)
- **平台支持**: Android原生应用 (当前版本)
- **构建工具**: Vite + uni-cli

### 后端 (FastAPI)
- **框架**: Python FastAPI 0.104.1
- **数据库**: SQLite (开发) / MySQL (生产)
- **认证**: JWT Token + RBAC权限模型
- **ORM**: SQLAlchemy 2.0.23
- **服务器**: Uvicorn

## 核心业务模块

### 1. 用户管理系统
- **角色体系**: admin (系统管理员) | manager (项目经理) | inspector (现场工程师) | user (普通用户)
- **权限模型**: 基于角色的访问控制(RBAC)
- **认证机制**: JWT Bearer Token，30分钟过期
- **默认账户**:
  - admin/admin123 (管理员)
  - inspector/inspector123 (检查员)
  - tom/tom123456 (Tom用户)
  - test_user/user123 (测试用户)

### 2. 站点管理系统
- **站点状态**: planning → construction → operational → maintenance
- **地理信息**: GPS坐标、地址、省市区三级联动
- **分配机制**: 站点与施工人员的关联管理
- **数据模型**: `backend/app/models/site.py:6-31`

### 3. 检查系统 (核心模块)
#### 检查模板系统
- **动态模板生成**: 基于站点类型自动生成检查清单
- **模板结构**: JSON格式存储，支持站点级和扇区级检查项
- **版本管理**: 模板版本控制机制

#### 检查执行流程
```
创建检查 → 选择站点 → 执行检查项 → 拍照记录 → 数据验证 → 提交审核 → 完成归档
```

#### 高级检查功能
- **GPS水印拍照**: 自动添加经纬度、时间戳、检查员信息
- **防篡改机制**: 文件哈希值、数字签名验证
- **离线支持**: IndexedDB + localStorage双重保障
- **实时同步**: 网络恢复后自动批量同步

### 4. 任务管理系统
#### 任务工作流
```
PENDING → ASSIGNED → ACCEPTED → IN_PROGRESS → SUBMITTED → UNDER_REVIEW → APPROVED/REJECTED → COMPLETED
```

#### 任务类型
- `opening_inspection`: 新站点设备安装任务
- `maintenance`: 维护检查任务
- `power_issue`: 断电问题处理
- `transmission_issue`: 传输问题
- `gps_issue`: GPS问题
- `signal_issue`: 信号问题

### 5. OMC系统集成
- **设备状态同步**: offline → online → activated
- **实时监控**: 基站设备状态查询
- **日志记录**: 完整的OMC操作审计日志
- **数据模型**: `backend/app/models/inspection.py:250-286`

## 关键技术特性

### 1. 离线优先架构
```javascript
// 离线存储策略: uniapp-site-manager/stores/offline.js:1-795
- IndexedDB主存储 (优先)
- localStorage备用存储
- 自动网络状态检测
- 智能同步队列管理
- 冲突检测与解决
```

### 2. GPS和位置服务
- **高精度定位**: GPS accuracy验证
- **逆地理编码**: 坐标转地址
- **照片地理标记**: 自动GPS水印
- **位置验证**: 现场位置与站点坐标匹配

### 3. 质量保证机制
- **数据验证规则**:
  - 天线方位角: 0-360度
  - 天线挂高: 0-100米  
  - 下倾角: 0-20度
  - 驻波比: 1.0-2.0
- **审核工作流**: 多级审批，完整审计追踪
- **评分系统**: 0-100分质量评分机制

### 4. 现代化UI设计
- **设计语言**: 橙色主题 (#f97316)，卡片式布局
- **响应式设计**: 适配多种屏幕尺寸
- **用户体验**: 手势操作、下拉刷新、无限滚动
- **离线指示**: 实时网络状态显示

## 项目文件结构

### 后端核心文件
```
backend/
├── app/
│   ├── api/          # API路由层
│   │   ├── auth.py   # 认证API (login/register/me)
│   │   ├── users.py  # 用户管理API
│   │   ├── sites.py  # 站点管理API
│   │   ├── inspections.py # 检查系统API (核心模块)
│   │   └── tasks.py  # 任务管理API
│   ├── models/       # 数据模型层
│   │   ├── user.py   # 用户模型
│   │   ├── site.py   # 站点模型
│   │   └── inspection.py # 检查系统模型 (复杂)
│   ├── core/         # 核心组件
│   │   ├── config.py # 配置管理
│   │   ├── database.py # 数据库连接
│   │   └── security.py # 安全组件
│   └── main.py       # 应用入口
└── start_backend.py  # 自动化启动脚本
```

### 前端核心文件
```
uniapp-site-manager/
├── pages/            # 页面组件
│   ├── home/         # 首页 (统计面板)
│   ├── site/         # 站点管理页面
│   ├── inspection/   # 检查系统页面 (核心功能)
│   ├── task/         # 任务管理页面
│   └── profile/      # 个人中心
├── stores/           # 状态管理 (Pinia)
│   ├── user.js       # 用户状态管理
│   ├── site.js       # 站点状态管理
│   ├── inspection.js # 检查状态管理
│   └── offline.js    # 离线数据管理 (核心)
├── config/
│   └── api.js        # API配置管理
└── App.vue           # 应用根组件
```

## 重要实现细节

### 检查系统设计模式
检查系统采用**模板+实例**的设计模式:

1. **InspectionTemplate**: 定义检查模板结构
2. **SiteInspection**: 检查实例，关联特定站点和检查员
3. **InspectionCheckItem**: 具体检查项，支持扇区级细分
4. **InspectionPhoto**: 照片管理，包含GPS信息和防篡改机制

### 状态同步机制
系统实现了复杂的**三层状态同步**:
1. **本地状态**: Pinia store实时状态
2. **离线存储**: IndexedDB/localStorage持久化
3. **服务器状态**: FastAPI数据库同步

### 权限控制实现
前端权限控制: `uniapp-site-manager/stores/user.js:10-22`
```javascript
const canAccessTaskManagement = computed(() => isAdmin.value)
const canAccessSiteManagement = computed(() => isAdmin.value)
const canCreateTasks = computed(() => isAdmin.value)
```

## API端点总览

### 认证相关
- `POST /api/auth/login` - 用户登录
- `POST /api/auth/register` - 用户注册  
- `GET /api/auth/me` - 获取当前用户信息

### 核心业务API
- `GET /api/sites/` - 站点列表 (支持筛选)
- `POST /api/inspections/` - 创建检查记录
- `GET /api/inspections/detail/{id}` - 检查详情
- `POST /api/inspections/detail/{id}/photos` - 上传检查照片
- `GET /api/tasks/` - 任务列表
- `POST /api/tasks/{id}/review` - 任务审核

### 系统管理
- `GET /health` - 健康检查
- `GET /api/inspections/statistics/overview` - 检查统计
- `GET /api/tasks/statistics/overview` - 任务统计

## 业务流程核心

### 典型检查流程
1. **管理员**: 创建站点，分配给施工人员
2. **施工人员**: 接受任务，前往现场
3. **现场检查**: 按模板逐项检查，GPS拍照取证
4. **数据采集**: 天线参数、设备状态、环境信息
5. **提交审核**: 数据完整性验证后提交
6. **审核通过**: 管理员审核，评分，完成流程

### 关键业务规则
- **强制GPS验证**: 确保现场作业真实性
- **照片防篡改**: 哈希值验证，数字签名
- **状态机管理**: 严格的状态转换控制
- **权限隔离**: 用户只能操作分配给自己的任务

## 启动和部署

### 快速启动
```bash
# 后端自动化启动
python start_backend.py

# 前端开发
cd uniapp-site-manager
npm install && npm run dev
```

### 服务地址
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc

## 项目特色亮点

1. **企业级检查系统**: 完整的现场检查、拍照、审核工作流
2. **离线优先设计**: 支持断网环境下的数据采集和同步
3. **GPS防伪技术**: 照片自动水印，位置验证机制
4. **移动优先体验**: 专为现场作业优化的移动端UI
5. **一键部署脚本**: 自动环境配置、依赖安装、数据库初始化

## 技术债务和注意事项

1. **CORS配置**: 开发环境允许所有来源 (`allow_origins=["*"]`)
2. **默认密钥**: 需要在生产环境更换 `SECRET_KEY`
3. **文件权限**: uploads目录权限管理
4. **数据库**: 生产环境需要迁移到MySQL

## 扩展计划

根据设计文档，后续可能的扩展方向:
- **物料管理模块**: 设备申请、库存管理
- **知识库系统**: 技术文档、FAQ管理
- **报表系统**: Excel/PDF导出
- **AI辅助检查**: 图像识别、智能评分
- **IoT集成**: 设备状态自动采集

这是一个功能完整、架构合理的企业级移动应用，特别适合通信行业的现场作业管理场景。