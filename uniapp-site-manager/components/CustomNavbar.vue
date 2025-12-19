<template>
	<view
		class="custom-navbar"
		:class="{ 'custom-navbar--light': variant === 'light' }"
		:style="navbarStyle"
	>
		<view class="navbar-content">
			<!-- 左侧按钮区域 -->
			<view class="navbar-left">
				<view
					v-if="showBack"
					class="u-nav-btn"
					:class="variant === 'light' ? 'u-nav-btn--light' : 'u-nav-btn--brand'"
					@click="handleBack"
				>
					<uni-icons class="nav-icon" type="back" size="36rpx" :color="iconColor" />
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
import { ref, onMounted, computed, toRefs } from 'vue'

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
	variant: {
		type: String,
		default: 'brand' // brand | light
	},
	backgroundColor: {
		type: String,
		default: ''
	},
	autoBack: {
		type: Boolean,
		default: true
	},
})

const { variant } = toRefs(props)

// Emits
const emit = defineEmits(['back'])

// 状态栏高度
const statusBarHeight = ref(0)

// 获取系统状态栏高度
onMounted(() => {
	const systemInfo = uni.getSystemInfoSync()
	statusBarHeight.value = systemInfo.statusBarHeight || 0
})

const iconColor = computed(() => (props.variant === 'light' ? 'var(--color-primary)' : '#fff'))

const navbarStyle = computed(() => {
	const style = {
		paddingTop: `${statusBarHeight.value}px`,
	}
	if (props.backgroundColor) {
		style.background = props.backgroundColor
	}
	return style
})

// 返回操作
const handleBack = () => {
	emit('back')
	if (props.autoBack) {
		uni.navigateBack()
	}
}
</script>

<style scoped>
	.custom-navbar {
		padding-left: 30rpx;
		padding-right: 30rpx;
		padding-bottom: 20rpx;
		color: #fff;
		position: relative;
		z-index: 999;
		background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
	}

	.custom-navbar--light {
		background: var(--bg-elevated);
		color: var(--text-primary);
		box-shadow: 0 1px 0 var(--border-soft);
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
	
	.nav-icon {
		font-size: 36rpx;
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
		color: inherit;
		text-align: center;
		max-width: 100%;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}
</style>
