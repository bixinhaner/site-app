<template>
	<view class="custom-navbar" :style="{ paddingTop: statusBarHeight + 'px' }">
		<view class="navbar-content">
			<!-- 左侧按钮区域 -->
			<view class="navbar-left">
				<view 
					v-if="showBack" 
					class="nav-button back-button" 
					@click="handleBack"
				>
					<uni-icons class="nav-icon" type="back" size="36rpx" color="#fff" />
				</view>
			</view>
			
			<!-- 中间标题区域 -->
			<view class="navbar-center">
				<text class="navbar-title">{{ title }}</text>
			</view>
			
			<!-- 右侧操作区域 -->
			<view class="navbar-right">
				<slot name="right"></slot>
			</view>
		</view>
	</view>
</template>

<script setup>
import { ref, onMounted } from 'vue'

// Props
const props = defineProps({
	title: {
		type: String,
		default: ''
	},
	showBack: {
		type: Boolean,
		default: false
	},
	backgroundColor: {
		type: String,
		default: ''
	}
})

// Emits
const emit = defineEmits(['back'])

// 状态栏高度
const statusBarHeight = ref(0)

// 获取系统状态栏高度
onMounted(() => {
	const systemInfo = uni.getSystemInfoSync()
	statusBarHeight.value = systemInfo.statusBarHeight || 0
})

// 返回操作
const handleBack = () => {
	emit('back')
	if (!emit('back')) {
		uni.navigateBack()
	}
}
</script>

<style scoped>
	.custom-navbar {
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
		padding-left: 30rpx;
		padding-right: 30rpx;
		padding-bottom: 20rpx;
		color: #fff;
		position: relative;
		z-index: 999;
	}
	
	.navbar-content {
		display: flex;
		align-items: center;
		justify-content: space-between;
		height: 88rpx;
		position: relative;
	}
	
	.navbar-left,
	.navbar-right {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
	}
	
	.navbar-right {
		justify-content: flex-end;
	}
	
	.nav-button {
		width: 88rpx;
		height: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 44rpx;
		background: rgba(255, 255, 255, 0.2);
		transition: all 0.3s ease;
	}
	
	.nav-button:active {
		background: rgba(255, 255, 255, 0.3);
		transform: scale(0.95);
	}
	
	.nav-icon {
		font-size: 36rpx;
		color: white;
	}
	
	.navbar-center {
		position: absolute;
		left: 88rpx;
		right: 88rpx;
		display: flex;
		align-items: center;
		justify-content: center;
		pointer-events: none;
	}
	
	.navbar-title {
		font-size: 36rpx;
		font-weight: bold;
		color: white;
		text-align: center;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
