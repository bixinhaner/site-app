# 站点信息管理系统

现代化的通信站点信息管理解决方案，基于 UniApp + Python FastAPI 架构开发。

## 🏗️ 系统架构

### 前端
- **框架**: UniApp (Vue 3)
- **状态管理**: Pinia
- **UI设计**: 现代化橙色主题设计
- **平台支持**: Android（当前版本）

### 后端
- **框架**: Python FastAPI
- **数据库**: SQLite (开发环境) / MySQL (生产环境)
- **认证**: JWT Token
- **文档**: 自动生成 OpenAPI 文档

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

# 运行后端启动脚本
python start_backend.py
```

启动脚本会自动：
- 检查Python版本
- 创建虚拟环境
- 安装依赖包
- 初始化数据库
- 创建默认用户
- 启动服务

### 2. 配置前端

```bash
# 进入UniApp项目目录
cd uniapp-site-manager

# 使用HBuilderX打开项目
# 或者使用命令行构建
npm install
npm run dev
```

### 3. 默认账户

系统会自动创建以下测试账户：

**管理员账户**
- 用户名: `admin`
- 密码: `admin123`
- 角色: 系统管理员

**普通用户账户**
- 用户名: `test_user`
- 密码: `user123`
- 角色: 现场工程师

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
复制 `backend/.env.example` 为 `.env` 并根据需要修改配置：

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
在 `uniapp-site-manager` 中配置后端API地址（stores中的各个文件）。

## 📝 开发说明

### 项目结构

```
site-app/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据模型
│   │   └── schemas/        # 数据验证
│   ├── requirements.txt    # Python依赖
│   └── .env.example       # 环境配置示例
├── uniapp-site-manager/    # 前端应用
│   ├── pages/             # 页面文件
│   ├── stores/            # 状态管理
│   ├── static/            # 静态资源
│   └── package.json       # 前端依赖
├── start_backend.py       # 后端启动脚本
└── README.md             # 项目说明
```

### 开发流程
1. 后端API开发 (FastAPI + SQLAlchemy)
2. 前端页面开发 (UniApp + Vue 3)
3. 状态管理 (Pinia)
4. 接口联调和测试

## 🔍 故障排除

### 常见问题

**1. 后端启动失败**
- 检查Python版本是否为3.8+
- 确认所有依赖已正确安装
- 检查端口8000是否被占用

**2. 前端无法连接后端**
- 确认后端服务已启动
- 检查API地址配置是否正确
- 确认CORS配置

**3. 数据库连接问题**
- 检查数据库文件权限
- 确认.env配置文件正确

## 📄 许可证

本项目仅供学习和开发使用。

## 👥 贡献

欢迎提交Issue和Pull Request来改进项目。

## 📞 联系方式

如有问题，请通过以下方式联系：
- 项目Issues
- 技术支持邮箱: support@example.com

---

**注意**: 这是一个开发版本，请勿直接用于生产环境。生产环境部署前请进行充分的测试和安全配置。