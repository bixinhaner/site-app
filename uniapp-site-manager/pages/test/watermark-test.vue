<template>
	<view class="test-container">
		<view class="test-header">
			<text class="test-title">水印功能测试</text>
			<text class="test-subtitle">测试自动水印添加功能</text>
		</view>
		
		<view class="test-section">
			<text class="section-title">配置测试</text>
			
			<view class="config-item">
				<text class="config-label">水印位置:</text>
				<picker 
					:value="positionIndex" 
					:range="positionOptions" 
					:range-key="'name'"
					@change="onPositionChange"
				>
					<view class="picker-text">{{ positionOptions[positionIndex].name }}</view>
				</picker>
			</view>
			
			<view class="config-item">
				<text class="config-label">启用哈希:</text>
				<switch :checked="enableHash" @change="onHashChange" />
			</view>
			
			<view class="config-item">
				<text class="config-label">启用签名:</text>
				<switch :checked="enableSignature" @change="onSignatureChange" />
			</view>
		</view>
		
		<view class="test-section">
			<text class="section-title">测试操作</text>
			
			<view class="test-buttons">
				<button class="test-btn" @click="testCamera" :disabled="isLoading">
					{{ isLoading ? '处理中...' : '测试拍照水印' }}
				</button>
				
				<button class="test-btn secondary" @click="testOffline">
					测试离线功能
				</button>
				
				<button class="test-btn secondary" @click="testSecurity">
					测试安全验证
				</button>
			</view>
		</view>
		
		<view class="test-section" v-if="testResults.length > 0">
			<text class="section-title">测试结果</text>
			
			<view class="results-list">
				<view 
					class="result-item" 
					v-for="(result, index) in testResults" 
					:key="index"
					:class="{ success: result.success, error: !result.success }"
				>
					<view class="result-header">
						<text class="result-title">{{ result.title }}</text>
						<text class="result-status">{{ result.success ? '✅' : '❌' }}</text>
					</view>
					<text class="result-message">{{ result.message }}</text>
					<text class="result-time">{{ result.timestamp }}</text>
				</view>
			</view>
		</view>
		
		<view class="test-section" v-if="lastPhoto">
			<text class="section-title">最新照片</text>
			
			<view class="photo-preview">
				<image :src="lastPhoto.path" mode="aspectFit" class="preview-image"></image>
				
				<view class="photo-info">
					<view class="info-row">
						<text class="info-label">文件大小:</text>
						<text class="info-value">{{ formatFileSize(lastPhoto.size) }}</text>
					</view>
					<view class="info-row" v-if="lastPhoto.gps">
						<text class="info-label">GPS坐标:</text>
						<text class="info-value">{{ formatGPS(lastPhoto.gps) }}</text>
					</view>
					<view class="info-row" v-if="lastPhoto.hash">
						<text class="info-label">哈希值:</text>
						<text class="info-value hash">{{ lastPhoto.hash }}</text>
					</view>
					<view class="info-row" v-if="lastPhoto.signature">
						<text class="info-label">数字签名:</text>
						<text class="info-value hash">{{ lastPhoto.signature }}</text>
					</view>
				</view>
			</view>
		</view>
	</view>
</template>

