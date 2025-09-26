<template>
  <view class="location-test-page">
    <view class="header">
      <text class="title">内置定位功能测试</text>
      <text class="subtitle">使用 UniApp 内置定位API</text>
    </view>
    
    <view class="status-section">
      <view class="status-card" :class="locationStatus.class">
        <text class="status-text">{{ locationStatus.text }}</text>
        <text class="status-desc">{{ locationStatus.desc }}</text>
      </view>
    </view>
    
    <view class="button-group">
      <button @click="testBuiltinLocation" class="test-btn primary">获取当前位置</button>
      <button @click="testChooseLocation" class="test-btn success">选择地图位置</button>
      <button @click="testOpenLocation" class="test-btn info" :disabled="!currentLocation">在地图中查看</button>
      <button @click="startLocationWatch" class="test-btn warning" v-if="!isWatching">开始位置监听</button>
      <button @click="stopLocationWatch" class="test-btn danger" v-if="isWatching">停止位置监听</button>
    </view>
    
    <view class="result-section" v-if="currentLocation">
      <text class="section-title">当前位置信息</text>
      <view class="info-item">
        <text class="label">纬度:</text>
        <text class="value">{{ currentLocation.latitude }}</text>
      </view>
      <view class="info-item">
        <text class="label">经度:</text>
        <text class="value">{{ currentLocation.longitude }}</text>
      </view>
      <view class="info-item">
        <text class="label">精度:</text>
        <text class="value">{{ currentLocation.accuracy }}米</text>
      </view>
      <view class="info-item">
        <text class="label">海拔:</text>
        <text class="value">{{ currentLocation.altitude }}米</text>
      </view>
      <view class="info-item">
        <text class="label">速度:</text>
        <text class="value">{{ currentLocation.speed }}m/s</text>
      </view>
      <view class="info-item">
        <text class="label">地址:</text>
        <text class="value">{{ currentLocation.address || '未获取' }}</text>
      </view>
      <view class="info-item">
        <text class="label">更新时间:</text>
        <text class="value">{{ formatTime(currentLocation.timestamp) }}</text>
      </view>
    </view>
    
    <view class="log-section">
      <text class="section-title">操作日志</text>
      <scroll-view class="log-content" scroll-y>
        <view v-for="(log, index) in logs" :key="index" class="log-item">
          <text class="log-time">[{{ log.time }}]</text>
          <text class="log-message" :class="log.type">{{ log.message }}</text>
        </view>
      </scroll-view>
      <button @click="clearLogs" class="clear-btn">清空日志</button>
    </view>
    
    <view class="feature-comparison">
      <text class="section-title">功能对比</text>
      <view class="comparison-table">
        <view class="table-header">
          <text class="col-feature">功能</text>
          <text class="col-builtin">内置API</text>
          <text class="col-custom">自定义插件</text>
        </view>
        <view class="table-row">
          <text class="col-feature">基础定位</text>
          <text class="col-builtin success">✅ 支持</text>
          <text class="col-custom pending">⏳ 开发中</text>
        </view>
        <view class="table-row">
          <text class="col-feature">地址解析</text>
          <text class="col-builtin success">✅ 支持</text>
          <text class="col-custom pending">⏳ 开发中</text>
        </view>
        <view class="table-row">
          <text class="col-feature">持续监听</text>
          <text class="col-builtin success">✅ 支持</text>
          <text class="col-custom pending">⏳ 开发中</text>
        </view>
        <view class="table-row">
          <text class="col-feature">自定义参数</text>
          <text class="col-builtin limited">⚠️ 有限</text>
          <text class="col-custom pending">⏳ 开发中</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  name: 'TestLocationBuiltin',
  data() {
    return {
      currentLocation: null,
      isWatching: false,
      watchId: null,
      locationStatus: {
        text: '准备就绪',
        desc: '点击按钮测试内置定位功能',
        class: 'status-ready'
      },
      logs: []
    }
  },
  
  onLoad() {
    this.addLog('页面加载', '开始测试内置定位功能', 'info');
  },
  
  onUnload() {
    // 页面销毁时停止位置监听
    this.stopLocationWatch();
  },
  
  methods: {
    // 测试内置定位
    testBuiltinLocation() {
      this.addLog('开始定位', '使用 uni.getLocation API...', 'info');
      this.updateStatus('定位中...', '正在获取位置信息', 'status-loading');
      
      uni.getLocation({
        type: 'gcj02', // 国测局坐标系
        geocode: true,  // 解析地址信息
        success: (res) => {
          this.currentLocation = {
            ...res,
            timestamp: Date.now()
          };
          
          this.updateStatus('定位成功', `精度: ${res.accuracy}米`, 'status-success');
          this.addLog('定位成功', `位置: ${res.latitude}, ${res.longitude}`, 'success');
          
          if (res.address) {
            this.addLog('地址解析', res.address.name || '地址信息已获取', 'success');
          }
          
          uni.showToast({
            title: '定位成功',
            icon: 'success'
          });
        },
        fail: (err) => {
          this.updateStatus('定位失败', err.errMsg, 'status-error');
          this.addLog('定位失败', err.errMsg, 'error');
          
          uni.showModal({
            title: '定位失败',
            content: `错误信息: ${err.errMsg}\n\n可能原因:\n1. 未授予定位权限\n2. GPS服务未开启\n3. 网络连接问题`,
            showCancel: false
          });
        }
      });
    },
    
    // 测试地图选择位置
    testChooseLocation() {
      this.addLog('地图选择', '打开地图选择位置...', 'info');
      
      uni.chooseLocation({
        success: (res) => {
          this.currentLocation = {
            latitude: res.latitude,
            longitude: res.longitude,
            name: res.name,
            address: res.address,
            timestamp: Date.now()
          };
          
          this.updateStatus('位置选择成功', res.name, 'status-success');
          this.addLog('地图选择成功', `${res.name} - ${res.address}`, 'success');
        },
        fail: (err) => {
          this.addLog('地图选择失败', err.errMsg, 'error');
        }
      });
    },
    
    // 在地图中查看位置
    testOpenLocation() {
      if (!this.currentLocation) {
        uni.showToast({
          title: '请先获取位置',
          icon: 'none'
        });
        return;
      }
      
      this.addLog('打开地图', '在地图中显示当前位置...', 'info');
      
      uni.openLocation({
        latitude: this.currentLocation.latitude,
        longitude: this.currentLocation.longitude,
        name: this.currentLocation.name || '当前位置',
        address: this.currentLocation.address?.name || '详细地址',
        success: () => {
          this.addLog('地图打开成功', '已在地图中显示位置', 'success');
        },
        fail: (err) => {
          this.addLog('地图打开失败', err.errMsg, 'error');
        }
      });
    },
    
    // 开始位置监听
    startLocationWatch() {
      this.addLog('开始监听', '启动位置监听服务...', 'info');
      
      this.watchId = uni.onLocationChange((res) => {
        this.currentLocation = {
          ...res,
          timestamp: Date.now()
        };
        
        this.updateStatus('位置监听中', `精度: ${res.accuracy}米`, 'status-watching');
        this.addLog('位置更新', `${res.latitude}, ${res.longitude}`, 'info');
      });
      
      this.isWatching = true;
      this.updateStatus('监听已启动', '位置变化时自动更新', 'status-watching');
      
      uni.showToast({
        title: '监听已启动',
        icon: 'success'
      });
    },
    
    // 停止位置监听
    stopLocationWatch() {
      if (this.watchId) {
        uni.offLocationChange(this.watchId);
        this.watchId = null;
      }
      
      this.isWatching = false;
      this.updateStatus('监听已停止', '位置监听服务已关闭', 'status-ready');
      this.addLog('停止监听', '位置监听服务已停止', 'info');
      
      uni.showToast({
        title: '监听已停止',
        icon: 'success'
      });
    },
    
    // 更新状态
    updateStatus(text, desc, statusClass) {
      this.locationStatus = {
        text,
        desc,
        class: statusClass
      };
    },
    
    // 添加日志
    addLog(type, message, level = 'info') {
      const log = {
        time: new Date().toLocaleTimeString(),
        type: level,
        message: `[${type}] ${message}`
      };
      
      this.logs.unshift(log);
      
      // 限制日志数量
      if (this.logs.length > 50) {
        this.logs.splice(50);
      }
    },
    
    // 清空日志
    clearLogs() {
      this.logs = [];
    },
    
    // 格式化时间
    formatTime(timestamp) {
      return new Date(timestamp).toLocaleString();
    }
  }
}
</script>

