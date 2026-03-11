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
│   ├── db/                    # 备份元数据库（backup_meta.db）
│   ├── db-backups/            # 备份压缩包目录（db_backup_*.zip）
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
│   │   ├── i18n/              # 国际化配置与词库
│   │   ├── components/common/ # 通用组件（含语言切换器）
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
- **CLI 构建兼容说明（2026-03）**
- `scripts/build.js` 会自动把 `UNI_INPUT_DIR` 指向 `uniapp-site-manager` 根目录，兼容当前“源码不在 src/”的目录结构（避免 CLI 误找 `src/manifest.json`）。
- 执行 `npm run build:dev / build:prod / build:h5:dev / build:h5:prod` 时，统一走 `npm run build -- --platform <platform>`，不再依赖额外的 `build:h5` 等子脚本。
- 若本地未安装 `sass`，CLI 会临时复用同仓库 `web-admin/node_modules/sass` 并在构建结束后清理临时链接，不影响 HBuilderX 正常编包流程。
- 仅 CLI 构建时启用 `UNI_CLI_VUE_BRIDGE`，为 `@dcloudio/uni-app` 需要的私有导出做兼容桥接；HBuilderX 默认流程不启用该桥接。
- **UniApp H5 本地调试（2026-03）**
- 现在可以直接用浏览器跑 `uniapp-site-manager` 的 H5 登录、首页和库存工作台，不再停留在白屏或只到登录页。
- 本地联调前，请先把移动端接口地址切到本机后端（例如 `http://127.0.0.1:8000`）；否则 H5 仍会沿用本地缓存里的线上地址。
- 退库收货页会按当前账号的库存范围动态说明数据口径：普通账号不会进入该页，仓库负责人显示“管理仓”，全仓角色显示“全部仓库”。
- **App 列表默认 100 条上限修复（2026-03-10）**
- 移动端 `站点/工单` 在未传分页参数时，已改为自动翻页聚合，不再被后端默认 `limit=100` 截断；首页 `Total Sites / Operational / Maintenance` 和工单统计会基于完整数据计算。
- 需要分页的页面（例如检查前“选择站点”）仍可继续传 `skip/limit` 按页取数，避免一次性加载过多数据。
- 后端 `GET /api/sites/` 与 `GET /api/work-orders` 列表接口补充了稳定排序后再分页，减少跨页重复或漏项风险。

#### Web 管理端
```bash
cd web-admin
npm install
npm run dev                    # 默认运行在 5173 端口
npm run build                  # 生产构建
```
- **多语言切换（2026-03）**：
- 登录页右上角提供语言切换器；进入后台后，语言切换器在顶部导航栏（用户信息左侧）。
- 语言菜单支持三种语言：`中文 / English / Bahasa Indonesia`。
- 默认语言优先级：用户上次选择 > 浏览器语言（`en*` 自动英文、`id* / in*` 自动印尼语，其它默认中文）。
- 切换后即时生效，并持久化到浏览器本地存储。
- 为兼容历史页面中的中文硬编码，遗留文案桥接层已支持英文和印尼语两种目标语言（含执行工单及关联页面）。
- **站点模块国际化补齐（2026-03）**：
- 已补齐“仪表盘-站点概况”“仪表盘-站点事件趋势”“站点地图”以及路由 `SiteMap` 的中英文词条；切换英文后不再出现中英混杂（包括站点趋势图例、站点地图页面标题/筛选项/按钮/图例/提示文案）。
- **站点地图图例标签修复（2026-03-10）**：
- 已修复站点地图“状态图例”标签取值，统一走国际化状态词条；中英文切换后图例与站点状态胶囊、地图弹窗保持一致。
- **站点详情关键节点时间（2026-03-10）**：
- 站点详情页“站点基本信息”下新增“关键节点时间”模块，展示安装开始、安装完成、上线、激活、SSV 五个节点的首次发生时间（无记录显示“未发生”）。
- 新增接口 `GET /api/sites/{site_id}/milestones`，时间口径与仪表盘站点趋势保持一致：
- 安装开始=“仍关联有效开站工单”的设备首次绑定（bind/rebind），安装完成=开站工单首次提交，上线=开站工单首次 activated，激活=开站工单首次 completed，SSV=SSV 工单首次 completed（均排除 VOIDED）。
- **站点详情国际化与信息区重排（2026-03-10）**：
- 已补齐 `SiteDetail` 页面文案国际化（中英文）：页面标题、操作按钮、基础信息、关键节点、编辑/删除弹窗、工单表格、设备状态表格、提示消息与确认框文案。
- “站点基本信息”已改为统一卡片化排版：核心信息分组展示，跳过记录独立信息块，减少重复字段，信息层级更清晰，移动端自动单列适配。
- **站点列表批量逐条编辑（2026-03-10）**：
- `站点管理 -> 站点列表` 新增“批量编辑”入口（需 `sites:update:write` 权限），支持勾选多条站点后在同一弹窗里逐行修改不同字段值并一次提交。
- 后端新增 `PUT /api/sites/batch-update`，按行返回成功/失败明细（含行号、站点ID/编码、错误原因）；支持“部分成功、部分失败”场景，便于现场一次处理多站点数据。
- **站点批量更新（Excel回写，2026-03-10）**：
- 当站点数量较多时，可走 `站点列表导出 -> Excel编辑 -> 站点信息维护页上传` 的方式批量更新，不需要在弹窗逐条手改。
- `站点信息维护` 页新增“批量更新（Excel回写）”页签，支持 `dry-run` 试运行校验与正式执行更新；结果会返回逐行动作（`would_update / updated / noop`）与失败原因，便于一次性处理大批量数据。
- **登录后首页兜底（2026-03）**：
- Web 管理端登录后不再固定跳 `/dashboard`；如果当前账号没有仪表盘权限，系统会自动跳到该账号第一个有权访问的菜单页。
- 路由守卫也会使用同一套兜底规则，避免登录成功后因为首页无权限而卡住或反复重定向。

### 服务访问地址
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Web 管理端**: http://localhost:5173
- **健康检查**: http://localhost:8000/health

