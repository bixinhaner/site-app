# 站点信息管理APP详细设计方案

## 文档信息
- **项目名称**: 站点信息管理APP
- **文档版本**: v1.0
- **创建日期**: 2025-08-20
- **文档类型**: 详细设计方案

---

## 目录
1. [项目概述](#项目概述)
2. [系统架构设计](#系统架构设计)
3. [详细功能模块设计](#详细功能模块设计)
4. [数据库设计](#数据库设计)
5. [开发计划和里程碑](#开发计划和里程碑)
6. [总结和建议](#总结和建议)

---

## 1. 项目概述

### 1.1 需求背景
随着公司业务发展，近几年我司接手越来越多运营商工程建网项目，在验收过程中发现物料丢失、未按规划安装、安装质量差、安装参数不上报、验收进度慢、验收检查成本高、验收报告质量参差不齐、报告审核慢（多轮沟通多次上站）等一系列问题，严重影响工程质量和效率。

我们希望通过手机APP来规范管理现场施工过程，提供简便快捷的工具，实现从物料-规划-安装-验收全链路闭环管控，减少人为差错，提升工程质量，提高工作效率的目标。

### 1.2 项目目标
构建一个移动端APP，实现运营商工程建网项目的全生命周期管理，从物料管理到规划、安装、验收的闭环控制，提升工程质量和效率。

### 1.3 核心业务流程
```
物料申请 → 规划导入 → 人员分配 → 现场施工 → 数据采集 → 验收审核 → 报告归档
```

### 1.4 功能模块优先级
| No | 功能模块 | 建议开发优先顺序 |
|----|----------|------------------|
| 1 | 用户管理模块 | 1 |
| 2 | 规划数据管理模块 | 1 |
| 3 | 物料管理模块 | 3 |
| 4 | 现场信息管理模块 | 1 |
| 5 | 信息查询模块 | 3 |
| 6 | 报表输出模块 | 2 |
| 7 | 日志管理模块 | 2 |

---

## 2. 系统架构设计

### 2.1 技术架构
```
┌─────────────────┐    ┌─────────────────┐
│   移动端APP     │    │   Web管理端     │
│ (React Native)  │    │   (React/Vue)   │
└─────────────────┘    └─────────────────┘
         │                      │
         └──────────┬───────────┘
                    │
         ┌─────────────────┐
         │   API网关       │
         │ (Spring Gateway)│
         └─────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
┌─────────┐  ┌─────────┐  ┌─────────┐
│用户服务 │  │业务服务 │  │文件服务 │
│ (Auth)  │  │(Business)│  │ (File)  │
└─────────┘  └─────────┘  └─────────┘
    │               │               │
    └───────────────┼───────────────┘
                    │
    ┌─────────────────────────────────┐
    │         数据存储层             │
    │ MySQL + Redis + MinIO + ES     │
    └─────────────────────────────────┘
```

### 2.2 技术栈选择
- **移动端**: React Native（iOS/Android统一开发）
- **后端服务**: Spring Boot + Spring Security + Spring Data JPA
- **数据库**: MySQL 8.0（主从架构）
- **缓存**: Redis Cluster
- **文件存储**: MinIO对象存储
- **搜索引擎**: Elasticsearch（日志检索）
- **消息队列**: RabbitMQ
- **监控**: Prometheus + Grafana

### 2.3 部署架构
- **客户端**: iOS/Android APP + PWA
- **服务端**: 微服务架构，Docker容器化部署
- **数据库**: MySQL主从 + Redis集群
- **文件存储**: MinIO对象存储
- **搜索引擎**: Elasticsearch（日志检索）
- **负载均衡**: Nginx + Kubernetes Ingress
- **CI/CD**: GitLab CI + Docker + Kubernetes

---

## 3. 详细功能模块设计

### 3.1 用户管理模块（优先级1）

#### 3.1.1 用户注册流程
```
用户输入信息 → 短信验证 → 角色申请 → 管理员审核 → 账号激活
```

#### 3.1.2 核心功能
- **用户注册**: 手机号、姓名、公司、角色申请
- **身份验证**: 短信验证码、JWT Token管理
- **权限控制**: RBAC权限模型，支持角色继承
- **用户管理**: 用户CRUD、状态管理、批量操作

#### 3.1.3 权限矩阵
| 角色 | 规划管理 | 物料管理 | 现场管理 | 信息查询 | 报表输出 | 用户管理 | 日志管理 |
|------|----------|----------|----------|----------|----------|----------|----------|
| 系统管理员 | 读写 | 读写 | 读写 | 读写 | 读写 | 读写 | 读写 |
| 网络规划员 | 读写 | 读 | 读 | 读写 | 读 | 读 | 读 |
| 现场施工员 | 读(分配站点) | 读 | 读写(分配站点) | 读写 | 读 | 读 | 读 |
| 报告审核员 | 读 | 读 | 读写 | 读写 | 读写 | 读 | 读写 |

#### 3.1.4 技术实现要点
- **短信验证**: 集成阿里云/腾讯云短信服务
- **JWT Token**: 支持刷新令牌机制
- **权限缓存**: Redis缓存用户权限信息
- **密码策略**: 强密码规则、定期更换提醒

### 3.2 规划数据管理模块（优先级1）

#### 3.2.1 数据结构设计
```json
{
  "siteInfo": {
    "siteId": "string",
    "siteName": "string", 
    "frequency": ["string"],
    "sectorCount": "number",
    "sectors": [{
      "sectorId": "string",
      "azimuth": "number",
      "tilt": "number", 
      "antennaPort": "string",
      "height": "number"
    }],
    "switchConfig": {},
    "assignedUser": "string",
    "status": "string",
    "coordinates": {
      "latitude": "number",
      "longitude": "number"
    }
  }
}
```

#### 3.2.2 核心功能
- **数据导入**: Excel批量导入，数据格式验证
- **数据编辑**: 在线编辑器，实时保存
- **版本管理**: 变更历史，回滚功能
- **站点分配**: 施工人员分配，权限自动更新
- **数据验证**: 参数合规性检查

#### 3.2.3 技术实现要点
- **Excel解析**: Apache POI解析Excel文件
- **数据验证**: JSR-303注解验证 + 自定义验证器
- **版本控制**: 基于时间戳的版本管理
- **批量操作**: 支持批量导入、批量分配

### 3.3 现场信息管理模块（优先级1）

#### 3.3.1 检查模板结构
```json
{
  "checkTemplate": {
    "siteId": "string",
    "checkLevels": [{
      "level": "站点级安装检查",
      "items": [{
        "itemId": "string",
        "itemName": "string",
        "photoRequired": true,
        "photoDescription": "string",
        "dataRequired": true,
        "dataType": "number|string|select",
        "dataValidation": {
          "min": "number",
          "max": "number", 
          "options": ["string"]
        },
        "assignedRole": "string",
        "status": "pending|completed|rejected"
      }]
    }]
  }
}
```

#### 3.3.2 检查项详细定义

**站点级安装检查项**
| 检查项 | 拍照要求 | 数据填写 | 填写人 |
|--------|----------|----------|--------|
| Picture of Tower ID with Coordinate | 站点大门 | - | 施工队 |
| Full Picture of Tower&Antenna Height Check | 全塔 | 挂高 | 施工队 |
| Picture of Cabinet installation Environment | 机柜全景 | - | 施工队 |
| Picture of Fixed Cabinet | 机柜内底部 | - | 施工队 |
| Picture of External Cabinet Grounding | 接地线对端 | - | 施工队 |
| Picture of Dust Filter | 机柜内底部 | - | 施工队 |
| Picture of Fan Power Connection | 机柜内风扇电源线 | - | 施工队 |
| Picture of Air Breaker | 指向连接的空开 | 空开容量 | 施工队 |
| Picture of Rectifier Capacity | 全部电源模块状态 | 电源模块容量 | 施工队 |
| Screen Shoot of Hardware Alarm Check by NOC | 网管基站告警 | 提供截图 | NOC |
| Post-Installation Check | 维护窗、机柜门关闭，清理废弃物 | 提供照片 | 施工队 |

**小区级安装检查项**
| 检查项 | 拍照要求 | 数据填写 | 填写人 |
|--------|----------|----------|--------|
| Antenna downtilt check | 坡度仪值 | 下倾角值 | 施工队 |
| Azimuth check | 天线覆盖方向，罗盘值 | 方位角值 | 施工队 |
| RRU installation stability check | 基站和抱杆连接处 | - | 施工队 |
| RRU connections check | 基站下部、侧部线缆连接处 | - | 施工队 |
| RRU cable check | 基站线缆塔上水平走线 | - | 施工队 |
| Antenna connections check - Sector 1 | 天线底部线缆连接处 | - | 施工队 |
| GPS antenna connection check | GPS天线下部线缆连接处 | - | 施工队 |
| RRU Grounding check | 塔上地排 | - | 施工队 |
| VSWR check | 网管查询截图 | 驻波比值 | NOC |
| AISG connection check - Sector 1 | 网管查询截图 | - | NOC |
| Fiber and power cable bundle&routing check | 基站线缆沿塔向下走线 | - | 施工队 |
| L2300 MHz power cable check - Sector 1 | 4.0mm线缆 | - | 施工队 |
| SN Check | 基站铭牌 | - | 施工队 |

#### 3.3.3 核心功能
- **模板生成**: 基于规划数据自动生成检查模板
- **离线采集**: 本地存储，支持断网操作
- **照片管理**: 
  - 强制实时拍照（禁用相册选择）
  - GPS水印（经纬度、时间戳）
  - 照片压缩和加密上传
- **数据验证**: 实时校验，完整性检查
- **提交流程**: 本地保存 → 数据校验 → 网络上传 → 审核流程

#### 3.3.4 数据验证规则
- **天线方向角**: 0-360度
- **天线挂高**: 0-100米
- **下倾角**: 0-20度
- **驻波比**: 1.0-2.0
- **GPS坐标**: 有效的经纬度范围

#### 3.3.5 审核工作流
```
数据提交 → 完整性检查 → 待审核 → 审核员审核 → [通过/驳回] → 归档/修改
```

#### 3.3.6 技术实现要点
- **离线存储**: SQLite本地数据库
- **照片水印**: Canvas绘制GPS和时间信息
- **文件上传**: 分片上传，断点续传
- **数据同步**: 网络恢复时自动同步

### 3.4 报表输出模块（优先级2）

#### 3.4.1 报表类型
- **施工进度报表**: 按时间、区域、施工队统计
- **质量检查报表**: 检查项通过率、问题分析
- **物料使用报表**: 物料消耗、库存统计
- **施工队评分报表**: 质量评分、工期统计

#### 3.4.2 报表模板设计
```json
{
  "progressReport": {
    "title": "施工进度报表",
    "period": "2025-01-01 to 2025-01-31",
    "summary": {
      "totalSites": 100,
      "completedSites": 85,
      "inProgressSites": 10,
      "pendingSites": 5
    },
    "details": [{
      "region": "区域A",
      "contractor": "施工队1", 
      "siteCount": 20,
      "completedCount": 18,
      "completionRate": "90%"
    }]
  }
}
```

#### 3.4.3 导出功能
- **Excel导出**: 支持多Sheet、图表、样式
- **PDF报告**: 格式化报告模板
- **数据筛选**: 时间范围、站点、人员等多维度筛选

#### 3.4.4 技术实现要点
- **Excel生成**: Apache POI生成复杂Excel报表
- **PDF生成**: iText生成PDF报告
- **图表生成**: ECharts生成图表，导出为图片

### 3.5 日志管理模块（优先级2）

#### 3.5.1 日志类型
- **操作日志**: 用户操作、数据变更
- **系统日志**: 系统运行、性能监控
- **业务日志**: 业务流程、状态变更
- **安全日志**: 登录、权限变更

#### 3.5.2 日志格式
```json
{
  "logEntry": {
    "id": "string",
    "timestamp": "2025-01-01T10:00:00Z",
    "level": "INFO|WARN|ERROR",
    "module": "USER|SITE|MATERIAL|INSPECTION",
    "action": "CREATE|UPDATE|DELETE|LOGIN|LOGOUT",
    "userId": "string",
    "userIp": "string",
    "details": {
      "targetId": "string",
      "beforeValue": {},
      "afterValue": {},
      "description": "string"
    }
  }
}
```

#### 3.5.3 技术实现要点
- **日志收集**: Spring AOP拦截器自动记录
- **日志存储**: Elasticsearch存储，支持全文检索
- **日志分析**: Kibana可视化分析
- **日志轮转**: 按时间和大小自动轮转

### 3.6 物料管理模块（优先级3）

#### 3.6.1 物料档案管理
```json
{
  "material": {
    "id": "string",
    "name": "string",
    "category": "基站设备|天线|线缆|工具",
    "model": "string",
    "specifications": {
      "brand": "string",
      "power": "string",
      "frequency": "string"
    },
    "unit": "台|米|个",
    "currentStock": 100,
    "minStock": 10,
    "maxStock": 1000,
    "price": 1000.00
  }
}
```

#### 3.6.2 核心功能
- **物料档案**: 物料类型、规格、供应商管理
- **需求计划**: 基于站点类型自动匹配物料需求
- **申请流程**: 申请 → 审核 → 分发 → 签收
- **库存管理**: 入库、出库、盘点、预警

#### 3.6.3 申请流程
```
需求分析 → 物料申请 → 库管审核 → 领导审批 → 物料分发 → 现场签收
```

### 3.7 信息查询模块（优先级3）

#### 3.7.1 知识库内容
- **技术文档**: 产品手册、安装指南、规范要求
- **工具清单**: 安装工具列表、使用说明
- **安全指导**: 施工安全规范、应急处理
- **FAQ管理**: 常见问题收集、答案维护
- **通讯录**: 各角色联系人信息

#### 3.7.2 文档管理系统
```json
{
  "document": {
    "id": "string",
    "title": "string",
    "category": "技术文档|安全指导|FAQ",
    "content": "string",
    "attachments": ["string"],
    "version": "string",
    "author": "string",
    "createTime": "2025-01-01T10:00:00Z",
    "updateTime": "2025-01-01T10:00:00Z"
  }
}
```

---

## 4. 数据库设计

### 4.1 数据库架构
- **主数据库**: MySQL 8.0，存储业务数据
- **缓存数据库**: Redis，存储会话和缓存数据
- **搜索引擎**: Elasticsearch，存储日志和搜索数据
- **文件存储**: MinIO，存储图片和文档

### 4.2 核心数据表设计

#### 4.2.1 用户管理相关表
```sql
-- 用户表
CREATE TABLE users (
    id VARCHAR(32) PRIMARY KEY COMMENT '用户ID',
    phone VARCHAR(11) UNIQUE NOT NULL COMMENT '手机号',
    name VARCHAR(50) NOT NULL COMMENT '姓名',
    company VARCHAR(100) COMMENT '公司名称',
    role_id VARCHAR(32) COMMENT '角色ID',
    password_hash VARCHAR(255) COMMENT '密码哈希',
    status ENUM('pending', 'active', 'disabled') DEFAULT 'pending' COMMENT '用户状态',
    last_login_time TIMESTAMP NULL COMMENT '最后登录时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_phone (phone),
    INDEX idx_role (role_id),
    INDEX idx_status (status)
) COMMENT='用户表';

-- 角色权限表
CREATE TABLE roles (
    id VARCHAR(32) PRIMARY KEY COMMENT '角色ID',
    name VARCHAR(50) NOT NULL COMMENT '角色名称',
    code VARCHAR(50) UNIQUE NOT NULL COMMENT '角色代码',
    permissions JSON COMMENT '权限配置',
    description TEXT COMMENT '角色描述',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_code (code)
) COMMENT='角色表';

-- 权限表
CREATE TABLE permissions (
    id VARCHAR(32) PRIMARY KEY COMMENT '权限ID',
    name VARCHAR(50) NOT NULL COMMENT '权限名称',
    code VARCHAR(50) UNIQUE NOT NULL COMMENT '权限代码',
    module VARCHAR(50) NOT NULL COMMENT '所属模块',
    action VARCHAR(50) NOT NULL COMMENT '操作类型',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_code (code),
    INDEX idx_module (module)
) COMMENT='权限表';
```

#### 4.2.2 站点管理相关表
```sql
-- 站点基础信息表
CREATE TABLE sites (
    id VARCHAR(32) PRIMARY KEY COMMENT '站点ID',
    site_name VARCHAR(100) NOT NULL COMMENT '站点名称',
    site_code VARCHAR(50) UNIQUE COMMENT '站点编码',
    site_type VARCHAR(50) COMMENT '站点类型',
    latitude DECIMAL(10,7) COMMENT '纬度',
    longitude DECIMAL(10,7) COMMENT '经度',
    address TEXT COMMENT '站点地址',
    frequency_bands JSON COMMENT '频段信息',
    sector_count INT DEFAULT 3 COMMENT '扇区数量',
    assigned_user_id VARCHAR(32) COMMENT '分配施工人员ID',
    status ENUM('planning', 'assigned', 'in_progress', 'completed', 'accepted') DEFAULT 'planning' COMMENT '站点状态',
    planned_start_date DATE COMMENT '计划开工日期',
    planned_end_date DATE COMMENT '计划完工日期',
    actual_start_date DATE COMMENT '实际开工日期', 
    actual_end_date DATE COMMENT '实际完工日期',
    created_by VARCHAR(32) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_site_code (site_code),
    INDEX idx_assigned_user (assigned_user_id),
    INDEX idx_status (status),
    INDEX idx_created_by (created_by)
) COMMENT='站点基础信息表';

-- 站点扇区配置表
CREATE TABLE site_sectors (
    id VARCHAR(32) PRIMARY KEY COMMENT '扇区ID',
    site_id VARCHAR(32) NOT NULL COMMENT '站点ID',
    sector_id VARCHAR(10) NOT NULL COMMENT '扇区编号',
    azimuth DECIMAL(5,2) COMMENT '方位角',
    tilt DECIMAL(4,2) COMMENT '下倾角',
    antenna_port VARCHAR(50) COMMENT '天线端口',
    height DECIMAL(5,2) COMMENT '挂高',
    antenna_model VARCHAR(100) COMMENT '天线型号',
    rru_model VARCHAR(100) COMMENT 'RRU型号',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_site_id (site_id),
    FOREIGN KEY (site_id) REFERENCES sites(id) ON DELETE CASCADE
) COMMENT='站点扇区配置表';

-- 站点规划变更历史表
CREATE TABLE site_change_history (
    id VARCHAR(32) PRIMARY KEY COMMENT '变更记录ID',
    site_id VARCHAR(32) NOT NULL COMMENT '站点ID',
    change_type ENUM('create', 'update', 'assign', 'status_change') COMMENT '变更类型',
    before_value JSON COMMENT '变更前数据',
    after_value JSON COMMENT '变更后数据',
    change_reason TEXT COMMENT '变更原因',
    changed_by VARCHAR(32) COMMENT '变更人',
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '变更时间',
    INDEX idx_site_id (site_id),
    INDEX idx_changed_by (changed_by),
    INDEX idx_changed_at (changed_at)
) COMMENT='站点规划变更历史表';
```

#### 4.2.3 现场检查相关表
```sql
-- 检查模板表
CREATE TABLE check_templates (
    id VARCHAR(32) PRIMARY KEY COMMENT '模板ID',
    site_id VARCHAR(32) NOT NULL COMMENT '站点ID',
    template_name VARCHAR(100) NOT NULL COMMENT '模板名称',
    template_data JSON NOT NULL COMMENT '模板数据',
    version VARCHAR(20) DEFAULT '1.0' COMMENT '模板版本',
    status ENUM('draft', 'active', 'archived') DEFAULT 'draft' COMMENT '模板状态',
    created_by VARCHAR(32) COMMENT '创建人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_site_id (site_id),
    INDEX idx_status (status)
) COMMENT='检查模板表';

-- 现场检查记录表
CREATE TABLE site_inspections (
    id VARCHAR(32) PRIMARY KEY COMMENT '检查记录ID',
    site_id VARCHAR(32) NOT NULL COMMENT '站点ID',
    template_id VARCHAR(32) NOT NULL COMMENT '检查模板ID',
    inspector_id VARCHAR(32) NOT NULL COMMENT '检查员ID',
    inspection_data JSON COMMENT '检查数据',
    photos JSON COMMENT '照片信息',
    completion_rate DECIMAL(5,2) DEFAULT 0 COMMENT '完成率',
    status ENUM('draft', 'submitted', 'under_review', 'approved', 'rejected') DEFAULT 'draft' COMMENT '检查状态',
    submitted_at TIMESTAMP NULL COMMENT '提交时间',
    reviewed_by VARCHAR(32) COMMENT '审核人',
    reviewed_at TIMESTAMP NULL COMMENT '审核时间',
    review_comments TEXT COMMENT '审核意见',
    score DECIMAL(3,1) COMMENT '质量评分',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_site_id (site_id),
    INDEX idx_inspector_id (inspector_id),
    INDEX idx_status (status),
    INDEX idx_submitted_at (submitted_at)
) COMMENT='现场检查记录表';

-- 检查项记录表
CREATE TABLE inspection_items (
    id VARCHAR(32) PRIMARY KEY COMMENT '检查项记录ID',
    inspection_id VARCHAR(32) NOT NULL COMMENT '检查记录ID',
    item_id VARCHAR(50) NOT NULL COMMENT '检查项ID',
    item_name VARCHAR(200) NOT NULL COMMENT '检查项名称',
    item_type ENUM('photo', 'data', 'both') NOT NULL COMMENT '检查项类型',
    photo_url VARCHAR(500) COMMENT '照片URL',
    photo_gps JSON COMMENT '照片GPS信息',
    data_value VARCHAR(500) COMMENT '数据值',
    status ENUM('pending', 'completed', 'failed') DEFAULT 'pending' COMMENT '检查项状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_inspection_id (inspection_id),
    INDEX idx_status (status),
    FOREIGN KEY (inspection_id) REFERENCES site_inspections(id) ON DELETE CASCADE
) COMMENT='检查项记录表';
```

#### 4.2.4 物料管理相关表
```sql
-- 物料基础信息表
CREATE TABLE materials (
    id VARCHAR(32) PRIMARY KEY COMMENT '物料ID',
    name VARCHAR(100) NOT NULL COMMENT '物料名称',
    code VARCHAR(50) UNIQUE COMMENT '物料编码',
    category VARCHAR(50) COMMENT '物料分类',
    specifications JSON COMMENT '物料规格',
    unit VARCHAR(20) COMMENT '计量单位',
    brand VARCHAR(50) COMMENT '品牌',
    model VARCHAR(100) COMMENT '型号',
    current_stock INT DEFAULT 0 COMMENT '当前库存',
    min_stock INT DEFAULT 0 COMMENT '最小库存',
    max_stock INT DEFAULT 0 COMMENT '最大库存',
    unit_price DECIMAL(10,2) COMMENT '单价',
    supplier VARCHAR(100) COMMENT '供应商',
    status ENUM('active', 'discontinued') DEFAULT 'active' COMMENT '物料状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_code (code),
    INDEX idx_category (category),
    INDEX idx_status (status)
) COMMENT='物料基础信息表';

-- 物料申请表
CREATE TABLE material_requests (
    id VARCHAR(32) PRIMARY KEY COMMENT '申请ID',
    request_no VARCHAR(50) UNIQUE NOT NULL COMMENT '申请单号',
    site_id VARCHAR(32) COMMENT '关联站点ID',
    requester_id VARCHAR(32) NOT NULL COMMENT '申请人ID',
    request_type ENUM('normal', 'urgent', 'replacement') DEFAULT 'normal' COMMENT '申请类型',
    request_items JSON NOT NULL COMMENT '申请物料清单',
    total_amount DECIMAL(12,2) COMMENT '申请总金额',
    request_reason TEXT COMMENT '申请原因',
    status ENUM('pending', 'approved', 'rejected', 'distributed', 'completed') DEFAULT 'pending' COMMENT '申请状态',
    approved_by VARCHAR(32) COMMENT '审批人',
    approved_at TIMESTAMP NULL COMMENT '审批时间',
    approval_comments TEXT COMMENT '审批意见',
    distributed_by VARCHAR(32) COMMENT '分发人',
    distributed_at TIMESTAMP NULL COMMENT '分发时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_request_no (request_no),
    INDEX idx_site_id (site_id),
    INDEX idx_requester_id (requester_id),
    INDEX idx_status (status)
) COMMENT='物料申请表';

-- 库存变动记录表
CREATE TABLE stock_movements (
    id VARCHAR(32) PRIMARY KEY COMMENT '变动记录ID',
    material_id VARCHAR(32) NOT NULL COMMENT '物料ID',
    movement_type ENUM('in', 'out', 'transfer', 'adjust') NOT NULL COMMENT '变动类型',
    quantity INT NOT NULL COMMENT '变动数量',
    before_stock INT NOT NULL COMMENT '变动前库存',
    after_stock INT NOT NULL COMMENT '变动后库存',
    reference_id VARCHAR(32) COMMENT '关联单据ID',
    reference_type VARCHAR(50) COMMENT '关联单据类型',
    reason TEXT COMMENT '变动原因',
    operator_id VARCHAR(32) COMMENT '操作人',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_material_id (material_id),
    INDEX idx_movement_type (movement_type),
    INDEX idx_created_at (created_at)
) COMMENT='库存变动记录表';
```

#### 4.2.5 系统管理相关表
```sql
-- 操作日志表
CREATE TABLE operation_logs (
    id VARCHAR(32) PRIMARY KEY COMMENT '日志ID',
    user_id VARCHAR(32) COMMENT '操作用户ID',
    user_name VARCHAR(50) COMMENT '操作用户名',
    module VARCHAR(50) NOT NULL COMMENT '操作模块',
    action VARCHAR(100) NOT NULL COMMENT '操作动作',
    resource_id VARCHAR(32) COMMENT '操作资源ID',
    resource_type VARCHAR(50) COMMENT '操作资源类型',
    details JSON COMMENT '操作详情',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    user_agent TEXT COMMENT '用户代理',
    request_url VARCHAR(500) COMMENT '请求URL',
    execution_time INT COMMENT '执行时间(毫秒)',
    status ENUM('success', 'failed') DEFAULT 'success' COMMENT '操作状态',
    error_message TEXT COMMENT '错误信息',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_user_id (user_id),
    INDEX idx_module (module),
    INDEX idx_action (action),
    INDEX idx_created_at (created_at),
    INDEX idx_status (status)
) COMMENT='操作日志表';

-- 文件存储表
CREATE TABLE files (
    id VARCHAR(32) PRIMARY KEY COMMENT '文件ID',
    original_name VARCHAR(255) NOT NULL COMMENT '原始文件名',
    stored_name VARCHAR(255) NOT NULL COMMENT '存储文件名',
    file_path VARCHAR(500) NOT NULL COMMENT '文件路径',
    file_size BIGINT COMMENT '文件大小',
    mime_type VARCHAR(100) COMMENT '文件类型',
    file_hash VARCHAR(64) COMMENT '文件哈希值',
    related_id VARCHAR(32) COMMENT '关联对象ID',
    related_type VARCHAR(50) COMMENT '关联对象类型',
    uploaded_by VARCHAR(32) COMMENT '上传者ID',
    upload_ip VARCHAR(45) COMMENT '上传IP',
    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开',
    status ENUM('uploading', 'completed', 'failed', 'deleted') DEFAULT 'uploading' COMMENT '文件状态',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_related (related_id, related_type),
    INDEX idx_uploaded_by (uploaded_by),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) COMMENT='文件存储表';

-- 系统配置表
CREATE TABLE system_configs (
    id VARCHAR(32) PRIMARY KEY COMMENT '配置ID',
    config_key VARCHAR(100) UNIQUE NOT NULL COMMENT '配置键',
    config_value TEXT COMMENT '配置值',
    config_type ENUM('string', 'number', 'boolean', 'json') DEFAULT 'string' COMMENT '配置类型',
    description TEXT COMMENT '配置描述',
    is_public BOOLEAN DEFAULT FALSE COMMENT '是否公开配置',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_config_key (config_key)
) COMMENT='系统配置表';

-- 知识库文档表
CREATE TABLE knowledge_docs (
    id VARCHAR(32) PRIMARY KEY COMMENT '文档ID',
    title VARCHAR(200) NOT NULL COMMENT '文档标题',
    category VARCHAR(50) NOT NULL COMMENT '文档分类',
    content LONGTEXT COMMENT '文档内容',
    summary TEXT COMMENT '文档摘要',
    tags VARCHAR(500) COMMENT '标签',
    attachments JSON COMMENT '附件信息',
    version VARCHAR(20) DEFAULT '1.0' COMMENT '文档版本',
    author_id VARCHAR(32) COMMENT '作者ID',
    author_name VARCHAR(50) COMMENT '作者姓名',
    status ENUM('draft', 'published', 'archived') DEFAULT 'draft' COMMENT '文档状态',
    view_count INT DEFAULT 0 COMMENT '查看次数',
    like_count INT DEFAULT 0 COMMENT '点赞次数',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_category (category),
    INDEX idx_status (status),
    INDEX idx_author_id (author_id),
    FULLTEXT idx_content (title, content, summary)
) COMMENT='知识库文档表';
```

### 4.3 数据库索引策略
- **主键索引**: 所有表使用UUID作为主键
- **唯一索引**: 用户手机号、站点编码等唯一字段
- **复合索引**: 常用查询组合字段，如(site_id, status)
- **全文索引**: 知识库内容搜索
- **时间索引**: 按时间范围查询的字段

### 4.4 数据库优化建议
- **分库分表**: 日志表按月分表
- **读写分离**: 主从复制，读写分离
- **缓存策略**: Redis缓存热点数据
- **归档策略**: 历史数据定期归档

---

## 5. 开发计划和里程碑

### 5.1 项目开发阶段

#### 第一阶段：核心基础功能（8周）
**里程碑：MVP版本发布**

**Week 1-2: 项目搭建与基础架构**
- 开发环境搭建（Git、CI/CD、Docker）
- 后端API框架搭建（Spring Boot + MySQL + Redis）
- 移动端项目初始化（React Native）
- 数据库设计与创建
- 基础工具类和通用组件开发

**Week 3-4: 用户管理模块**
- 用户注册、登录功能
- 短信验证码集成
- JWT Token认证机制
- RBAC权限系统实现
- 用户管理后台界面

**Week 5-6: 规划数据管理模块**
- Excel数据导入功能
- 站点信息CRUD操作
- 扇区配置管理
- 站点分配功能
- 数据变更历史记录

**Week 7-8: 现场信息管理模块（基础版）**
- 检查模板自动生成
- 基础数据采集界面
- 照片拍摄功能
- 数据本地存储
- 基础数据验证

#### 第二阶段：功能完善与优化（6周）
**里程碑：Beta版本发布**

**Week 9-10: 现场信息管理（增强版）**
- GPS水印功能实现
- 离线数据存储与同步
- 数据完整性校验
- 审核工作流实现
- 数据提交与召回功能

**Week 11-12: 报表输出模块**
- 报表模板设计
- Excel报表生成（Apache POI）
- PDF报告生成（iText）
- 数据筛选与导出功能
- 报表管理界面

**Week 13-14: 日志管理模块**
- 操作日志自动记录（AOP）
- 日志查询与筛选功能
- 日志分析与统计
- 安全事件监控
- 日志导出功能

#### 第三阶段：扩展功能与测试（4周）
**里程碑：正式版本发布**

**Week 15-16: 物料管理模块**
- 物料档案管理
- 物料申请流程
- 库存管理功能
- 物料需求自动匹配
- 库存预警功能

**Week 17-18: 信息查询模块与测试**
- 知识库文档管理
- 技术文档上传与分类
- FAQ管理系统
- 通讯录管理
- 全功能集成测试
- 性能优化与Bug修复

### 5.2 技术实现关键点

#### 5.2.1 离线数据同步机制
```javascript
// 离线数据管理策略
class OfflineManager {
  // 保存离线数据
  static async saveOfflineData(data) {
    const storageKey = `offline_${data.type}_${data.id}`;
    const offlineData = {
      ...data,
      timestamp: Date.now(),
      synced: false,
      retryCount: 0
    };
    
    await AsyncStorage.setItem(storageKey, JSON.stringify(offlineData));
    return storageKey;
  }
  
  // 网络恢复时同步数据
  static async syncPendingData() {
    try {
      const keys = await AsyncStorage.getAllKeys();
      const offlineKeys = keys.filter(key => key.startsWith('offline_'));
      
      for (const key of offlineKeys) {
        const dataStr = await AsyncStorage.getItem(key);
        const data = JSON.parse(dataStr);
        
        if (!data.synced) {
          try {
            await this.uploadData(data);
            await AsyncStorage.removeItem(key);
          } catch (error) {
            // 增加重试次数，超过阈值则放弃
            data.retryCount++;
            if (data.retryCount < 3) {
              await AsyncStorage.setItem(key, JSON.stringify(data));
            } else {
              await AsyncStorage.removeItem(key);
            }
          }
        }
      }
    } catch (error) {
      console.error('同步离线数据失败:', error);
    }
  }
}
```

#### 5.2.2 照片水印与GPS功能
```javascript
// 拍照组件实现
class CameraManager {
  static async takePhotoWithWatermark() {
    try {
      // 获取GPS位置
      const position = await this.getCurrentPosition();
      
      // 拍照
      const photo = await ImagePicker.openCamera({
        width: 1920,
        height: 1080,
        cropping: false,
        includeExif: true,
        compressImageQuality: 0.8
      });
      
      // 添加水印
      const watermarkedPhoto = await this.addWatermark(photo, {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy,
        timestamp: new Date().toISOString(),
        address: await this.getAddressByGPS(position.coords)
      });
      
      return {
        uri: watermarkedPhoto.uri,
        gpsInfo: {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
          accuracy: position.coords.accuracy,
          timestamp: new Date().toISOString()
        }
      };
    } catch (error) {
      throw new Error(`拍照失败: ${error.message}`);
    }
  }
  
  static async addWatermark(photo, gpsInfo) {
    // 使用Canvas添加水印
    const canvas = await Canvas.createImageFromURI(photo.uri);
    const ctx = canvas.getContext('2d');
    
    // 绘制水印文本
    const watermarkText = [
      `GPS: ${gpsInfo.latitude.toFixed(6)}, ${gpsInfo.longitude.toFixed(6)}`,
      `精度: ${gpsInfo.accuracy}m`,
      `时间: ${moment(gpsInfo.timestamp).format('YYYY-MM-DD HH:mm:ss')}`,
      `地址: ${gpsInfo.address}`
    ];
    
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(10, canvas.height - 120, 500, 100);
    
    ctx.fillStyle = 'white';
    ctx.font = '16px Arial';
    watermarkText.forEach((text, index) => {
      ctx.fillText(text, 20, canvas.height - 90 + (index * 20));
    });
    
    return await canvas.toDataURL();
  }
}
```

#### 5.2.3 数据验证框架
```java
// 后端数据验证
@Component
public class SiteDataValidator {
    
    @Autowired
    private SiteConfigProperties siteConfig;
    
    public ValidationResult validateSiteData(SiteInspectionData data) {
        ValidationResult result = new ValidationResult();
        
        // 验证天线参数
        for (SectorData sector : data.getSectors()) {
            // 方位角验证 (0-360度)
            if (sector.getAzimuth() < 0 || sector.getAzimuth() > 360) {
                result.addError("方位角必须在0-360度之间");
            }
            
            // 下倾角验证 (0-20度)
            if (sector.getTilt() < 0 || sector.getTilt() > 20) {
                result.addError("下倾角必须在0-20度之间");
            }
            
            // 挂高验证 (0-100米)
            if (sector.getHeight() < 0 || sector.getHeight() > 100) {
                result.addError("天线挂高必须在0-100米之间");
            }
        }
        
        // 验证驻波比
        if (data.getVswr() < 1.0 || data.getVswr() > 2.0) {
            result.addError("驻波比必须在1.0-2.0之间");
        }
        
        // 验证GPS坐标
        if (!isValidGPS(data.getLatitude(), data.getLongitude())) {
            result.addError("GPS坐标无效");
        }
        
        return result;
    }
}
```

### 5.3 团队配置与协作

#### 5.3.1 团队结构（建议6-8人）
```
项目经理 (1人)
├── 后端开发团队 (2人)
│   ├── 高级后端工程师 (Spring Boot/MySQL专家)
│   └── 后端工程师 (API开发/数据库设计)
├── 前端开发团队 (2人)
│   ├── 移动端工程师 (React Native专家)
│   └── 前端工程师 (UI/UX实现)
├── 测试团队 (1人)
│   └── 测试工程师 (功能测试/自动化测试)
├── 设计团队 (1人)
│   └── UI/UX设计师 (界面设计/用户体验)
└── 运维团队 (1人)
    └── DevOps工程师 (部署/监控/运维)
```

#### 5.3.2 开发协作流程
```
需求分析 → 技术设计 → 任务分解 → 并行开发 → 联调测试 → 部署发布
    ↓         ↓         ↓         ↓         ↓         ↓
 PRD文档   技术方案   开发计划   代码Review  测试报告   发布记录
```

#### 5.3.3 质量保证措施
- **代码审查**: 所有代码必须经过Code Review
- **自动化测试**: 单元测试覆盖率 ≥ 80%
- **持续集成**: Git提交自动触发构建和测试
- **性能监控**: 接口响应时间、并发性能监控
- **安全审计**: 定期安全漏洞扫描

### 5.4 技术风险与应对策略

#### 5.4.1 主要技术风险
| 风险点 | 风险等级 | 影响 | 应对策略 |
|--------|----------|------|----------|
| 离线数据同步 | 高 | 数据丢失 | 多重备份、增量同步、冲突检测 |
| GPS定位精度 | 中 | 位置不准 | 多次定位取平均值、手动校正 |
| 照片防篡改 | 高 | 数据可信度 | 数字签名、区块链存证 |
| 大文件上传 | 中 | 上传失败 | 分片上传、断点续传 |
| 并发性能 | 中 | 系统卡顿 | 缓存优化、数据库优化 |

#### 5.4.2 应对措施
- **技术选型**: 选择成熟稳定的技术栈
- **原型验证**: 核心功能提前验证可行性
- **灰度发布**: 分阶段发布，逐步扩大用户范围
- **监控告警**: 建立完善的监控和告警机制
- **应急预案**: 制定故障应急处理预案

---

## 6. 总结和建议

### 6.1 项目价值评估

#### 6.1.1 直接价值
- **效率提升**: 数字化管理减少人工错误，提高工作效率30%以上
- **质量保证**: 标准化检查流程，确保工程质量一致性
- **成本降低**: 减少重复验收、降低沟通成本20%以上
- **风险控制**: 实时监控施工进度，及时发现和解决问题

#### 6.1.2 间接价值
- **数据积累**: 建立工程数据资产，支持后续分析优化
- **知识沉淀**: 形成标准化作业指导书和最佳实践
- **人员培养**: 提升团队数字化能力和工程管理水平
- **竞争优势**: 提升公司在工程项目上的竞争力

### 6.2 关键成功因素

#### 6.2.1 技术因素
- **用户体验**: 移动端操作简便，离线功能稳定可靠
- **数据安全**: 照片防篡改、数据传输加密、访问控制
- **系统稳定**: 高并发处理能力、数据备份恢复机制
- **扩展性**: 模块化设计，支持功能扩展和集成

#### 6.2.2 管理因素
- **需求管理**: 深度理解业务流程，及时响应需求变更
- **项目管理**: 严格控制项目进度、质量和成本
- **变更控制**: 建立规范的变更管理流程
- **风险管理**: 提前识别和应对技术风险

#### 6.2.3 用户因素
- **培训推广**: 提供充分的用户培训和技术支持
- **渐进推广**: 从试点到全面推广的分阶段实施
- **反馈机制**: 建立用户反馈渠道，持续优化改进
- **激励机制**: 建立使用激励机制，提高用户积极性

### 6.3 风险控制建议

#### 6.3.1 技术风险控制
- **技术选型**: 选择成熟技术栈，避免技术风险
- **架构设计**: 采用微服务架构，降低系统复杂度
- **性能优化**: 提前进行性能测试和优化
- **安全防护**: 建立多层次安全防护体系

#### 6.3.2 项目风险控制
- **需求冻结**: 关键需求在开发前确认并冻结
- **迭代开发**: 采用敏捷开发方法，快速响应变化
- **质量把控**: 建立严格的质量控制体系
- **进度监控**: 建立项目进度监控和预警机制

### 6.4 后续发展规划

#### 6.4.1 短期优化（6个月内）
- **性能优化**: 提升系统响应速度和并发能力
- **功能完善**: 根据用户反馈完善现有功能
- **用户体验**: 优化界面设计和操作流程
- **数据分析**: 增加数据统计和分析功能

#### 6.4.2 中期扩展（1年内）
- **AI辅助**: 图像识别自动检查、智能质量评分
- **IoT集成**: 设备状态自动采集、远程监控
- **移动办公**: 支持更多移动办公场景
- **集成对接**: 与其他系统的数据集成

#### 6.4.3 长期发展（2年内）
- **大数据分析**: 工程质量趋势分析、预测性维护
- **区块链应用**: 数据不可篡改、多方协作信任
- **云原生架构**: 全面云化部署，支持弹性扩展
- **生态建设**: 建立合作伙伴生态，扩展应用场景

### 6.5 投资回报分析

#### 6.5.1 开发投入估算
- **人力成本**: 6-8人团队 × 4-5个月 ≈ 150-200万元
- **技术成本**: 服务器、软件许可证等 ≈ 20-30万元
- **其他成本**: 测试、培训、推广等 ≈ 30-50万元
- **总投入**: 约200-280万元

#### 6.5.2 预期收益
- **效率提升**: 节省人工成本30% ≈ 年节省200-300万元
- **质量改善**: 减少返工成本 ≈ 年节省100-200万元
- **风险降低**: 避免项目延期损失 ≈ 年节省50-100万元
- **年度收益**: 约350-600万元

#### 6.5.3 投资回报
- **投资回收期**: 6-12个月
- **3年总收益**: 1000-1800万元
- **投资回报率**: 350%-500%

### 6.6 实施建议

#### 6.6.1 实施策略
1. **分阶段实施**: 从核心功能开始，逐步扩展完善
2. **试点先行**: 选择1-2个项目进行试点应用
3. **逐步推广**: 试点成功后逐步推广到所有项目
4. **持续优化**: 根据使用反馈持续优化改进

#### 6.6.2 组织保障
1. **成立项目组**: 由公司高层牵头的项目推进组
2. **专人负责**: 指定专门的项目经理负责协调
3. **资源保障**: 确保人力、资金、技术资源到位
4. **考核激励**: 建立项目成功的考核激励机制

#### 6.6.3 技术保障
1. **技术选型**: 选择成熟稳定的技术方案
2. **团队建设**: 组建有经验的开发团队
3. **质量保证**: 建立严格的质量控制体系
4. **运维支持**: 建立专业的运维支持团队

通过这个详细的设计方案，可以为站点信息管理APP的开发提供全面的技术指导和实施路径，确保项目的成功实施和预期目标的实现。

---

**文档结束**