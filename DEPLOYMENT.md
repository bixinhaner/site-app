# 🚀 站点信息管理系统 - 80端口部署方案

## 📋 部署架构概述

**服务器IP**: `113.45.25.135`  
**开放端口**: 仅80端口  
**解决方案**: Nginx反向代理，将8000和3030端口服务通过80端口访问

### 🏗️ 访问路径设计
```
http://113.45.25.135/site-api/     → 后端API服务 (8000端口)
http://113.45.25.135/site-admin/   → Web管理端 (3030端口)
http://113.45.25.135/health        → 健康检查
http://113.45.25.135/docs          → API文档
```

---

## 🔧 服务器端配置

### 1. Nginx反向代理配置

将项目根目录的 `nginx-site-app.conf` 文件部署到服务器：

```bash
# 1. 上传配置文件到服务器
scp nginx-site-app.conf root@113.45.25.135:/etc/nginx/sites-available/site-app

# 2. 启用站点配置
sudo ln -s /etc/nginx/sites-available/site-app /etc/nginx/sites-enabled/

# 3. 测试配置文件
sudo nginx -t

# 4. 重新加载Nginx
sudo systemctl reload nginx
```

### 2. 后端服务启动

在服务器上启动后端API服务：

```bash
# 方式1: 直接启动 (推荐用于生产环境)
cd /path/to/site-app/backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 方式2: 使用gunicorn (生产环境推荐)
pip install gunicorn
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000

# 方式3: 后台运行
nohup python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > backend.log 2>&1 &
```

### 3. Web管理端服务

在服务器上构建并启动Web管理端：

```bash
# 1. 构建生产版本
cd /path/to/site-app/web-admin
npm install
npm run build

# 2. 使用serve或nginx托管 (端口3030)
npx serve -s dist -p 3030

# 或者配置nginx直接托管build产物
```

---

## 📱 前端配置调整

### ⚡ 新版配置系统（推荐）

#### 统一环境配置
已实现统一的配置管理系统，解决跨机器部署的API地址问题：

**Web管理端**：
```bash
# 1. 复制环境变量模板
cd web-admin
cp .env.example .env.production

# 2. 修改生产环境配置
echo "VITE_API_BASE_URL=http://113.45.25.135/site-api" > .env.production

# 3. 构建生产版本
npm run build
```

**自动适配配置**：
- ✅ 开发环境：自动使用 `http://localhost:8000`
- ✅ 生产环境：使用环境变量 `VITE_API_BASE_URL`
- ✅ 同服务器部署：留空自动使用当前域名

#### 配置文件说明

**统一配置中心** (`web-admin/src/config/env.js`)：
```javascript
// 自动检测环境并应用相应配置
const getBaseURL = () => {
  // 优先使用构建时环境变量
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL
  }
  
  // 生产环境自动适配当前域名
  if (import.meta.env.PROD && typeof window !== 'undefined') {
    return window.location.origin
  }
  
  // 开发环境默认
  return 'http://localhost:8000'
}
```

**环境变量模板** (`.env.example`)：
```bash
# 开发环境
VITE_API_BASE_URL=http://localhost:8000

# 生产环境 - 指定服务器IP
VITE_API_BASE_URL=http://113.45.25.135/site-api

# 同服务器部署 - 使用相对路径
VITE_API_BASE_URL=
```

### 🔄 兼容性配置（旧版）

#### UniApp移动端配置

已更新 `uniapp-site-manager/config/env.js`:

```javascript
// 生产环境配置自动使用80端口访问
const productionConfig = {
  API_BASE_URL: 'http://113.45.25.135/site-api',  // 通过Nginx反向代理
  APP_NAME: '站点管理系统',
  APP_VERSION: '1.0.0',
  DEBUG: 'false'
}
```

#### Web管理端配置 (手动修改方式)

如果不使用环境变量，可以直接修改配置文件：

```javascript
// web-admin/src/config/env.js - 修改默认配置
const config = {
  API_BASE_URL: 'http://113.45.25.135/site-api',
  // 其他配置...
}
```

