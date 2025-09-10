<template>
	<view class="uni-load-more" :class="{ 'uni-load-more--line': showLine }">
		<view v-if="status === 'loading'" class="uni-load-more__text">
			<view class="uni-load-more__spinner">
				<view class="uni-load-more__dot" v-for="n in 3" :key="n"></view>
			</view>
			{{ contentText.contentrefresh }}
		</view>
		<view v-else-if="status === 'noMore'" class="uni-load-more__text">
			{{ contentText.contentnomore }}
		</view>
		<view v-else class="uni-load-more__text">
			{{ contentText.contentdown }}
		</view>
	</view>
</template>

<script>
export default {
	name: 'UniLoadMore',
	props: {
		status: {
			type: String,
			default: 'more'
		},
		showLine: {
			type: Boolean,
			default: false
		},
		contentText: {
			type: Object,
			default: () => ({
				contentdown: '上拉显示更多',
				contentrefresh: '正在加载...',
				contentnomore: '没有更多数据了'
			})
		}
	}
}
</script>

<style lang="scss" scoped>
.uni-load-more {
	display: flex;
	justify-content: center;
	align-items: center;
	padding: 20px;
	color: #999;
	font-size: 14px;
	
	&--line {
		border-top: 1px solid #eee;
	}
}

.uni-load-more__text {
	display: flex;
	align-items: center;
	gap: 8px;
}

.uni-load-more__spinner {
	display: flex;
	gap: 4px;
}

.uni-load-more__dot {
	width: 6px;
	height: 6px;
	background: #f97316;
	border-radius: 50%;
	animation: loading 1.4s infinite ease-in-out;
	
	&:nth-child(1) {
		animation-delay: -0.32s;
	}
	
	&:nth-child(2) {
		animation-delay: -0.16s;
	}
}

@keyframes loading {
	0%, 80%, 100% {
		transform: scale(0);
	}
	40% {
		transform: scale(1);
	}
}
</style>