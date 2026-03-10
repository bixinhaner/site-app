import { createRouter, createWebHistory, RouterView } from 'vue-router'
import { useUserStore } from '../stores/user'
import { buildRouteSnapshot, trackOperation } from '../utils/operationTrack'
import i18n from '../i18n'
import { resolveRouteTitle } from '../i18n/translator'
import { isSameRouteTarget, resolveDefaultAuthenticatedRoute, routeHasAccess } from './access'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    redirect: '/dashboard',
    component: () => import('../layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('../views/Dashboard.vue'),
        meta: { title: '仪表盘', icon: 'DataAnalysis' }
      },
      // 库存管理（二级菜单）
      {
        path: 'inventory',
        name: 'InventoryMgmt',
        component: RouterView,
        meta: { title: '库存管理', icon: 'TakeawayBox' },
        children: [
          { path: '', redirect: { name: 'InventoryList' }, meta: { hidden: true } },
          {
            path: 'equipment',
            name: 'Equipment',
            component: () => import('../views/equipment/EquipmentList.vue'),
            meta: { title: '设备类型管理', icon: 'Box', group: 'asset', order: 2 }
          },
          {
            path: 'packages',
            name: 'Packages',
            component: () => import('../views/package/PackageList.vue'),
            meta: { title: '设备套装配置', icon: 'Collection', group: 'asset', order: 3 }
          },
          {
            path: 'list',
            name: 'InventoryList',
            component: () => import('../views/stock/InventoryList.vue'),
            meta: { title: '设备库存管理', icon: 'List', group: 'flow', order: 1 }
          },
          {
            path: 'stock-in',
            name: 'StockIn',
            component: () => import('../views/stock/StockIn.vue'),
            meta: { title: '入库管理', icon: 'Upload', group: 'flow', order: 2 }
          },
          {
            path: 'material-requests',
            name: 'MaterialRequestList',
            component: () => import('../views/stock/MaterialRequestList.vue'),
            meta: { title: '物料申请', icon: 'DocumentAdd', roles: ['admin', 'warehouse_manager', 'manager'], group: 'flow', order: 3 }
          },
          {
            path: 'material-requests/:id',
            name: 'MaterialRequestDetail',
            component: () => import('../views/stock/MaterialRequestDetail.vue'),
            meta: { title: '申请单详情', hidden: true, roles: ['admin', 'warehouse_manager', 'manager'] }
          },
          {
            path: 'issue-drafts',
            name: 'IssueDraftList',
            component: () => import('../views/stock/IssueDraftList.vue'),
            meta: { title: '待确认出库', icon: 'DocumentChecked', accessKey: 'inventory-issue-confirm', group: 'flow', order: 4 }
          },
          {
            path: 'issue-drafts/:id',
            name: 'IssueDraftDetail',
            component: () => import('../views/stock/IssueDraftDetail.vue'),
            meta: { title: '出库确认', hidden: true, accessKey: 'inventory-issue-confirm' }
          },
          {
            path: 'manual-stock-out',
            name: 'ManualStockOut',
            component: () => import('../views/stock/ManualStockOut.vue'),
            meta: { title: '快速出库（无申请）', icon: 'Position', roles: ['admin', 'warehouse_manager', 'manager'], group: 'flow', order: 6 }
          },
          {
            path: 'return-receiving',
            name: 'ReturnReceiving',
            component: () => import('../views/stock/ReturnReceiving.vue'),
            meta: { title: '退库收货', icon: 'CircleCheck', accessKey: 'inventory-return-receiving', group: 'flow', order: 5 }
          },
          {
            path: 'flow-settings',
            name: 'StockFlowSettings',
            component: () => import('../views/stock/StockFlowSettings.vue'),
            meta: { title: '库存流程设置', icon: 'Setting', roles: ['admin', 'warehouse_manager', 'manager'], group: 'asset', order: 4 }
          },
          {
            path: 'history',
            name: 'StockHistory',
            component: () => import('../views/stock/StockHistory.vue'),
            meta: { title: '出入库记录', icon: 'Document', accessKey: 'inventory-history', group: 'ledger', order: 1 }
          },
          {
            path: 'user-ownership',
            name: 'UserOwnership',
            component: () => import('../views/stock/UserOwnership.vue'),
            meta: { title: '人员领用台账', icon: 'UserFilled', roles: ['admin', 'warehouse_manager', 'manager'], group: 'ledger', order: 5 }
          },
          {
            path: 'warehouses',
            name: 'Warehouses',
            component: () => import('../views/stock/WarehouseList.vue'),
            meta: { title: '仓库管理', icon: 'OfficeBuilding', group: 'asset', order: 1 }
          },
          {
            path: 'instances',
            name: 'EquipmentInstances',
            component: () => import('../views/equipment/EquipmentInstances.vue'),
            meta: { title: '设备实例清单', icon: 'Tickets', group: 'ledger', order: 3 }
          },
          {
            path: 'lifecycle',
            name: 'EquipmentLifecycle',
            component: () => import('../views/equipment/EquipmentLifecycle.vue'),
            meta: { title: '设备生命周期', icon: 'TrendCharts', accessKey: 'inventory-history', group: 'ledger', order: 4 }
          }
        ]
      },
      // 站点管理（二级菜单）
      {
        path: 'sites',
        name: 'SitesMgmt',
        component: RouterView,
        meta: { title: '站点管理', icon: 'Location' },
        children: [
          { path: 'list', name: 'SiteList', component: () => import('../views/site/SiteList.vue'), meta: { title: '站点列表', icon: 'Location' } },
          { path: 'map', name: 'SiteMap', component: () => import('../views/site/SiteMap.vue'), meta: { title: '站点地图', icon: 'MapLocation' } },
          { path: 'planning-lld-global', name: 'SitePlanningLldGlobal', component: () => import('../views/site/SitePlanningLldGlobal.vue'), meta: { title: 'LLD 规划总览', icon: 'DataAnalysis', roles: ['admin', 'manager', 'planner'] } },
          { path: 'detail/:id', name: 'SiteDetail', component: () => import('../views/site/SiteDetail.vue'), meta: { title: '站点详情', hidden: true } },
          { path: 'survey-stage-batch', name: 'SiteSurveyStageBatch', component: () => import('../views/site/SiteSurveyStageBatch.vue'), meta: { title: '勘察阶段批量设置', hidden: true, roles: ['admin', 'manager'] } },
          // 新版 LLD 站点规划页面
          { path: 'planning-lld/:id', name: 'SitePlanningLld', component: () => import('../views/site/SitePlanningLld.vue'), meta: { title: '站点规划（LLD）', hidden: true } },
          { path: 'basic-import', name: 'SiteBasicBatch', component: () => import('../views/site/SiteBasicBatch.vue'), meta: { title: '站点信息导入', icon: 'Plus' } },
          // 新版 LLD 规划导入页面
          { path: 'planning-batch-lld', name: 'SitePlanningBatchLld', component: () => import('../views/site/SitePlanningBatchLld.vue'), meta: { title: '规划信息导入（LLD）', icon: 'Operation' } },
          { path: 'basic-import-history', name: 'SiteBasicImportHistory', component: () => import('../views/site/SiteBasicImportHistory.vue'), meta: { title: '导入历史', hidden: true } },
          // 旧版勘察功能已废弃，路由删除
          { path: 'archives', name: 'SurveyArchives', component: () => import('../views/archives/ArchiveList.vue'), meta: { title: '勘察档案', icon: 'DocumentCopy' } },
          { path: 'archives/:id', name: 'SurveyArchiveDetail', component: () => import('../views/archives/ArchiveDetail.vue'), meta: { title: '档案详情', hidden: true } },
          { path: 'opening-archives', name: 'OpeningArchives', component: () => import('../views/opening-archives/OpeningArchiveList.vue'), meta: { title: '开站档案', icon: 'DocumentAdd' } },
          { path: 'opening-archives/:id', name: 'OpeningArchiveDetail', component: () => import('../views/opening-archives/OpeningArchiveDetail.vue'), meta: { title: '开站档案详情', hidden: true } },
          { path: 'ssv-archives', name: 'SSVArchives', component: () => import('../views/ssv-archives/SSVArchiveList.vue'), meta: { title: 'SSV 档案', icon: 'Document' } },
          { path: 'ssv-archives/:id', name: 'SSVArchiveDetail', component: () => import('../views/ssv-archives/SSVArchiveDetail.vue'), meta: { title: 'SSV 档案详情', hidden: true } }
        ]
      },
      // 检查管理（二级菜单）
      {
        path: 'inspections',
        name: 'InspectionsMgmt',
        component: RouterView,
        meta: { title: '检查管理', icon: 'Finished' },
        children: [
          { path: 'templates', name: 'InspectionTemplates', component: () => import('../views/inspection/TemplateManagement.vue'), meta: { title: '检查模板', icon: 'Document' } },
          { path: 'templates/:id', name: 'TemplateEditor', component: () => import('../views/inspection/TemplateEditor.vue'), meta: { title: '模板编辑器', hidden: true } }
        ]
      },
      // 工单管理（二级菜单）
      {
        path: 'work-orders',
        name: 'WorkOrders',
        component: RouterView,
        meta: { title: '工单管理', icon: 'Tickets' },
        children: [
          { path: 'my-execution', name: 'MyExecutionWorkOrders', component: () => import('../views/workorder/MyExecutionWorkOrders.vue'), meta: { title: '我的执行工单', icon: 'DocumentChecked', accessKey: 'web-workorder-entry' } },
          { path: 'list', name: 'WorkOrderList', component: () => import('../views/workorder/WorkOrderList.vue'), meta: { title: '工单列表', icon: 'List' } },
          { path: 'review', name: 'WorkOrderReview', component: () => import('../views/workorder/WorkOrderReview.vue'), meta: { title: '工单审核台', icon: 'Stamp' } },
          { path: 'execute/:id', name: 'WorkOrderExecute', component: () => import('../views/workorder/WorkOrderExecute.vue'), meta: { title: '工单执行台', hidden: true, accessKey: 'web-workorder-entry' } }
        ]
      },
      // 用户管理（二级菜单）
      {
        path: 'users',
        name: 'UsersMgmt',
        component: RouterView,
        meta: { title: '用户管理', icon: 'User' },
        children: [
          { path: 'list', name: 'UserList', component: () => import('../views/user/UserList.vue'), meta: { title: '用户列表', icon: 'UserFilled' } }
        ]
      },
      // 系统配置
      {
        path: 'settings',
        name: 'Settings',
        component: RouterView,
        meta: { title: '系统配置', icon: 'Setting' },
        children: [
          {
            path: 'mobile-location',
            name: 'MobileLocationSettings',
            component: () => import('../views/system/MobileLocationSettings.vue'),
            meta: { title: '移动端配置', icon: 'Iphone' }
          },
          {
            path: 'workorder-execution',
            name: 'WorkOrderExecutionSettings',
            component: () => import('../views/system/WorkOrderExecutionSettings.vue'),
            meta: { title: 'Web工单执行配置', icon: 'Monitor' }
          },
          {
            path: 'geocode-cache',
            name: 'GeocodeCache',
            component: () => import('../views/system/GeocodeCache.vue'),
            meta: { title: '逆地理缓存', icon: 'Location', roles: ['admin', 'manager'] }
          },
          {
            path: 'omc',
            name: 'OmcConfig',
            component: () => import('../views/system/OmcConfig.vue'),
            meta: { title: 'OMC API 配置', icon: 'Cpu' }
          },
          {
            path: 'omc-states',
            name: 'OmcDeviceStates',
            component: () => import('../views/system/OmcDeviceStateList.vue'),
            meta: { title: 'OMC 设备状态', icon: 'TrendCharts' }
          },
          {
            path: 'mock-omc',
            name: 'MockOmc',
            component: () => import('../views/system/MockOmc.vue'),
            meta: { title: '模拟 OMC 测试桩', icon: 'Cpu' }
          },
          {
            path: 'backup',
            name: 'DataBackup',
            component: () => import('../views/system/DataBackup.vue'),
            meta: { title: '数据备份', icon: 'FolderOpened' }
          },
          {
            path: 'operation-logs',
            name: 'OperationLogs',
            component: () => import('../views/system/OperationLogs.vue'),
            meta: { title: '操作日志', icon: 'Document', roles: ['admin', 'manager'] }
          },
          {
            path: 'mobile-logs',
            name: 'MobileClientLogs',
            component: () => import('../views/system/MobileClientLogs.vue'),
            meta: { title: '移动端日志', icon: 'Document', roles: ['admin', 'manager'] }
          },
          {
            path: 'app-version',
            name: 'AppVersionManage',
            component: () => import('../views/system/AppVersionManage.vue'),
            meta: { title: 'App版本管理', icon: 'Upload', roles: ['admin', 'manager'] }
          },
          {
            path: 'release-notes/:versionId',
            name: 'ReleaseNotesPreview',
            component: () => import('../views/system/ReleaseNotesPreview.vue'),
            meta: { title: 'Release Notes', icon: 'Document', hidden: true, roles: ['admin', 'manager'] }
          },
          {
            path: 'app-usage-stats',
            name: 'AppVersionStats',
            component: () => import('../views/system/AppVersionStats.vue'),
            meta: { title: 'App使用统计', icon: 'DataAnalysis', hidden: true, roles: ['admin', 'manager'] }
          },
          {
            path: 'ai',
            name: 'AiManagement',
            component: () => import('../views/system/AiManagement.vue'),
            meta: { title: 'AI管理', icon: 'MagicStick', roles: ['admin', 'manager', 'reviewer'] }
          },
          {
            path: 'permissions',
            name: 'PermissionCenter',
            component: () => import('../views/system/PermissionCenter.vue'),
            meta: { title: '角色权限', icon: 'Lock', roles: ['admin'] }
          }
        ]
      },
      // 兼容旧路径的重定向
      { path: 'equipment', redirect: { name: 'Equipment' }, meta: { hidden: true } },
      { path: 'packages', redirect: { name: 'Packages' }, meta: { hidden: true } },
      { path: 'stock-in', redirect: { name: 'StockIn' }, meta: { hidden: true } },
      { path: 'stock-history', redirect: { name: 'StockHistory' }, meta: { hidden: true } },
      { path: 'import-history', redirect: { name: 'StockHistory', query: { type: 'import' } }, meta: { hidden: true } }
    ]
  }
]