### 生产部署组网差异（Indonesia / Savanna）
- **标准模式（Indonesia）**：公网 `80/443` 直达 Caddy，由 Caddy 自动申请和续期 HTTPS 证书（Let’s Encrypt）。
- **Savanna 模式（Uganda）**：HTTPS 证书和 TLS 终止放在防火墙/网关，Caddy 仅接收 HTTP 回源（通常 `:80`），不做证书签发和 HTTPS 跳转。
- **域名要求**：域名必须与入口证书匹配；例如证书是 `*.savannafibre.com` 时，应使用 `siteapp.savannafibre.com`，不要使用 `siteapp.savannafibre.co.ug`。
- **详细操作**：见 `surge-deployment.md` 第 `2.6` 节（两套 Caddyfile 模板）。

### 移动端登录可选服务器（右上角国旗切换）
- **Indonesia（默认）**: `https://siteapp.indonesiacentral.cloudapp.azure.com`
- **Uganda**: `https://siteapp.savannafibre.com`
- **China**: `http://113.45.25.135/api`

## 👥 用户系统

### 默认账户
| 用户名 | 密码 | 角色 | 权限 |
|--------|------|------|------|
| admin | admin123 | admin | 系统管理员 (全权限) |
| inspector | inspector123 | inspector | 现场检查员 |
| tom | tom123456 | inspector | 现场检查员 |
| test_user | user123 | user | 普通用户 |
| planner | planner123 | planner | 网络规划人员 |

### RBAC（2026-03）
- 后端已升级为 **多角色 + 权限码** 模型，`users.role` 字段已移除，改为 `users` + `user_roles` 关联。
- 权限码采用 `module:resource:action` 结构，例如：`workorder:dispatch:write`、`inventory:return:write`。
- `admin` 账号绕过全部权限校验；`manager` 不再自动等同 `admin`。
- 新增两项终端登录权限：`auth:web-login` 和 `auth:app-login`。登录接口会根据 `client_type` / `X-Client` 判断是 Web 端还是 App 端；如果角色没勾选对应权限，会在登录时直接提示原因并拒绝新登录。
- 当前采用“方案 A”：只限制**新登录**。已经签发的 token 不会因为后续撤销登录权限而立刻失效，刷新/续期逻辑也不主动踢下线。
- 新增 Web 工单执行相关权限码：
- `workorder:execute:web`：允许在 `web-admin` 使用“我的执行工单”入口；但菜单是否显示、哪些工单类型可见、哪些类型可编辑，还要同时受 `auth:web-login`、Web 工单执行总开关和类型配置控制
- `Web工单执行配置` 页面现在只对“权限系统管理员”开放，入口权限统一收口到 `authz:manage:all`
- Web 管理端新增 **系统配置 -> 角色权限** 页面（`/settings/permissions`），支持：
- 新建/编辑/删除自定义角色
- 配置角色权限点
- 配置角色数据范围（站点 / 工单 / 检查）
- 用户管理页支持给用户分配多个角色
- 权限配置页现在按 **APP端权限 / WEB端权限** 分区展示，并把各自的“登录权限”固定放在最前面，方便先看“能不能登录”，再看“登录后能做什么”。
- 当前迭代已覆盖：`web-admin + backend + uniapp-site-manager`。
- UniApp 现已接入统一权限能力：登录态会返回 `roles / permissions / data_scopes`，前端统一通过 `hasRole / hasPermission / can / getDataScope` 做判断。
- UniApp 接入原则：`权限优先，旧角色兜底`。如果账号还没有任何 `app:*` 权限码，则继续按旧 `role` 规则兼容，保证老角色升级后功能范围不突变。
- 默认内置角色的 app 权限模板已按旧移动端行为对齐，例如 `warehouse_manager` 仍保留原先可见的检查/地图入口，但不会额外获得站点列表、工单列表这类旧版没有的功能；后续新建/自定义角色，建议直接按权限码控制 app 功能。
- 默认内置角色的数据范围模板也会随启动自动补齐到数据库；初始化已做幂等处理，同一台服务器重复重启、重复执行初始化不会再因为 `role_permissions` 或 `role_data_scopes` 重复写入而启动失败。
- 库存链路已单独返回 `inventory_scope / managed_warehouse_ids`，范围明确分成 `self / managed / all` 三档：
- `self`：只看自己的申请、领料、退库和本人出入库记录
- `managed`：在 `self` 基础上，再看自己负责仓库的数据；典型场景是 `warehouse.manager_id = 当前用户`
- `all`：看全部仓库；默认由 `admin / manager` 或显式授予 `inventory:warehouse:all` 获得
- 仓库侧工作台（物料审批、出库确认、退库收货）现在统一按 `managed / all` 开放，不再靠 `inventory:material-request:write`、`inventory:return:write` 这类权限码反推“仓库身份”。
- `inventory:warehouse:write` 现在只表示“仓库配置管理”，不再顺带放开入库、快速出库、人员领用台账或全仓访问；这类能力分别要求显式的 `inventory:stock-in:write`、`inventory:stock-out:write`、`inventory:user-ownership:read`、`inventory:history:read`。
- 默认内置角色里，`inspector / planner / reviewer / user` 已显式保留“个人申请 / 个人退库”所需权限；是否额外拥有仓库审批能力，取决于是否真的负责某个仓库，而不是角色名本身。
- 启动时如果发现数据库中的系统内置角色权限仍停留在“已知旧模板”，后端会自动修正到当前默认模板；只在命中旧模板快照时才修，不会无差别覆盖人工改过的系统角色。

