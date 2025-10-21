<template>
  <view class="container">
    <view class="header">
      <text class="title">{{ $t('stock.scan') }}</text>
      <view class="scan-info">
        <text class="info-text">{{ $t('stock.scanInfo') }}</text>
      </view>
    </view>

    <!-- 扫码区域 -->
    <view class="scan-section">
      <view class="scan-button" @click="startScan">
        <view class="scan-icon">📷</view>
        <text class="scan-text">{{ $t('stock.clickToScan') }}</text>
      </view>
      
      <view v-if="scanResult" class="scan-result">
        <text class="result-title">{{ $t('stock.scanResult') }}:</text>
        <text class="result-code">{{ scanResult }}</text>
        
        <!-- 解析后的结果展示 -->
        <view v-if="parsedBarcode" class="parsed-result">
          <view v-if="parsedBarcode.success" class="parse-success">
            <view class="parse-header">
              <text class="parse-title">{{ $t('stock.identifiedInfo') }}:</text>
              <text class="parse-format">[{{ getFormatName(parsedBarcode.format) }}]</text>
            </view>
            
            <view class="parse-details">
              <view v-if="parsedBarcode.sn" class="detail-item">
                <text class="detail-label">{{ $t('stock.serialNumber') }}:</text>
                <text class="detail-value sn-value">{{ parsedBarcode.sn }}</text>
              </view>
              
              <view v-if="parsedBarcode.mac1" class="detail-item">
                <text class="detail-label">{{ $t('stock.macAddress') }}:</text>
                <text class="detail-value mac-value">{{ formatMacAddress(parsedBarcode.mac1) }}</text>
              </view>
              
              <view v-if="parsedBarcode.mac2" class="detail-item">
                <text class="detail-label">{{ $t('stock.macAddress') }}2:</text>
                <text class="detail-value mac-value">{{ formatMacAddress(parsedBarcode.mac2) }}</text>
              </view>
            </view>
          </view>
          
          <view v-else class="parse-error">
            <text class="error-icon">⚠️</text>
            <text class="error-text">{{ parsedBarcode.error }}</text>
          </view>
        </view>
      </view>
    </view>

    <!-- 工单选择 -->
    <view v-if="availablePackages.length > 0" class="work-order-section">
      <view class="section-title">{{ $t('stock.selectWorkOrderOptional') }}</view>
      <picker @change="onWorkOrderChange" :value="selectedWorkOrderIndex" :range="workOrderOptions">
        <view class="picker-input">
          <text>{{ selectedWorkOrder ? selectedWorkOrder.title : $t('stock.noWorkOrder') }}</text>
          <text class="picker-arrow">▼</text>
        </view>
      </picker>
    </view>

    <!-- 套装选择 -->
    <view v-if="availablePackages.length > 1" class="package-section">
      <view class="section-title">{{ $t('stock.choosePackage') }}</view>
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
          <text class="package-type">{{ $t('stock.suitableFor') }}: {{ pkg.site_type || $t('common.all') }}</text>
        </view>
      </view>
    </view>

    <!-- 套装清单 -->
    <view v-if="selectedPackage" class="package-detail">
      <view class="section-title">{{ $t('stock.packageConfirm') }}</view>
      
      <view class="package-info">
        <view class="info-row">
          <text class="info-label">{{ $t('stock.packageNameLabel') }}:</text>
          <text class="info-value">{{ selectedPackage.package_name }}</text>
        </view>
        <view class="info-row">
          <text class="info-label">{{ $t('stock.packageCodeLabel') }}:</text>
          <text class="info-value">{{ selectedPackage.package_code }}</text>
        </view>
      </view>
      
      <view class="items-list">
        <view v-for="item in selectedPackage.items" :key="item.equipment_id" class="item-card">
          <view class="item-header">
            <text class="item-name">{{ item.equipment_name }}</text>
            <view class="item-quantity">
              <text class="quantity-text">{{ item.quantity }} {{ item.unit }}</text>
              <text v-if="item.is_required" class="required-tag">{{ $t('stock.requiredTag') }}</text>
            </view>
          </view>
          <text class="item-code">{{ $t('stock.codeLabel') }}: {{ item.equipment_code }}</text>
        </view>
      </view>
      
      <!-- 确认按钮 -->
      <view class="action-buttons">
        <button class="btn-cancel" @click="resetScan">{{ $t('stock.rescan') }}</button>
        <button class="btn-confirm" @click="confirmPickup" :disabled="confirming">
          {{ confirming ? $t('stock.confirming') : $t('stock.confirmPickup') }}
        </button>
      </view>
    </view>

    <!-- 领料记录 -->
    <view class="history-section">
      <view class="section-title">
        <text>{{ $t('stock.myPickups') }}</text>
        <text class="refresh-btn" @click="loadPickupHistory">{{ $t('common.refresh') }}</text>
      </view>
      
      <view v-if="pickupHistory.length === 0" class="empty-state">
        <text>{{ $t('stock.noPickupRecords') }}</text>
      </view>
      
      <view v-else class="history-list">
        <view v-for="record in pickupHistory" :key="record.id" class="history-item">
          <view class="history-header">
            <text class="history-package">{{ record.package_name }}</text>
            <text class="history-time">{{ formatTime(record.pickup_time) }}</text>
          </view>
          <view class="history-detail">
            <text class="history-barcode">{{ $t('stock.barcodeLabel') }}: {{ record.main_device_barcode }}</text>
            <text class="history-status" :class="{ 'confirmed': record.is_confirmed }">
              {{ record.is_returned ? $t('stock.statusReturned') : (record.is_confirmed ? $t('stock.statusConfirmed') : $t('stock.statusPending')) }}
            </text>
          </view>
          
          <!-- 显示解析后的设备信息 -->
          <view v-if="record.serial_number || record.mac_address_1 || record.mac_address_2" class="history-parsed-info">
            <view v-if="record.serial_number" class="parsed-info-item">
              <text class="parsed-label">{{ $t('stock.serialNumber') }}:</text>
              <text class="parsed-value">{{ record.serial_number }}</text>
            </view>
            <view v-if="record.mac_address_1" class="parsed-info-item">
              <text class="parsed-label">MAC1:</text>
              <text class="parsed-value">{{ formatMacAddress(record.mac_address_1) }}</text>
            </view>
            <view v-if="record.mac_address_2" class="parsed-info-item">
              <text class="parsed-label">MAC2:</text>
              <text class="parsed-value">{{ formatMacAddress(record.mac_address_2) }}</text>
            </view>
          </view>
          <view class="history-actions" v-if="showReturnAction">
            <button v-if="!record.is_returned" class="btn-outline btn-sm" @click="confirmReturn(record)">{{ $t('stock.return') }}</button>
          </view>
        </view>
      </view>
    </view>

    <!-- Loading遮罩 -->
    <view v-if="loading" class="loading-mask">
      <view class="loading-content">
        <text>{{ $t('stock.processing') }}</text>
      </view>
    </view>
  </view>
