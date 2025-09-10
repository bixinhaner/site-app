# 站点信息管理系统

现代化的通信站点信息管理解决方案，基于 UniApp（移动端）+ Python FastAPI（后端）架构开发。

## 🏗️ 系统架构

### 前端（UniApp 移动端）
- 框架: UniApp (Vue 3)
- 状态管理: Pinia
- 平台: Android/H5（脚手架已包含 H5 构建脚本）

### 后端
- 框架: Python FastAPI
- 数据库: SQLite（开发）/ 可扩展至 MySQL（生产）
- 认证: JWT
- 文档: OpenAPI（/docs, /redoc）

## 🚀 功能特性

### 核心功能
- ✅ 用户认证和权限管理
- ✅ 站点信息管理
- ✅ 现场检查和拍照记录
- ✅ GPS定位和地图集成
- ✅ 数据统计和报告

### 用户角色
- **系统管理员**: 全系统管理权限
- **项目经理**: 站点和人员管理
- **现场工程师**: 现场检查和数据录入

## 📱 界面展示

系统采用现代化的移动端UI设计：
- 橙色主题色彩搭配
- 卡片式布局设计
- 直观的导航和操作
- 响应式适配

## 🛠️ 快速开始

### 环境要求
- Python 3.8+
- Node.js 14+
- HBuilderX (UniApp开发工具)

### 1. 启动后端服务

```bash
# 克隆项目
cd site-app

# 方式A：一键启动（推荐，自动创建 venv/安装依赖/初始化/启动）
python3 start_backend.py

# 方式B：手动启动（可控）
python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt
cd backend && ../venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

启动脚本会自动：
- 检查Python版本
- 创建虚拟环境
- 安装依赖包
- 初始化数据库
- 创建默认用户
- 启动服务

### 2. 启动移动端（UniApp）

```bash
# 进入UniApp项目目录
cd uniapp-site-manager
npm install
# 需要 @dcloudio/uni-cli 或使用 HBuilderX
npm run dev               # 本地调试（app-plus/h5）
npm run build:h5:prod     # 构建 H5 产物
```

### 3. 默认账户

系统会自动创建以下测试账户：

**管理员账户**
- 用户名: `admin`
- 密码: `admin123`
- 角色: 系统管理员

**其他默认账户**（由 `start_backend.py` 初始化）
- 检查员: `inspector` / `inspector123`
- Tom（检查员）: `tom` / `tom123456`
- 普通用户: `test_user` / `user123`

## 📖 API文档

后端服务启动后，可通过以下地址访问API文档：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🗄️ 数据库设计

### 主要数据表
- **users**: 用户信息
- **sites**: 站点信息
- **inspections**: 检查记录

详细的数据库设计请参考 `站点信息管理APP详细设计方案.md`

## 🔧 配置说明

### 后端配置
复制 `backend/.env.example` 为 `backend/.env` 并根据需要修改配置（执行 `python3 start_backend.py` 会在 backend 目录下自动创建 `.env` 和 `uploads/`）：

```env
# 应用配置
APP_NAME=站点信息管理系统
SECRET_KEY=your-secret-key

# 数据库配置
DATABASE_URL=sqlite:///./site_manager.db

# 文件上传
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760
```

### 前端配置
在 `uniapp-site-manager/config/api.js` 或 `stores/*` 中配置后端 API 地址；开发环境默认指向 `http://localhost:8000`。

### 测试与验证
- 后端快捷测试脚本（需后端已运行）：
  - `python backend/test_login.py`
  - `python backend/test_task_api.py`
  说明：仓库仅保留上述两个快速验证脚本，其它冗余测试脚本已移除。

## 📝 开发说明

### 项目结构

```
site-app/
├── backend/                    # 后端服务（FastAPI）
│   ├── app/
│   │   ├── api/               # 路由：/api/auth, /api/tasks, /api/sites, ...
│   │   ├── core/              # 配置/数据库/安全
│   │   ├── models/            # ORM 模型
│   │   └── schemas/           # Pydantic 模型
│   ├── uploads/               # 运行期上传目录（自动创建）
│   ├── requirements.txt       # Python 依赖
│   ├── .env.example           # 环境配置示例
│   └── test_*.py              # 快速验证脚本（仅保留 login/task_api）
├── uniapp-site-manager/       # 移动端（UniApp）
│   ├── pages/                 # 页面
│   ├── stores/                # 状态管理
│   ├── config/                # API/env 配置
│   ├── manifest.json          # 应用清单
│   └── package.json           # 前端依赖与脚本
├── start_backend.py            # 一键启动后端
└── README.md                   # 项目说明
```

### 开发流程
1. 后端 API 开发（FastAPI + SQLAlchemy）
2. 移动端页面开发（UniApp + Vue 3 + Pinia）
3. 接口联调与联测
4. 验证用例与手工回归（见“测试与验证”）

### 提交与协作
- 建议使用 Conventional Commits：如 `feat(backend): ...`、`fix(uniapp): ...`
- 发起 PR 时附带变更说明、动机、测试步骤与必要截图；涉及配置/命令变化时同步更新文档。

## 🔍 故障排除

### 常见问题

**1. 后端启动失败**
- 检查Python版本是否为3.8+
- 确认所有依赖已正确安装
- 检查端口8000是否被占用

**2. 前端无法连接后端**
- 确认后端服务已启动
- 检查 API 地址配置是否正确（`uniapp-site-manager/config/api.js`）
- 确认CORS配置

**3. 数据库连接问题**
- 检查数据库文件权限
- 确认.env配置文件正确

## 📄 许可证

本项目仅供学习和开发使用。请勿提交敏感信息（密钥、生产库地址等），避免提交本地数据库文件（如 `*.db`）。

## 👥 贡献

欢迎提交Issue和Pull Request来改进项目。

## 📞 联系方式

如有问题，请通过以下方式联系：
- 项目Issues
- 技术支持邮箱: support@example.com

---

**注意**: 这是一个开发版本，请勿直接用于生产环境。生产环境部署前请进行充分的测试和安全配置。