### 🚀 快速部署脚本

创建 `deploy.sh` 自动化部署：
```bash
#!/bin/bash
SERVER_IP="113.45.25.135"

# Web管理端构建
cd web-admin
echo "VITE_API_BASE_URL=http://$SERVER_IP/site-api" > .env.production
npm install && npm run build

# 上传到服务器
scp -r dist/ root@$SERVER_IP:/var/www/site-admin/

echo "部署完成！访问: http://$SERVER_IP/site-admin/"
```

---

## ✅ 部署验证

### 1. 健康检查

```bash
# 测试后端API
curl http://113.45.25.135/site-api/health

# 测试API文档
curl http://113.45.25.135/docs
```

### 2. 功能测试

```bash
# 测试用户登录API
curl -X POST http://113.45.25.135/site-api/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# 测试Web管理端访问
curl http://113.45.25.135/site-admin/
```

### 3. 日志监控

```bash
# 查看Nginx访问日志
tail -f /var/log/nginx/site-app.access.log

# 查看Nginx错误日志
tail -f /var/log/nginx/site-app.error.log

# 查看后端服务日志
tail -f backend.log
```

---

## 🔒 安全配置建议

### 1. SSL证书配置

```nginx
# 添加HTTPS支持
server {
    listen 443 ssl;
    server_name 113.45.25.135;
    
    ssl_certificate /path/to/certificate.crt;
    ssl_certificate_key /path/to/private.key;
    
    # 其他配置...
}
```

### 2. 防火墙设置

```bash
# 确保只开放80和443端口
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw deny 8000/tcp
sudo ufw deny 3030/tcp
```

### 3. 访问控制

```nginx
# 限制特定路径访问
location /site-admin/admin {
    allow 192.168.1.0/24;  # 仅允许内网访问
    deny all;
}
```

---

## 🚨 故障排除

### 常见问题

1. **502 Bad Gateway**
   - 检查后端服务是否在8000端口运行
   - 检查防火墙是否阻止内部通信

2. **404 Not Found**
   - 检查Nginx配置中的proxy_pass路径
   - 确认服务运行在正确端口

3. **CORS错误**
   - 检查后端CORS配置
   - 确认请求头设置正确

### 调试命令

```bash
# 检查端口占用
netstat -tlnp | grep :8000
netstat -tlnp | grep :3030

# 检查Nginx配置
sudo nginx -t

# 重启服务
sudo systemctl restart nginx
sudo systemctl restart site-app-backend  # 如果使用systemd
```

---

## 📊 性能优化

### 1. Nginx缓存配置

```nginx
# 静态资源缓存
location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg)$ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

### 2. Gzip压缩

```nginx
# 启用gzip压缩
gzip on;
gzip_vary on;
gzip_types text/plain application/json application/javascript text/css;
```

### 3. 连接池优化

```nginx
# 后端连接优化
upstream backend {
    server 127.0.0.1:8000;
    keepalive 32;
}
```

---

## 📝 维护说明

### 1. 日志轮转

```bash
# 配置logrotate
sudo vim /etc/logrotate.d/site-app
```

### 2. 自动重启

```bash
# 使用systemd管理服务
sudo systemctl enable site-app-backend
sudo systemctl enable nginx
```

### 3. 监控脚本

```bash
#!/bin/bash
# 健康检查脚本
if ! curl -f http://127.0.0.1/site-api/health; then
    echo "Service is down, restarting..."
    # 重启逻辑
fi
```

---

## 🎯 总结

通过Nginx反向代理成功实现：
- ✅ 8000端口后端API → `http://113.45.25.135/site-api/`
- ✅ 3030端口Web管理端 → `http://113.45.25.135/site-admin/`
- ✅ 仅使用80端口对外访问
- ✅ UniApp已配置正确的API地址
- ✅ 完整的部署和故障排除方案

现在可以在不开放8000和3030端口的情况下，通过80端口正常访问所有服务！