</template>

<script>
import { parseBarcode, formatMacAddress, getParseResultSummary, isValidParseResult } from '@/utils/barcode-parser.js'
import { buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
import { useUserStore } from '@/stores/user'

export default {
  setup() {
    const userStore = useUserStore()
    return {
      userStore
    }
  },
  
  data() {
    return {
      scanResult: '',
      parsedBarcode: null, // 解析后的条码信息
      selectedPackageIndex: 0,
      selectedWorkOrderIndex: 0,
      availablePackages: [],
      myWorkOrders: [],
      pickupHistory: [],
      loading: false,
      confirming: false,
      userLocation: null,
      // 临时隐藏“归还”功能入口，后续设计完善后再开启
      showReturnAction: false
    }
  },
  
  computed: {
    selectedPackage() {
      return this.availablePackages[this.selectedPackageIndex]
    },
    
    selectedWorkOrder() {
      // 如果选择索引为0，表示"无关联工单"，返回null
      if (this.selectedWorkOrderIndex === 0) {
        return null
      }
      // 否则返回对应的工单（需要减1，因为第0项是"无关联工单"）
      return this.myWorkOrders[this.selectedWorkOrderIndex - 1]
    },
    
    workOrderOptions() {
      return [this.$t('stock.noWorkOrder'), ...this.myWorkOrders.map(workOrder => workOrder.title)]
    }
  },
  
  onLoad() {
    this.loadMyWorkOrders()
    this.loadPickupHistory()
    this.getCurrentLocation()
  },
  
  methods: {
    async startScan() {
      try {
        console.log('开始扫码...')
        const result = await new Promise((resolve, reject) => {
          uni.scanCode({
            scanType: ['barCode', 'qrCode'],
            success: resolve,
            fail: reject
          })
        })
        
        console.log('=== 扫码原始结果 ===')
        console.log('result:', result)
        console.log('result.result:', result.result)
        console.log('result类型:', typeof result.result)
        console.log('result长度:', result.result ? result.result.length : 0)
        
        this.scanResult = result.result
        
        console.log('=== 开始解析条码 ===')
        console.log('调用parseBarcode，输入:', result.result)
        this.parsedBarcode = parseBarcode(result.result)
        
        console.log('=== 解析结果 ===')
        console.log('parsedBarcode:', JSON.stringify(this.parsedBarcode, null, 2))
        console.log('解析成功?:', this.parsedBarcode.success)
        console.log('SN:', this.parsedBarcode.sn)
        console.log('MAC1:', this.parsedBarcode.mac1)
        console.log('MAC2:', this.parsedBarcode.mac2)
        console.log('格式:', this.parsedBarcode.format)
        
        if (!this.parsedBarcode.success) {
          console.log('=== 解析失败 ===')
          console.log('错误信息:', this.parsedBarcode.error)
          uni.showToast({
            title: this.parsedBarcode.error,
            icon: 'none'
          })
          return
        }
        
        console.log('=== 验证解析结果 ===')
        const isValid = isValidParseResult(this.parsedBarcode)
        console.log('isValidParseResult:', isValid)
        
        if (!isValid) {
          console.log('=== 验证失败 ===')
          uni.showToast({
            title: this.$t('stock.invalidBarcode'),
            icon: 'none'
          })
          return
        }
        
        console.log('=== 开始处理扫码数据 ===')
        this.processScannedCode(this.parsedBarcode)
      } catch (error) {
        console.error('扫码失败:', error)
        uni.showToast({
          title: this.$t('stock.scanFailed'),
          icon: 'none'
        })
      }
    },
    
    async processScannedCode(parsedData) {
      console.log('=== 开始后台查询 ===')
      console.log('parsedData输入:', JSON.stringify(parsedData, null, 2))
      console.log('查询用的SN:', parsedData.sn)
      
      this.loading = true
      
      try {
        // 使用解析后的SN查询设备信息
        const queryUrl = `/api/equipment/${parsedData.sn}/barcode-info`
        console.log('=== API查询 ===')
        console.log('查询URL:', queryUrl)
        const fullApiUrl = buildApiUrl(queryUrl)
        console.log('完整API地址:', fullApiUrl)
        
        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: fullApiUrl,
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            success: resolve,
            fail: reject
          })
        })
        
        console.log('=== API响应 ===')
        console.log('响应状态:', response.status)
        console.log('响应数据:', JSON.stringify(response.data || response, null, 2))
        console.log('设备信息:', response.equipment || response.data?.equipment)
        console.log('可用套装:', response.available_packages || response.data?.available_packages)
        console.log('设备实例:', response.equipment_instance || response.data?.equipment_instance)
        
        const equipmentData = response.data || response
        
        if (equipmentData.equipment && equipmentData.available_packages && equipmentData.available_packages.length > 0) {
          console.log('=== 查询成功 ===')
          console.log('找到设备:', equipmentData.equipment.name)
          console.log('可用套装数量:', equipmentData.available_packages.length)
          
          this.availablePackages = equipmentData.available_packages
          this.selectedPackageIndex = 0
          
          uni.showToast({
            title: this.$t('stock.deviceRecognizedToast', { name: equipmentData.equipment.name }),
            icon: 'success'
          })
        } else {
          console.log('=== 查询失败 ===')
          console.log('设备存在?:', !!equipmentData.equipment)
          console.log('套装存在?:', !!equipmentData.available_packages)
          console.log('套装数量:', equipmentData.available_packages ? equipmentData.available_packages.length : 0)
          
          // 显示详细的设备识别信息
          let message = `${this.$t('stock.deviceNotRegisteredTitle')}\n${this.$t('stock.serialNumber')}: ${parsedData.sn}`
          if (parsedData.mac1) {
            message += `\nMAC: ${this.formatMacAddress(parsedData.mac1)}`
          }
          if (parsedData.mac2) {
            message += `\nMAC2: ${this.formatMacAddress(parsedData.mac2)}`
          }
          message += `\n\n${this.$t('stock.deviceNotRegisteredHint')}`
          
          uni.showModal({
            title: this.$t('stock.deviceNotRegisteredTitle'),
            content: message,
            showCancel: true,
            confirmText: this.$t('stock.rescan'),
            cancelText: this.$t('stock.copySn'),
            success: (res) => {
              if (res.confirm) {
                this.resetScan()
              } else {
                // 复制SN到剪贴板
                uni.setClipboardData({
                  data: parsedData.sn,
                  success: () => {
                    uni.showToast({ title: this.$t('stock.copySn'), icon: 'success' })
                  }
                })
              }
            }
          })
        }
      } catch (error) {
        console.error('=== API请求失败 ===')
        console.error('错误详情:', error)
        console.error('错误响应:', error.response?.data)
        console.error('错误状态:', error.response?.status)
        console.error('错误消息:', error.message)
        
        uni.showToast({
          title: this.$t('messages.operationFailed') + ': ' + (error.response?.data?.detail || error.message),
          icon: 'none'
        })
      } finally {
        this.loading = false
      }
    },
    
    selectPackage(index) {
      this.selectedPackageIndex = index
    },
    
    onWorkOrderChange(e) {
      this.selectedWorkOrderIndex = e.detail.value
    },
    
    async confirmPickup() {
      if (!this.selectedPackage) {
        uni.showToast({ title: this.$t('stock.pleaseSelectPackage'), icon: 'none' })
        return
      }
      
      try {
        this.confirming = true
        
        const pickupData = {
          barcode: this.scanResult,
          parsed_barcode: this.parsedBarcode, // 传递解析后的数据
          package_id: this.selectedPackage.id,
          work_order_id: this.selectedWorkOrder?.id || null,
          gps_location: this.userLocation
        }
        
        console.log('🚀 [confirmPickup] 开始确认领料')
        console.log('🚀 [confirmPickup] 请求数据:', pickupData)
        
        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/scan-checkout'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: pickupData,
            success: resolve,
            fail: reject
          })
        })
        
        console.log('🚀 [confirmPickup] 完整响应:', response)
        console.log('🚀 [confirmPickup] 响应数据:', response.data)
        console.log('🚀 [confirmPickup] 响应状态码:', response.statusCode)
        
        const responseData = response.data
        
        if (responseData.action === 'checkout_success') {
          uni.showModal({
            title: this.$t('stock.pickupSuccessTitle'),
            content: `${this.$t('stock.documentNumber')}: ${responseData.document_number}\n${this.$t('stock.packageLabel')}: ${responseData.package.name}`,
            showCancel: false,
            confirmText: this.$t('common.confirm'),
            success: () => {
              this.resetScan()
              this.loadPickupHistory()
            }
          })
        } else if (responseData.action === 'already_picked') {
          uni.showModal({
            title: this.$t('stock.pickupSuccessTitle'),
            content: this.$t('stock.alreadyPicked', { picked_at: responseData.picked_at || '' }),
            showCancel: false,
            confirmText: this.$t('common.confirm'),
            success: () => {
              this.resetScan()
              this.loadPickupHistory()
            }
          })
        } else if (responseData.action === 'insufficient_stock') {
          let shortage = responseData.shortage_items.map(item => 
            `${item.equipment_name}: ${this.$t('stock.requiredLabel')}${item.required}，${this.$t('stock.availableLabel')}${item.available}`
          ).join('\n')
          
          uni.showModal({
            title: this.$t('stock.insufficientStockTitle'),
            content: shortage,
            showCancel: false
          })
        } else {
          console.warn('🚀 [confirmPickup] 未知的响应类型:', responseData.action)
          uni.showToast({
            title: this.$t('stock.responseUnknown'),
            icon: 'none'
          })
        }
      } catch (error) {
        console.error('🚀 [confirmPickup] 确认领料失败:', error)
        console.error('🚀 [confirmPickup] 错误详情:', error.data)
        console.error('🚀 [confirmPickup] 错误状态码:', error.statusCode)
        
        let errorMessage = this.$t('messages.networkError')
        if (error.data?.detail) {
          errorMessage = error.data.detail
        } else if (error.statusCode) {
          errorMessage = `服务器错误 (${error.statusCode})`
        }
        
        uni.showToast({
          title: this.$t('stock.pickupFailedPrefix') + errorMessage,
          icon: 'none',
          duration: 3000
        })
      } finally {
        this.confirming = false
        console.log('🚀 [confirmPickup] 领料确认流程结束')
      }
    },
    
    resetScan() {
      this.scanResult = ''
      this.parsedBarcode = null
      this.availablePackages = []
      this.selectedPackageIndex = 0
      this.selectedWorkOrderIndex = 0
    },
    
    getFormatName(format) {
      const map = {
        'sn_mac_comma': this.$t('stock.formatSnMacComma'),
        'key_value_pairs': this.$t('stock.formatKeyValuePairs'),
        'pure_sn': this.$t('stock.formatPureSn')
      }
      return map[format] || this.$t('stock.formatUnknown')
    },
    
    formatMacAddress(mac) {
      return formatMacAddress(mac)
    },
    
    async loadMyWorkOrders() {
      try {
        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/work-orders/'),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            data: { status_filter: 'ACTIVE' },
            success: resolve,
            fail: reject
          })
        })
        this.myWorkOrders = response.data || []
        console.log('加载工单列表成功:', this.myWorkOrders.length, '个工单')
      } catch (error) {
        console.error('加载工单列表失败:', error)
      }
    },
    
    async loadPickupHistory() {
      try {
        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/my-pickups'),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            success: resolve,
            fail: reject
          })
        })
        this.pickupHistory = response.data?.pickup_records || []
      } catch (error) {
        console.error('加载领料记录失败:', error)
      }
    },
    
    confirmReturn(record) {
      if (!record) return
      uni.showModal({
        title: this.$t('stock.returnConfirmTitle'),
        content: this.$t('stock.returnConfirmContent'),
        confirmText: this.$t('common.confirm'),
        cancelText: this.$t('common.cancel'),
        success: (res) => {
          if (res.confirm) {
            this.returnPickup(record)
          }
        },
      })
    },
    
    async returnPickup(record) {
      if (!record || !record.id) return
      try {
        this.loading = true
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/return-pickup'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: { pickup_record_id: record.id, notes: 'App端归还' },
            success: resolve,
            fail: reject,
          })
        })
        if (res.statusCode === 200) {
          uni.showToast({ title: this.$t('stock.returnSuccess'), icon: 'success' })
          this.loadPickupHistory()
        } else {
          uni.showToast({ title: this.$t('stock.returnFailed'), icon: 'none' })
        }
      } catch (error) {
        const msg = error?.data?.detail || this.$t('stock.returnFailed')
        uni.showToast({ title: msg, icon: 'none' })
      } finally {
        this.loading = false
      }
    },
    
    async getCurrentLocation() {
      try {
        console.log('使用原生插件获取当前位置...')
        
        // 获取原生定位插件
        const locationPlugin = uni.requireNativePlugin('my-location-plugin')
        
        if (!locationPlugin) {
          throw new Error('原生定位插件未加载')
        }
        
        // 调用插件的同步定位方法
        const result = locationPlugin.getLocationSync()
        console.log('原生插件位置结果:', result)
        
        // 解析结果
        let parsedResult = result
        if (typeof result === 'string') {
          try {
            parsedResult = JSON.parse(result)
          } catch (parseError) {
            console.error('解析原生插件结果失败:', parseError)
            return
          }
        }
        
        if (parsedResult && parsedResult.success && parsedResult.data) {
          const data = parsedResult.data
          this.userLocation = {
            latitude: data.latitude,
            longitude: data.longitude,
            accuracy: data.accuracy || 0
          }
        } else {
          console.warn('原生插件获取位置失败:', parsedResult?.message)
        }
        
      } catch (error) {
        console.warn('原生插件获取位置失败:', error.message)
      }
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
.container { background-color: var(--bg-page); min-height: 100vh; padding: 20rpx; }

.header {
  background: var(--bg-elevated);
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow-card);
  
  .title {
    font-size: 36rpx;
    font-weight: 600;
    color: var(--text-primary);
    display: block;
    margin-bottom: 16rpx;
  }
  
  .scan-info {
    .info-text {
      font-size: 28rpx;
      color: var(--text-secondary);
    }
  }
}

