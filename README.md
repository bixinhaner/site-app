# 站点信息管理系统

一个面向通信运营商的现代化站点信息管理系统，采用 FastAPI + UniApp + Vue 三端架构，提供从设备物料管理到现场检查、工单流程的全链路解决方案。

## 🏗️ 项目架构

### 技术栈
- **后端**: Python FastAPI + SQLAlchemy + SQLite/MySQL
- **移动端**: UniApp + Vue 3 + Pinia (支持 Android/H5/小程序)
- **Web管理端**: Vue 3 + Element Plus + Vite
- **数据库**: SQLite (开发) / MySQL (生产)
- **认证**: JWT Token 认证，30分钟过期

### 项目结构
```
site-app/
├── backend/                    # FastAPI 后端服务
│   ├── app/
│   │   ├── api/               # API 路由 (auth, users, sites, inspections, work_orders, etc.)
│   │   ├── models/            # SQLAlchemy 数据模型
│   │   ├── core/              # 核心配置 (database, security, config)
│   │   ├── schemas/           # Pydantic 数据验证
│   │   ├── services/          # 业务逻辑服务
│   │   └── utils/             # 工具函数
│   ├── requirements.txt       # Python 依赖
│   └── start_backend.py       # 一键启动脚本
├── uniapp-site-manager/       # UniApp 移动端
│   ├── pages/                 # 页面组件 (login, home, workorder, inspection, etc.)
│   ├── stores/                # Pinia 状态管理
│   ├── utils/                 # 工具函数
│   ├── config/                # 环境配置
│   └── package.json
├── web-admin/                 # Vue Web 管理端
│   ├── src/
│   │   ├── views/             # 页面组件
│   │   ├── api/               # API 服务
│   │   ├── stores/            # 状态管理
│   │   └── router/            # 路由配置
│   └── package.json
└── start_backend.py           # 项目一键启动脚本
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- Node.js 14+
- HBuilderX (用于 UniApp 开发)

### 后端服务启动

#### 一键启动 (推荐)
```bash
# 自动创建虚拟环境、安装依赖、初始化数据库、创建默认用户
python start_backend.py
```

#### 手动启动
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 复制配置文件
cp .env.example .env

# 启动服务 (支持移动端访问)
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 前端启动

#### UniApp 移动端
```bash
cd uniapp-site-manager
npm install
npm run dev                    # 开发模式
npm run build:h5:prod         # 构建 H5 版本
npm run build:prod            # 构建 App 版本
```

#### Web 管理端
```bash
cd web-admin
npm install
npm run dev                    # 默认运行在 5173 端口
npm run build                  # 生产构建
```

### 服务访问地址
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Web 管理端**: http://localhost:5173
- **健康检查**: http://localhost:8000/health

## 👥 用户系统

### 默认账户
| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| admin | admin123 | admin | 系统管理员 (全权限) |
| inspector | inspector123 | inspector | 现场检查员 |
| tom | tom123456 | inspector | 现场检查员 |
| test_user | user123 | user | 普通用户 |
| planner | planner123 | planner | 网络规划人员 |

### 权限角色
- **admin**: 系统管理员，拥有所有权限
- **manager**: 项目经理，管理站点和人员分配
- **inspector**: 现场工程师，执行检查和数据录入
- **planner**: 网络规划人员，负责站点规划
- **user**: 普通用户，查看分配的任务

## 🏢 核心功能模块

### 1. 工单管理系统
- **工单状态流**: PENDING → ACTIVE → SUBMITTED → UNDER_REVIEW → APPROVED/REJECTED → ACTIVATED → COMPLETED
- **工单类型**: 开通检查、维护、电源问题、传输问题、GPS问题、信号问题
- **优先级管理**: 低、普通、高、紧急
- **分配和审核**: 支持多级审批和完整审计追踪

### 2. 现场检查系统
- **模板驱动**: JSON 格式的检查模板，支持站点级和扇区级检查项
- **GPS 定位**: 强制 GPS 验证，确保现场作业真实性
- **照片水印**: 自动添加经纬度、时间戳、检查员信息
- **水印模板化配置（2026-02）**: Web 管理端支持按“全局/角色/用户”分配不同水印模板，可配置样式（颜色、透明度、位置、字号、边距、水印区域占比等）和内容项（图标显隐、坐标、地址、时间、人员、检查项、站点、前后缀文本）
- **离线支持**: IndexedDB 本地存储，网络恢复后自动同步
- **防篡改机制**: 文件哈希值验证和数字签名

### 3. 设备物料管理
- **库存管理**: 设备出入库、库存查询、退库申请
- **新流程（移动端）**: 物料申请 → 仓库审批 → 自助领料 → 仓库出库确认
- **退库创建（移动端）**: 改为“按实际申请”，不再强依赖人工先选出库单；主设备仅支持扫码加入，辅料按系统给出的可退上限填写
- **退库校验提示（移动端）**: 扫码 SN 会先做可退校验，失败时弹窗展示“原因 + 建议 + 相关人员/单据信息”
- **退库批次视图（移动端）**: 一次提交记为一个批次，后台可自动拆分多张退库单，列表按批次聚合展示状态、驳回原因与拆分单据
- **退库防超退（并发）**: 提交时会做额度锁定与原子状态更新；若并发导致可退额度或SN状态变化，会返回明确提示并要求刷新后重试
- **退库收货（Web 管理端）**: 仓库收货页改为批次维度展示（批次头 + 单据明细），单据超过 8 条默认折叠；收货/拒收仍按单据执行
- **首页库存入口（移动端）**: 我的设备、物料申请、审批物料申请、出库确认、退库申请、快速出库
- **申请明细可读性优化（移动端）**: 物料申请创建页的"申请明细"改为上下分区布局（上方完整展示设备名/编码/类型，下方数量操作与删除），避免窄屏下信息被操作按钮挤压成 `...`
- **放弃领货（移动端）**: 已审批但尚未发生出库的申请单可执行"放弃领货"（需填写原因）；系统会自动取消该申请单下未完成的领料单并释放占用，状态标记为 `abandoned`
- **放弃领货（Web 管理端）**: 申请单详情页支持"放弃领货"按钮（原因必填）；仅"已批准/部分批准且未出库"可操作，成功后同步展示放弃原因与状态
- **出库确认规则**: 主设备 SN 默认全选待确认项，支持手动取消个别 SN 不确认
- **部分出库后的处理**: 当领料单进入“部分出库（partially_confirmed）”后，仓库可执行“驳回剩余”，系统会清理该单未确认 SN 与未确认辅料数量，避免剩余项长期占用；若该单已无待确认剩余，也可直接收口为已完成（confirmed）
- **无可出库场景收口**: 若领料单处于“部分出库”但已无待确认项，点击“确认出库”会提示“是否关闭该出库单”，确认后自动收口
- **设备状态**: offline → online → activated
- **物料分类**: 支持多级分类管理

### 4. 站点管理
- **站点规划**: 支持站点信息录入和规划管理
- **基站状态**: 离线、在线、已激活
- **地理信息**: GPS 坐标管理和位置验证
- **设备关联**: 站点与设备的关联管理
- **站点概况-安装站点**: 位于“规划站点”和“上线站点”之间，显示为 `安装站点/总站点`；其中安装站点按“开站工单达到已提交及以上阶段（SUBMITTED/UNDER_REVIEW/APPROVED/ACTIVATED/COMPLETED）”按站点去重统计，点击后跳转工单列表并自动按同口径筛选

### 5. 用户行为日志
- **全链路追踪**: 自动记录用户操作轨迹
- **会话管理**: 自动生成 session ID
- **API 拦截**: 记录所有请求响应
- **离线日志**: 支持离线日志同步

## 🔧 API 接口

### 认证相关
- `POST /api/auth/login` - 用户登录
- `GET /api/auth/me` - 获取当前用户信息
- `POST /api/auth/register` - 用户注册

### 工单管理
- `GET /api/work-orders` - 获取工单列表
- `GET /api/work-orders/{id}` - 获取工单详情
- `POST /api/work-orders/{id}/items/{item_id}` - 更新检查项
- `POST /api/work-orders/{id}/photos` - 上传检查照片
- `POST /api/work-orders/{id}/complete` - 完成工单

### 检查管理
- `GET /api/inspections` - 获取检查列表
- `GET /api/inspections/detail/{id}` - 获取检查详情
- `POST /api/inspections` - 创建新检查
- `PUT /api/inspections/{id}` - 更新检查状态

### 设备管理
- `GET /api/equipment` - 获取设备列表
- `POST /api/equipment` - 添加设备
- `GET /api/stock` - 库存查询
- `GET /api/stock/material-requests` - 物料申请列表
- `POST /api/stock/material-requests/{id}/abandon` - 申请人放弃领货（仅已审批且未出库；自动取消未完成领料单）
- `POST /api/stock/material-requests/{id}/approve` - 仓库审批通过
- `POST /api/stock/material-requests/{id}/reject` - 仓库审批驳回
- `GET /api/stock/issue-drafts` - 领料单列表（含待出库确认）
- `POST /api/stock/issue-drafts/{id}/confirm` - 仓库确认出库
- `POST /api/stock/issue-drafts/{id}/reject` - 仓库驳回整单
- `POST /api/stock/issue-drafts/{id}/reject-remaining` - 仓库驳回剩余待确认项并收口（仅部分出库状态；无剩余时也可直接收口）
- `POST /api/stock/returns/validate-sn` - 退库扫码 SN 可退校验（返回详细原因/建议）
- `GET /api/stock/returns/actual-candidates` - 获取按实际申请退库候选数据（辅料可退上限等）
- `POST /api/stock/returns/by-actual` - 按实际申请退库（后台自动关联并拆分单据，提交时做并发防超退校验）
- `GET /api/stock/returns/workbench-batches` - 仓库侧退库批次工作台（批次维度，含单据明细）
- `GET /api/stock/my-return-batches` - 我的退库批次列表（批次维度）

### 日志系统
- `POST /api/logs` - 创建用户日志
- `POST /api/logs/batch` - 批量同步日志

### 移动端配置
- `GET /api/system/mobile-settings` - 管理端获取完整移动端配置（管理员/项目经理）
- `PUT /api/system/mobile-settings` - 管理端更新完整移动端配置（管理员/项目经理）
- `GET /api/system/mobile-settings/effective` - 移动端获取“当前用户生效”的配置（含定位策略、水印策略、水印模板）
- `GET /api/system/location-mode` - 获取定位模式全局默认值（兼容旧版）
- `PUT /api/system/location-mode` - 更新定位模式全局默认值（兼容旧版）

## 🗄️ 数据库设计

### 核心数据表
- **users**: 用户信息和权限管理
- **sites**: 站点基础信息
- **work_orders**: 工单主表
- **work_order_items**: 工单检查项
- **work_order_photos**: 工单照片附件
- **inspection_templates**: 检查模板
- **site_inspections**: 检查实例
- **equipment**: 设备管理
- **user_logs**: 用户行为日志
- **audit_events**: 审计事件记录

### 业务状态机
```
工单流程: PENDING → ACTIVE → SUBMITTED → UNDER_REVIEW → APPROVED → ACTIVATED → COMPLETED
检查状态: draft → in_progress → submitted → under_review → approved/rejected → completed
设备状态: offline → online → activated
```

## 📱 移动端特性

### 离线优先架构
- **本地存储**: IndexedDB 主存储 + localStorage 备用
- **数据同步**: 三层状态同步 (本地 ↔ 离线存储 ↔ 服务器)
- **冲突解决**: 基于时间戳的冲突检测和解决

### GPS 和位置服务
- **高精度定位**: GPS accuracy 验证
- **位置匹配**: 现场位置与站点坐标匹配验证
- **自动水印**: 照片自动添加位置和时间信息
- **模板化水印生效**: 登录后调用 `/api/system/mobile-settings/effective` 获取当前用户生效模板；优先级为 `按用户 > 按角色 > 全局默认`
- **本地上传兼容规则**: 当“本地上传不带经纬度/地址”时，仍可按模板控制其他内容展示，并支持强制/非强制“本地上传标注”

### 图片白图规避（2026-02 更新）
- **前置拦截**: 选图后先做本地可读性校验（尺寸、文件可读性、异常小文件），异常图片直接阻断，不进入检查项详情。
- **路径兼容修复**: 新增本地图片路径识别（如 `content://`、`/storage/...`、`file://` 等），避免误拼接成网络 URL 导致白图。
- **Canvas绘制路径标准化**: 水印渲染统一优先使用 `uni.getImageInfo(...).path` 的绝对可绘制路径（如 `file://...`），避免 `_doc/...` 在部分 Android 机型上出现“导出成功但画面白板”。
- **Canvas多路径重试**: 同一张照片会按多种本地路径格式自动重试绘制（`file://`、绝对路径、原始路径），降低不同机型对路径格式兼容差异造成的白图概率。
- **导出结果强校验**: 对导出后的水印图增加文件体积合理性校验，若命中“疑似纯白图”会自动触发降级重试，而不是直接把白图放进检查项。
- **保守分辨率策略**: Android 端默认先用 2.5K 边长渲染，再逐级降到 2K/1.6K/1.28K，减少高分辨率机型内存压力导致的白板输出。
- **持久化处理**: 选图后优先尝试持久化路径，降低临时文件失效导致的偶发白图问题。
- **水印防白图**: 水印渲染阶段新增“疑似纯白图”检测，命中后直接阻断并提示重拍。
- **预览失败提示**: 本地图片加载失败时会明确提示“删除后重拍”，减少误判为上传成功的情况。

