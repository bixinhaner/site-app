<template>
	<view class="review-container">
		<view class="header">
			<text class="title">{{ $t('inspection.review') }}</text>
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
		background: linear-gradient(135deg, #f97316, #fb923c);
		display: flex;
		flex-direction: column;
	}
	
	.header {
		padding: 40px 20px 20px;
		text-align: center;
	}
	
	.title {
		color: white;
		font-size: 24px;
		font-weight: 600;
		display: block;
		margin-bottom: 8px;
	}
	
	.subtitle {
		color: rgba(255, 255, 255, 0.8);
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