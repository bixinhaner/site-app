<template>
  <div class="main-layout" :style="{ '--sidebar-transform': sidebarCollapsed ? '-100%' : '0' }">
    <!-- 顶部导航栏 -->
    <el-header class="layout-header">
      <div class="header-content">
        <div class="header-left">
          <el-icon @click="toggleSidebar" class="menu-toggle">
            <Menu />
          </el-icon>
          <h1 class="system-title">{{ t('app.systemName') }}</h1>
        </div>
        
        <div class="header-right">
          <LocaleSwitcher />
          <el-dropdown trigger="click">
            <div class="user-info">
              <el-avatar :size="32" :src="userStore.user?.avatar">
                {{ displayUserName.slice(0, 1) || t('common.userFallback').slice(0, 1) }}
              </el-avatar>
              <span class="username">{{ displayUserName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  {{ t('common.logout') }}
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </div>
    </el-header>

    <el-container class="layout-body">
      <!-- 侧边栏导航 -->
      <el-aside :width="sidebarCollapsed ? '64px' : '240px'" class="layout-sidebar">
        <el-menu
          :default-active="$route.name"
          class="sidebar-menu"
          :collapse="sidebarCollapsed"
          :router="true"
        >
          <template v-for="route in menuRoutes" :key="route.name">
            <!-- 二级菜单：有children且非隐藏 -->
            <el-sub-menu v-if="route.children && visibleChildren(route).length" :index="route.name">
              <template #title>
                <el-icon><component :is="route.meta.icon" /></el-icon>
                <span class="menu-label" :title="getRouteTitle(route)">{{ getRouteTitle(route) }}</span>
              </template>
              <!-- 库存管理菜单：按 group 分组展示（默认全部展开）；侧边栏折叠时回退为普通列表 -->
              <template v-if="isInventoryRoute(route) && !sidebarCollapsed">
                <el-menu-item-group v-for="g in inventoryChildGroups(route)" :key="g.key">
                  <template #title>
                    <div class="menu-group-title" :data-group="g.key">
                      <span class="menu-group-dot" :data-group="g.key" />
                      <span class="menu-group-text">{{ g.title }}</span>
                    </div>
                  </template>

                  <el-menu-item
                    v-for="child in g.items"
                    :key="child.name"
                    :index="child.name"
                    :route="{ name: child.name }"
                  >
                    <el-icon><component :is="child.meta?.icon || route.meta.icon" /></el-icon>
                    <span class="menu-label" :title="getRouteTitle(child)">{{ getRouteTitle(child) }}</span>
                  </el-menu-item>
                </el-menu-item-group>
              </template>

              <template v-else>
                <el-menu-item
                  v-for="child in (isInventoryRoute(route) ? inventoryMenuChildren(route) : visibleChildren(route))"
                  :key="child.name"
                  :index="child.name"
                  :route="{ name: child.name }"
                >
                  <el-icon><component :is="child.meta?.icon || route.meta.icon" /></el-icon>
                  <span class="menu-label" :title="getRouteTitle(child)">{{ getRouteTitle(child) }}</span>
                </el-menu-item>
              </template>
            </el-sub-menu>
            
            <!-- 一级菜单：无children或children都隐藏 -->
            <el-menu-item v-else :index="route.name" :route="{ name: route.name }">
              <el-icon><component :is="route.meta.icon" /></el-icon>
              <span class="menu-label" :title="getRouteTitle(route)">{{ getRouteTitle(route) }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="layout-main">
        <!-- 面包屑导航 -->
        <div class="breadcrumb-container">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="homeRoute">{{ t('common.home') }}</el-breadcrumb-item>
            <el-breadcrumb-item v-if="getRouteTitle(currentRoute)">
              {{ getRouteTitle(currentRoute) }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <!-- 页面内容 -->
        <router-view v-slot="{ Component, route }">
          <transition name="fade">
            <component v-if="Component" :is="Component" :key="route.fullPath" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'
import { containsCJK, resolveRouteTitle } from '../i18n/translator'
import LocaleSwitcher from '../components/common/LocaleSwitcher.vue'
import { resolveDefaultAuthenticatedRoute, routeHasAccess } from '../router/access'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const { t, locale } = useI18n()

const isNarrowViewport = () =>
  typeof window !== 'undefined' && window.matchMedia('(max-width: 768px)').matches

const sidebarCollapsed = ref(isNarrowViewport())
const wasNarrowViewport = ref(isNarrowViewport())

const syncSidebarByViewport = () => {
  const nowNarrow = isNarrowViewport()
  if (nowNarrow !== wasNarrowViewport.value) {
    sidebarCollapsed.value = nowNarrow
    wasNarrowViewport.value = nowNarrow
  }
}
const displayUserName = computed(() => {
  const fullName = userStore.user?.full_name
  const username = userStore.user?.username
  if (locale.value !== 'zh-CN' && fullName && containsCJK(fullName) && username) {
    return username
  }
  return fullName || username || t('common.userFallback')
})

const hasRouteAccess = (r) => routeHasAccess(r, userStore)

const getRouteTitle = (routeLike) => {
  return resolveRouteTitle(routeLike, String(routeLike?.name || ''))
}

// 菜单路由配置
const menuRoutes = computed(() => {
  return router.options.routes
    .find(route => route.path === '/')
    ?.children
    // 仅展示带有标题的菜单项
    .filter(r => r.meta && (r.meta.titleKey || r.meta.title) && !r.meta.hidden && hasRouteAccess(r)) || []
})

const currentRoute = computed(() => route)
const homeRoute = computed(() => {
  return resolveDefaultAuthenticatedRoute(router.options.routes, userStore) || { name: 'Dashboard' }
})

// 过滤可见子菜单
const visibleChildren = (route) => {
  if (!route.children) return []
  return route.children.filter(c => !c.meta?.hidden && (c.meta?.titleKey || c.meta?.title) && hasRouteAccess(c))
}

const isInventoryRoute = (r) => r?.name === 'InventoryMgmt'

const INVENTORY_GROUP_META = [
  { key: 'flow', titleKey: 'inventory.groups.flow', order: 1 },
  { key: 'asset', titleKey: 'inventory.groups.asset', order: 2 },
  { key: 'ledger', titleKey: 'inventory.groups.ledger', order: 3 },
  { key: 'other', titleKey: 'inventory.groups.other', order: 99 },
]

const inventoryChildGroups = (route) => {
  const children = visibleChildren(route)
  const groupOrderMap = new Map(INVENTORY_GROUP_META.map((g) => [g.key, g.order]))
  const groupTitleMap = new Map(INVENTORY_GROUP_META.map((g) => [g.key, t(g.titleKey)]))

  const groups = new Map()
  for (const child of children) {
    const key = child?.meta?.group || 'other'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(child)
  }

  const sortedGroups = Array.from(groups.entries())
    .map(([key, items]) => {
      const sortedItems = [...items].sort((a, b) => {
        const ao = Number(a?.meta?.order ?? 9999)
        const bo = Number(b?.meta?.order ?? 9999)
        if (ao !== bo) return ao - bo
        const aTitle = getRouteTitle(a)
        const bTitle = getRouteTitle(b)
        return String(aTitle || a?.name || '').localeCompare(String(bTitle || b?.name || ''), locale.value)
      })
      return {
        key,
        title: groupTitleMap.get(key) || String(key),
        order: groupOrderMap.get(key) ?? 99,
        items: sortedItems,
      }
    })
    .sort((a, b) => a.order - b.order)

  return sortedGroups
}

const inventoryMenuChildren = (route) => {
  if (!isInventoryRoute(route)) return visibleChildren(route)
  return inventoryChildGroups(route).flatMap((g) => g.items)
}

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 退出登录
const handleLogout = async () => {
  try {
    userStore.logout()
    ElMessage.success(t('common.logoutSuccess'))
    router.push('/login')
  } catch (error) {
    console.error('退出登录失败:', error)
    ElMessage.error(t('common.logoutFailed'))
  }
}

// 初始化用户信息
onMounted(async () => {
  if (typeof window !== 'undefined') {
    window.addEventListener('resize', syncSidebarByViewport, { passive: true })
  }

  if (!userStore.user && userStore.token) {
    try {
      await userStore.initialize()
    } catch (error) {
      console.error('初始化用户信息失败:', error)
      router.push('/login')
    }
  }
})

onBeforeUnmount(() => {
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', syncSidebarByViewport)
  }
})
</script>

<style scoped lang="scss">
.main-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.layout-header {
  background: white;
  border-bottom: 1px solid var(--border-color);
  padding: 0 24px;
  box-shadow: var(--box-shadow);
  z-index: 1001;

  .header-content {
    display: flex;
    justify-content: space-between;
    align-items: center;
    height: 100%;
  }

  .header-left {
    display: flex;
    align-items: center;
    gap: 16px;
    
    .menu-toggle {
      font-size: 18px;
      color: var(--text-secondary);
      cursor: pointer;
      padding: 8px;
      border-radius: 4px;
      transition: all 0.3s ease;
      
      &:hover {
        background-color: var(--primary-light);
        color: white;
      }
    }
    
    .system-title {
      color: var(--primary-color);
      font-size: 20px;
      font-weight: 600;
      margin: 0;
      max-width: min(48vw, 620px);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
  }

  .header-right {
    display: flex;
    align-items: center;
    gap: 12px;

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: background-color 0.3s ease;
      
      &:hover {
        background-color: #f8fafc;
      }
      
      .username {
        color: var(--text-primary);
        font-weight: 500;
      }
    }
  }
}

.layout-body {
  flex: 1;
  overflow: hidden;
}

.layout-sidebar {
  background: white;
  border-right: 1px solid var(--border-color);
  transition: width 0.3s ease;
  
  .sidebar-menu {
    height: 100%;
    border: none;
    padding: 12px 0;
    
    .el-menu-item {
      margin: 4px 12px;
      border-radius: 6px;
      height: 48px;
      line-height: 48px;
      
      &:hover {
        background-color: var(--primary-light) !important;
        color: white !important;
      }
      
      &.is-active {
        background-color: var(--primary-color) !important;
        color: white !important;
      }
      
      .el-icon {
        margin-right: 8px;
        font-size: 16px;
      }

      .menu-label {
        display: inline-block;
        max-width: 158px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        vertical-align: middle;
      }
    }

    :deep(.el-menu-item-group__title) {
      padding: 14px 20px 8px;
      height: auto;
      line-height: 1;
      color: var(--text-secondary);
      font-size: 12px;
      letter-spacing: 0.2px;
      opacity: 0.95;
    }

    .menu-group-title {
      display: inline-flex;
      align-items: center;
      gap: 10px;
    }

    .menu-group-dot {
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: rgba(100, 116, 139, 0.9);
      box-shadow: 0 0 0 4px rgba(100, 116, 139, 0.12);
    }

    .menu-group-dot[data-group='flow'] {
      background: rgba(249, 115, 22, 0.95);
      box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.16);
    }

    .menu-group-dot[data-group='asset'] {
      background: rgba(37, 99, 235, 0.95);
      box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.14);
    }

    .menu-group-dot[data-group='ledger'] {
      background: rgba(16, 185, 129, 0.95);
      box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.14);
    }

    .menu-group-text {
      font-weight: 650;
    }
  }
}

