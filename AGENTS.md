# Repository Guidelines

## Rule
- 开发过程中若有任何不确定，必须主动向用户提问。
- If temporary verification and test scripts or code are generated during the task, please create them in the project's temp directory. If the directory does not exist, create it.Other temporary files or code that do not affect business operations during the task should also be placed in the temp directory.
- python都是用虚拟环境运行的。
- 每次有变动请审视根目录的README.md，并更新内容，确保文档始终与代码实现一致，且该文档说人话易于理解，避免深度技术语言。

## Project Structure & Module Organization
- Root helpers: `start_backend.py` boots the FastAPI server; `docs/` holds reference material; DB snapshots live under `db/`.
- `backend/app/` contains the FastAPI application, with routers, models, and utilities grouped by feature; script-style tests sit alongside in `backend/test_*.py`.
- `web-admin/` hosts the Vue 3 + Vite admin UI (`src/`, `router/`, `views/`, static assets in `public/`).
- `uniapp-site-manager/` provides the UniApp mobile client (`pages/`, `stores/`, `config/`, `manifest.json`). Runtime uploads persist in `backend/uploads/` (keep out of version control).

## Build, Test, and Development Commands
- `python3 -m venv venv && ./venv/bin/pip install -r backend/requirements.txt` — create an isolated backend environment.
- `python3 start_backend.py` or `uvicorn app.main:app --reload --port 8000` (from `backend/`) — launch the API locally on port 8000.
- `python backend/test_login.py` / `python backend/test_task_api.py` — run smoke tests against the live API (users seeded such as `admin/admin123`).
- `npm install && npm run dev` in `web-admin/` — start the Vue admin console with hot reload.
- `npm install && npm run dev` in `uniapp-site-manager/` — launch the UniApp dev server (requires `@dcloudio/uni-cli` or HBuilderX).

## Coding Style & Naming Conventions
- Python follows PEP 8: 4-space indents, `snake_case` for functions/variables, `PascalCase` for classes, type hints on touched signatures.
- Vue/JS uses 2-space indents, single quotes, trailing commas; Single File Components named in `PascalCase` (e.g., `EquipmentList.vue`).
- Keep REST endpoints under `/api/...`; colocate request/response schemas with their router modules.

## Testing Guidelines
- Backend tests are standalone scripts; ensure the API is running before executing them.
- Name new tests `backend/test_<feature>.py` and target local endpoints.
- No automated frontend tests; validate critical UI flows manually and capture evidence for PRs.

## Security & Configuration Tips
- Load backend config from `backend/.env` (copy from `.env.example`); never commit secrets or `.db` artifacts.
- Limit CORS to required origins in development and production.
- Treat `backend/uploads/` as runtime storage only; do not store credentials or long-lived assets there.

## Production SSH Access
- 生产环境 SSH 信息记录在本机 `~/.ssh/config`，不要把私钥正文、sudo 密码或生产 `.env` 密钥写入仓库。
- Surge 生产环境：
  - 连接命令：`ssh site-app-surge`
  - HostName：`70.153.137.18`
  - User：`baicells`
  - Port：`50533`
  - IdentityFile：`/Users/like/Downloads/Surge-app_key.pem`
- Savanna 生产环境：
  - 连接命令：`ssh site-app-savanna`
  - 目标主机：`localhost:8722`
  - User：`admin82`
  - IdentityFile：`/Users/like/.ssh/site_app_savanna_ed25519`
  - ProxyJump：`site-app-savanna-bastion`
- Savanna 跳板：
  - 连接命令：`ssh site-app-savanna-bastion`
  - HostName：`13.93.150.80`
  - User：`baicells`
  - Port：`53680`
  - IdentityFile：`/Users/like/.ssh/site_app_savanna_ed25519`
- 权限声明：Surge 和 Savanna 两个生产环境均按“具备 sudo 免密 root 权限”的运维前提处理。Savanna 登录 `admin82` 后可执行 `sudo su -` 切换到 root，再做部署、重启服务或编辑 root 拥有文件。执行生产写入/重启前，优先用 `sudo su -` 验证 root 权限；如果验证失败，停止写入/重启动作并向用户说明权限配置异常。

## Git 与提交规则

### Commit 格式

```
<type>(<scope>): <中文一句话概述>

例:
  fix(scope): 修复用户启用后看不到负责客户/商机/联系人
  feat(boq): 增加价格管理 BOQ 可销售清单
  hotfix(login): 修复生产登录 CORS 配置遗漏
  ux(account): 重组客户详情页 SAP 信息区
  docs(contributing): 补充 GitFlow 分支策略
```

`type` 可选：`feat` / `fix` / `hotfix` / `ux` / `ops` / `data` / `docs` / `chore` / `perm` / `test`

提交信息强制规则：
- 标题描述必须使用中文；`type`、`scope`、文件路径、命令、配置键等约定字段可保留英文
- 每次 commit 都必须写 body，并按序号描述修改功能和内容
- 序号顺序按影响面组织：业务/用户可见变化 → API/数据/权限 → 前端/UI → 运维/文档/测试 → 验证结果
- 每条序号写清“为什么”和“对用户/生产的影响”，避免只写“修改代码”

Commit body 模板：

```text
1. <功能或模块>：<具体改动、为什么这样改、对用户或生产的影响>
2. <功能或模块>：<具体改动、为什么这样改、对用户或生产的影响>
3. 验证：<执行的检查、测试、部署或未执行原因>
```
