<template>
  <view class="container">
    <view class="header">
      <text class="title">扫码领料</text>
      <view class="scan-info">
        <text class="info-text">扫描主设备条码自动配套设备套装</text>
      </view>
    </view>

    <!-- 扫码区域 -->
    <view class="scan-section">
      <view class="scan-button" @click="startScan">
        <view class="scan-icon">📷</view>
        <text class="scan-text">点击扫描设备条码</text>
      </view>
      
      <view v-if="scanResult" class="scan-result">
        <text class="result-title">扫描结果:</text>
        <text class="result-code">{{ scanResult }}</text>
      </view>
    </view>

    <!-- 任务选择 -->
    <view v-if="availablePackages.length > 0" class="task-section">
      <view class="section-title">选择关联任务 (可选)</view>
      <picker @change="onTaskChange" :value="selectedTaskIndex" :range="taskOptions">
        <view class="picker-input">
          <text>{{ selectedTask ? selectedTask.task_title : '选择任务 (可选)' }}</text>
          <text class="picker-arrow">▼</text>
        </view>
      </picker>
    </view>

    <!-- 套装选择 -->
    <view v-if="availablePackages.length > 1" class="package-section">
      <view class="section-title">选择设备套装</view>
      <view class="package-list">
        <view 
          v-for="(pkg, index) in availablePackages" 
          :key="pkg.id"
          class="package-item"
          :class="{ 'selected': selectedPackageIndex === index }"
          @click="selectPackage(index)"
        >
          <view class="package-header">
            <text class="package-name">{{ pkg.package_name }}</text>
            <text class="package-code">{{ pkg.package_code }}</text>
          </view>
          <text class="package-type">适用: {{ pkg.site_type || '通用' }}</text>
        </view>
      </view>
    </view>

    <!-- 套装清单 -->
    <view v-if="selectedPackage" class="package-detail">
      <view class="section-title">套装清单确认</view>
      
      <view class="package-info">
        <view class="info-row">
          <text class="info-label">套装名称:</text>
          <text class="info-value">{{ selectedPackage.package_name }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">套装编码:</text>
          <text class="info-value">{{ selectedPackage.package_code }}</text>
        </view>
      </view>
      
      <view class="items-list">
        <view v-for="item in selectedPackage.items" :key="item.equipment_id" class="item-card">
          <view class="item-header">
            <text class="item-name">{{ item.equipment_name }}</text>
            <view class="item-quantity">
              <text class="quantity-text">{{ item.quantity }} {{ item.unit }}</text>
              <text v-if="item.is_required" class="required-tag">必需</text>
            </view>
          </view>
          <text class="item-code">编码: {{ item.equipment_code }}</text>
        </view>
      </view>
      
      <!-- 确认按钮 -->
      <view class="action-buttons">
        <button class="btn-cancel" @click="resetScan">重新扫码</button>
        <button class="btn-confirm" @click="confirmPickup" :disabled="confirming">
          {{ confirming ? '确认中...' : '确认领料' }}
        </button>
      </view>
    </view>

    <!-- 领料记录 -->
    <view class="history-section">
      <view class="section-title">
        <text>我的领料记录</text>
        <text class="refresh-btn" @click="loadPickupHistory">刷新</text>
      </view>
      
      <view v-if="pickupHistory.length === 0" class="empty-state">
        <text>暂无领料记录</text>
      </view>
      
      <view v-else class="history-list">
        <view v-for="record in pickupHistory" :key="record.id" class="history-item">
          <view class="history-header">
            <text class="history-package">{{ record.package_name }}</text>
            <text class="history-time">{{ formatTime(record.pickup_time) }}</text>
          </view>
          <view class="history-detail">
            <text class="history-barcode">条码: {{ record.main_device_barcode }}</text>
            <text class="history-status" :class="{ 'confirmed': record.is_confirmed }">
              {{ record.is_confirmed ? '✓ 已确认' : '待确认' }}
            </text>
          </view>
        </view>
      </view>
    </view>

    <!-- Loading遮罩 -->
    <view v-if="loading" class="loading-mask">
      <view class="loading-content">
        <text>处理中...</text>
      </view>
    </view>
  </view>
</template>

<script>
export default {
  data() {
    return {
      scanResult: '',
      selectedPackageIndex: 0,
      selectedTaskIndex: 0,
      availablePackages: [],
      myTasks: [],
      pickupHistory: [],
      loading: false,
      confirming: false,
      userLocation: null
    }
  },
  
  computed: {
    selectedPackage() {
      return this.availablePackages[this.selectedPackageIndex]
    },
    
    selectedTask() {
      return this.myTasks[this.selectedTaskIndex]
    },
    
    taskOptions() {
      return ['无关联任务', ...this.myTasks.map(task => task.task_title)]
    }
  },
  
  onLoad() {
    this.loadMyTasks()
    this.loadPickupHistory()
    this.getCurrentLocation()
  },
  
  methods: {
    async startScan() {
      try {
        const result = await new Promise((resolve, reject) => {
          uni.scanCode({
            scanType: ['barCode', 'qrCode'],
            success: resolve,
            fail: reject
          })
        })
        
        this.scanResult = result.result
        this.processScannedCode(result.result)
      } catch (error) {
        console.error('扫码失败:', error)
        uni.showToast({
          title: '扫码失败，请重试',
          icon: 'none'
        })
      }
    },
    
    async processScannedCode(barcode) {
      this.loading = true
      
      try {
        const response = await this.$http.get(`/api/equipment/${barcode}/barcode-info`)
        
        if (response.equipment && response.available_packages.length > 0) {
          this.availablePackages = response.available_packages
          this.selectedPackageIndex = 0
          
          uni.showToast({
            title: `识别到设备: ${response.equipment.name}`,
            icon: 'success'
          })
        } else {
          uni.showToast({
            title: '未找到对应的设备套装',
            icon: 'none'
          })
        }
      } catch (error) {
        console.error('处理扫码结果失败:', error)
        uni.showToast({
          title: '设备识别失败',
          icon: 'none'
        })
      } finally {
        this.loading = false
      }
    },
    
    selectPackage(index) {
      this.selectedPackageIndex = index
    },
    
    onTaskChange(e) {
      this.selectedTaskIndex = e.detail.value
    },
    
    async confirmPickup() {
      if (!this.selectedPackage) {
        uni.showToast({ title: '请选择套装', icon: 'none' })
        return
      }
      
      try {
        this.confirming = true
        
        const pickupData = {
          barcode: this.scanResult,
          package_id: this.selectedPackage.id,
          task_id: this.selectedTask?.id || null,
          gps_location: this.userLocation
        }
        
        const response = await this.$http.post('/api/stock/scan-checkout', pickupData)
        
        if (response.action === 'checkout_success') {
          uni.showModal({
            title: '领料成功',
            content: `出库单号: ${response.document_number}\n套装: ${response.package.name}`,
            showCancel: false,
            confirmText: '确定',
            success: () => {
              this.resetScan()
              this.loadPickupHistory()
            }
          })
        } else if (response.action === 'insufficient_stock') {
          let shortage = response.shortage_items.map(item => 
            `${item.equipment_name}: 需要${item.required}，库存${item.available}`
          ).join('\n')
          
          uni.showModal({
            title: '库存不足',
            content: shortage,
            showCancel: false
          })
        }
      } catch (error) {
        console.error('确认领料失败:', error)
        uni.showToast({
          title: '领料失败: ' + (error.response?.data?.detail || '网络错误'),
          icon: 'none'
        })
      } finally {
        this.confirming = false
      }
    },
    
    resetScan() {
      this.scanResult = ''
      this.availablePackages = []
      this.selectedPackageIndex = 0
      this.selectedTaskIndex = 0
    },
    
    async loadMyTasks() {
      try {
        const response = await this.$http.get('/api/tasks/', {
          params: { assigned_to_me: true, status: 'accepted,in_progress' }
        })
        this.myTasks = response.tasks || []
      } catch (error) {
        console.error('加载任务列表失败:', error)
      }
    },
    
    async loadPickupHistory() {
      try {
        const response = await this.$http.get('/api/stock/my-pickups')
        this.pickupHistory = response.pickup_records || []
      } catch (error) {
        console.error('加载领料记录失败:', error)
      }
    },
    
    getCurrentLocation() {
      uni.getLocation({
        type: 'gcj02',
        success: (res) => {
          this.userLocation = {
            latitude: res.latitude,
            longitude: res.longitude,
            accuracy: res.accuracy
          }
        },
        fail: (error) => {
          console.warn('获取位置失败:', error)
        }
      })
    },
    
    formatTime(timeString) {
      if (!timeString) return ''
      const date = new Date(timeString)
      return `${date.getMonth() + 1}/${date.getDate()} ${date.getHours()}:${date.getMinutes().toString().padStart(2, '0')}`
    }
  }
}
</script>

<style lang="scss" scoped>
.container {
  background-color: #f8fafc;
  min-height: 100vh;
  padding: 20rpx;
}

.header {
  background: white;
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
  
  .title {
    font-size: 36rpx;
    font-weight: 600;
    color: #111827;
    display: block;
    margin-bottom: 16rpx;
  }
  
  .scan-info {
    .info-text {
      font-size: 28rpx;
      color: #6b7280;
    }
  }
}

.scan-section {
  background: white;
  padding: 40rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
  text-align: center;
  
  .scan-button {
    background: linear-gradient(135deg, #f97316, #ea580c);
    color: white;
    padding: 60rpx 40rpx;
    border-radius: 12rpx;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 20rpx;
    
    .scan-icon {
      font-size: 60rpx;
    }
    
    .scan-text {
      font-size: 32rpx;
      font-weight: 500;
    }
  }
  
  .scan-result {
    margin-top: 30rpx;
    padding: 20rpx;
    background: #f0f9f0;
    border-radius: 8rpx;
    
    .result-title {
      font-size: 28rpx;
      color: #16a34a;
      display: block;
      margin-bottom: 10rpx;
    }
    
    .result-code {
      font-size: 30rpx;
      font-weight: 600;
      color: #15803d;
    }
  }
}

.task-section, .package-section {
  background: white;
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: #111827;
  margin-bottom: 20rpx;
  display: block;
}

.picker-input {
  padding: 20rpx;
  border: 2rpx solid #e5e7eb;
  border-radius: 8rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f9fafb;
  
  .picker-arrow {
    color: #9ca3af;
  }
}

.package-list {
  .package-item {
    padding: 24rpx;
    border: 2rpx solid #e5e7eb;
    border-radius: 8rpx;
    margin-bottom: 16rpx;
    transition: all 0.3s;
    
    &.selected {
      border-color: #f97316;
      background: #fff7ed;
    }
    
    .package-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8rpx;
      
      .package-name {
        font-size: 30rpx;
        font-weight: 500;
        color: #111827;
      }
      
      .package-code {
        font-size: 24rpx;
        color: #6b7280;
      }
    }
    
    .package-type {
      font-size: 26rpx;
      color: #f97316;
    }
  }
}

.package-detail {
  background: white;
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
  
  .package-info {
    margin-bottom: 30rpx;
    
    .info-row {
      display: flex;
      justify-content: space-between;
      margin-bottom: 16rpx;
      
      .info-label {
        font-size: 28rpx;
        color: #6b7280;
      }
      
      .info-value {
        font-size: 28rpx;
        color: #111827;
        font-weight: 500;
      }
    }
  }
  
  .items-list {
    .item-card {
      padding: 24rpx;
      background: #f8fafc;
      border-radius: 8rpx;
      margin-bottom: 16rpx;
      
      .item-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8rpx;
        
        .item-name {
          font-size: 30rpx;
          color: #111827;
          font-weight: 500;
        }
        
        .item-quantity {
          display: flex;
          align-items: center;
          gap: 12rpx;
          
          .quantity-text {
            font-size: 28rpx;
            color: #f97316;
            font-weight: 600;
          }
          
          .required-tag {
            background: #dcfce7;
            color: #166534;
            padding: 4rpx 12rpx;
            border-radius: 4rpx;
            font-size: 22rpx;
          }
        }
      }
      
      .item-code {
        font-size: 24rpx;
        color: #6b7280;
      }
    }
  }
}

