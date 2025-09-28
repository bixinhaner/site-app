<template>
  <view class="location-test">
    <view class="header">
      <text class="title">定位插件测试</text>
    </view>
    
    <view class="button-group">
      <button @click="testSyncLocation" class="test-btn">测试同步定位</button>
      <button @click="testAsyncLocation" class="test-btn primary">测试异步定位</button>
      <button @click="testReverseGeocode" class="test-btn" :disabled="!locationData">地址解析</button>
      <button @click="startContinuous" class="test-btn success">开始持续定位</button>
      <button @click="stopContinuous" class="test-btn danger">停止持续定位</button>
    </view>
    
    <view class="result-section" v-if="locationData">
      <text class="section-title">位置信息</text>
      <view class="info-item">
        <text class="label">纬度:</text>
        <text class="value">{{ locationData.latitude }}</text>
      </view>
      <view class="info-item">
        <text class="label">经度:</text>
        <text class="value">{{ locationData.longitude }}</text>
      </view>
      <view class="info-item">
        <text class="label">精度:</text>
        <text class="value">{{ locationData.accuracy }}米</text>
      </view>
      <view class="info-item">
        <text class="label">海拔:</text>
        <text class="value">{{ locationData.altitude }}米</text>
      </view>
      <view class="info-item">
        <text class="label">速度:</text>
        <text class="value">{{ locationData.speed }}m/s</text>
      </view>
      <view class="info-item">
        <text class="label">提供者:</text>
        <text class="value">{{ locationData.provider }}</text>
      </view>
    </view>
    
    <view class="result-section" v-if="addressData">
      <text class="section-title">地址信息</text>
      <view class="info-item">
        <text class="label">国家:</text>
        <text class="value">{{ addressData.country }}</text>
      </view>
      <view class="info-item">
        <text class="label">省份:</text>
        <text class="value">{{ addressData.province }}</text>
      </view>
      <view class="info-item">
        <text class="label">城市:</text>
        <text class="value">{{ addressData.city }}</text>
      </view>
      <view class="info-item">
        <text class="label">详细地址:</text>
        <text class="value">{{ addressData.formattedAddress }}</text>
      </view>
    </view>
    
    <view class="log-section">
      <text class="section-title">测试日志</text>
      <scroll-view class="log-content" scroll-y>
        <view v-for="(log, index) in logs" :key="index" class="log-item">
          <text class="log-time">[{{ log.time }}]</text>
          <text class="log-message" :class="log.type">{{ log.message }}</text>
        </view>
      </scroll-view>
      <button @click="clearLogs" class="clear-btn">清空日志</button>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      locationPlugin: null,
      locationData: null,
      addressData: null,
      logs: [],
      isContinuousLocation: false
    }
  },
  
  onLoad() {
    this.addLog('初始化定位插件...', 'info');
    try {
      this.locationPlugin = uni.requireNativePlugin('my-location-plugin');
      this.addLog('定位插件初始化成功', 'success');
    } catch (error) {
      this.addLog('插件初始化失败: ' + error.message, 'error');
    }
  },
  
  onUnload() {
    // 页面销毁时停止定位
    if (this.locationPlugin) {
      this.locationPlugin.stopLocationUpdates();
    }
  },
  
  methods: {
    // 测试同步定位
    testSyncLocation() {
      this.addLog('开始同步定位测试...', 'info');
      
      if (!this.locationPlugin) {
        this.addLog('插件未初始化', 'error');
        return;
      }
      
      try {
        const result = this.locationPlugin.getLocationSync();
        if (result.success) {
          this.locationData = result.data;
          this.addLog('同步定位成功', 'success');
          this.addLog(`位置: ${result.data.latitude}, ${result.data.longitude}`, 'info');
        } else {
          this.addLog('同步定位失败: ' + result.error, 'error');
        }
      } catch (error) {
        this.addLog('同步定位异常: ' + error.message, 'error');
      }
    },
    
    // 测试异步定位
    testAsyncLocation() {
      this.addLog('开始异步定位测试...', 'info');
      
      if (!this.locationPlugin) {
        this.addLog('插件未初始化', 'error');
        return;
      }
      
      uni.showLoading({ title: '定位中...' });
      
      this.locationPlugin.getLocation((result) => {
        uni.hideLoading();
        
        if (result.success) {
          this.locationData = result.data;
          this.addLog('异步定位成功', 'success');
          this.addLog(`位置: ${result.data.latitude}, ${result.data.longitude}`, 'info');
          this.addLog(`精度: ${result.data.accuracy}米`, 'info');
          
          uni.showToast({
            title: '定位成功',
            icon: 'success'
          });
        } else {
          this.addLog('异步定位失败: ' + result.error, 'error');
          
          uni.showToast({
            title: '定位失败',
            icon: 'error'
          });
        }
      });
    },
    
    // 测试地址解析
    testReverseGeocode() {
      if (!this.locationData) {
        this.addLog('请先获取位置信息', 'warning');
        uni.showToast({
          title: '请先定位',
          icon: 'none'
        });
        return;
      }
      
      this.addLog('开始地址解析...', 'info');
      uni.showLoading({ title: '解析中...' });
      
      this.locationPlugin.reverseGeocode({
        latitude: this.locationData.latitude,
        longitude: this.locationData.longitude
      }, (result) => {
        uni.hideLoading();
        
        if (result.success) {
          this.addressData = result.data;
          this.addLog('地址解析成功', 'success');
          this.addLog(`地址: ${result.data.formattedAddress}`, 'info');
          
          uni.showToast({
            title: '解析成功',
            icon: 'success'
          });
        } else {
          this.addLog('地址解析失败: ' + result.error, 'error');
          
          uni.showToast({
            title: '解析失败',
            icon: 'error'
          });
        }
      });
    },
    
    // 开始持续定位
    startContinuous() {
      if (this.isContinuousLocation) {
        this.addLog('持续定位已在运行中', 'warning');
        return;
      }
      
      this.addLog('开始持续定位...', 'info');
      
      this.locationPlugin.startLocationUpdates({
        interval: 5000,   // 5秒间隔
        distance: 10      // 10米距离
      }, (result) => {
        if (result.success) {
          if (typeof result.data === 'string') {
            // 启动成功消息
            this.addLog(result.data, 'success');
            this.isContinuousLocation = true;
          } else {
            // 位置更新
            this.locationData = result.data;
            this.addLog(`位置更新: ${result.data.latitude}, ${result.data.longitude}`, 'info');
          }
        } else {
          this.addLog('持续定位失败: ' + result.error, 'error');
        }
      });
    },
    
    // 停止持续定位
    stopContinuous() {
      this.addLog('停止持续定位', 'info');
      this.locationPlugin.stopLocationUpdates();
      this.isContinuousLocation = false;
      
      uni.showToast({
        title: '已停止定位',
        icon: 'success'
      });
    },
    
    // 添加日志
    addLog(message, type = 'info') {
      const time = new Date().toLocaleTimeString();
      this.logs.unshift({
        time,
        message,
        type
      });
      
      // 限制日志数量
      if (this.logs.length > 100) {
        this.logs.splice(100);
      }
    },
    
    // 清空日志
    clearLogs() {
      this.logs = [];
    }
  }
}
</script>

