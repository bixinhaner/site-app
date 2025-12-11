<template>
  <view class="list-container" :key="languageStore.currentLocale">
    <view class="custom-navbar">
      <view class="navbar-content">
        <text class="navbar-title">{{ $t('workorder.title') }}</text>
        <view class="navbar-actions">
          <view class="action-btn" @click="toggleSearch">
            <text class="action-icon">{{ showSearch ? '✕' : '🔍' }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 可折叠搜索框 -->
    <view class="search-container" :class="{ 'search-container-open': showSearch }">
      <view class="search-box">
        <text class="search-icon">🔍</text>
        <input
          class="search-input"
          v-model="searchKeyword"
          :placeholder="$t('workorder.searchPlaceholder')"
          @input="onSearchInput"
          @confirm="handleSearch"
          @blur="handleSearchBlur"
          confirm-type="search"
          :focus="showSearch"
        />
        <text v-if="searchKeyword" class="clear-icon" @click="clearSearch">✕</text>
      </view>
    </view>

    <view class="filter-tabs">
      <view class="tab" :class="{active: status===''}" @click="setStatus('')">{{ $t('common.all') }}</view>
      <view class="tab" :class="{active: status==='PENDING'}" @click="setStatus('PENDING')">{{ $t('workorder.pending') }}</view>
      <view class="tab" :class="{active: status==='ACTIVE'}" @click="setStatus('ACTIVE')">{{ $t('workorder.inProgress') }}</view>
      <view class="tab" :class="{active: status==='SUBMITTED'}" @click="setStatus('SUBMITTED')">{{ $t('workorder.submitted') }}</view>
      <view class="tab" :class="{active: status==='COMPLETED'}" @click="setStatus('COMPLETED')">{{ $t('workorder.completed') }}</view>
    </view>

    <scroll-view 
      class="orders-scroll" 
      scroll-y 
      refresher-enabled 
      :refresher-triggered="refreshing" 
      @refresherrefresh="handleRefresh"
      :scroll-into-view="scrollIntoView"
      refresher-background="#f7f8fb"
    >
      <view class="order-list">
        <!-- 空状态提示 - 只在有搜索或筛选条件时显示 -->
        <view v-if="orders.length === 0 && (searchKeyword || status)" class="empty-state">
          <text class="empty-icon">📭</text>
          <text class="empty-text">{{ $t('messages.noData') }}</text>
        </view>
        <view
          class="order-item"
          v-for="wo in orders"
          :key="wo.id"
          :id="`wo-${wo.id}`"
          :class="{ 'order-item-focused': highlightedWorkOrderId === wo.id }"
          @click="openDetail(wo)"
        >
          <view class="order-header">
            <text class="order-title">{{ wo.title }}</text>
            <text class="order-status" :class="'status-' + wo.status">{{ statusText(wo.status) }}</text>
          </view>
          <view class="order-meta">
            <text class="site">📍 {{ wo.site_name || wo.site_id }}</text>
            <text class="time">⏱ {{ formatDateTime(wo.assigned_at) }}</text>
          </view>
          <view class="order-actions" v-if="wo.status === 'PENDING'">
            <button class="accept-btn" size="mini" @click.stop="handleAccept(wo)">{{ $t('workorder.accept') }}</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'ACTIVE'">
            <button class="continue-btn" size="mini" @click.stop="handleContinue(wo)">{{ $t('common.continue') }}</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'SUBMITTED'">
            <button class="recall-btn" size="mini" @click.stop="handleRecall(wo)">{{ $t('workorder.recall') }}</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'UNDER_REVIEW'">
            <button class="recall-btn" size="mini" @click.stop="handleRecall(wo)">{{ $t('workorder.recall') }}</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'REJECTED'">
            <button class="rejected-btn" size="mini" @click.stop="handleContinue(wo)">{{ $t('common.resubmit') }}</button>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted, watch, getCurrentInstance } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { useWorkOrderStore } from '@/stores/workorder'
import { useLanguageStore } from '@/stores/language'
import { useUserStore } from '@/stores/user'

const store = useWorkOrderStore()
const languageStore = useLanguageStore()
const userStore = useUserStore()
const orders = ref([])
const scrollIntoView = ref('')
const highlightedWorkOrderId = ref(null)
const status = ref('')
const searchKeyword = ref('')
const showSearch = ref(false)
const refreshing = ref(false)
const isPageVisible = ref(false)
let searchTimer = null

