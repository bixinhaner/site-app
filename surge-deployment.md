# Surge 部署说明（Ubuntu 22.04 / root / 仅 80/443）

适用场景：
- 服务器：Ubuntu 22.04，root 用户
- 目录：项目代码位于 `/usr/local/site-app`
- 对外端口：只开放 `80/443`（HTTP 自动跳转到 HTTPS）
- 反向代理：使用 **Caddy + Let’s Encrypt** 自动签发与续期证书
- 进程管理：使用 **pm2** 托管 `backend` 与 `caddy`
- 数据库：SQLite（全新库，不迁移历史数据）
- 同域名：`/` 为 WebAdmin；`/api/*` 反代到后端

---

## 1. 架构与端口说明

- 公网仅暴露：
  - `80`：仅用于跳转到 `443` + Let’s Encrypt 校验（建议保留）
  - `443`：对外提供 WebAdmin + API
- 后端 uvicorn：
  - **只监听本机**：`127.0.0.1:8000`（不对公网开放）
- Caddy：
  - 监听 `:80`、`:443`
  - 路由：
    - `/api/*`、`/uploads/*`、`/docs` 等转发到后端 `127.0.0.1:8000`
    - 其余路径由静态站点 `/usr/local/site-app/web-admin/dist` 提供（SPA 回退 `index.html`）

---

## 2. 首次部署步骤（可复制）

> 说明：以下命令默认以 root 执行。

### 2.1 前置检查

```bash
# 1) 域名是否解析到本机公网 IP（应返回你的公网 IP）
dig +short siteapp.indonesiacentral.cloudapp.azure.com

# 2) 80/443/8000 是否被占用（有占用先停掉对应服务）
ss -lntp | egrep ':(80|443|8000)\b' || true
```

> 注意：Azure 防火墙 / NSG 需要放行 `80/443` 入站，否则 Let’s Encrypt 可能签发失败。

### 2.2 安装依赖（Node + pm2 + Caddy）

```bash
apt update
apt install -y git curl python3 python3-venv gpg debian-keyring debian-archive-keyring apt-transport-https

# Node.js 20（用于构建 web-admin）
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs

# pm2
npm i -g pm2

# 安装 Caddy（官方源）
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | tee /etc/apt/sources.list.d/caddy-stable.list
apt update
apt install -y caddy

# 重要：停掉 systemd 的 caddy，避免与 pm2 抢占 80/443
systemctl stop caddy || true
systemctl disable caddy || true
```

### 2.3 拉代码到 `/usr/local/site-app`

```bash
cd /usr/local
git clone <你的仓库地址> site-app

cd /usr/local/site-app
```

### 2.4 后端：创建 venv + 安装依赖 + 写 `.env`

> 说明：本项目在部署中使用 `backend/venv` 作为虚拟环境路径（与 pm2 启动命令一致）。

```bash
cd /usr/local/site-app/backend

python3 -m venv venv
./venv/bin/pip install -U pip
./venv/bin/pip install -r requirements.txt
```

写 `/usr/local/site-app/backend/.env`：

```bash
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(64))')"

cat > /usr/local/site-app/backend/.env <<EOF
DEBUG=False
SECRET_KEY=${SECRET_KEY}
DATABASE_URL=sqlite:///./site_manager.db
ALLOWED_HOSTS_STR=*

# 启动自检：默认管理员（仅首次创建；已存在绝不重置密码）
AUTO_CREATE_ADMIN=true
DEFAULT_ADMIN_USERNAME=admin
DEFAULT_ADMIN_PASSWORD=请改成强密码
DEFAULT_ADMIN_EMAIL=admin@example.com
DEFAULT_ADMIN_FULL_NAME=系统管理员
EOF
```

> 说明：后端启动时若数据库中不存在 `admin`，会自动创建；若已存在，只会修复非法邮箱（避免 500），**不会重置密码**。

### 2.5 前端：构建 WebAdmin（dist）

```bash
cd /usr/local/site-app/web-admin
npm ci
npm run build

# 确认产物存在
ls -la /usr/local/site-app/web-admin/dist | head
```

### 2.6 写 Caddyfile（同域：前端 `/`，后端 `/api`）

