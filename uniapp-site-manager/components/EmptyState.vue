<template>
	<view class="empty-state" :class="{ 'empty-compact': compact }">
		<view class="empty-icon-container">
			<text class="empty-icon">{{ icon }}</text>
		</view>
		
		<text class="empty-title">{{ title }}</text>
		
		<text class="empty-description" v-if="description">{{ description }}</text>
		
		<button 
			v-if="actionText" 
			class="empty-action u-pressable"
			@click="handleAction"
		>
			{{ actionText }}
		</button>
		
		<slot></slot>
	</view>
</template>

<script setup>
/**
 * EmptyState - 空状态占位组件
 * 
 * @property {String} icon - 显示的 emoji 图标
 * @property {String} title - 标题文字
 * @property {String} description - 描述文字（可选）
 * @property {String} actionText - 操作按钮文字（可选，传入则显示按钮）
 * @property {Boolean} compact - 紧凑模式
 * 
 * @event action - 点击操作按钮时触发
 */
const props = defineProps({
	icon: {
		type: String,
		default: '📭'
	},
	title: {
		type: String,
		default: '暂无数据'
	},
	description: {
		type: String,
		default: ''
	},
	actionText: {
		type: String,
		default: ''
	},
	compact: {
		type: Boolean,
		default: false
	}
})

const emit = defineEmits(['action'])

const handleAction = () => {
	emit('action')
}
</script>

<style lang="scss" scoped>
.empty-state {
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	padding: 60px 40px;
	text-align: center;
}

.empty-compact {
	padding: 40px 20px;
	
	.empty-icon-container {
		width: 64px;
		height: 64px;
	}
	
	.empty-icon {
		font-size: 32px;
	}
	
	.empty-title {
		font-size: 14px;
	}
}

.empty-icon-container {
	width: 96px;
	height: 96px;
	background: linear-gradient(135deg, #f8f9fa, #e9ecef);
	border-radius: 50%;
	display: flex;
	align-items: center;
	justify-content: center;
	margin-bottom: 20px;
}

.empty-icon {
	font-size: 48px;
	opacity: 0.8;
}

.empty-title {
	font-size: 16px;
	font-weight: 600;
	color: var(--text-primary);
	margin-bottom: 8px;
}

.empty-description {
	font-size: 14px;
	color: var(--text-secondary);
	max-width: 240px;
	line-height: 1.5;
	margin-bottom: 20px;
}

.empty-action {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-height: 44px;
	padding: 0 24px;
	background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
	color: #fff;
	font-size: 14px;
	font-weight: 600;
	border: none;
	border-radius: var(--radius-sm);
	box-shadow: 0 2px 10px rgba(249, 115, 22, 0.28);
	margin-top: 8px;
}
</style>
