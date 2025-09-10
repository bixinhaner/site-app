import { createRouter, createWebHistory } from 'vue-router'
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
        path: 'inventory',
        name: 'Inventory',
        component: () => import('../views/stock/InventoryList.vue'),
        meta: { title: '设备库存管理', icon: 'TakeawayBox' }
      },
      {
        path: 'stock-in',
        name: 'StockIn',
        component: () => import('../views/stock/StockIn.vue'),
        meta: { title: '入库管理', icon: 'Upload' }
      },
      {
        path: 'stock-history',
        name: 'StockHistory',
        component: () => import('../views/stock/StockHistory.vue'),
        meta: { title: '出入库记录', icon: 'Document' }
      },
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