### UniApp 权限边界（2026-03）
- **功能权限**：控制菜单、首页入口、底部 Tab、页面可达性、关键按钮显示；这一层统一走权限码和 `can(...)`。
- **数据范围**：现在也接入统一角色管理，但不和功能权限码混用。当前已显式支持 `站点 / 工单 / 检查` 三类范围；例如 `inspector` 默认是“仅自己”，`surveyor` 默认是“仅自己且仅勘察”，其余内置角色默认是“全部”。
- **业务语义**：像 `surveyor` 只能处理勘察类业务，这种不是单纯“看多少数据”的规则，仍由后端业务逻辑兜底，不强行塞成权限码。
- 这三层是故意分开的：权限码负责“能不能打开某个功能”，数据范围负责“打开后能看到哪些数据”，业务语义负责“具体能处理哪类业务”。
- 多角色合并规则也拆开看：**功能权限取并集**；**数据范围按后端角色优先级取主范围**。为保证自定义角色可用，解析时会让“自定义角色”优先于基础 `user`，但仍不会压过 `admin / manager / warehouse_manager / planner / reviewer / inspector / surveyor` 这些现网内置角色。
- 如果某个角色还没有显式配置数据范围，后端会自动回退到旧角色语义，保证老账号升级后行为不突变。
- `admin` 继续全量绕过；`manager` 走显式权限，不再隐式等同 `admin`。

## 🏢 核心功能模块

### 1. 工单管理系统
- **工单状态流**: 主线为 `PENDING → ACTIVE → SUBMITTED → UNDER_REVIEW → APPROVED/REJECTED → ACTIVATED → COMPLETED`；其中 `PENDING / ACTIVE / SUBMITTED / UNDER_REVIEW / REJECTED` 可在 `web-admin` 进入 `VOIDED（已作废）`
- **工单类型**: 开通检查、维护、电源问题、传输问题、GPS问题、信号问题
- **优先级管理**: 低、普通、高、紧急
- **分配和审核**: 支持多级审批和完整审计追踪
- **工单作废（Web 管理端，2026-03）**: 仅 `web-admin` 支持“作废工单”，要求填写作废原因；作废后保留工单、检查记录、照片和审计历史，但冻结为只读，不允许继续审核、提交、认领、手工确认或 AI 采纳
- **作废前置校验（2026-03）**: 若设备级检查项仍绑定 `SN`，或该工单已生成勘察/开站/SSV 档案，系统会拒绝作废；作废后不再参与“进行中工单冲突”判断，可重新创建新工单
- **移动端兼容（2026-03）**: `uniapp` 不提供作废入口；现场人员列表默认不展示 `VOIDED` 工单，即便收到该状态也会显示“已作废”并保持只读
- **新建工单站点选择（2026-03）**: `web-admin` 新建工单时，站点下拉已改成“大规模数据友好”的远程搜索模式。首次展开只加载少量建议结果，输入站点名称或编码后通过 `/api/sites/search` 实时查询匹配站点，并保留已选站点回显；如果某账号仍只能看到部分站点，优先检查该账号是否属于 `admin / manager / planner`，或是否具备站点查看相关权限，因为非全量可见角色本来就只允许看到自己业务范围内的站点
- **SSV 创建规则开关（2026-03）**: Web 管理端 `系统配置 -> OMC API 配置` 新增“SSV 创建规则”区块，开关名称为“站点设备激活即可创建SSV”。默认关闭时沿用旧规则，只允许 `site.status = operational` 的站点创建 `SSV`；开启后不再判断站点状态，只要站点设备全部 `ever_activated` 就允许创建 `SSV`，包括 `maintenance` 等非运营中状态
- **设备更换后的站点状态兜底（2026-03-09）**: 设备更换工单在“完成 / 驳回 / 删除 / 作废 / 批量删除”后，后端会统一检查该站点是否还存在其它进行中的更换工单；如果没有，就自动把站点从 `maintenance` 恢复出去。恢复顺序是：优先用工单里记录的原状态 `site_status_before`，没有时再回看最近一次进入维护前的站点状态，最后才按 OMC/开站进度兜底推断，避免老工单、异常工单或历史脏数据把站点长期卡死在“维护中”。
- **Web 工单执行台（2026-03）**: `web-admin` 新增“我的执行工单”（`工单管理 -> 我的执行工单`），现在固定只展示“当前登录人自己被分配”的工单；在此基础上再按 Web 可见类型做过滤。其中“Web可编辑类型”可直接接受/填写/上传/绑定/提交/撤回，“仅可见不可编辑”的类型会在列表打上“仅App执行”标记，并允许进入详情只读查看，不能在 Web 接受或填写
- **执行列表口径统一（2026-03）**: “我的执行工单”里的分组标题、行状态、操作按钮和右上角条数现在统一以“当前分组最后一次成功返回的数据”为准；列表同时直接使用后端返回的 `web_access_mode` 判断“进入执行 / 查看执行 / 只读查看”，避免前端自己推断导致状态、权限和条数互相对不上。另已修正并复查 `web-admin` 的遗留 DOM 文本翻译桥：中文环境下不再把旧文本回写到新渲染结果；且仅当值确实由桥接层翻译写入时，切回中文才会还原原文，避免覆盖 Vue 刚渲染的新状态/新条数
- **与 App 兼容边界（2026-03）**: Web 执行台和 UniApp 继续共用同一套 `work_orders / site_inspections / inspection_check_items / inspection_photos` 数据，不会新增第二套填写表；Web 端改动只对 `X-Client=web-admin` 请求生效，App 原有填写流程不受影响
- **Web 工单执行配置（2026-03）**: `系统配置 -> Web工单执行配置` 现在只对“权限系统管理员”开放；`Web工单执行` 是真正总开关，关闭后角色/用户覆盖也不能绕过；工单类型能力已拆成“Web可见类型”和“Web可编辑类型”，且可编辑类型必须是可见类型子集。用户管理页编辑用户时会显示“Web工单执行生效预览”，能直接看到这个用户当前的菜单入口、可见类型、可编辑类型，以及被什么条件挡住

### 2. 现场检查系统
- **模板驱动**: JSON 格式的检查模板，支持站点级和扇区级检查项
- **GPS 定位**: 强制 GPS 验证，确保现场作业真实性
- **照片水印**: 自动添加经纬度、时间戳、检查员信息
- **水印模板化配置（2026-02）**: Web 管理端支持按“全局/角色/用户”分配不同水印模板，可配置样式（颜色、透明度、位置、字号、边距、水印区域占比等）和内容项（图标显隐、坐标、地址、时间、人员、检查项、站点、前后缀文本）
- **离线支持**: IndexedDB 本地存储，网络恢复后自动同步
- **防篡改机制**: 文件哈希值验证和数字签名
- **重复图索引联动清理（2026-03-10）**: 删除检查照片、批量清理重复照片、删除工单（含批量删除）时，会同步清理 `global_photo_hash_registry` 中对应的 `inspection_photo` 首传索引；同时上传判重会自动忽略并清理“来源照片已不存在”的脏索引，避免“旧工单已删，新工单上传同图仍被判重复”。

