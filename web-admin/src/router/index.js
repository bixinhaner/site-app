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
            path: 'import-history',
            name: 'ImportHistory',
            component: () => import('../views/stock/ImportHistory.vue'),
            meta: { title: 'SN导入记录', icon: 'Tickets' }
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
          { path: 'planning/:id', name: 'SitePlanning', component: () => import('../views/site/SitePlanning.vue'), meta: { title: '站点规划', hidden: true } },
          { path: 'planning-batch', name: 'SitePlanningBatch', component: () => import('../views/site/SitePlanningBatch.vue'), meta: { title: '规划批量导入', icon: 'Operation' } }
        ]
      },
      // 任务管理（二级菜单）
      {
        path: 'tasks',
        name: 'TasksMgmt',
        component: RouterView,
        meta: { title: '任务管理', icon: 'List' },
        children: [
          { path: 'list', name: 'TaskList', component: () => import('../views/task/TaskList.vue'), meta: { title: '任务列表', icon: 'List' } },
          { path: 'review', name: 'TaskReview', component: () => import('../views/task/TaskReview.vue'), meta: { title: '任务审核台', icon: 'Operation' } }
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
      // 兼容旧路径的重定向
      { path: 'equipment', redirect: { name: 'Equipment' }, meta: { hidden: true } },
      { path: 'packages', redirect: { name: 'Packages' }, meta: { hidden: true } },
      { path: 'stock-in', redirect: { name: 'StockIn' }, meta: { hidden: true } },
      { path: 'stock-history', redirect: { name: 'StockHistory' }, meta: { hidden: true } },
      { path: 'import-history', redirect: { name: 'ImportHistory' }, meta: { hidden: true } },
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