<style>
.location-test {
  padding: 20rpx;
}

.header {
  text-align: center;
  margin-bottom: 40rpx;
}

.title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 40rpx;
}

.test-btn {
  height: 80rpx;
  border-radius: 10rpx;
  font-size: 28rpx;
  background-color: #f5f5f5;
  color: #666;
}

.test-btn.primary {
  background-color: #007aff;
  color: white;
}

.test-btn.success {
  background-color: #4cd964;
  color: white;
}

.test-btn.danger {
  background-color: #ff3b30;
  color: white;
}

.result-section {
  margin-bottom: 40rpx;
  padding: 20rpx;
  background-color: #f8f8f8;
  border-radius: 10rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  margin-bottom: 20rpx;
  display: block;
}

.info-item {
  display: flex;
  margin-bottom: 10rpx;
  align-items: flex-start;
}

.label {
  width: 140rpx;
  color: #666;
  font-size: 26rpx;
}

.value {
  flex: 1;
  color: #333;
  font-size: 26rpx;
  word-break: break-all;
}

.log-section {
  background-color: #f8f8f8;
  border-radius: 10rpx;
  padding: 20rpx;
}

.log-content {
  height: 400rpx;
  background-color: #fff;
  border-radius: 8rpx;
  padding: 10rpx;
  margin-bottom: 20rpx;
}

.log-item {
  display: flex;
  margin-bottom: 8rpx;
  font-size: 24rpx;
}

.log-time {
  color: #999;
  width: 120rpx;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  margin-left: 10rpx;
}

.log-message.info {
  color: #333;
}

.log-message.success {
  color: #4cd964;
}

.log-message.error {
  color: #ff3b30;
}

.log-message.warning {
  color: #ff9500;
}

.clear-btn {
  height: 60rpx;
  line-height: 60rpx;
  background-color: #ff3b30;
  color: white;
  border-radius: 8rpx;
  font-size: 26rpx;
}
</style>