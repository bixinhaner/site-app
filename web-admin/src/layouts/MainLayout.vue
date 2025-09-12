<template>
  <div class="main-layout" :style="{ '--sidebar-transform': sidebarCollapsed ? '-100%' : '0' }">
    <!-- 顶部导航栏 -->
    <el-header class="layout-header">
      <div class="header-content">
        <div class="header-left">
          <el-icon @click="toggleSidebar" class="menu-toggle">
            <Menu />
          </el-icon>
          <h1 class="system-title">设备货物管理系统</h1>
        </div>
        
        <div class="header-right">
          <el-dropdown trigger="click">
            <div class="user-info">
              <el-avatar :size="32" :src="userStore.user?.avatar">
                {{ userStore.user?.full_name?.slice(0, 1) || 'U' }}
              </el-avatar>
              <span class="username">{{ userStore.user?.full_name || userStore.user?.username }}</span>
              <el-icon><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon>
                  退出登录
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
                <span>{{ route.meta.title }}</span>
              </template>
              <el-menu-item
                v-for="child in visibleChildren(route)"
                :key="child.name"
                :index="child.name"
                :route="{ name: child.name }"
              >
                <el-icon><component :is="child.meta?.icon || route.meta.icon" /></el-icon>
                <span>{{ child.meta?.title || child.name }}</span>
              </el-menu-item>
            </el-sub-menu>
            
            <!-- 一级菜单：无children或children都隐藏 -->
            <el-menu-item v-else :index="route.name" :route="{ name: route.name }">
              <el-icon><component :is="route.meta.icon" /></el-icon>
              <span>{{ route.meta.title }}</span>
            </el-menu-item>
          </template>
        </el-menu>
      </el-aside>

      <!-- 主内容区 -->
      <el-main class="layout-main">
        <!-- 面包屑导航 -->
        <div class="breadcrumb-container">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item :to="{ name: 'Dashboard' }">首页</el-breadcrumb-item>
            <el-breadcrumb-item v-if="currentRoute?.meta?.title">
              {{ currentRoute.meta.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        
        <!-- 页面内容 -->
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '../stores/user'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const sidebarCollapsed = ref(false)

// 菜单路由配置
const menuRoutes = computed(() => {
  return router.options.routes
    .find(route => route.path === '/')
    ?.children
    // 仅展示带有标题的菜单项
    .filter(r => r.meta && r.meta.title && !r.meta.hidden) || []
})

const currentRoute = computed(() => route)

// 过滤可见子菜单
const visibleChildren = (route) => {
  if (!route.children) return []
  return route.children.filter(c => !c.meta?.hidden && c.meta?.title)
}

// 切换侧边栏折叠状态
const toggleSidebar = () => {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

// 退出登录
const handleLogout = async () => {
  try {
    userStore.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  } catch (error) {
    console.error('退出登录失败:', error)
    ElMessage.error('退出登录失败')
  }
}

// 初始化用户信息
onMounted(async () => {
  if (!userStore.user && userStore.token) {
    try {
      await userStore.initialize()
    } catch (error) {
      console.error('初始化用户信息失败:', error)
      router.push('/login')
    }
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
    }
  }

  .header-right {
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
  
  .breadcrumb-container {
    padding: 12px 16px;
  }
}
</style>