.action-buttons {
  display: flex;
  gap: 20rpx;
  margin-top: 40rpx;
  
  button {
    flex: 1;
    padding: 24rpx;
    border-radius: 8rpx;
    font-size: 32rpx;
    font-weight: 500;
    border: none;
  }
  
  .btn-cancel {
    background: #f3f4f6;
    color: #374151;
  }
  
  .btn-confirm {
    background: #f97316;
    color: white;
    
    &:disabled {
      background: #d1d5db;
      color: #9ca3af;
    }
  }
}

.history-section {
  background: white;
  padding: 30rpx;
  border-radius: 12rpx;
  box-shadow: 0 2rpx 8rpx rgba(0, 0, 0, 0.1);
  
  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24rpx;
    
    .refresh-btn {
      font-size: 26rpx;
      color: #f97316;
      padding: 8rpx 16rpx;
      border: 1rpx solid #f97316;
      border-radius: 4rpx;
    }
  }
  
  .empty-state {
    text-align: center;
    padding: 60rpx;
    color: #9ca3af;
    font-size: 28rpx;
  }
  
  .history-list {
    .history-item {
      padding: 20rpx;
      border: 1rpx solid #e5e7eb;
      border-radius: 8rpx;
      margin-bottom: 16rpx;
      
      .history-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 12rpx;
        
        .history-package {
          font-size: 28rpx;
          color: #111827;
          font-weight: 500;
        }
        
        .history-time {
          font-size: 24rpx;
          color: #6b7280;
        }
      }
      
      .history-detail {
        display: flex;
        justify-content: space-between;
        align-items: center;
        
        .history-barcode {
          font-size: 24rpx;
          color: #6b7280;
        }
        
        .history-status {
          font-size: 24rpx;
          color: #f59e0b;
          
          &.confirmed {
            color: #10b981;
          }
        }
      }
    }
  }
}

.loading-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
  
  .loading-content {
    background: white;
    padding: 60rpx 80rpx;
    border-radius: 12rpx;
    
    text {
      font-size: 32rpx;
      color: #111827;
    }
  }
}
</style>