### 3. 设备物料管理
- **库存管理**: 设备出入库、库存查询、退库申请
- **Web 管理端页面调整（2026-03）**: 已删除“领料记录”页面，避免与全量出库台账混淆；需要按 SN 排查时，统一使用“出入库记录”“人员领用台账”“设备实例清单”
- **Web 管理端页面调整（2026-03）**: 已删除“检查记录”“检查审核台”页面；检查模块当前保留“检查模板/模板编辑器”，检查数据审核统一在工单审核流程中处理
- **设备实例清单检索（Web，2026-03）**: 支持“未选择设备类型时直接按 SN 全局查询”；匹配顺序为“完整 SN -> SN 前缀 -> SN 片段包含”，未输入 SN 时仍需先选择设备类型
- **新流程（移动端）**: 物料申请 → 仓库审批 → 自助领料 → 仓库出库确认
- **库存范围模型（2026-03-08）**: 出入库记录、物料审批、出库确认、退库收货统一按 `self / managed / all` 三档控制；普通账号不再因为某个写权限被错误当成“仓库侧角色”
- **仓库配置权限收口（2026-03-09）**: `inventory:warehouse:write` 已收回到“仓库资料维护”本身；入库、SN 导入、快速出库、设备实例维护、流程设置、人员领用台账都改成各自独立的显式权限码，再叠加 `managed / all` 范围判断
- **入库单号去冲突（2026-03-09）**: 入库单据编号已改成和申请单/出库单同一套“毫秒时间 + 随机后缀”规则，连续两次入库不会再因为同秒生成重复单号而触发 500
- **套装主设备数量（2026-03）**: 设备套装中的主设备数量支持配置为大于 1；Web/移动端“套装一键带出”会按“套装明细数量 × 套装数量”展开到申请明细，主设备不再固定为 1
- **退库创建（移动端）**: 改为“按实际申请”，不再强依赖人工先选出库单；主设备仅支持扫码加入，辅料按系统给出的可退上限填写
- **退库校验提示（移动端）**: 扫码 SN 会先做可退校验，失败时弹窗展示“原因 + 建议 + 相关人员/单据信息”
- **退库批次视图（移动端）**: 一次提交记为一个批次，后台可自动拆分多张退库单，列表按批次聚合展示状态、驳回原因与拆分单据
- **退库防超退（并发）**: 提交时会做额度锁定与原子状态更新；若并发导致可退额度或SN状态变化，会返回明确提示并要求刷新后重试
- **设备解绑状态回退统一（2026-03-05）**: 无论是检查页解绑（`/api/inspections/detail/{id}/bind-equipment` 传空 `equipment_sn`）还是退库一键解绑（`/api/stock/scan-return/unbind`），都会对“设备级解绑”执行同一状态回退规则：`pending_inspection/inspected -> issued`，避免出现“已解绑但不可退库”
- **退库收货（Web / App）**: 仓库收货页统一改为批次维度展示（批次头 + 单据明细）；Web 与 App 都支持按单据继续收货或拒收，但只显示自己管理仓库下的退库批次
- **退库收货范围提示（移动端 H5，2026-03）**: 退库收货页顶部说明不再固定写“管理仓”；现在会跟随 `inventory_scope` 动态展示本人 / 管理仓 / 全仓口径，避免页面文案和实际数据范围不一致
- **人员领用台账范围（Web 管理端）**: `人员领用台账`、用户领用明细和出库单详情现在也跟随 `managed / all` 范围；仓库负责人只能看到自己管理仓库下产生的领用与出库记录
- **首页库存入口（移动端）**: 我的设备、物料申请、审批物料申请、出库确认、退库收货、退库申请、快速出库
- **出入库记录范围（Web 管理端）**: 不再默认“有查看权限就看全仓”；现在按本人 / 管理仓 / 全仓三档返回，manager_id 的仓库负责人会自动获得管理仓视角
- **首页工作台按钮布局（移动端）**: 首页工作台入口固定 4 列等宽，英文/印尼语等长文案会自动换行断词，避免右侧溢出；左右边界与页面内容区保持对齐
- **库存单位国际化（移动端）**: `web-admin` 仍按中文单位值（台/套/个/副/米）配置与存储，`uniapp` 在显示时会自动映射为当前语言文案（中文/英文/印尼语），避免非中文环境直接显示中文单位
- **申请明细可读性优化（移动端）**: 物料申请创建页的"申请明细"改为上下分区布局（上方完整展示设备名/编码/类型，下方数量操作与删除），避免窄屏下信息被操作按钮挤压成 `...`
- **数量步进器支持手写（移动端，2026-03-05）**: 库存模块中所有 `- / +` 数量控件都支持直接点中间数字手写输入；输入框失焦后会自动按整数和上下限纠正（如退库辅料按 `0~最大可退`、套装数量按 `1~999`），同时保留原有加减按钮操作。
- **放弃领货（移动端）**: 已审批但尚未发生出库的申请单可执行"放弃领货"（需填写原因）；系统会自动取消该申请单下未完成的领料单并释放占用，状态标记为 `abandoned`
- **放弃领货（Web 管理端）**: 申请单详情页支持"放弃领货"按钮（原因必填）；仅"已批准/部分批准且未出库"可操作，成功后同步展示放弃原因与状态
- **出库确认规则**: 主设备 SN 默认全选待确认项，支持手动取消个别 SN 不确认
- **扫码格式兼容（2026-03）**: 领料/退库链路统一兼容 `SN,MAC1~4` 复合条码（2~5 段）；当客户端未正确解析时，后端也会兜底提取首段 SN，避免把整串 `SN,MAC...` 当作 SN 导致“设备实例不存在”
- **扫码类型兼容（2026-03）**: 移动端设备扫码类型白名单已放宽（含 `UPC/EAN/Code39/Code93/ITF` 等常见误识别类型），并继续以 SN 解析与校验作为最终准入，减少“类型误判导致无法扫码”的现场问题
- **扫码策略统一（2026-03）**: `uniapp` 所有设备扫码入口（领料、领料单扫码、退库扫码、快速出库扫码、检查绑定扫码）统一复用 `utils/scan-code.js`，按同一规则处理“类型校验 -> 条码解析 -> SN 校验 -> 错误码返回”，避免各页面规则不一致
- **扫码防误触（移动端，2026-03）**: 设备扫码启用“自动重扫 + 同一失败结果连续 3 次才提示 + 一次识别即确认”策略；其中“同一失败结果”按错误类型与识别内容严格比对，减少镜头对焦阶段的误报中断，用户取消扫码会静默返回
- **领料辅料卡片布局优化（移动端，2026-03）**: `Picking` 页“Aux materials”在窄屏下改为更稳妥的两列+计划数量独占一行布局，步进器不再挤压重叠；同时收紧卡片留白并补齐底部安全区，避免底部按钮遮挡最后一项
- **部分出库后的处理**: 当领料单进入“部分出库（partially_confirmed）”后，仓库可执行“驳回剩余”，系统会清理该单未确认 SN 与未确认辅料数量，避免剩余项长期占用；若该单已无待确认剩余，也可直接收口为已完成（confirmed）
- **无可出库场景收口**: 若领料单处于“部分出库”但已无待确认项，点击“确认出库”会提示“是否关闭该出库单”，确认后自动收口
- **设备状态**: offline → online → activated
- **物料分类**: 支持多级分类管理