### 原生插件支持
- **定位插件**: 支持原生定位服务
- **扫码功能**: 二维码和条形码扫描
- **相机集成**: 拍照和图片处理

## ⚙️ 配置说明

### 移动端水印模板配置（新增）
- 管理入口：`Web 管理端 -> 系统管理 -> 移动端配置 -> 照片水印模板`
- 支持内容：
  - 模板管理：新增、复制、删除、设置默认模板
  - 模板样式：位置、文字色、背景色与透明度、字号、行高、内外边距、圆角、最大宽度比例、水印区域占比
  - 模板内容：图标显隐、本地上传标注、GPS、精度、地址、时间、检查员、检查项、站点、前缀/后缀文本、坐标精度
  - 分配规则：全局默认 + 按角色覆盖 + 按用户覆盖
  - 场景策略：拍照场景启用、相册场景启用、本地上传无定位时是否强制本地标注
  - 管理端预览：支持 `720p(1280x720)`、`1080p(1920x1080)`、`2k(2560x1440)`、`4k(3840x2160)` 四档 Tab 预览
  - 放大查看：可在预览中打开“原始分辨率效果”弹窗，支持 自适应(Fit)/25%/50%/100%/200% 缩放并滚动查看细节
  - 弹窗定位基准：原始分辨率弹窗预览按画布左上锚点展示，水印位置按图片真实坐标映射（避免缩放时视觉错位）
