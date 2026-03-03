const actionMap = {
  删除: 'delete',
  启用: 'enable',
  禁用: 'disable',
  更新: 'update',
  创建: 'create',
}

const toAction = (action) => actionMap[action] || action
const yesNoMap = { 是: 'Yes', 否: 'No' }
const toYesNo = (value) => yesNoMap[value] || value
const resultMap = { 成功: 'Success', 失败: 'Failed' }
const toResult = (value) => resultMap[value] || value

const legacyDynamicOverrides = [
  {
    pattern: /^确定要(删除|启用|禁用)设备 "(.*?)" 吗？$/,
    replace: (_, action, name) => `Are you sure you want to ${toAction(action)} the device "${name}"?`,
  },
  {
    pattern: /^确定要(删除|启用|禁用)套装 "(.*?)" 吗？$/,
    replace: (_, action, name) => `Are you sure you want to ${toAction(action)} the package "${name}"?`,
  },
  {
    pattern: /^确定要(删除|启用|禁用)用户 "(.*?)" 吗？$/,
    replace: (_, action, name) => `Are you sure you want to ${toAction(action)} the user "${name}"?`,
  },
  {
    pattern: /^确认(启用|禁用|删除)$/,
    replace: (_, action) => `Confirm ${toAction(action)}`,
  },
  {
    pattern: /^确认删除模板 "(.*?)" 吗？$/,
    replace: (_, templateName) => `Are you sure you want to delete template "${templateName}"?`,
  },
  { pattern: /^设备启用成功$/, replace: 'Device enabled successfully' },
  { pattern: /^设备禁用成功$/, replace: 'Device disabled successfully' },
  { pattern: /^设备删除成功$/, replace: 'Device deleted successfully' },
  {
    pattern: /^设备(.*?)成功$/,
    replace: (_, action) => `Device ${toAction(action)}d successfully`,
  },
  { pattern: /^套装启用成功$/, replace: 'Package enabled successfully' },
  { pattern: /^套装禁用成功$/, replace: 'Package disabled successfully' },
  { pattern: /^套装删除成功$/, replace: 'Package deleted successfully' },
  {
    pattern: /^套装(.*?)成功$/,
    replace: (_, action) => `Package ${toAction(action)}d successfully`,
  },
  { pattern: /^启用成功$/, replace: 'Enabled successfully' },
  { pattern: /^禁用成功$/, replace: 'Disabled successfully' },
  {
    pattern: /^出库成功：(.*?)$/,
    replace: (_, docNo) => `Stock-out succeeded: ${docNo}`,
  },
  {
    pattern: /^超距 (.*?) 张$/,
    replace: (_, count) => `Exceeded threshold: ${count} photos`,
  },
  {
    pattern: /^站点列表_(.*?)\.xlsx$/,
    replace: (_, date) => `site-list-${date}.xlsx`,
  },
  {
    pattern: /^主设备库存_(.*?)\.xlsx$/,
    replace: (_, date) => `main-device-inventory-${date}.xlsx`,
  },
  {
    pattern: /^辅材库存_(.*?)\.xlsx$/,
    replace: (_, date) => `auxiliary-material-inventory-${date}.xlsx`,
  },
  {
    pattern: /^人员领用台账_全部物料_(.*?)\.xlsx$/,
    replace: (_, date) => `user-ownership-all-materials-${date}.xlsx`,
  },
  {
    pattern: /^(.*?)_(.*?)_领用明细_(.*?)\.xlsx$/,
    replace: (_, userName, tabName, date) => `${userName}-${tabName}-pickup-details-${date}.xlsx`,
  },
  {
    pattern: /^勘察档案_(.*?)_(.*?)_v(.*?)_(.*?)\.(.*?)$/,
    replace: (_, code, name, ver, ts, ext) => `survey-archive-${code}-${name}-v${ver}-${ts}.${ext}`,
  },
  {
    pattern: /^开站档案_(.*?)_(.*?)_v(.*?)_(.*?)\.(.*?)$/,
    replace: (_, code, name, ver, ts, ext) => `opening-archive-${code}-${name}-v${ver}-${ts}.${ext}`,
  },
  {
    pattern: /^SSV档案_(.*?)_(.*?)_v(.*?)_(.*?)\.(.*?)$/,
    replace: (_, code, name, ver, ts, ext) => `ssv-archive-${code}-${name}-v${ver}-${ts}.${ext}`,
  },
  {
    pattern: /^请等待 (.*?)s 后再刷新 OMC 状态$/,
    replace: (_, seconds) => `Please wait ${seconds}s before refreshing OMC status`,
  },
  {
    pattern: /^请等待 (.*?)s 后再刷新设备状态$/,
    replace: (_, seconds) => `Please wait ${seconds}s before refreshing device status`,
  },
  {
    pattern: /^请等待 (.*?)s 后再检测该设备$/,
    replace: (_, seconds) => `Please wait ${seconds}s before checking this device`,
  },
  {
    pattern: /^有 (.*?) 张图片加载失败，将尝试直接预览原始链接$/,
    replace: (_, count) => `${count} images failed to load. The system will try previewing original links directly.`,
  },
  {
    pattern: /^最多只能选择 (.*?) 张图片$/,
    replace: (_, count) => `You can select up to ${count} images`,
  },
  {
    pattern: /^图片大小不能超过 (.*?)MB$/,
    replace: (_, size) => `Image size cannot exceed ${size} MB`,
  },
  {
    pattern: /^主设备 (.*?) 必须填写序列号\(SN\)$/,
    replace: (_, name) => `Serial number (SN) is required for main device ${name}`,
  },
  {
    pattern: /^主设备 (.*?) 数量必须为1$/,
    replace: (_, name) => `Quantity for main device ${name} must be 1`,
  },
  {
    pattern: /^校验失败：发现 (.*?) 个问题，已阻止导入$/,
    replace: (_, count) => `Validation failed: ${count} issue(s) found. Import has been blocked.`,
  },
  {
    pattern: /^校验失败：发现 (.*?) 个问题，已阻止整文件导入$/,
    replace: (_, count) => `Validation failed: ${count} issue(s) found. Full-file import has been blocked.`,
  },
  {
    pattern: /^共 (.*?) 行，成功 (.*?) 行，失败 (.*?) 行$/,
    replace: (_, total, success, failed) => `Total ${total} rows, ${success} succeeded, ${failed} failed`,
  },
  {
    pattern: /^共 (.*?) 个站点，成功 (.*?) 个，失败 (.*?) 个$/,
    replace: (_, total, success, failed) => `Total ${total} sites, ${success} succeeded, ${failed} failed`,
  },
  {
    pattern: /^费用\((.*?)\)$/,
    replace: (_, currency) => `Cost (${currency})`,
  },
  {
    pattern: /^确认导入辅料入库\？(?:\\n|\n)原始行数：(.*?)(?:\\n|\n)辅料种类数：(.*?)(?:\\n|\n)入库总数量：(.*?)$/,
    replace: (_, rawRows, typeCount, quantity) =>
      `Confirm import for auxiliary material stock-in?\nRaw rows: ${rawRows}\nMaterial types: ${typeCount}\nTotal quantity: ${quantity}`,
  },
  {
    pattern: /^确认导入辅料入库\？(?:\\\\n)+原始行数：(.*?)(?:\\\\n)+辅料种类数：(.*?)(?:\\\\n)+入库总数量：(.*?)$/,
    replace: (_, rawRows, typeCount, quantity) =>
      `Confirm import for auxiliary material stock-in?\nRaw rows: ${rawRows}\nMaterial types: ${typeCount}\nTotal quantity: ${quantity}`,
  },
  {
    pattern: /^检测到 (.*?) 个重复SN将被跳过:(?:\\n|\n)+(.*?)(?:\\n|\n)+是否继续导入剩余 (.*?) 个SN？$/,
    replace: (_, dupCount, details, remainCount) =>
      `${dupCount} duplicate SN(s) will be skipped:\n${details}\nContinue importing the remaining ${remainCount} SN(s)?`,
  },
  {
    pattern: /^将 AI 建议写入“审核结果\/审核意见”？(?:\\n|\n)检查项：(.*?)$/,
    replace: (_, itemName) => `Write AI suggestions into "Review Result / Review Comment"?\nInspection item: ${itemName}`,
  },
  {
    pattern: /^确认设备 SN (.*?) 已激活？该操作不可撤销，将同时确认“已上线”，并可能触发工单状态推进。$/,
    replace: (_, sn) =>
      `Confirm device SN ${sn} is activated? This action is irreversible, will also confirm "Online", and may advance work order status.`,
  },
  {
    pattern: /^确认设备 SN (.*?) 已上线？该操作不可撤销，且可能触发工单状态推进。$/,
    replace: (_, sn) =>
      `Confirm device SN ${sn} is online? This action is irreversible and may advance work order status.`,
  },
  {
    pattern: /^确认新建补勘工单？创建成功后将自动把站点恢复为需要勘察（保留跳过记录）。(.*?)$/,
    replace: (_, extra) =>
      `Confirm creating a supplementary survey work order? After creation, the site will be restored to "Survey Required" (skip record retained). ${extra}`,
  },
  {
    pattern: /^确定要删除这个(.*?) Cell \((.*?), 扇区(.*?)\) 吗？$/,
    replace: (_, rat, band, sector) => `Are you sure you want to delete this ${rat} Cell (${band}, sector ${sector})?`,
  },
  {
    pattern: /^确定要删除选中的 (.*?) 个工单吗？(?:\\n|\n)+注意：只能删除\"待分配\"或\"已分配\"状态的工单。$/,
    replace: (_, count) =>
      `Are you sure you want to delete ${count} selected work order(s)? Only "Pending Assignment" or "Assigned" work orders can be deleted.`,
  },
  {
    pattern: /^确定要重新分配选中的 (.*?) 个工单吗？(?:\\n|\n)+注意：只能重新分配\"待分配\"或\"已分配\"状态的工单。$/,
    replace: (_, count) =>
      `Are you sure you want to reassign ${count} selected work order(s)? Only "Pending Assignment" or "Assigned" work orders can be reassigned.`,
  },
  {
    pattern: /^确认清理超过\s*(.*?)\s*天的移动端日志[？?]$/,
    replace: (_, count) => `Are you sure you want to clear mobile logs older than ${count} days?`,
  },
  {
    pattern: /^确认清理超过\s*(.*?)\s*天的操作日志[？?]$/,
    replace: (_, count) => `Confirm to clear operation logs older than ${count} days?`,
  },
  {
    pattern: /^已放弃领货，已取消(.*?)个未完成领料单$/,
    replace: (_, count) => `Pickup abandoned. ${count} unfinished issue draft(s) have been cancelled.`,
  },
  {
    pattern: /^批量删除 \((.*?)\)$/,
    replace: (_, count) => `Batch delete (${count})`,
  },
  {
    pattern: /^共 (.*?) 种主设备$/,
    replace: (_, count) => `Total ${count} main device types`,
  },
  {
    pattern: /^总库存量:\s*(.*?)$/,
    replace: (_, count) => `Total inventory: ${count}`,
  },
  {
    pattern: /^查看实例 \((.*?)\)$/,
    replace: (_, count) => `View instances (${count})`,
  },
  {
    pattern: /^总金额:\s*¥(.*?)$/,
    replace: (_, amount) => `Total amount: ¥${amount}`,
  },
  {
    pattern: /^批次 (.*?) 条$/,
    replace: (_, count) => `Batch ${count} items`,
  },
  {
    pattern: /^发起：\s*(.*?)$/,
    replace: (_, value) => `Initiated: ${value}`,
  },
  {
    pattern: /^最近更新：\s*(.*?)$/,
    replace: (_, value) => `Latest update: ${value}`,
  },
  {
    pattern: /^已领货 (.*?)$/,
    replace: (_, count) => `Picked up ${count}`,
  },
  {
    pattern: /^退库待收货 (.*?)$/,
    replace: (_, count) => `Awaiting return receipt ${count}`,
  },
  {
    pattern: /^已安装 (.*?)$/,
    replace: (_, count) => `Installed ${count}`,
  },
  {
    pattern: /^已退库 (.*?)$/,
    replace: (_, count) => `Returned ${count}`,
  },
  {
    pattern: /^领 (.*?)$/,
    replace: (_, count) => `Pickup ${count}`,
  },
  {
    pattern: /^装 (.*?)$/,
    replace: (_, count) => `Installed ${count}`,
  },
  {
    pattern: /^待收 (.*?)$/,
    replace: (_, count) => `Pending receipt ${count}`,
  },
  {
    pattern: /^退 (.*?)$/,
    replace: (_, count) => `Returned ${count}`,
  },
  {
    pattern: /^共 (.*?) 条$/,
    replace: (_, count) => `Total ${count} items`,
  },
  {
    pattern: /^(.*?) 进行中$/,
    replace: (_, count) => `${count} in progress`,
  },
  {
    pattern: /^(.*?) 总计$/,
    replace: (_, count) => `${count} total`,
  },
  {
    pattern: /^共 (.*?) 个检查分类$/,
    replace: (_, count) => `${count} inspection categories`,
  },
  {
    pattern: /^获取坐标， 再通过后端代理调用逆地理接口获取地址信息（国内优先 Baidu，海外走 Google；后端按约 30m 网格缓存，提高命中率并减少第三方调用）。$/,
    replace:
      'Get coordinates, then call reverse geocoding through backend proxy (Baidu first for China, Google for overseas). Backend caches by ~30m grids to improve hit rate and reduce third-party calls.',
  },
  {
    pattern: /^缩略预览比例：(.*?)$/,
    replace: (_, value) => `Thumbnail preview scale: ${value}`,
  },
  {
    pattern: /^默认模板 \((.*?)\)$/,
    replace: (_, key) => `Default template (${key})`,
  },
  {
    pattern: /^请求 (.*?)$/,
    replace: (_, count) => `Requests ${count}`,
  },
  {
    pattern: /^L1 命中 (.*?)$/,
    replace: (_, count) => `L1 hits ${count}`,
  },
  {
    pattern: /^L2 命中 (.*?)$/,
    replace: (_, count) => `L2 hits ${count}`,
  },
  {
    pattern: /^百度调用 (.*?)$/,
    replace: (_, count) => `Baidu calls ${count}`,
  },
  {
    pattern: /^Google 调用 (.*?)$/,
    replace: (_, count) => `Google calls ${count}`,
  },
  {
    pattern: /^Google 直连 (.*?)$/,
    replace: (_, count) => `Google direct ${count}`,
  },
  {
    pattern: /^写入 SQLite (.*?)$/,
    replace: (_, count) => `SQLite writes ${count}`,
  },
  {
    pattern: /^负缓存命中 (.*?)$/,
    replace: (_, count) => `Negative cache hits ${count}`,
  },
  {
    pattern: /^熔断拦截 (.*?)$/,
    replace: (_, count) => `Circuit-breaker blocks ${count}`,
  },
  {
    pattern: /^熔断触发 (.*?)$/,
    replace: (_, count) => `Circuit-breaker trips ${count}`,
  },
  {
    pattern: /^曾上线: (是|否)$/,
    replace: (_, value) => `Previously online: ${toYesNo(value)}`,
  },
  {
    pattern: /^曾激活: (是|否)$/,
    replace: (_, value) => `Previously activated: ${toYesNo(value)}`,
  },
  {
    pattern: /^当前目标：(.*?)$/,
    replace: (_, target) => `Current target: ${target}`,
  },
  {
    pattern: /^待分配 (.*?) · 审核中 (.*?) · 已完成 (.*?)$/,
    replace: (_, pending, reviewing, done) => `Pending assignment ${pending} · In review ${reviewing} · Completed ${done}`,
  },
  {
    pattern: /^站点：(.*?)$/,
    replace: (_, siteName) => `Site: ${siteName}`,
  },
  {
    pattern: /^(.*?) 在【(.*?)】(.*?)（(.*?)，名称:(.*?)） - (.*?)$/,
    replace: (_, user, section, action, type, name, result) =>
      `${user} in [${section}] ${action} (${type}, Name: ${name}) - ${toResult(result)}`,
  },
  {
    pattern: /^(.*?) - 成功$/,
    replace: (_, prefix) => `${prefix} - Success`,
  },
  {
    pattern: /^(.*?) - 失败$/,
    replace: (_, prefix) => `${prefix} - Failed`,
  },
  {
    pattern: /^未配置$/,
    replace: 'Not configured',
  },
  {
    pattern: /^已配置：(.*?)$/,
    replace: (_, masked) => `Configured: ${masked}`,
  },
]

export default legacyDynamicOverrides