const { $t } = getCurrentInstance().appContext.config.globalProperties

const reload = async () => {
  try {
    refreshing.value = true
    console.log('🔄 工单列表刷新中...', { status: status.value, keyword: searchKeyword.value })
    const res = await store.getMyWorkOrders(status.value || undefined, searchKeyword.value || undefined)
    if (res.success) {
      orders.value = res.data
      console.log('✅ 工单列表刷新成功', { count: res.data?.length })

      // 如果有需要聚焦的工单，则滚动到对应卡片位置并短暂高亮
      if (store.focusedWorkOrderId) {
        const targetId = store.focusedWorkOrderId
        const exists = (res.data || []).some(wo => wo.id === targetId)
        if (exists) {
          scrollIntoView.value = `wo-${targetId}`
          highlightedWorkOrderId.value = targetId
          // 2 秒后取消高亮，并清理聚焦标记
          setTimeout(() => {
            if (highlightedWorkOrderId.value === targetId) {
              highlightedWorkOrderId.value = null
            }
            store.clearFocusedWorkOrder()
          }, 2000)
        } else {
          scrollIntoView.value = ''
          highlightedWorkOrderId.value = null
          store.clearFocusedWorkOrder()
        }
      } else {
        scrollIntoView.value = ''
        highlightedWorkOrderId.value = null
      }
    } else {
      console.error('❌ 工单列表刷新失败', res.error)
      uni.showToast({ title: $t('messages.dataLoadFailed'), icon: 'none' })
    }
  } catch (error) {
    console.error('❌ 工单列表刷新异常', error)
    uni.showToast({ title: $t('messages.networkError'), icon: 'none' })
  } finally {
    refreshing.value = false
  }
}

// 下拉刷新处理
const handleRefresh = async () => {
  await reload()
}

const setStatus = async (s) => {
  status.value = s
  await reload()
}

// 实时搜索（防抖处理）
const onSearchInput = () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
  }
  searchTimer = setTimeout(() => {
    handleSearch()
  }, 500) // 500ms防抖
}

// 执行搜索
const handleSearch = async () => {
  if (searchTimer) {
    clearTimeout(searchTimer)
    searchTimer = null
  }
  await reload()
}

// 清除搜索
const clearSearch = () => {
  searchKeyword.value = ''
  reload()
  // 如果搜索框已清空，延迟收起以显示动画
  setTimeout(() => {
    showSearch.value = false
  }, 300)
}

// 切换搜索显示状态
const toggleSearch = () => {
  showSearch.value = !showSearch.value
}

// 搜索框失去焦点时的处理
const handleSearchBlur = () => {
  // 如果没有搜索内容，延迟收起搜索框
  if (!searchKeyword.value.trim()) {
    setTimeout(() => {
      showSearch.value = false
    }, 200)
  }
}

const openDetail = (wo) => {
  if (wo.inspection_id) {
    uni.navigateTo({ 
      url: `/pages/inspection/detail?id=${wo.inspection_id}&fromWorkOrder=${wo.id}` 
    })
  } else {
    uni.showToast({ title: $t('messages.noInspectionLinked'), icon: 'none' })
  }
}

const statusText = (s) => {
  const { $t } = getCurrentInstance().appContext.config.globalProperties
  return ({
    PENDING: $t('workorder.pending'),
    ACTIVE: $t('workorder.inProgress'),
    SUBMITTED: $t('workorder.submitted'),
    UNDER_REVIEW: $t('workorder.underReview'),
    APPROVED: $t('workorder.approved'),
    REJECTED: $t('workorder.rejected'),
    COMPLETED: $t('workorder.completed')
  })[s] || s
}

const formatDateTime = (val) => {
  if (!val) return '-'
  const locale = getCurrentInstance().appContext.config.globalProperties.$language?.currentLocale || 'zh'
  return new Date(val).toLocaleString(locale === 'zh' ? 'zh-CN' : 'en-US')
}