<style>
.location-test-page {
  padding: 20rpx;
  background-color: #f5f5f5;
  min-height: 100vh;
}

.header {
  text-align: center;
  margin-bottom: 30rpx;
  padding: 40rpx 20rpx;
  background-color: #fff;
  border-radius: 16rpx;
}

.title {
  font-size: 36rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 10rpx;
}

.subtitle {
  font-size: 26rpx;
  color: #666;
  display: block;
}

.status-section {
  margin-bottom: 30rpx;
}

.status-card {
  padding: 30rpx;
  border-radius: 16rpx;
  text-align: center;
}

.status-ready {
  background-color: #f0f9ff;
  border: 2rpx solid #3b82f6;
}

.status-loading {
  background-color: #fef3c7;
  border: 2rpx solid #f59e0b;
}

.status-success {
  background-color: #f0f9ff;
  border: 2rpx solid #10b981;
}

.status-error {
  background-color: #fef2f2;
  border: 2rpx solid #ef4444;
}

.status-watching {
  background-color: #f3e8ff;
  border: 2rpx solid #8b5cf6;
}

.status-text {
  font-size: 32rpx;
  font-weight: bold;
  display: block;
  margin-bottom: 10rpx;
}

.status-ready .status-text { color: #3b82f6; }
.status-loading .status-text { color: #f59e0b; }
.status-success .status-text { color: #10b981; }
.status-error .status-text { color: #ef4444; }
.status-watching .status-text { color: #8b5cf6; }

.status-desc {
  font-size: 26rpx;
  color: #666;
  display: block;
}

.button-group {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 30rpx;
}

.test-btn {
  height: 80rpx;
  border-radius: 12rpx;
  font-size: 28rpx;
  font-weight: 500;
}

.test-btn.primary {
  background-color: #3b82f6;
  color: white;
}

.test-btn.success {
  background-color: #10b981;
  color: white;
}

.test-btn.info {
  background-color: #06b6d4;
  color: white;
}

.test-btn.warning {
  background-color: #f59e0b;
  color: white;
}

.test-btn.danger {
  background-color: #ef4444;
  color: white;
}

.result-section, .log-section, .feature-comparison {
  background-color: #fff;
  border-radius: 16rpx;
  padding: 30rpx;
  margin-bottom: 30rpx;
}

.section-title {
  font-size: 32rpx;
  font-weight: bold;
  color: #333;
  display: block;
  margin-bottom: 20rpx;
}

.info-item {
  display: flex;
  align-items: flex-start;
  margin-bottom: 15rpx;
  padding-bottom: 10rpx;
  border-bottom: 1rpx solid #f0f0f0;
}

.info-item:last-child {
  border-bottom: none;
  margin-bottom: 0;
}

.label {
  width: 140rpx;
  color: #666;
  font-size: 26rpx;
  flex-shrink: 0;
}

.value {
  flex: 1;
  color: #333;
  font-size: 26rpx;
  word-break: break-all;
}

.log-content {
  height: 300rpx;
  background-color: #f8f8f8;
  border-radius: 8rpx;
  padding: 15rpx;
  margin-bottom: 20rpx;
}

.log-item {
  display: flex;
  margin-bottom: 8rpx;
  font-size: 24rpx;
  align-items: flex-start;
}

.log-time {
  color: #999;
  width: 100rpx;
  flex-shrink: 0;
}

.log-message {
  flex: 1;
  margin-left: 10rpx;
}

.log-message.info { color: #333; }
.log-message.success { color: #10b981; }
.log-message.error { color: #ef4444; }

.clear-btn {
  background-color: #6b7280;
  color: white;
  border-radius: 8rpx;
  height: 60rpx;
  font-size: 26rpx;
}

.comparison-table {
  border: 1rpx solid #e5e7eb;
  border-radius: 8rpx;
  overflow: hidden;
}

.table-header {
  background-color: #f9fafb;
  display: flex;
  padding: 20rpx 0;
  font-weight: bold;
  color: #374151;
  font-size: 26rpx;
}

.table-row {
  display: flex;
  padding: 15rpx 0;
  border-top: 1rpx solid #e5e7eb;
  font-size: 24rpx;
}

.col-feature {
  flex: 2;
  padding: 0 15rpx;
  color: #374151;
}

.col-builtin, .col-custom {
  flex: 1.5;
  padding: 0 15rpx;
  text-align: center;
  font-weight: 500;
}

.success { color: #10b981; }
.limited { color: #f59e0b; }
.pending { color: #6b7280; }
</style>