- 移动端生效方式：
  - 登录或 Token 校验通过后自动拉取 `/api/system/mobile-settings/effective`
  - 检查详情与拍照页使用同一套水印渲染引擎，按当前用户模板实时渲染

### 环境配置

#### 后端配置 (.env)
```env
# 应用配置
APP_NAME=站点信息管理系统
SECRET_KEY=your-super-secret-key
DEBUG=true

# 数据库
DATABASE_URL=sqlite:///./site_manager.db

# JWT配置
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 文件上传
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
ALLOWED_FILE_TYPES=jpg,jpeg,png,pdf
```

#### 前端配置 (config/env.js)
```javascript
const config = {
  API_BASE_URL: 'http://localhost:8000',  // 开发环境
  // API_BASE_URL: 'http://113.45.25.135/api',  // 生产环境
  APP_NAME: '站点管理系统',
  DEBUG: true
}
```

### 网络配置
- **开发环境**: 后端服务监听 `0.0.0.0:8000`，支持局域网访问
- **CORS 配置**: 允许所有来源访问（开发环境）
- **移动端访问**: 需要使用局域网 IP 地址

## 🧪 测试和调试

### API 测试
```bash
# 健康检查
curl http://localhost:8000/health

# 登录测试
python backend/test_login.py

# 任务API测试
python backend/test_task_api.py
```

