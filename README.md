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

#### Web 管理端
```bash
cd web-admin
npm install
npm run dev                    # 默认运行在 5173 端口
npm run build                  # 生产构建
```
- **中英文切换（2026-03）**：
- 登录页右上角提供语言切换器；进入后台后，语言切换器在顶部导航栏（用户信息左侧）。
- 语言菜单固定英文文案：`Language / Chinese / English`。
- 默认语言优先级：用户上次选择 > 浏览器语言（`en*` 自动英文，其它默认中文）。
- 切换后即时生效，并持久化到浏览器本地存储。

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
- Web 管理端新增 **系统配置 -> 角色权限** 页面（`/settings/permissions`），支持：
- 新建/编辑/删除自定义角色
- 配置角色权限点
- 用户管理页支持给用户分配多个角色
- 当前迭代覆盖范围：`web-admin + backend`，不包含 UniApp 客户端鉴权改造。

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
- **Web 管理端页面调整（2026-03）**: 已删除“领料记录”页面，避免与全量出库台账混淆；需要按 SN 排查时，统一使用“出入库记录”“人员领用台账”“设备实例清单”
- **Web 管理端页面调整（2026-03）**: 已删除“检查记录”“检查审核台”页面；检查模块当前保留“检查模板/模板编辑器”，检查数据审核统一在工单审核流程中处理
- **设备实例清单检索（Web，2026-03）**: 支持“未选择设备类型时直接按 SN 全局查询”；未输入 SN 时仍需先选择设备类型
- **新流程（移动端）**: 物料申请 → 仓库审批 → 自助领料 → 仓库出库确认
- **套装主设备数量（2026-03）**: 设备套装中的主设备数量支持配置为大于 1；Web/移动端“套装一键带出”会按“套装明细数量 × 套装数量”展开到申请明细，主设备不再固定为 1
- **退库创建（移动端）**: 改为“按实际申请”，不再强依赖人工先选出库单；主设备仅支持扫码加入，辅料按系统给出的可退上限填写
- **退库校验提示（移动端）**: 扫码 SN 会先做可退校验，失败时弹窗展示“原因 + 建议 + 相关人员/单据信息”
- **退库批次视图（移动端）**: 一次提交记为一个批次，后台可自动拆分多张退库单，列表按批次聚合展示状态、驳回原因与拆分单据
- **退库防超退（并发）**: 提交时会做额度锁定与原子状态更新；若并发导致可退额度或SN状态变化，会返回明确提示并要求刷新后重试
- **设备解绑状态回退统一（2026-03-05）**: 无论是检查页解绑（`/api/inspections/detail/{id}/bind-equipment` 传空 `equipment_sn`）还是退库一键解绑（`/api/stock/scan-return/unbind`），都会对“设备级解绑”执行同一状态回退规则：`pending_inspection/inspected -> issued`，避免出现“已解绑但不可退库”
- **退库收货（Web 管理端）**: 仓库收货页改为批次维度展示（批次头 + 单据明细），单据超过 8 条默认折叠；收货/拒收仍按单据执行
- **首页库存入口（移动端）**: 我的设备、物料申请、审批物料申请、出库确认、退库申请、快速出库
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

### 权限管理（RBAC）
- `GET /api/authz/permissions` - 权限点列表
- `GET /api/authz/permissions/modules` - 按模块分组的权限点
- `GET /api/authz/roles` - 角色列表（含当前授权）
- `POST /api/authz/roles` - 创建角色
- `PUT /api/authz/roles/{role_id}` - 更新角色信息
- `PUT /api/authz/roles/{role_id}/permissions` - 配置角色权限
- `DELETE /api/authz/roles/{role_id}` - 删除角色（系统角色不可删）
- `GET /api/authz/users/{user_id}/roles` - 查询用户角色
- `PUT /api/authz/users/{user_id}/roles` - 配置用户角色
- `GET /api/authz/users/{user_id}/effective-permissions` - 查询用户生效权限

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
- `GET /api/system/location-mode` - 获取定位模式全局默认值（兼容旧版）
- `PUT /api/system/location-mode` - 更新定位模式全局默认值（兼容旧版）

## 🗄️ 数据库设计

### 核心数据表
- **users**: 用户基础信息（不再存单角色）
- **roles**: 角色定义
- **permissions**: 权限点定义
- **user_roles**: 用户-角色关联
- **role_permissions**: 角色-权限关联
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
- 升级兼容修复（2026-03-04）：
  - 修复“升级后历史照片水印模板看起来丢失”的问题。后端现在会兼容读取旧版存储结构（模板数组、驼峰字段、旧模板ID字符），自动映射为当前结构，避免被默认模板覆盖。
  - 兼容范围包含模板内容、样式字段、场景策略与模板分配规则（默认/按角色/按用户）。