html[lang='en-US'],
html[lang='id-ID'] {
  .layout-sidebar {
    .sidebar-menu {
      .el-menu-item {
        min-height: 48px;
        height: auto;
        line-height: 1.25;
        padding-top: 8px;
        padding-bottom: 8px;
      }

      :deep(.el-sub-menu__title) {
        min-height: 48px;
        height: auto;
        line-height: 1.25;
        padding-top: 8px;
        padding-bottom: 8px;
      }

      .menu-label {
        max-width: 176px;
        white-space: normal;
        overflow: visible;
        text-overflow: clip;
        line-height: 1.25;
        display: -webkit-box;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }
    }
  }
}

.layout-main {
  background: var(--bg-color);
  overflow-y: auto;
  padding: 0;

  .breadcrumb-container {
    background: white;
    padding: 16px 24px;
    border-bottom: 1px solid var(--border-color);
    margin-bottom: 0;
    
    .el-breadcrumb {
      font-size: 14px;
      
      .el-breadcrumb__inner {
        color: var(--text-secondary);
        
        &.is-link {
          color: var(--primary-color);
          
          &:hover {
            color: var(--primary-dark);
          }
        }
      }
    }
  }
}

// 页面切换动画
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from, .fade-leave-to {
  opacity: 0;
}

// 响应式设计
@media (max-width: 768px) {
  .layout-header {
    padding: 0 16px;
    
    .header-left {
      .system-title {
        display: none;
      }
    }
  }
  
  .layout-sidebar {
    position: fixed;
    top: var(--header-height);
    left: 0;
    height: calc(100vh - var(--header-height));
    z-index: 1000;
    transform: translateX(var(--sidebar-transform));
    transition: transform 0.3s ease;
  }

  .layout-header {
    .header-right {
      gap: 8px;

      .username {
        display: none;
      }
    }
  }
  
  .breadcrumb-container {
    padding: 12px 16px;
  }
}
</style>
