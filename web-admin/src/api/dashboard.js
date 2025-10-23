import request from '@/utils/request'
import { stockApi } from '@/api/stock'
import { workOrderAPI } from '@/api/workorder'
import { userAPI } from '@/api/user'
import { siteSurveysApi } from '@/api/siteSurveys'
import { useUserStore } from '@/stores/user'

// 顶部概览：并发拉取核心统计
export async function fetchTopStats() {
  const userStore = useUserStore()

  const now = new Date()
  const from = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

  // 优先尝试后端聚合接口（Phase 2）
  const aggregated = await safeGet(() => request.get('/api/dashboard/summary'), null)
  if (aggregated && aggregated.work_orders) {
    return aggregated
  }

  const [woStats, userStats, invDash, sitesApprox, inspUnder, inspSubmitted, surveys7d] = await Promise.all([
    // 工单统计
    safeGet(() => workOrderAPI.getWorkOrderStats(), {}),
    // 用户统计
    safeGet(() => userAPI.getUserStats(), {}),
    // 库存看板（含低库存计数 + 最近出入库）
    safeGet(() => stockApi.getInventoryDashboard(), {}),
    // 站点状态“近似”统计：拉取前100条本页数据进行分组
    safeGet(() => request.get('/api/sites/', { params: { limit: 100 } }), []),
    // 待审核检查（under_review）
    safeGet(() => request.get('/api/inspections/', { params: { status: 'under_review' } }), []),
    // 待审核检查（submitted）
    safeGet(() => request.get('/api/inspections/', { params: { status: 'submitted' } }), []),
    // 勘察近7日新增：用分页接口 total 作为计数
    safeGet(() => siteSurveysApi.page({ page: 1, page_size: 1, date_from: from.toISOString(), date_to: now.toISOString() }), { total: 0 }),
  ])

  // 站点状态分布（近似）
  const siteStatusCounts = Array.isArray(sitesApprox)
    ? sitesApprox.reduce((acc, s) => { const k = s.status || 'unknown'; acc[k] = (acc[k] || 0) + 1; return acc }, {})
    : {}

  return {
    work_orders: {
      total: Number(woStats.total_work_orders || 0),
      status: woStats.status_stats || {},
    },
    users: {
      total: Number(userStats.total_users || 0),
      active: Number(userStats.active_users || 0),
    },
    inventory: {
      low_stock_count: Number(invDash?.summary?.low_stock_items || 0),
      main_device_total_stock: Number(invDash?.summary?.main_device_total_stock || 0),
      recent_transactions: invDash?.recent_transactions || [],
    },
    sites: {
      approx: true,
      status: siteStatusCounts,
      sample_size: Array.isArray(sitesApprox) ? sitesApprox.length : 0,
    },
    inspections: {
      pending_review_count: Number((inspUnder?.length || 0) + (inspSubmitted?.length || 0)),
    },
    surveys: {
      last7d_new: Number(surveys7d?.total || 0),
    },
    time_range: { from: from.toISOString(), to: now.toISOString() },
  }
}

// 我的待办（工单、检查）
export async function fetchTodos() {
  const userStore = useUserStore()
  const uid = userStore.user?.id
  const isAdmin = userStore.isAdmin
  const isManager = userStore.isManager

  // 我的工单：待分配/已分配
  const [minePending, mineActive] = await Promise.all([
    safeGet(() => workOrderAPI.getWorkOrders({ status: 'PENDING', assigned_to: uid }), []),
    safeGet(() => workOrderAPI.getWorkOrders({ status: 'ACTIVE', assigned_to: uid }), []),
  ])

  const myOrders = [...(minePending || []), ...(mineActive || [])]
    .sort((a, b) => dateVal(a?.due_date) - dateVal(b?.due_date))
    .slice(0, 5)

  // 待我审核的检查（仅管理员/经理展示）：under_review + submitted 合并 Top5
  let reviewList = []
  if (isAdmin || isManager) {
    const [underV, submittedV] = await Promise.all([
      safeGet(() => request.get('/api/inspections/', { params: { status: 'under_review' } }), []),
      safeGet(() => request.get('/api/inspections/', { params: { status: 'submitted' } }), []),
    ])
    reviewList = [...(underV || []), ...(submittedV || [])].slice(0, 5)
  }

  return { my_orders: myOrders, review_inspections: reviewList }
}

// 风险与预警（低库存、逾期工单）
export async function fetchRisks() {
  const userStore = useUserStore()
  const uid = userStore.user?.id
  const isAdmin = userStore.isAdmin
  const isManager = userStore.isManager

  // 低库存 Top5
  const lowStockResp = await safeGet(() => stockApi.getInventoryList({ low_stock_only: true }), {})
  const lowStock = Array.isArray(lowStockResp?.inventory) ? lowStockResp.inventory.slice(0, 5) : []

  // 逾期工单：PENDING/ACTIVE，管理员看全部，其它看分配给自己的
  const baseParams = (status) => ({ status, ...(isAdmin || isManager ? {} : { assigned_to: uid }) })
  const [woP, woA] = await Promise.all([
    safeGet(() => workOrderAPI.getWorkOrders(baseParams('PENDING')) , []),
    safeGet(() => workOrderAPI.getWorkOrders(baseParams('ACTIVE')) , []),
  ])
  const now = Date.now()
  const overdue = [...woP, ...woA]
    .filter(w => w?.due_date && new Date(w.due_date).getTime() < now)
    .sort((a, b) => dateVal(a?.due_date) - dateVal(b?.due_date))
    .slice(0, 5)

  // 近7天内将到期
  const soon = [...woP, ...woA]
    .filter(w => w?.due_date && daysBetween(now, new Date(w.due_date).getTime()) <= 7 && new Date(w.due_date).getTime() >= now)
    .sort((a, b) => dateVal(a?.due_date) - dateVal(b?.due_date))
    .slice(0, 5)

  return { low_stock: lowStock, overdue, due_soon: soon }
}

// 最近动态（出入库、工单、勘察、日志）
export async function fetchActivity() {
  const userStore = useUserStore()
  const isAdmin = userStore.isAdmin
  const isManager = userStore.isManager

  const [transactions, recentWorkOrders, recentSurveys, logs] = await Promise.all([
    safeGet(() => request.get('/api/stock/transactions', { params: { limit: 10 } }), []),
    safeGet(() => workOrderAPI.getWorkOrders({ limit: 10 }), []),
    safeGet(() => siteSurveysApi.page({ page: 1, page_size: 10, sort_by: 'created_at', sort_dir: 'desc' }), { items: [] }),
    // 普通用户只能看到自己的日志，接口内部限制
    safeGet(() => (isAdmin || isManager) ? request.get('/api/logs', { params: { limit: 10 } }) : Promise.resolve([]), []),
  ])

  return {
    stock_transactions: Array.isArray(transactions) ? transactions.slice(0, 5) : [],
    work_orders: Array.isArray(recentWorkOrders) ? recentWorkOrders.slice(0, 5) : [],
    site_surveys: Array.isArray(recentSurveys?.items) ? recentSurveys.items.slice(0, 5) : [],
    logs: Array.isArray(logs) ? logs.slice(0, 5) : [],
  }
}

// 工具函数
function dateVal(d) { return d ? new Date(d).getTime() : Number.MAX_SAFE_INTEGER }
function daysBetween(t0, t1) { return Math.floor((t1 - t0) / (24 * 3600 * 1000)) }

async function safeGet(fn, fallback) {
  try { return await fn() } catch (e) { return fallback }
}