- 并发与误清空保护（2026-03-05）：
  - 新增 `config_version` 乐观锁：管理端保存时必须带当前版本号；若其他会话已改动，接口会返回 `409`，前端提示刷新并重新加载最新配置，避免“后保存覆盖先保存”。
  - 新增模板清空二次确认：当本次保存会把“自定义模板数量”从 `>0` 变成 `0`（仅保留 `default`）时，后端会先返回 `409` 要求确认；前端弹框确认后才会带 `confirm_template_reset=true` 重试。
  - 新增后台审计字段：每次成功保存都会记录 `template_count_before/after`、`template_ids_before/after`、`config_version_before/after`，用于排查“模板消失/配置回滚”来源。
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

## 🌐 WebAdmin 国际化说明（中文/英文）

### 已实现范围
- `web-admin` 已接入 `vue-i18n`，支持 `zh-CN` 和 `en-US`。
- 登录页、主框架（顶部标题、菜单、面包屑、路由标题、退出提示）已按 i18n key 驱动。
- Element Plus 组件内置文案（分页、日期等）会跟随语言切换。
- 为了兼容历史页面中大量中文硬编码，增加了遗留文案桥接层：切换英文时会自动把页面中的中文文本、placeholder、title 等映射为英文。
- 为运行时动态文案（含变量拼接）增加了“动态句式翻译规则”，避免英文模式下出现 `确定要删除 XXX 吗` 这类残留中文。
- 对高频英文文案增加人工校准规则（删除确认、批量提示、导出文件名、状态提示），避免机器翻译生硬。
- 英文 UI 协调性专项优化（2026-03）：统一 `Actions/Direction/Document` 等关键列名与短语；收敛操作列按钮布局；修复侧栏英文菜单在窄屏下过度省略；优化标签与表格单元格英文换行策略，避免单词被拆字母换行。
- 英文窄屏可用性专项优化（2026-03-03）：`MaterialRequests/IssueDrafts/ReturnReceiving/StockHistory` 筛选栏改为响应式断点布局，移动端自动分行；列表页增加紧凑列模式（窄屏隐藏次要列）；移动端侧栏默认折叠，避免首屏被菜单覆盖。
- 新增高优先级短语覆盖（如 `Warehouse (default mine)`、`Awaiting receipt`、`Search doc/device/SN`），降低英文 placeholder 在控件内被截断概率。
- 菜单精简（2026-03-03）：`Report Center / 报表中心` 菜单入口已从 web-admin 侧栏移除（该页面尚未实现，避免展示空白占位功能）。

### 关键文件
- `web-admin/src/i18n/index.js`：i18n 初始化与消息注册。
- `web-admin/src/i18n/messages/zh-CN.js`：中文主词条。
- `web-admin/src/i18n/messages/en-US.js`：英文主词条。
- `web-admin/src/i18n/translator.js`：语言切换、路由标题解析、遗留词库懒加载。
- `web-admin/src/i18n/useLegacyDomI18n.js`：遗留中文 DOM 自动翻译桥接。
- `web-admin/src/i18n/legacy-en-map.js`：中文短语 -> 英文映射词库（自动生成）。
- `web-admin/src/i18n/legacy-dynamic-patterns.js`：动态句式自动翻译规则（自动生成）。
- `web-admin/src/i18n/legacy-dynamic-overrides.js`：人工校准规则（优先级高于自动规则）。
- `web-admin/src/components/common/LocaleSwitcher.vue`：语言切换组件（登录页右上角 + 后台顶部导航复用）。
- `temp/generate_webadmin_legacy_i18n_map.mjs`：词库生成脚本（从现有代码提取中文并自动翻译）。
- `temp/generate_webadmin_dynamic_i18n_patterns.mjs`：动态句式规则生成脚本（提取模板字符串并生成正则翻译规则）。
- `temp/scan_visible_cjk_routes.sh`：英文模式可见中文巡检（用于定位漏翻译）。
- `temp/scan_horizontal_overflow_routes.sh`：英文模式水平截断巡检（分别支持 desktop/mobile）。
- `temp/scan_en_ui_harmony.sh`：英文 UI 协调性巡检（词内断行 + ellipsis 裁剪）。
- `temp/scan_en_clipped_controls.sh`：英文控件裁切巡检（输入框/下拉/按钮/表头等可见文本裁切检测）。
- `temp/scan_bad_en_terms.sh`：英文坏味道术语巡检（如 `operate`、`Documents/documents`、`to confirm`）。

### 新增/修改文案时怎么做
1. 新功能文案优先写到 `messages/zh-CN.js` 与 `messages/en-US.js`，页面里使用 `$t('...')`。
2. 历史页面若仍有中文硬编码，可先保持不动，桥接层会在英文模式下自动翻译。
3. 当历史中文变更多、翻译命中下降时，执行：
```bash
node temp/generate_webadmin_legacy_i18n_map.mjs
node temp/generate_webadmin_dynamic_i18n_patterns.mjs
```
4. 重新构建验证：
```bash
cd web-admin && npm run build
```

### 排查基线（2026-03）
- 静态中文词条覆盖：扫描 `2577` 条，除注释外均可翻译。
- 动态模板句式覆盖：采样 `161` 条，剩余 `3` 条为源码中的模板片段（非真实运行时文案），不影响页面显示。
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
