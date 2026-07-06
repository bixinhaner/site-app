# 仪表盘开站交付卡片筛选跳转设计

## 背景

仪表盘“开站交付概况”卡片展示的是站点生命周期统计，例如勘察、规划、安装开始、安装完成、部分上线、完全上线、部分激活、完全激活、SSV。用户点击卡片时，期望看到“这张卡片统计出来的站点到底是哪几个”。

当前实现里，部分卡片只是跳到站点列表、工单列表、勘察档案或规划页面，没有带上与仪表盘统计一致的筛选条件。尤其是“部分上线 / 完全上线 / 部分激活 / 完全激活 / SSV”这些卡片，点击后会进入未筛选的站点总表，用户无法直接定位对应站点。

## 目标

将“开站交付概况”9 个卡片统一跳转到站点列表，并按仪表盘同一统计口径筛出对应站点。

覆盖卡片：

- 勘察站点
- 规划站点
- 安装开始站点
- 安装完成站点
- 部分上线站点
- 完全上线站点
- 部分激活站点
- 完全激活站点
- SSV 站点

## 非目标

- 不新增独立明细页。
- 不新增弹窗明细。
- 不改变仪表盘统计口径。
- 不改变站点基础状态 `status` 的含义。
- 不把这些进度筛选混入站点状态下拉。
- 不改小区扩容概况卡片；小区扩容卡片当前目标是查看扩容工单。
- 不改“站点进度分组”表格的分组跳转；它已能带分组筛选。

## 当前代码判断

前端：

- `web-admin/src/components/dashboard/SiteProgressOverview.vue` 负责“开站交付概况”卡片。
- 目前多个卡片跳转为 `{ name: 'SiteList' }`，没有筛选 query。
- 勘察、规划、安装开始、安装完成当前分别跳档案页、规划页或工单列表，目标对象不统一。
- `web-admin/src/views/site/SiteList.vue` 目前能从 URL query 读取站点分组筛选，但不支持进度筛选。

后端：

- `backend/app/api/dashboard.py` 使用 `site_progress_snapshots` 与设备事实分数计算仪表盘口径。
- `backend/app/api/sites.py` 的 `/api/sites/search` 当前只支持 `keyword/status/status_in/site_type/assigned_to/group_*`。
- “部分上线 / 部分激活”不是简单的站点状态，必须由后端复用仪表盘同一套设备分数逻辑筛选。

## 推荐设计

### 1. 后端增加进度筛选参数

在 `/api/sites/search` 增加可选参数：

```text
site_progress_filter
```

允许值：

```text
survey_done
planning_done
install_started
installed
partial_online
fully_online
partial_activated
fully_activated
ssv_passed
```

后端根据该参数筛选站点集合，再叠加现有筛选条件：

- 先应用站点可见权限。
- 再应用 `keyword/status/site_type/group_*` 等现有筛选。
- 再应用 `site_progress_filter`，或在同一 query 中 join/filter，最终返回分页结果。

推荐实现上抽出一个小的服务函数，例如：

```text
apply_site_progress_filter(query, db, site_progress_filter, metric_mode)
```

这样 dashboard 和 sites API 不直接复制复杂判断，后续站点地图或导出也能复用。

### 2. 筛选口径

各筛选值含义：

| 筛选值 | 口径 |
| --- | --- |
| `survey_done` | 有有效勘察档案的站点，与仪表盘 `survey_done` 一致 |
| `planning_done` | 站点状态属于已规划及以后阶段，与仪表盘 `planning_done` 一致 |
| `install_started` | `site_progress_snapshots.install_started_at` 不为空 |
| `installed` | `site_progress_snapshots.install_completed_at` 不为空 |
| `partial_online` | 未达到完全上线，但开站基线设备位中至少 1 台曾上线 |
| `fully_online` | 当前全局站点进度统计口径下达到上线里程碑 |
| `partial_activated` | 未达到完全激活，但开站基线设备位中至少 1 台曾激活 |
| `fully_activated` | 当前全局站点进度统计口径下达到激活里程碑 |
| `ssv_passed` | `site_progress_snapshots.ssv_at` 不为空 |

上线和激活必须跟随系统现有“站点进度统计口径”开关：

- 流程口径：读取 `online_at / activated_at`。
- 设备事实口径：读取 `online_at_device_fact / activated_at_device_fact`。

部分上线和部分激活继续按开站基线设备位计算，避免小区扩容把开站交付分母从 3 拉成 6。

### 3. 前端跳转

`SiteProgressOverview.vue` 中 9 个卡片统一跳转：

```js
{ name: 'SiteList', query: { site_progress_filter: 'partial_online' } }
```

映射：

| 卡片 | query |
| --- | --- |
| 勘察站点 | `site_progress_filter=survey_done` |
| 规划站点 | `site_progress_filter=planning_done` |
| 安装开始站点 | `site_progress_filter=install_started` |
| 安装完成站点 | `site_progress_filter=installed` |
| 部分上线站点 | `site_progress_filter=partial_online` |
| 完全上线站点 | `site_progress_filter=fully_online` |
| 部分激活站点 | `site_progress_filter=partial_activated` |
| 完全激活站点 | `site_progress_filter=fully_activated` |
| SSV 站点 | `site_progress_filter=ssv_passed` |

### 4. 站点列表体验

站点列表读取 `route.query.site_progress_filter` 后：

- 设置本地筛选状态。
- 请求 `/api/sites/search` 时带上 `site_progress_filter`。
- 在筛选区显示一个来源标签：

```text
仪表盘筛选：部分上线站点
```

标签提供清除按钮，清除后：

- 移除本地 `siteProgressFilter`。
- 更新 URL query。
- 重新加载站点总表或保留其它筛选条件。

该筛选不放入“状态”下拉，因为它不是站点基础状态，而是进度统计状态。

### 5. 错误处理

- 后端收到未知 `site_progress_filter` 返回 400，提示“不支持的仪表盘站点筛选”。
- 若快照缺失或版本落后，沿用现有 `ensure_site_progress_snapshots` 策略补建/补算。
- 若设备分数无法计算，部分上线/部分激活不应误计入，保持与仪表盘一致。

### 6. 测试建议

后端：

- 覆盖 9 个 `site_progress_filter` 的集合筛选。
- 覆盖 `partial_online` 与 `fully_online` 互斥。
- 覆盖 `partial_activated` 与 `fully_activated` 互斥。
- 覆盖 `site_progress_filter + group_category_id/group_option_id` 组合筛选。
- 覆盖无效筛选值返回 400。

前端：

- 站点列表能从 query 初始化进度筛选。
- 仪表盘 9 个卡片跳转 query 正确。
- 清除筛选后 URL 和列表同步恢复。
- 构建通过。

## 推荐实施顺序

1. 后端抽出并接入 `site_progress_filter` 筛选逻辑。
2. 站点列表读取、展示、清除 `site_progress_filter`。
3. 仪表盘 9 个卡片统一跳站点列表并带 query。
4. 补充 README 实现说明。
5. 执行后端脚本测试和 `web-admin npm run build`。
