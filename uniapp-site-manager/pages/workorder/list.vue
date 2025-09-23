<template>
  <view class="list-container">
    <view class="custom-navbar">
      <view class="navbar-content">
        <text class="navbar-title">我的工单</text>
      </view>
    </view>

    <view class="filter-tabs">
      <view class="tab" :class="{active: status===''}" @click="setStatus('')">全部</view>
      <view class="tab" :class="{active: status==='PENDING'}" @click="setStatus('PENDING')">待处理</view>
      <view class="tab" :class="{active: status==='ACTIVE'}" @click="setStatus('ACTIVE')">执行中</view>
      <view class="tab" :class="{active: status==='SUBMITTED'}" @click="setStatus('SUBMITTED')">已提交</view>
      <view class="tab" :class="{active: status==='COMPLETED'}" @click="setStatus('COMPLETED')">已完成</view>
    </view>

    <scroll-view class="orders-scroll" scroll-y :refreshing="refreshing" @refresh="reload">
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
            <button class="accept-btn" size="mini" @click.stop="handleAccept(wo)">接受工单</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'ACTIVE'">
            <button class="continue-btn" size="mini" @click.stop="handleContinue(wo)">继续执行</button>
          </view>
          <view class="order-actions" v-else-if="wo.status === 'REJECTED'">
            <button class="rejected-btn" size="mini" @click.stop="handleContinue(wo)">修改重提</button>
          </view>
        </view>
      </view>
    </scroll-view>
  </view>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useWorkOrderStore } from '@/stores/workorder'

const store = useWorkOrderStore()
const orders = ref([])
const status = ref('')
const refreshing = ref(false)

const reload = async () => {
  refreshing.value = true
  const res = await store.getMyWorkOrders(status.value || undefined)
  if (res.success) orders.value = res.data
  refreshing.value = false
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
    uni.showToast({ title: '该工单暂无关联检查', icon: 'none' })
  }
}

const statusText = (s) => ({
  PENDING: '待处理', ACTIVE: '执行中', SUBMITTED: '已提交', 
  UNDER_REVIEW: '审核中', APPROVED: '已通过', REJECTED: '已驳回', COMPLETED: '已完成'
})[s] || s

const formatDateTime = (val) => val ? new Date(val).toLocaleString('zh-CN') : '-'

const handleAccept = async (wo) => {
  uni.showLoading({ title: '接受中...' })
  try {
    const res = await store.acceptWorkOrder(wo.id)
    if (res.success) {
      uni.showToast({ title: '接受成功', icon: 'success' })
      await reload()
      // 跳转到检查页面
      const inspectionId = res.data.inspection_id
      uni.navigateTo({ url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${wo.id}` })
    } else {
      uni.showToast({ title: res.error || '接受失败', icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: '接受失败', icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

const handleContinue = async (wo) => {
  uni.showLoading({ title: '获取检查...' })
  try {
    const res = await store.getInspection(wo.id)
    if (res.success) {
      const inspectionId = res.data.inspection_id
      if (inspectionId) {
        uni.navigateTo({ 
          url: `/pages/inspection/detail?id=${inspectionId}&fromWorkOrder=${wo.id}`,
          fail: (err) => {
            uni.showToast({ title: '页面跳转失败', icon: 'error' })
          }
        })
      } else {
        uni.showToast({ title: '检查ID不存在', icon: 'error' })
      }
    } else {
      uni.showToast({ title: res.error || '获取失败', icon: 'error' })
    }
  } catch (e) {
    uni.showToast({ title: '获取失败', icon: 'error' })
  } finally {
    uni.hideLoading()
  }
}

onMounted(reload)
</script>

<style lang="scss" scoped>
	.list-container {
		min-height: 100vh;
		background-color: #f5f5f5;
	}
	
	// 自定义导航栏 - 统一风格
	.custom-navbar {
		background: linear-gradient(135deg, #f97316, #fb923c);
		padding: 44rpx 32rpx 24rpx;
		color: white;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: 600;
	}
	
	// 筛选标签 - 统一卡片风格
	.filter-tabs {
		display: flex;
		gap: 16rpx;
		padding: 20rpx 32rpx;
		background: white;
		box-shadow: 0 2rpx 12rpx rgba(0, 0, 0, 0.06);
	}
	
	.tab {
		padding: 12rpx 24rpx;
		border-radius: 20rpx;
		background: #f8f9fa;
		color: #6b7280;
		font-size: 28rpx;
		transition: all 0.3s ease;
		
		&.active {
			background: linear-gradient(135deg, #f97316, #fb923c);
			color: white;
			box-shadow: 0 2rpx 8rpx rgba(249, 115, 22, 0.3);
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
		background: white;
		margin: 16rpx 0;
		padding: 24rpx;
		border-radius: 24rpx;
		box-shadow: 0 4rpx 16rpx rgba(0, 0, 0, 0.08);
		transition: transform 0.2s ease;
		
		&:active {
			transform: translateY(2rpx);
		}
	}
	
	.order-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 16rpx;
	}
	
	.order-title {
		font-weight: 600;
		color: #111827;
		font-size: 32rpx;
		flex: 1;
		margin-right: 16rpx;
	}
	
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
		color: #6b7280;
		font-size: 26rpx;
		margin-bottom: 16rpx;
		
		.site {
			flex: 1;
			margin-right: 16rpx;
		}
		
		.time {
			white-space: nowrap;
		}
	}
	
	// 操作按钮
	.order-actions {
		margin-top: 16rpx;
		display: flex;
		justify-content: flex-end;
	}
	
	.accept-btn, .continue-btn, .rejected-btn {
		font-size: 24rpx;
		padding: 8rpx 16rpx;
		border-radius: 16rpx;
		border: none;
		color: white;
		font-weight: 500;
	}
	
	.accept-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
	}
	
	.continue-btn {
		background: linear-gradient(135deg, #1d4ed8, #3b82f6);
	}
	
	.rejected-btn {
		background: linear-gradient(135deg, #dc2626, #ef4444);
	}
</style>
