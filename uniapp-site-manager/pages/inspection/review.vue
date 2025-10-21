<template>
	<view class="review-container">
		<!-- 自定义导航栏 -->
		<view class="custom-navbar">
			<view class="navbar-content">
				<view class="navbar-left">
					<view class="nav-button back-button" @click="goBack">
						<text class="nav-icon">←</text>
					</view>
				</view>
				<view class="navbar-center">
					<text class="navbar-title">{{ $t('inspection.review') }}</text>
				</view>
				<view class="navbar-right"></view>
			</view>
		</view>
		
		<view class="header">
			<text class="subtitle">{{ $t('messages.featureInDevelopment') }}...</text>
		</view>
		
		<view class="content">
			<view class="placeholder">
				<text class="placeholder-icon">✅</text>
				<text class="placeholder-title">{{ $t('inspection.reviewFunction') }}</text>
				<text class="placeholder-desc">{{ $t('messages.featureComingSoon') }}</text>
				
				<button class="back-btn" @click="goBack">{{ $t('common.back') }}</button>
			</view>
		</view>
	</view>
</template>

<script setup>
	const goBack = () => {
		uni.navigateBack()
	}
</script>

<style lang="scss" scoped>
	.review-container {
		height: 100vh;
		background: var(--bg-page);
		display: flex;
		flex-direction: column;
	}
	
	// 自定义导航栏
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
		font-weight: bold;
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
	
	.header {
		padding: 20px;
		text-align: center;
	}
	
	.subtitle {
		color: #666;
		font-size: 14px;
	}
	
	.content {
		flex: 1;
		background: white;
		margin: 20px;
		border-radius: 20px;
		display: flex;
		align-items: center;
		justify-content: center;
	}
	
	.placeholder {
		text-align: center;
		padding: 40px;
	}
	
	.placeholder-icon {
		font-size: 60px;
		display: block;
		margin-bottom: 20px;
	}
	
	.placeholder-title {
		font-size: 20px;
		color: #333;
		font-weight: 600;
		display: block;
		margin-bottom: 10px;
	}
	
	.placeholder-desc {
		font-size: 14px;
		color: #666;
		display: block;
		margin-bottom: 30px;
	}
	
	.back-btn {
		background: linear-gradient(135deg, #f97316, #fb923c);
		color: white;
		border: none;
		border-radius: 25px;
		padding: 12px 30px;
		font-size: 16px;
	}
</style>