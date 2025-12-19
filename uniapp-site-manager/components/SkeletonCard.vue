<template>
	<view class="skeleton-card" :class="['skeleton-' + mode]">
		<!-- 列表卡片骨架 -->
		<template v-if="mode === 'list'">
			<view class="skeleton-header">
				<view class="skeleton-line skeleton-title"></view>
				<view class="skeleton-badge"></view>
			</view>
			<view class="skeleton-body">
				<view class="skeleton-line skeleton-text"></view>
				<view class="skeleton-line skeleton-text short"></view>
			</view>
			<view class="skeleton-footer">
				<view class="skeleton-line skeleton-meta"></view>
				<view class="skeleton-btn"></view>
			</view>
		</template>
		
		<!-- 统计卡片骨架 -->
		<template v-else-if="mode === 'stat'">
			<view class="skeleton-icon-box"></view>
			<view class="skeleton-stat-info">
				<view class="skeleton-line skeleton-number"></view>
				<view class="skeleton-line skeleton-label"></view>
			</view>
		</template>
		
		<!-- 活动条目骨架 -->
		<template v-else-if="mode === 'activity'">
			<view class="skeleton-avatar"></view>
			<view class="skeleton-activity-content">
				<view class="skeleton-line skeleton-text"></view>
				<view class="skeleton-line skeleton-meta"></view>
			</view>
			<view class="skeleton-badge small"></view>
		</template>
		
		<!-- 快捷操作骨架 -->
		<template v-else-if="mode === 'action'">
			<view class="skeleton-action-icon"></view>
			<view class="skeleton-line skeleton-action-label"></view>
		</template>
		
		<!-- 默认/简单骨架 -->
		<template v-else>
			<view class="skeleton-line skeleton-title"></view>
			<view class="skeleton-line skeleton-text"></view>
			<view class="skeleton-line skeleton-text short"></view>
		</template>
	</view>
</template>

<script setup>
/**
 * SkeletonCard - 骨架屏加载占位组件
 * 
 * @property {String} mode - 骨架模式
 *   - 'list': 列表卡片（工单/站点）
 *   - 'stat': 统计卡片
 *   - 'activity': 活动条目
 *   - 'action': 快捷操作
 *   - 'default': 默认简单骨架
 */
defineProps({
	mode: {
		type: String,
		default: 'default',
		validator: (value) => ['default', 'list', 'stat', 'activity', 'action'].includes(value)
	}
})
</script>

<style lang="scss" scoped>
// 骨架动画
@keyframes skeleton-pulse {
	0% {
		opacity: 1;
	}
	50% {
		opacity: 0.4;
	}
	100% {
		opacity: 1;
	}
}

.skeleton-card {
	background: var(--bg-elevated);
	border-radius: var(--radius-md);
	padding: 16px;
	box-shadow: var(--shadow-card);
}

// 骨架线条基础样式
.skeleton-line {
	background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
	background-size: 200% 100%;
	border-radius: 4px;
	animation: skeleton-pulse 1.5s ease-in-out infinite;
}

.skeleton-title {
	height: 20px;
	width: 60%;
}

.skeleton-text {
	height: 14px;
	width: 100%;
	margin-top: 8px;
	
	&.short {
		width: 40%;
	}
}

.skeleton-meta {
	height: 12px;
	width: 30%;
}

// 列表卡片骨架
.skeleton-list {
	.skeleton-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 12px;
	}
	
	.skeleton-badge {
		width: 60px;
		height: 24px;
		background: #f0f0f0;
		border-radius: 12px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
	}
	
	.skeleton-body {
		margin-bottom: 12px;
	}
	
	.skeleton-footer {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding-top: 12px;
		border-top: 1px solid var(--border-soft);
	}
	
	.skeleton-btn {
		width: 80px;
		height: 32px;
		background: #f0f0f0;
		border-radius: 16px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
	}
}

// 统计卡片骨架
.skeleton-stat {
	display: flex;
	align-items: center;
	gap: 12px;
	
	.skeleton-icon-box {
		width: 48px;
		height: 48px;
		background: #f0f0f0;
		border-radius: 12px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
	}
	
	.skeleton-stat-info {
		flex: 1;
	}
	
	.skeleton-number {
		height: 24px;
		width: 50px;
		margin-bottom: 4px;
	}
	
	.skeleton-label {
		height: 12px;
		width: 70px;
		margin-top: 4px;
	}
}

// 活动条目骨架
.skeleton-activity {
	display: flex;
	align-items: center;
	gap: 12px;
	padding: 12px 16px;
	
	.skeleton-avatar {
		width: 40px;
		height: 40px;
		background: #f0f0f0;
		border-radius: 10px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
		flex-shrink: 0;
	}
	
	.skeleton-activity-content {
		flex: 1;
		
		.skeleton-text {
			width: 70%;
			margin-top: 0;
		}
		
		.skeleton-meta {
			margin-top: 6px;
		}
	}
	
	.skeleton-badge.small {
		width: 50px;
		height: 20px;
		background: #f0f0f0;
		border-radius: 6px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
	}
}

// 快捷操作骨架
.skeleton-action {
	display: flex;
	flex-direction: column;
	align-items: center;
	gap: 8px;
	padding: 20px 12px;
	
	.skeleton-action-icon {
		width: 32px;
		height: 32px;
		background: #f0f0f0;
		border-radius: 8px;
		animation: skeleton-pulse 1.5s ease-in-out infinite;
	}
	
	.skeleton-action-label {
		height: 12px;
		width: 48px;
		margin-top: 0;
	}
}
</style>
