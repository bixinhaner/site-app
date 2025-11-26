import request from '@/utils/request'
import { workOrderAPI } from '@/api/workorder'
import { stockApi } from '@/api/stock'
import { siteSurveysApi } from '@/api/siteSurveys'
import { useUserStore } from '@/stores/user'
// 顶部概览：使用后端聚合结果（要求精确，不做近似兜底）
export async function fetchTopStats() {
  return request.get('/api/dashboard/summary')
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

  return { my_orders: myOrders }
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

async function safeGet(fn, fallback) { try { return await fn() } catch (e) { return fallback } }