.scan-section {
  background: var(--bg-elevated);
  padding: 40rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow-card);
  text-align: center;
  
  .scan-button {
    background: linear-gradient(135deg, var(--color-primary), var(--color-primary-light));
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
      word-break: break-all;
    }
    
    .parsed-result {
      margin-top: 20rpx;
      
      .parse-success {
        background: #ffffff;
        border: 1rpx solid #10b981;
        border-radius: 8rpx;
        padding: 20rpx;
        
        .parse-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 16rpx;
          
          .parse-title {
            font-size: 28rpx;
            color: #065f46;
            font-weight: 600;
          }
          
          .parse-format {
            font-size: 22rpx;
            color: #059669;
            background: #d1fae5;
            padding: 4rpx 8rpx;
            border-radius: 4rpx;
          }
        }
        
        .parse-details {
          .detail-item {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12rpx;
            
            &:last-child {
              margin-bottom: 0;
            }
            
            .detail-label {
              font-size: 26rpx;
              color: #374151;
              font-weight: 500;
            }
            
            .detail-value {
              font-size: 26rpx;
              font-weight: 600;
              max-width: 60%;
              text-align: right;
              word-break: break-all;
              
              &.sn-value {
                color: #1d4ed8;
              }
              
              &.mac-value {
                color: #7c3aed;
                font-family: monospace;
              }
            }
          }
        }
      }
      
      .parse-error {
        background: #fef2f2;
        border: 1rpx solid #fca5a5;
        border-radius: 8rpx;
        padding: 20rpx;
        display: flex;
        align-items: center;
        gap: 12rpx;
        
        .error-icon {
          font-size: 32rpx;
        }
        
        .error-text {
          font-size: 26rpx;
          color: #dc2626;
          flex: 1;
        }
      }
    }
  }
}

