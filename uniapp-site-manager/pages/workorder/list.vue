<template>
  <view class="list-container" :key="languageStore.currentLocale">
    <view class="custom-navbar">
      <view class="navbar-content">
        <text class="navbar-title">{{ $t('workorder.title') }}</text>
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
      refresher-background="#f7f8fb"
    >
      <view class="order-list">
        <view class="order-item" v-for="wo in orders" :key="wo.id" @click="openDetail(wo)">
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

const store = useWorkOrderStore()
const languageStore = useLanguageStore()
const orders = ref([])
const status = ref('')
const refreshing = ref(false)
const isPageVisible = ref(false)

const { $t } = getCurrentInstance().appContext.config.globalProperties

const reload = async () => {
  try {
    refreshing.value = true
    console.log('🔄 工单列表刷新中...', { status: status.value })
    const res = await store.getMyWorkOrders(status.value || undefined)
    if (res.success) {
      orders.value = res.data
      console.log('✅ 工单列表刷新成功', { count: res.data?.length })
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
	
	// 筛选标签 - 统一卡片风格
	.filter-tabs {
		display: flex;
		gap: 16rpx;
		padding: 20rpx 32rpx;
		background: var(--bg-elevated);
		box-shadow: var(--shadow-card);
	}
	
	.tab {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 88rpx; /* >=44px */
		padding: 0 28rpx;
		border-radius: 24rpx;
		background: #f8f9fa;
		color: #6b7280;
		font-size: 28rpx;
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
	
	// 工单卡片 - 统一卡片样式
	.order-item {
		background: var(--bg-elevated);
		margin: 16rpx 0;
		padding: 24rpx;
		border-radius: 24rpx;
		box-shadow: var(--shadow-card);
		transition: transform 0.2s ease;
		
		&:active { transform: translateY(2rpx); }
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
	
	.accept-btn, .continue-btn, .rejected-btn {
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
	
	.rejected-btn {
		background: linear-gradient(135deg, #dc2626, #ef4444);
	}
</style>