### 4. 站点管理
- **站点规划**: 支持站点信息录入和规划管理
- **基站状态**: 离线、在线、已激活
- **地理信息**: GPS 坐标管理和位置验证
- **设备关联**: 站点与设备的关联管理
- **站点概况-安装开始站点**: 位于“规划站点”和“安装完成站点”之间，显示为 `安装开始站点/总站点`；口径是站点在“仍关联有效开站工单”的绑定历史里第一次开始绑定 SN（`bind/rebind`）后计入，按站点去重统计（删除工单后会回退）
- **站点概况-安装完成站点**: 原“安装站点”已更名，显示为 `安装完成站点/总站点`；口径不变，按“开站工单达到已提交及以上阶段（SUBMITTED/UNDER_REVIEW/APPROVED/ACTIVATED/COMPLETED）”按站点去重统计，点击后跳转工单列表并自动按同口径筛选
- **仪表盘-站点事件趋势（2026-03）**: 仪表盘新增“站点事件趋势”图表，支持 `按日/按周/按月`、`新增量/累计值`、`自动(推荐)/柱状图/折线图` 三组切换。自动模式下：新增量默认柱状图、累计值默认折线图；同时也可手动强制切换图形类型。事件按“站点首次发生时间”统计：`安装开始=仍关联有效开站工单的首次 bind/rebind`、`安装完成=开站工单首次 submitted_at`、`上线=开站工单首次 activated_at`、`激活=开站工单首次 completed_at`、`SSV=SSV工单首次 completed_at`。累计值由“区间前基线 + 各周期新增”计算，避免切换周期后累计曲线从 0 重新起算。趋势分桶时区口径与浏览器本地一致（前端传 `Date.getTimezoneOffset()` 给后端）
- **仪表盘-趋势区块间距（2026-03）**: “站点事件趋势”卡片与其下方“工单概览/库存预警/用户概览/待审工单”卡片之间已增加固定垂直留白（24px），避免上下区块视觉粘连
- **站点地图（Web，2026-03）**: `站点管理 -> 站点地图` 已上线，提供“左侧站点列表 + 右侧地图”联动视图。支持关键词、状态、类型、省/市/区、坐标状态、SSV 状态、仅看当前视野等常用筛选；点位点击可查看站点关键信息，列表可一键定位并跳转“站点详情/站点规划”。地图底图使用 OpenStreetMap（免 key），并在页面内给出状态图例和“缺少坐标站点”提示，方便快速定位数据缺口。图例位置已避开地图缩放控件，状态识别采用“高对比颜色 + 不同形状”双编码，降低相近颜色误判
- **仪表盘-站点地图快捷入口（2026-03）**: “仪表盘 -> 站点概况”在标题区提供按钮“查看站点地图”，当前页跳转到站点地图，并按 `sites:list:read` 权限显示；不影响原有各站点概况卡片点击行为

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

### 权限管理（RBAC）
- `GET /api/authz/permissions` - 权限点列表
- `GET /api/authz/permissions/modules` - 按模块分组的权限点
- `GET /api/authz/data-scopes/definitions` - 数据范围定义列表
- `GET /api/authz/roles` - 角色列表（含当前授权）
- `POST /api/authz/roles` - 创建角色
- `PUT /api/authz/roles/{role_id}` - 更新角色信息
- `PUT /api/authz/roles/{role_id}/permissions` - 配置角色权限
- `PUT /api/authz/roles/{role_id}/data-scopes` - 配置角色数据范围
- `DELETE /api/authz/roles/{role_id}` - 删除角色（系统角色不可删）
- `GET /api/authz/users/{user_id}/roles` - 查询用户角色
- `PUT /api/authz/users/{user_id}/roles` - 配置用户角色
- `GET /api/authz/users/{user_id}/effective-permissions` - 查询用户生效权限、数据范围，以及 Web 工单执行生效预览
- `GET /api/authz/me/effective-permissions` - 查询当前登录账号的生效权限、数据范围、库存范围画像与 Web 工单执行预览

### 站点管理
- `GET /api/sites/search` - 站点分页搜索（关键词/状态/类型/排序）
- `PUT /api/sites/{site_id}` - 单条更新站点基础信息
- `PUT /api/sites/batch-update` - 批量更新站点基础信息（支持每条站点传不同字段值，返回逐条结果）
- `GET /api/sites/basic/batch-update-template` - 下载站点基础信息批量更新模板
- `POST /api/sites/basic/batch-update-upload` - 上传站点基础信息批量更新文件（支持 `dry_run`）