.work-order-section, .package-section {
  background: var(--bg-elevated);
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow-card);
}

.section-title {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 20rpx;
  display: block;
}

.picker-input {
  min-height: 88rpx;
  padding: 0 20rpx;
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
    
    &.selected { border-color: var(--color-primary); background: #fff7ed; }
    
    .package-header {
      display: flex;
      justify-content: space-between;
      margin-bottom: 8rpx;
      
      .package-name {
        font-size: 30rpx;
        font-weight: 500;
        color: var(--text-primary);
      }
      
      .package-code {
        font-size: 24rpx;
        color: #6b7280;
      }
    }
    
    .package-type {
      font-size: 26rpx; color: var(--color-primary);
    }
  }
}

.package-detail {
  background: var(--bg-elevated);
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow-card);
  
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
      
      .info-value { font-size: 28rpx; color: var(--text-primary); font-weight: 500; }
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
          
          .quantity-text { font-size: 28rpx; color: var(--color-primary); font-weight: 600; }
          
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
  
  button { flex: 1; min-height: 88rpx; padding: 0 24rpx; border-radius: 12rpx; font-size: 32rpx; font-weight: 500; border: none; display: inline-flex; align-items: center; justify-content: center; }
  
  .btn-cancel {
    background: #f3f4f6;
    color: #374151;
  }
  
  .btn-confirm {
    background: var(--color-primary);
    color: white;
    
    &:disabled {
      background: #d1d5db;
      color: #9ca3af;
    }
  }
}