const handleAccept = async (wo) => {
  uni.showLoading({ title: $t('messages.accepting') })
  try {
    const res = await store.acceptWorkOrder(wo.id)
    if (res.success) {
      uni.showToast({ title: $t('messages.acceptSuccess'), icon: 'success' })
      await reload()
      // 跳转到检查页面
      const inspectionId = res.data.inspection_id
      uni.navigateTo({ url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${wo.id}` })
    } else {
      uni.showToast({ title: res.error || $t('messages.acceptFailed'), icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: $t('messages.acceptFailed'), icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

const handleContinue = async (wo) => {
  uni.showLoading({ title: $t('messages.loadingInspection') })
  try {
    const res = await store.getInspection(wo.id)
    if (res.success) {
      const inspectionId = res.data.inspection_id
      if (inspectionId) {
        uni.navigateTo({ 
          url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${wo.id}`,
          fail: (err) => {
            uni.showToast({ title: $t('messages.navigationFailed'), icon: 'error' })
          }
        })
      } else {
        uni.showToast({ title: $t('messages.inspectionIdNotFound'), icon: 'error' })
      }
    } else {
      uni.showToast({ title: res.error || $t('messages.loadFailed'), icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: $t('messages.loadFailed'), icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

const handleRecall = async (wo) => {
  // 权限兜底：仅指派人可撤回
  if (wo.assigned_to && userStore.userInfo?.id && wo.assigned_to !== userStore.userInfo.id) {
    uni.showToast({ title: $t('messages.noPermission'), icon: 'none' })
    return
  }
  const confirmed = await new Promise((resolve) => {
    uni.showModal({ title: $t('messages.recallConfirmTitle'), content: $t('messages.recallConfirmContent'), success: (res)=> resolve(!!res.confirm), fail: ()=> resolve(false) })
  })
  if (!confirmed) return
  uni.showLoading({ title: $t('messages.recalling') })
  try {
    const res = await store.recallWorkOrder(wo.id)
    if (res.success) {
      uni.showToast({ title: $t('messages.recallSuccess'), icon: 'success' })
      const inspectionId = res.data?.work_order?.inspection_id || wo.inspection_id
      if (inspectionId) {
        uni.navigateTo({ url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${wo.id}` })
      }
      await reload()
    } else {
      uni.showToast({ title: res.error || $t('messages.recallFailed'), icon: 'none' })
    }
  } catch (e) {
    uni.showToast({ title: $t('messages.recallFailed'), icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

// 监听语言变化，更新页面标题
watch(() => languageStore.currentLocale, () => {
  uni.setNavigationBarTitle({
    title: $t('workorder.title')
  })
})

// 页面初次加载
onMounted(() => {
  console.log('📱 工单列表页面 onMounted')
  // 动态设置页面标题
  uni.setNavigationBarTitle({
    title: $t('workorder.title')
  })
  isPageVisible.value = true
  reload()
})

// 每次页面显示时刷新数据
onShow(() => {
  console.log('👁️ 工单列表页面 onShow', { isPageVisible: isPageVisible.value })
  // 避免重复刷新（onMounted后立即触发onShow）
  if (isPageVisible.value) {
    console.log('🔄 页面重新显示，自动刷新数据')
    reload()
  }
  isPageVisible.value = true
})
</script>

<style lang="scss" scoped>
	.list-container {
		min-height: 100vh;
		background-color: var(--bg-page);
	}
	
	// 自定义导航栏 - 统一风格
	.custom-navbar {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding: 44rpx 30rpx 20rpx;
		color: #fff;
	}

	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 88rpx;
	}

	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
	}

	.navbar-actions {
		display: flex;
		gap: 20rpx;
	}

	.action-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		width: 68rpx;
		height: 68rpx;
		border-radius: 50%;
		background: rgba(255, 255, 255, 0.2);
		transition: all 0.3s ease;
	}

	.action-btn:active {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(0.95);
	}

	.action-icon {
		font-size: 40rpx;
	}

	// 搜索框样式 - 可折叠
	.search-container {
		height: 0;
		overflow: hidden;
		opacity: 0;
		transform: translateY(-20rpx);
		transition: all 0.3s ease;
	}

	.search-container-open {
		height: auto;
		opacity: 1;
		transform: translateY(0);
		padding: 16rpx 32rpx;
		background: var(--bg-elevated);
		box-shadow: var(--shadow-card);
		border-bottom: 1rpx solid #f0f0f0;
	}

	.search-box {
		display: flex;
		align-items: center;
		background: #f8f9fa;
		border-radius: 50rpx;
		padding: 0 24rpx;
		height: 80rpx;
	}

	.search-icon {
		font-size: 32rpx;
		margin-right: 16rpx;
		color: #6b7280;
	}

	.search-input {
		flex: 1;
		height: 80rpx;
		font-size: 28rpx;
		color: var(--text-primary);
	}

	.clear-icon {
		font-size: 32rpx;
		color: #6b7280;
		padding: 8rpx;
	}

	// 筛选标签 - 紧凑布局
	.filter-tabs {
		display: flex;
		gap: 12rpx;
		padding: 16rpx 24rpx;
		background: var(--bg-elevated);
		box-shadow: var(--shadow-card);
	}
	
	.tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 68rpx;
		padding: 0 20rpx;
		border-radius: 20rpx;
		background: #f8f9fa;
		color: #6b7280;
		font-size: 26rpx;
		transition: all 0.3s ease;
		
		&.active {
			background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
			color: #fff;
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.28);
		}
	}
	
	// 滚动容器
	.orders-scroll {
		height: calc(100vh - 180rpx);
	}
	
	.order-list {
		padding: 0 20rpx;
	}

	// 空状态提示
	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		padding: 120rpx 40rpx;
		color: var(--text-secondary);
	}

	.empty-icon {
		font-size: 120rpx;
		margin-bottom: 32rpx;
		opacity: 0.5;
	}

	.empty-text {
		font-size: 28rpx;
		color: var(--text-secondary);
	}

// 工单卡片 - 统一卡片样式
	.order-item {
		background: var(--bg-elevated);
		margin: 16rpx 0;
		padding: 24rpx;
		border-radius: 24rpx;
		box-shadow: var(--shadow-card);
		transition: transform 0.2s ease, background-color 0.3s ease, box-shadow 0.3s ease;
		
		&:active { transform: translateY(2rpx); }
	}

	// 高亮聚焦的工单卡片（从首页最近活动跳转时短暂高亮）
	.order-item-focused {
		background-color: #fff7ed; /* tailwind amber-50 */
		box-shadow: 0 0 0 3rpx #fed7aa;
	}
	
	.order-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16rpx;
	}
	
	.order-title { font-weight: 600; color: var(--text-primary); font-size: 32rpx; flex: 1; margin-right: 16rpx; }
	
	// 状态标签 - 统一状态颜色
	.order-status {
		font-size: 24rpx;
		padding: 8rpx 16rpx;
		border-radius: 16rpx;
		font-weight: 500;
		
		&.status-PENDING {
			background: #f3f4f6;
			color: #6b7280;
		}
		
		&.status-ACTIVE {
			background: #dbeafe;
			color: #1d4ed8;
		}
		
		&.status-SUBMITTED {
			background: #fef3c7;
			color: #b45309;
		}
		
		&.status-UNDER_REVIEW {
			background: #e0e7ff;
			color: #6366f1;
		}
		
		&.status-APPROVED {
			background: #d1fae5;
			color: #059669;
		}
		
		&.status-REJECTED {
			background: #fee2e2;
			color: #dc2626;
		}
		
		&.status-COMPLETED {
			background: #d1fae5;
			color: #059669;
		}
	}
	
	.order-meta {
		display: flex;
		justify-content: space-between;
		color: var(--text-secondary);
		font-size: 26rpx;
		margin-bottom: 16rpx;
		
		.site { flex: 1; margin-right: 16rpx; }
		.time { white-space: nowrap; }
	}
	
	// 操作按钮
	.order-actions {
		margin-top: 16rpx;
		display: flex;
		justify-content: flex-end;
	}
	
.accept-btn, .continue-btn, .recalled-btn, .rejected-btn, .recall-btn {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx; /* >=44px */
		padding: 0 24rpx;
		border-radius: 20rpx;
		border: none;
		color: #fff;
		font-size: 26rpx;
		font-weight: 600;
}

.accept-btn { background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light)); }

.continue-btn {
	background: linear-gradient(135deg, #1d4ed8, #3b82f6);
}

.recall-btn { background: linear-gradient(135deg, #1d4ed8, #3b82f6); }

.rejected-btn {
	background: linear-gradient(135deg, #dc2626, #ef4444);
}
</style>