### 工单管理
- `GET /api/work-orders` - 获取工单列表
- `GET /api/work-orders/search` - 按关键字、状态、多状态、多类型分页筛选工单
- `GET /api/work-orders/{id}` - 获取工单详情
- `GET /api/work-orders/{id}/execution-context` - 获取 Web 工单执行页所需的聚合上下文（工单、检查、进度、生效开关，以及当前工单在 Web 端是可编辑、只读还是不可用）
- `POST /api/work-orders/{id}/accept` - 接受工单并创建关联检查实例
- `POST /api/work-orders/{id}/submit` - 提交工单
- `POST /api/work-orders/{id}/recall` - 撤回已提交工单（回到可编辑状态）
- `POST /api/work-orders/{id}/void` - 作废工单（仅 Web 管理端；原因必填）
- `POST /api/work-orders/{id}/complete` - 完成工单
- `POST /api/work-orders/batch-operation` - 批量操作工单（支持 `delete / change_status / change_assignee / change_priority / void`）

### 检查管理
- `GET /api/inspections` - 获取检查列表
- `GET /api/inspections/detail/{inspection_id}` - 获取检查详情
- `GET /api/inspections/detail/{inspection_id}/items` - 获取检查项列表
- `PUT /api/inspections/detail/{inspection_id}/items/{item_id}` - 更新检查项（Web 与 App 共用）
- `POST /api/inspections/detail/{inspection_id}/photos/precheck` - 检查照片上传预检
- `POST /api/inspections/detail/{inspection_id}/photos` - 上传检查照片
- `DELETE /api/inspections/photos/{photo_id}` - 删除检查照片
- `POST /api/inspections/detail/{inspection_id}/bind-equipment` - 绑定或解绑设备
- `GET /api/inspections/detail/{id}` - 获取检查详情
- `POST /api/inspections` - 创建新检查
- `PUT /api/inspections/{id}` - 更新检查状态
- `POST /api/inspections/detail/{id}/bind-equipment` - 绑定/解绑设备（`equipment_sn` 为空表示解绑）

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
- `POST /api/stock/scan-return/unbind` - 退库一键解绑（清理设备级检查绑定/照片并回退设备状态）
- `GET /api/stock/returns/actual-candidates` - 获取按实际申请退库候选数据（辅料可退上限等）
- `POST /api/stock/returns/by-actual` - 按实际申请退库（后台自动关联并拆分单据，提交时做并发防超退校验）
- `GET /api/stock/returns/workbench-batches` - 仓库侧退库批次工作台（批次维度，含单据明细）
- `GET /api/stock/returns/{id}` - 仓库侧退库单详情
- `POST /api/stock/returns/{id}/receive` - 仓库侧确认退库收货（支持部分收货）
- `POST /api/stock/returns/{id}/reject` - 仓库侧拒收退库单
- `GET /api/stock/my-return-batches` - 我的退库批次列表（批次维度）

### 系统备份（Web 管理端）
- `GET /api/system/backup/config` - 获取备份策略配置
- `PUT /api/system/backup/config` - 更新备份策略配置
- `POST /api/system/backup/run` - 手动触发备份
- `GET /api/system/backup/history` - 获取备份历史记录
- `GET /api/system/backup/{backup_id}/download` - 下载指定备份记录对应的 zip 包
- `POST /api/system/backup/{backup_id}/restore` - 从指定备份恢复数据库
- `GET /api/system/backup/restore-history` - 获取恢复操作历史

### 日志系统
- `POST /api/logs` - 创建用户日志
- `POST /api/logs/batch` - 批量同步日志

### 移动端配置
- `GET /api/system/mobile-settings` - 管理端获取完整移动端配置（管理员/项目经理）
- `PUT /api/system/mobile-settings` - 管理端更新完整移动端配置（管理员/项目经理，需携带 `config_version`；若版本冲突返回 `409`，需先刷新再保存）
- `GET /api/system/mobile-settings/effective` - 移动端获取“当前用户生效”的配置（含定位策略、水印策略、水印模板）

### Web工单执行配置
- `GET /api/system/workorder-execution-settings` - 获取完整 Web 工单执行配置（仅权限管理员可访问，含全局、角色、用户覆盖）
- `PUT /api/system/workorder-execution-settings` - 更新完整 Web 工单执行配置（仅权限管理员可访问，需携带当前 `config_version`，冲突时返回 `409`）
- `GET /api/system/workorder-execution-settings/effective` - 获取“当前登录人”在 Web 管理端生效的工单执行策略
- `GET /api/system/location-mode` - 获取定位模式全局默认值（兼容旧版）
- `PUT /api/system/location-mode` - 更新定位模式全局默认值（兼容旧版）

## 🗄️ 数据库设计

### 核心数据表
- **users**: 用户基础信息（不再存单角色）
- **roles**: 角色定义
- **permissions**: 权限点定义
- **user_roles**: 用户-角色关联
- **role_permissions**: 角色-权限关联
- **role_data_scopes**: 角色-数据范围关联
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
- **超距提示口径（2026-03）**: 当“实拍坐标 vs 规划坐标”距离超阈值时，仅在 Web 审核端做提示；不再因超距改写照片水印内容，也不自动改动检查结果

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
- 升级兼容修复（2026-03-04）：
  - 修复“升级后历史照片水印模板看起来丢失”的问题。后端现在会兼容读取旧版存储结构（模板数组、驼峰字段、旧模板ID字符），自动映射为当前结构，避免被默认模板覆盖。
  - 兼容范围包含模板内容、样式字段、场景策略与模板分配规则（默认/按角色/按用户）。
- 并发与误清空保护（2026-03-05）：
  - 新增 `config_version` 乐观锁：管理端保存时必须带当前版本号；若其他会话已改动，接口会返回 `409`，前端提示刷新并重新加载最新配置，避免“后保存覆盖先保存”。
  - 新增模板清空二次确认：当本次保存会把“自定义模板数量”从 `>0` 变成 `0`（仅保留 `default`）时，后端会先返回 `409` 要求确认；前端弹框确认后才会带 `confirm_template_reset=true` 重试。
  - 新增后台审计字段：每次成功保存都会记录 `template_count_before/after`、`template_ids_before/after`、`config_version_before/after`，用于排查“模板消失/配置回滚”来源。