<script setup>
	import { ref, onMounted } from 'vue'
	import { watermarkConfig, securityUtils } from '@/config/watermark.js'
	import { useUserStore } from '@/stores/user'
	
	const userStore = useUserStore()
	
	// 响应式数据
	const isLoading = ref(false)
	const testResults = ref([])
	const lastPhoto = ref(null)
	
	// 配置选项
	const positionIndex = ref(0)
	const positionOptions = ref([
		{ name: '左下角', value: 'bottomLeft' },
		{ name: '右下角', value: 'bottomRight' },
		{ name: '左上角', value: 'topLeft' },
		{ name: '右上角', value: 'topRight' },
		{ name: '居中', value: 'center' }
	])
	
	const enableHash = ref(watermarkConfig.security.enableHash)
	const enableSignature = ref(watermarkConfig.security.enableSignature)
	
	// 生命周期
	onMounted(() => {
		addTestResult('测试页面初始化', '水印测试页面加载完成', true)
	})
	
	// 事件处理
	const onPositionChange = (e) => {
		positionIndex.value = e.detail.value
		watermarkConfig.position.default = positionOptions.value[positionIndex.value].value
		addTestResult('配置更新', `水印位置已改为: ${positionOptions.value[positionIndex.value].name}`, true)
	}
	
	const onHashChange = (e) => {
		enableHash.value = e.detail.value
		watermarkConfig.security.enableHash = e.detail.value
		addTestResult('配置更新', `哈希验证已${e.detail.value ? '启用' : '禁用'}`, true)
	}
	
	const onSignatureChange = (e) => {
		enableSignature.value = e.detail.value
		watermarkConfig.security.enableSignature = e.detail.value
		addTestResult('配置更新', `数字签名已${e.detail.value ? '启用' : '禁用'}`, true)
	}
	
	// 测试功能
	const testCamera = async () => {
		try {
			isLoading.value = true
			
			// 模拟拍照流程
			uni.navigateTo({
				url: '/pages/inspection/camera?inspectionId=test&checkItemId=test&itemIndex=0'
			})
			
			addTestResult('拍照测试', '已跳转到拍照页面，请完成拍照测试', true)
			
		} catch (error) {
			addTestResult('拍照测试', '测试失败: ' + error.message, false)
		} finally {
			isLoading.value = false
		}
	}
	
	const testOffline = async () => {
		try {
			// 测试离线功能
			const testData = {
				timestamp: new Date().toISOString(),
				gps: { latitude: 39.9042, longitude: 116.4074, accuracy: 5.0 },
				inspector: 'test_user',
				checkItem: '离线测试项',
				siteName: '测试站点'
			}
			
			// 模拟离线保存
			const storageKey = 'offline_test_' + Date.now()
			uni.setStorageSync(storageKey, testData)
			
			// 验证保存
			const savedData = uni.getStorageSync(storageKey)
			const isValid = JSON.stringify(savedData) === JSON.stringify(testData)
			
			addTestResult('离线测试', isValid ? '离线数据保存和读取成功' : '离线数据验证失败', isValid)
			
		} catch (error) {
			addTestResult('离线测试', '测试失败: ' + error.message, false)
		}
	}
	
	const testSecurity = async () => {
		try {
			// 测试安全功能
			const testData = {
				path: '/test/path/image.jpg',
				size: 123456,
				timestamp: new Date().toISOString(),
				gps: { latitude: 39.9042, longitude: 116.4074 }
			}
			
			// 生成哈希
			const hash = securityUtils.generateSimpleHash(testData)
			
			// 生成签名
			const signature = securityUtils.generateSignature(testData)
			
			// 验证哈希
			const verifyHash = securityUtils.generateSimpleHash(testData)
			const hashValid = hash === verifyHash
			
			// 验证完整性
			const integrityValid = securityUtils.verifyIntegrity(hash, testData)
			
			const success = hashValid && integrityValid
			const message = `哈希: ${hashValid ? '✅' : '❌'}, 完整性: ${integrityValid ? '✅' : '❌'}`
			
			addTestResult('安全测试', message, success)
			
			// 显示生成的安全信息
			addTestResult('安全信息', `哈希值: ${hash.substring(0, 16)}...`, true)
			addTestResult('安全信息', `签名: ${signature.substring(0, 16)}...`, true)
			
		} catch (error) {
			addTestResult('安全测试', '测试失败: ' + error.message, false)
		}
	}
	
	// 工具函数
	const addTestResult = (title, message, success = true) => {
		testResults.value.unshift({
			title,
			message,
			success,
			timestamp: new Date().toLocaleString('zh-CN')
		})
		
		// 限制结果数量
		if (testResults.value.length > 10) {
			testResults.value.pop()
		}
	}
	
	const formatFileSize = (size) => {
		if (!size) return '未知'
		if (size < 1024) return size + 'B'
		if (size < 1024 * 1024) return (size / 1024).toFixed(1) + 'KB'
		return (size / (1024 * 1024)).toFixed(1) + 'MB'
	}
	
	const formatGPS = (gps) => {
		if (!gps || !gps.latitude) return '无GPS信息'
		return `${gps.latitude.toFixed(6)}, ${gps.longitude.toFixed(6)}`
	}
