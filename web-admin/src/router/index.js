import { createRouter, createWebHistory, RouterView } from 'vue-router'
import { useUserStore } from '../stores/user'

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
            meta: { title: '设备类型管理', icon: 'Box' }
          },
          {
            path: 'packages',
            name: 'Packages',
            component: () => import('../views/package/PackageList.vue'),
            meta: { title: '设备套装配置', icon: 'Collection' }
          },
          {
            path: 'list',
            name: 'InventoryList',
            component: () => import('../views/stock/InventoryList.vue'),
            meta: { title: '设备库存管理', icon: 'List' }
          },
          {
            path: 'stock-in',
            name: 'StockIn',
            component: () => import('../views/stock/StockIn.vue'),
            meta: { title: '入库管理', icon: 'Upload' }
          },
          {
            path: 'history',
            name: 'StockHistory',
            component: () => import('../views/stock/StockHistory.vue'),
            meta: { title: '出入库记录', icon: 'Document' }
          },
          {
            path: 'warehouses',
            name: 'Warehouses',
            component: () => import('../views/stock/WarehouseList.vue'),
            meta: { title: '仓库管理', icon: 'OfficeBuilding' }
          },
          {
            path: 'instances',
            name: 'EquipmentInstances',
            component: () => import('../views/equipment/EquipmentInstances.vue'),
            meta: { title: '设备实例清单', icon: 'Tickets' }
          },
          {
            path: 'lifecycle',
            name: 'EquipmentLifecycle',
            component: () => import('../views/equipment/EquipmentLifecycle.vue'),
            meta: { title: '设备生命周期', icon: 'TrendCharts' }
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
          { path: 'detail/:id', name: 'SiteDetail', component: () => import('../views/site/SiteDetail.vue'), meta: { title: '站点详情', hidden: true } },
          // 旧版站点规划页面（逐步下线）
          { path: 'planning/:id', name: 'SitePlanning', component: () => import('../views/site/SitePlanning.vue'), meta: { title: '站点规划（旧）', hidden: true } },
          // 新版 LLD 站点规划页面
          { path: 'planning-lld/:id', name: 'SitePlanningLld', component: () => import('../views/site/SitePlanningLld.vue'), meta: { title: '站点规划（LLD新）', hidden: true } },
          { path: 'basic-import', name: 'SiteBasicBatch', component: () => import('../views/site/SiteBasicBatch.vue'), meta: { title: '站点信息导入', icon: 'Plus' } },
          // 旧版规划导入页面
          { path: 'planning-batch', name: 'SitePlanningBatch', component: () => import('../views/site/SitePlanningBatch.vue'), meta: { title: '规划信息导入（旧）', icon: 'Operation' } },
          // 新版 LLD 规划导入页面
          { path: 'planning-batch-lld', name: 'SitePlanningBatchLld', component: () => import('../views/site/SitePlanningBatchLld.vue'), meta: { title: '规划信息导入（LLD新）', icon: 'Operation' } },
          { path: 'basic-import-history', name: 'SiteBasicImportHistory', component: () => import('../views/site/SiteBasicImportHistory.vue'), meta: { title: '导入历史', hidden: true } },
          { path: 'surveys', name: 'SiteSurveys', component: () => import('../views/surveys/SurveyList.vue'), meta: { title: '勘察档案（旧-废弃）', icon: 'PictureFilled' } },
          { path: 'surveys/new', name: 'SiteSurveyNew', component: () => import('../views/surveys/SurveyForm.vue'), meta: { title: '新建勘察', hidden: true } },
          { path: 'surveys/:id', name: 'SiteSurveyDetail', component: () => import('../views/surveys/SurveyDetail.vue'), meta: { title: '勘察详情', hidden: true } }
          ,
          { path: 'archives', name: 'SurveyArchives', component: () => import('../views/archives/ArchiveList.vue'), meta: { title: '勘察档案(新)', icon: 'DocumentCopy' } },
          { path: 'archives/:id', name: 'SurveyArchiveDetail', component: () => import('../views/archives/ArchiveDetail.vue'), meta: { title: '档案详情', hidden: true } }
        ]
      },
      // 检查管理（二级菜单）
      {
        path: 'inspections',
        name: 'InspectionsMgmt',
        component: RouterView,
        meta: { title: '检查管理', icon: 'Finished' },
        children: [
          { path: 'list', name: 'InspectionList', component: () => import('../views/inspection/InspectionList.vue'), meta: { title: '检查记录', icon: 'Finished' } },
          { path: 'review', name: 'InspectionReview', component: () => import('../views/inspection/InspectionReview.vue'), meta: { title: '检查审核台', icon: 'Stamp' } },
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
          { path: 'list', name: 'WorkOrderList', component: () => import('../views/workorder/WorkOrderList.vue'), meta: { title: '工单列表', icon: 'List' } },
          { path: 'review', name: 'WorkOrderReview', component: () => import('../views/workorder/WorkOrderReview.vue'), meta: { title: '工单审核台', icon: 'Stamp' } }
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
          }
        ]
      },
      // 兼容旧路径的重定向
      { path: 'equipment', redirect: { name: 'Equipment' }, meta: { hidden: true } },
      { path: 'packages', redirect: { name: 'Packages' }, meta: { hidden: true } },
      { path: 'stock-in', redirect: { name: 'StockIn' }, meta: { hidden: true } },
      { path: 'stock-history', redirect: { name: 'StockHistory' }, meta: { hidden: true } },
      { path: 'import-history', redirect: { name: 'StockHistory', query: { type: 'import' } }, meta: { hidden: true } },
      {
        path: 'reports',
        name: 'Reports',
        component: () => import('../views/report/Reports.vue'),
        meta: { title: '报表中心', icon: 'PieChart' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next('/login')
  } else if (to.path === '/login' && userStore.isLoggedIn) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