### Web工单执行配置（新增）
- 管理入口：`Web 管理端 -> 系统配置 -> Web工单执行配置`
- 执行入口：`Web 管理端 -> 工单管理 -> 我的执行工单`
- 设计原则：
  - 默认关闭
  - `Web工单执行` 是真正总开关，关闭后角色/用户覆盖不会生效
  - 配置页只对“权限系统管理员”开放
  - 只影响 `web-admin` 执行链路，不影响 App 现有工单填写
  - Web 和 App 继续共用同一套工单、检查项、照片、设备绑定数据
  - “Web可编辑类型”必须始终是“Web可见类型”的子集
  - 菜单“我的执行工单”只有在同时满足 `auth:web-login`、`workorder:execute:web`、总开关开启、且至少存在一个 Web 可见工单类型时才显示
- 当前可配置项：
  - 是否开放 Web 工单执行入口（总开关）
  - 是否允许照片上传
  - 无定位本地上传策略（三档）：
    - 禁止无定位上传
    - 允许无定位上传并加水印
    - 允许无定位上传且不加水印（原图直传）
  - 是否允许设备绑定/解绑
  - 是否允许提交
  - 是否允许撤回
  - 哪些工单类型允许在 Web 列表可见
  - 哪些工单类型允许在 Web 端执行编辑
- 覆盖粒度：
  - 全局默认：控制总开关和默认能力
  - 按角色覆盖：可覆盖可见类型、可编辑类型、照片、绑定、提交、撤回
  - 按用户覆盖：只用于例外场景，不能绕过总开关
- 日常授权动线：
  - 第一步：给用户分配可登录 Web 的角色（`auth:web-login`）
  - 第二步：给用户分配可执行工单的角色（`workorder:execute:web`）
  - 第三步：确认总开关已开启，并给该用户命中的工单类型配置好“Web可见 / Web可编辑”范围
  - 第四步：派单给该用户
  - 第五步：在“用户管理 -> 编辑用户”里查看“Web工单执行生效预览”，确认卡在登录权限、执行权限、总开关，还是没有命中可见类型
  - 预览卡片里的“执行入口 / Web登录 / 执行权限 / 总开关 / 可见类型 / 可编辑类型”都直接按后端当前生效结果显示；如果刚改完角色但还没保存，先保存再点“刷新”看最终结果
- 当前执行动线：
  - 从“我的执行工单”按状态分组查看：待接受、执行中、已提交、已驳回
  - 这个入口不区分角色，统一只返回“assigned_to = 当前登录人”的工单；不会再混入分配给别人的工单
  - 在“只看自己工单”的前提下，列表再按 Web 可见类型做过滤；只读类型会标记“仅App执行”
  - 列表状态文案、操作按钮和右上角条数会跟随当前分组的最新成功请求一起更新；全局遗留 DOM 翻译逻辑已改为“中文只同步当前 DOM、英文基于最新原文翻译”，并且只回切桥接层自己写入的值，因此不会再出现“分组已切换，但状态/按钮/条数还停留在上一组”的串位现象
  - 执行台里的“保存草稿”会把当前检查项保存为“填写中（in_progress）”；“保存并标记完成”会把当前检查项改为“已完成（completed）”。两者都会保存当前字段值和备注，但只有“标记完成”会触发完成态校验（如必填字段、必拍照片）
  - 针对 2026-03 的线上 `422`：前端已修正检查项数据序列化，未填写字段会显式传 `value: null`，不再出现 `data_value[].value` 缺失导致保存草稿/标记完成直接失败；同时错误提示会优先展示后端返回的字段级校验信息，避免页面只出现红叉无可读文案
  - 点进单条工单后进入执行台；详情页也沿用同一规则，只有当前登录人名下的工单才能打开；若该类型属于 Web 可编辑类型，则可按检查项逐项填写
  - 执行台左侧“检查项导航”在长列表场景下会固定为组件内滚动区，鼠标滚轮/触控板可直接上下滚动并选择底部检查项，不会再出现内容被截住却滚不动的情况
  - 当浏览器无法拿到定位时，执行台会按“无定位本地上传策略”处理：
    - 禁止：直接拦截上传
    - 允许并加水印：沿用原有本地上传水印流程
    - 允许且不加水印：直接上传原图，不再强制加本地水印
  - 若该类型仅 Web 可见不可编辑，则允许查看当前工单和检查进度，但接受工单、填写检查项、上传照片、绑定设备、提交、撤回都必须回到 App 端处理
  - Web 与 App 填写的是同一份数据，刷新后两端可看到彼此最新修改

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

## 🌐 WebAdmin 国际化说明（中文/英文/印尼语）

### 已实现范围
- `web-admin` 已接入 `vue-i18n`，支持 `zh-CN`、`en-US`、`id-ID`。
- 登录页、主框架（顶部标题、菜单、面包屑、路由标题、退出提示）已按 i18n key 驱动。
- Element Plus 组件内置文案（分页、日期等）会跟随语言切换。
- 为了兼容历史页面中大量中文硬编码，增加了遗留文案桥接层：切换英文/印尼语时会自动把页面中的中文文本、placeholder、title 等映射到对应语言。
- 为运行时动态文案（含变量拼接）增加了“动态句式翻译规则”，避免英文/印尼语模式下出现 `确定要删除 XXX 吗` 这类残留中文。
- 对高频英文文案增加人工校准规则（删除确认、批量提示、导出文件名、状态提示），避免机器翻译生硬。
- 英文 UI 协调性专项优化（2026-03）：统一 `Actions/Direction/Document` 等关键列名与短语；收敛操作列按钮布局；修复侧栏英文菜单在窄屏下过度省略；优化标签与表格单元格英文换行策略，避免单词被拆字母换行。
- 英文窄屏可用性专项优化（2026-03-03）：`MaterialRequests/IssueDrafts/ReturnReceiving/StockHistory` 筛选栏改为响应式断点布局，移动端自动分行；列表页增加紧凑列模式（窄屏隐藏次要列）；移动端侧栏默认折叠，避免首屏被菜单覆盖。
- 新增高优先级短语覆盖（如 `Warehouse (default mine)`、`Awaiting receipt`、`Search doc/device/SN`），降低英文 placeholder 在控件内被截断概率。
- 菜单精简（2026-03-03）：`Report Center / 报表中心` 菜单入口已从 web-admin 侧栏移除（该页面尚未实现，避免展示空白占位功能）。