</script>

<style scoped>
	.test-container {
		padding: 20rpx;
		background: #f5f5f5;
		min-height: 100vh;
	}
	
	.test-header {
		background: white;
		border-radius: 15rpx;
		padding: 30rpx;
		margin-bottom: 20rpx;
		text-align: center;
	}
	
	.test-title {
		font-size: 36rpx;
		font-weight: bold;
		color: #333;
		display: block;
		margin-bottom: 10rpx;
	}
	
	.test-subtitle {
		font-size: 26rpx;
		color: #666;
		display: block;
	}
	
	.test-section {
		background: white;
		border-radius: 15rpx;
		padding: 30rpx;
		margin-bottom: 20rpx;
	}
	
	.section-title {
		font-size: 32rpx;
		font-weight: bold;
		color: #333;
		display: block;
		margin-bottom: 20rpx;
	}
	
	.config-item {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: 20rpx 0;
		border-bottom: 1rpx solid #eee;
	}
	
	.config-item:last-child {
		border-bottom: none;
	}
	
	.config-label {
		font-size: 28rpx;
		color: #333;
	}
	
	.picker-text {
		color: #007bff;
		font-size: 28rpx;
	}
	
	.test-buttons {
		display: flex;
		flex-direction: column;
		gap: 15rpx;
	}
	
	.test-btn {
		background: #007bff;
		color: white;
		border: none;
		border-radius: 10rpx;
		padding: 25rpx;
		font-size: 30rpx;
		font-weight: bold;
	}
	
	.test-btn.secondary {
		background: #6c757d;
	}
	
	.test-btn:disabled {
		background: #ccc;
		color: #666;
	}
	
	.results-list {
		max-height: 600rpx;
		overflow-y: auto;
	}
	
	.result-item {
		padding: 20rpx;
		margin-bottom: 15rpx;
		border-radius: 10rpx;
		border-left: 6rpx solid #ddd;
	}
	
	.result-item.success {
		background: #d4edda;
		border-left-color: #28a745;
	}
	
	.result-item.error {
		background: #f8d7da;
		border-left-color: #dc3545;
	}
	
	.result-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 8rpx;
	}
	
	.result-title {
		font-size: 28rpx;
		font-weight: bold;
		color: #333;
	}
	
	.result-status {
		font-size: 24rpx;
	}
	
	.result-message {
		font-size: 26rpx;
		color: #666;
		display: block;
		margin-bottom: 8rpx;
	}
	
	.result-time {
		font-size: 22rpx;
		color: #999;
		display: block;
	}
	
	.photo-preview {
		border: 1rpx solid #ddd;
		border-radius: 10rpx;
		overflow: hidden;
	}
	
	.preview-image {
		width: 100%;
		height: 400rpx;
	}
	
	.photo-info {
		padding: 20rpx;
		background: #f8f9fa;
	}
	
	.info-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		margin-bottom: 15rpx;
	}
	
	.info-row:last-child {
		margin-bottom: 0;
	}
	
	.info-label {
		font-size: 26rpx;
		color: #666;
		flex-shrink: 0;
		width: 160rpx;
	}
	
	.info-value {
		font-size: 26rpx;
		color: #333;
		flex: 1;
		text-align: right;
		word-break: break-all;
	}
	
	.info-value.hash {
		font-family: monospace;
		font-size: 22rpx;
	}
</style>