const ROUTE_PERMISSION_MAP = {
  Dashboard: ['dashboard:view:read'],
  Equipment: ['inventory:equipment:read'],
  Packages: ['inventory:package:read'],
  InventoryList: ['inventory:stock:read'],
  StockIn: ['inventory:stock-in:write'],
  MaterialRequestList: ['inventory:material-request:read'],
  MaterialRequestDetail: ['inventory:material-request:read'],
  IssueDraftList: ['inventory:issue-draft:read'],
  IssueDraftDetail: ['inventory:issue-draft:write'],
  ManualStockOut: ['inventory:stock-out:write'],
  ReturnReceiving: ['inventory:return:write'],
  StockFlowSettings: ['inventory:flow-settings:write'],
  StockHistory: ['inventory:history:read'],
  UserOwnership: ['inventory:user-ownership:read'],
  Warehouses: ['inventory:warehouse:read'],
  EquipmentInstances: ['inventory:stock:read'],
  EquipmentLifecycle: ['inventory:history:read'],
  SiteList: ['sites:list:read'],
  SiteMap: ['sites:list:read'],
  SitePlanningLldGlobal: ['sites:lld:read'],
  SiteDetail: ['sites:detail:read'],
  SiteSurveyStageBatch: ['sites:survey-stage:write'],
  SitePlanningLld: ['sites:lld:write'],
  SiteBasicBatch: ['sites:create:write', 'sites:update:write'],
  SitePlanningBatchLld: ['sites:lld:write'],
  SiteBasicImportHistory: ['sites:list:read', 'sites:create:write', 'sites:update:write'],
  SurveyArchives: ['sites:detail:read'],
  SurveyArchiveDetail: ['sites:detail:read'],
  OpeningArchives: ['sites:detail:read'],
  OpeningArchiveDetail: ['sites:detail:read'],
  SSVArchives: ['sites:detail:read'],
  SSVArchiveDetail: ['sites:detail:read'],
  InspectionTemplates: ['inspection:template:read'],
  TemplateEditor: ['inspection:template:write'],
  MyExecutionWorkOrders: ['workorder:execute:web'],
  WorkOrderList: ['workorder:list:read'],
  WorkOrderReview: ['workorder:review:write'],
  WorkOrderExecute: ['workorder:execute:web'],
  UserList: ['users:list:read'],
  MobileLocationSettings: ['system:mobile-settings:read'],
  WorkOrderExecutionSettings: ['authz:manage:all'],
  GeocodeCache: ['system:geocode-cache:read'],
  OmcConfig: ['system:mobile-settings:write'],
  OmcDeviceStates: ['system:logs:read'],
  MockOmc: ['system:mobile-settings:write'],
  DataBackup: ['system:backup:write'],
  OperationLogs: ['system:logs:read'],
  MobileClientLogs: ['system:logs:read'],
  AppVersionManage: ['system:app-version:read'],
  ReleaseNotesPreview: ['system:app-version:read'],
  AppVersionStats: ['system:app-version:read'],
  AiManagement: ['system:ai:read'],
  PermissionCenter: ['authz:manage:all'],
}