### 前端调试
- **浏览器开发者工具**: 查看网络请求和控制台日志
- **HBuilderX 控制台**: UniApp 调试信息
- **Swagger UI**: http://localhost:8000/docs

### 常见问题排查
1. **端口冲突**: `lsof -i :8000` 检查端口占用
2. **网络连接**: 确认 API_BASE_URL 配置正确
3. **权限问题**: 检查 uploads 目录写入权限
4. **数据库初始化**: 运行 `python start_backend.py` 重新初始化

## 📋 开发规范

### 代码规范
- **后端**: 遵循 PEP 8 Python 代码规范
- **前端**: ESLint + Prettier 代码格式化
- **API 设计**: RESTful API 设计原则
- **数据库**: 使用 SQLAlchemy ORM，遵循数据库设计规范

### 提交规范
- **feat**: 新功能
- **fix**: 修复问题
- **docs**: 文档更新
- **style**: 代码格式调整
- **refactor**: 代码重构

## 🚀 部署说明

### 生产环境部署
1. **推荐方案（Ubuntu + Caddy + pm2）**:
   - 按仓库文档 `surge-deployment.md` 执行完整部署流程
   - 同域部署：`/` 提供 WebAdmin，`/api/*` 反向代理到 FastAPI
   - 后端仅监听 `127.0.0.1:8000`，公网只开放 `80/443`

2. **代码拉取方式（推荐 SSH）**:
   - 使用 GitHub 个人账号 SSH keys（`Settings -> SSH and GPG keys`）
   - 仓库地址使用 `git@github.com:bixinhaner/site-app.git`
   - 已克隆项目可执行 `git remote set-url origin git@github.com:bixinhaner/site-app.git`

3. **服务器基础要求**:
   - 放行 `80/443` 入站（证书签发与访问都依赖）
   - 正确设置后端环境变量与上传目录权限
   - 发布后执行健康检查：`/health`

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详细信息。

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📞 联系方式

- 项目负责人: [联系邮箱]
- 技术支持: [支持邮箱]
- 项目地址: [GitHub 仓库地址]