.history-section {
  background: var(--bg-elevated);
  padding: 30rpx;
  border-radius: 12rpx;
  box-shadow: var(--shadow-card);
  
  .section-title {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24rpx;
    
      .refresh-btn { display: inline-flex; align-items: center; justify-content: center; min-height: 88rpx; padding: 0 24rpx; font-size: 26rpx; color: var(--color-primary); border: 1rpx solid var(--color-primary); border-radius: 12rpx; }
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
        
        .history-package { font-size: 28rpx; color: var(--text-primary); font-weight: 500; }
        
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
      
      .history-parsed-info {
        margin-top: 12rpx;
        padding-top: 12rpx;
        border-top: 1rpx solid #f3f4f6;
        
        .parsed-info-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8rpx;
          
          &:last-child {
            margin-bottom: 0;
          }
          
          .parsed-label {
            font-size: 22rpx;
            color: #9ca3af;
            font-weight: 500;
          }
          
          .parsed-value {
            font-size: 22rpx;
            color: #374151;
            font-family: monospace;
            max-width: 60%;
            text-align: right;
            word-break: break-all;
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
    background: var(--bg-elevated);
    padding: 60rpx 80rpx;
    border-radius: 12rpx;
    
    text {
      font-size: 32rpx;
      color: var(--text-primary);
    }
  }
}

/* 统一按钮与动作区域样式 */
.history-actions {
  margin-top: 12rpx;
  display: flex;
  justify-content: flex-end;
  gap: 12rpx;
}

.btn-outline { background: #ffffff; color: var(--color-primary); border: 1rpx solid var(--color-primary); display: inline-flex; align-items: center; justify-content: center; min-height: 88rpx; padding: 0 24rpx; border-radius: 12rpx; font-size: 26rpx; }

.btn-sm { min-height: 88rpx; padding: 0 20rpx; font-size: 26rpx; }
</style>