const applyRoutePermissions = (routeList = []) => {
  routeList.forEach((route) => {
    if (!route.meta) route.meta = {}
    if (route.name && ROUTE_PERMISSION_MAP[route.name]) {
      route.meta.permissions = ROUTE_PERMISSION_MAP[route.name]
    }
    if (Array.isArray(route.children) && route.children.length > 0) {
      applyRoutePermissions(route.children)
    }
  })
}

applyRoutePermissions(routes)

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const fallbackRoute = resolveDefaultAuthenticatedRoute(router.options.routes, userStore)

  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    if (fallbackRoute) {
      next(fallbackRoute)
      return
    }
    next()
  } else {
    if (!routeHasAccess(to, userStore)) {
      if (fallbackRoute && !isSameRouteTarget(fallbackRoute, to)) {
        next(fallbackRoute)
        return
      }
      next('/login')
      return
    }
    next()
  }
})

router.afterEach((to, from) => {
  if (typeof document !== 'undefined' && to?.name === 'Login') {
    document.title = `${i18n.global.t('route.Login')} - ${i18n.global.t('app.pageSuffix')}`
  }

  const userStore = useUserStore()
  if (!userStore.isLoggedIn) return
  if (to?.path === '/login') return

  const titles = (to.matched || []).map(r => resolveRouteTitle(r)).filter(Boolean)
  const pageTitle = titles[titles.length - 1] || resolveRouteTitle(to, i18n.global.t('operation.pageDefault'))
  const moduleTitle = titles.length >= 2 ? titles[titles.length - 2] : (titles[0] || i18n.global.t('operation.moduleDefault'))

  if (typeof document !== 'undefined') {
    document.title = `${pageTitle} - ${i18n.global.t('app.pageSuffix')}`
  }

  trackOperation({
    module: moduleTitle,
    action: i18n.global.t('operation.actionOpenPage'),
    object_type: i18n.global.t('operation.objectTypePage'),
    object_name: pageTitle,
    data: {
      route: buildRouteSnapshot(to, from),
    },
  })
})

export default router