```bash
cat > /usr/local/site-app/Caddyfile <<'EOF'
siteapp.indonesiacentral.cloudapp.azure.com {
  encode zstd gzip

  @backend path /api/* /uploads/* /docs* /redoc* /openapi.json /health
  handle @backend {
    reverse_proxy 127.0.0.1:8000
  }

  handle {
    root * /usr/local/site-app/web-admin/dist
    try_files {path} /index.html
    file_server
  }

  # 可选：确认 HTTPS 一切正常后再开启（更“强制 HTTPS”）
  # header {
  #   Strict-Transport-Security "max-age=31536000; includeSubDomains"
  # }
}
EOF
```

> 关键点：必须使用 `handle @backend` 单独处理后端路径，避免被 `try_files ... /index.html` 重写，从而出现 `POST /api/auth/login -> 405` 的问题。

### 2.7 pm2 启动后端（仅本机监听）+ 启动 Caddy（对外 80/443）

```bash
# 后端（127.0.0.1:8000）
pm2 delete site-backend || true
pm2 start /usr/local/site-app/backend/venv/bin/python \
  --name site-backend \
  --cwd /usr/local/site-app/backend \
  --interpreter none \
  -- -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Caddy（80/443）
pm2 delete site-caddy || true
pm2 start /usr/bin/caddy \
  --name site-caddy \
  --interpreter none \
  -- run --config /usr/local/site-app/Caddyfile --adapter caddyfile
```

### 2.8 pm2 开机自启

```bash
pm2 save
pm2 startup systemd -u root --hp /root
pm2 save
```

### 2.9 验收（HTTP 跳 HTTPS / 后端健康 / 文档 / 登录）

```bash
# 1) HTTP 是否跳转到 HTTPS
curl -I http://siteapp.indonesiacentral.cloudapp.azure.com

# 2) HTTPS 访问
curl -I https://siteapp.indonesiacentral.cloudapp.azure.com

# 3) 后端健康检查（走同域 /health）
curl -sS https://siteapp.indonesiacentral.cloudapp.azure.com/health

# 4) API 文档
curl -I https://siteapp.indonesiacentral.cloudapp.azure.com/docs

# 5) 查看服务状态/日志
pm2 status
pm2 logs site-backend --lines 80
pm2 logs site-caddy --lines 120
```

---

## 3. 更新发布流程（建议固定流程）

### 3.1 标准更新（推荐）

适用于：后端依赖/前端依赖/构建产物可能变化的常规发布。

```bash
cd /usr/local/site-app
git pull

# 后端依赖（确保 bcrypt<4 等修复生效）
cd /usr/local/site-app/backend
./venv/bin/pip install -r requirements.txt

# 前端重新构建
cd /usr/local/site-app/web-admin
npm ci
npm run build

# 重启服务
pm2 restart site-backend
pm2 restart site-caddy

# 健康检查
curl -sS https://siteapp.indonesiacentral.cloudapp.azure.com/health
```

### 3.2 快速更新（可选）

适用于：只改了后端业务代码或前端页面代码，依赖不变时加速发布。

```bash
cd /usr/local/site-app
git pull

# 如果只是后端代码变更
pm2 restart site-backend

# 如果只是前端代码变更（但仍需要重新 build）
cd /usr/local/site-app/web-admin
npm run build
pm2 restart site-caddy
```

---

## 4. 常见问题（排障要点）

### 4.1 Let’s Encrypt 签发失败（Timeout / 连接问题）

重点检查：
- Azure 防火墙 / NSG 是否放行 `80/443` 入站
- 本机是否还有进程占用 `80/443`：`ss -lntp | egrep ':(80|443)\b'`
- 若启用 `ufw`：确认允许 `80/443`

### 4.2 WebAdmin 登录 `POST /api/auth/login` 返回 405

原因：Caddy 把 `/api/*` 也走了 `try_files ... /index.html`，POST 被静态站点处理而返回 405。  
解决：确保 Caddyfile 用 `handle @backend { reverse_proxy ... }` 单独处理后端路径（见上文示例）。

### 4.3 创建管理员时报 bcrypt / passlib 报错

原因：`passlib==1.7.4` 与新版 `bcrypt` 不兼容。  
解决：`backend/requirements.txt` 已加 `bcrypt<4`；部署/更新时执行一次：

```bash
cd /usr/local/site-app/backend
./venv/bin/pip install -r requirements.txt
```

### 4.4 登录返回 500（Internal Server Error）

常见原因：管理员邮箱使用了 `@xxx.local` 之类保留域名，触发后端响应模型 `EmailStr` 校验失败。  
解决：将管理员邮箱改为合法邮箱（如 `admin@example.com`）。后端启动逻辑会自动修复非法邮箱。