### 关键文件
- `web-admin/src/i18n/index.js`：i18n 初始化与消息注册。
- `web-admin/src/i18n/messages/zh-CN.js`：中文主词条。
- `web-admin/src/i18n/messages/en-US.js`：英文主词条。
- `web-admin/src/i18n/messages/id-ID.js`：印尼语主词条。
- `web-admin/src/i18n/translator.js`：语言切换、路由标题解析、遗留词库懒加载。
- `web-admin/src/i18n/useLegacyDomI18n.js`：遗留中文 DOM 自动翻译桥接。
- `web-admin/src/i18n/legacy-en-map.js`：中文短语 -> 英文映射词库（自动生成）。
- `web-admin/src/i18n/legacy-id-map.js`：中文短语 -> 印尼语映射词库（自动生成）。
- `web-admin/src/i18n/legacy-dynamic-patterns.js`：动态句式自动翻译规则（自动生成）。
- `web-admin/src/i18n/legacy-dynamic-patterns-id.js`：印尼语动态句式翻译规则（自动生成）。
- `web-admin/src/i18n/legacy-dynamic-overrides.js`：人工校准规则（优先级高于自动规则）。
- `web-admin/src/components/common/LocaleSwitcher.vue`：语言切换组件（登录页右上角 + 后台顶部导航复用）。
- `temp/generate_webadmin_legacy_i18n_map.mjs`：词库生成脚本（从现有代码提取中文并自动翻译）。
- `temp/generate_webadmin_dynamic_i18n_patterns.mjs`：动态句式规则生成脚本（提取模板字符串并生成正则翻译规则）。
- `temp/refresh_webadmin_legacy_en_map.mjs`：基于现有词库做增量补齐（只翻译新增中文词条）。
- `temp/refresh_webadmin_dynamic_patterns_en.mjs`：基于现有动态规则做增量补齐（只翻译新增模板句式）。
- `temp/generate_webadmin_id_messages.mjs`：从英文词条生成印尼语主词条。
- `temp/generate_webadmin_legacy_id_from_en_map.mjs`：从英文 legacy 词库生成印尼语 legacy 词库。
- `temp/generate_webadmin_dynamic_patterns_id_from_en.mjs`：从英文动态句式规则生成印尼语动态句式规则。
- `temp/scan_visible_cjk_routes.sh`：英文模式可见中文巡检（用于定位漏翻译）。
- `temp/scan_horizontal_overflow_routes.sh`：英文模式水平截断巡检（分别支持 desktop/mobile）。
- `temp/scan_en_ui_harmony.sh`：英文 UI 协调性巡检（词内断行 + ellipsis 裁剪）。
- `temp/scan_en_clipped_controls.sh`：英文控件裁切巡检（输入框/下拉/按钮/表头等可见文本裁切检测）。
- `temp/scan_bad_en_terms.sh`：英文坏味道术语巡检（如 `operate`、`Documents/documents`、`to confirm`）。

### 新增/修改文案时怎么做
1. 新功能文案优先写到 `messages/zh-CN.js`、`messages/en-US.js`、`messages/id-ID.js`，页面里使用 `$t('...')`。
2. 历史页面若仍有中文硬编码，可先保持不动，桥接层会在英文/印尼语模式下自动翻译。
3. 当历史中文变更多、翻译命中下降时，执行：
```bash
node temp/generate_webadmin_legacy_i18n_map.mjs
node temp/generate_webadmin_dynamic_i18n_patterns.mjs
node temp/refresh_webadmin_legacy_en_map.mjs
node temp/refresh_webadmin_dynamic_patterns_en.mjs
node temp/generate_webadmin_id_messages.mjs
node temp/generate_webadmin_legacy_id_from_en_map.mjs
node temp/generate_webadmin_dynamic_patterns_id_from_en.mjs
```
4. 重新构建验证：
```bash
cd web-admin && npm run build
```

### 排查基线（2026-03）
- 静态中文词条覆盖：扫描 `2577` 条，除注释外均可翻译。
- 动态模板句式覆盖：采样 `161` 条，剩余 `3` 条为源码中的模板片段（非真实运行时文案），不影响页面显示。
- DOM 回写风险复查（2026-03-09）：全量检索 `web-admin/src` 的 `MutationObserver / createTreeWalker / nodeValue / setAttribute` 等“可能直接改写可见文案”的代码后，确认只有 `useLegacyDomI18n.js` 这一处全局桥接逻辑。现已加“桥接写入标记”保护（属性 `i18nTranslated*`、文本节点 `__i18nTranslatedText`）：中文模式仅同步最新原文，不再把历史值回写；切语言时也只回切桥接层自己写过的英文值，不会覆盖组件新渲染结果。
- 英文可见中文巡检（40 个主路由，`temp/visible_cjk_scan_run8.txt`）：系统固定文案已清零，剩余中文主要来自业务数据本身（站点名、仓库名、人员名、模板名、地址、版本说明等）。
- 英文 UI 协调性复检（本轮）：
  - 水平截断（40 个主路由）：desktop `0` / mobile `0`（`temp/h_overflow_desktop_run5.txt`、`temp/h_overflow_mobile_run5.txt`）
  - 词内断行与 ellipsis 裁剪：desktop `0` / mobile `0`（`temp/en_ui_harmony_desktop_run3.txt`、`temp/en_ui_harmony_mobile_run3.txt`）
  - 控件裁切（下拉/输入/按钮/表头）：desktop `0` / mobile `0`（`temp/en_clipped_controls_desktop_run4.txt`、`temp/en_clipped_controls_mobile_run4.txt`）
  - 英文坏味道术语：仅 `Direction` 命中（`temp/en_bad_terms_run2.txt`，为合法术语，非问题）。

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
