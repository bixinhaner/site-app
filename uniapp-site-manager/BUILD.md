# 应用构建指南

本文档说明如何配置和构建不同环境的应用程序。

## 环境配置

### 配置文件位置
所有环境配置文件存放在 `env/` 目录下：

- `.env.development` - 开发环境配置
- `.env.production` - 生产环境配置
- `.env.example` - 配置示例文件

### 配置项说明

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `API_BASE_URL` | API服务器地址 | `http://192.168.1.100:8000` |
| `APP_NAME` | 应用名称 | `站点管理系统` |
| `APP_VERSION` | 应用版本 | `1.0.0` |
| `DEBUG` | 调试模式 | `true`/`false` |

## 构建命令

### 使用npm脚本构建

```bash
# 开发环境APP
npm run build:dev

# 生产环境APP  
npm run build:prod

# 开发环境H5
npm run build:h5:dev

# 生产环境H5
npm run build:h5:prod

# 开发环境微信小程序
npm run build:mp:dev

# 生产环境微信小程序
npm run build:mp:prod
```

### 使用shell脚本构建

```bash
# 基本用法
./scripts/build.sh --env production --platform app-plus

# 构建生产环境Android/iOS应用
./scripts/build.sh --env production --platform app-plus

# 构建开发环境H5应用
./scripts/build.sh --env development --platform h5

# 构建生产环境微信小程序
./scripts/build.sh --env production --platform mp-weixin
```

### 平台支持

| 平台 | 参数值 | 说明 |
|------|--------|------|
| Android/iOS | `app-plus` | 原生应用 |
| H5网页 | `h5` | 浏览器网页应用 |
| 微信小程序 | `mp-weixin` | 微信小程序 |
| 支付宝小程序 | `mp-alipay` | 支付宝小程序 |

## 配置步骤

### 1. 创建环境配置

复制示例配置文件：
```bash
cp env/.env.example env/.env.production
```

### 2. 修改配置

编辑对应环境的配置文件，设置正确的API地址：

**开发环境** (`env/.env.development`)：
```env
API_BASE_URL=http://192.168.1.100:8000
APP_NAME=站点管理系统
APP_VERSION=1.0.0
DEBUG=true
```

**生产环境** (`env/.env.production`)：
```env
API_BASE_URL=https://api.yourdomain.com
APP_NAME=站点管理系统
APP_VERSION=1.0.0
DEBUG=false
```

### 3. 构建应用

选择合适的构建命令进行构建。

## 配置安全

- ⚠️  **不要**将包含敏感信息的`.env.*`文件提交到代码仓库
- ✅  将`.env.*`添加到`.gitignore`文件中
- ✅  在部署服务器上单独配置生产环境文件
- ✅  使用`.env.example`作为配置模板

## 构建过程

构建脚本会执行以下步骤：

1. 读取指定环境的配置文件
2. 验证配置项的完整性
3. 替换代码中的配置占位符
4. 调用UniApp CLI进行构建
5. 恢复原始配置文件

## 故障排除

### 配置文件不存在
```
❌ 环境配置文件不存在: env/.env.production
```
**解决方法**：创建对应的配置文件或使用正确的环境名称。

### API地址配置错误
如果构建后应用无法连接服务器，检查：
1. 配置文件中的`API_BASE_URL`是否正确
2. 服务器是否可访问
3. 防火墙设置是否正确

### 构建失败
1. 检查Node.js版本是否兼容
2. 确认所有依赖已安装：`npm install`
3. 检查UniApp CLI是否正确安装

## 示例配置

### 本地开发
```env
API_BASE_URL=http://localhost:8000
DEBUG=true
```

### 局域网测试
```env  
API_BASE_URL=http://192.168.1.100:8000
DEBUG=true
```

### 生产部署
```env
API_BASE_URL=https://api.example.com
DEBUG=false
```