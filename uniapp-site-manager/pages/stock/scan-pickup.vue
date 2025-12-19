<template>
  <view class="container">
    <CustomNavbar :title="$t('stock.scanPickup')" :showBack="true" variant="brand" />

    <scroll-view class="page-content" scroll-y>
      <view class="header">
        <view class="scan-info">
          <text class="info-text">{{ $t('stock.myDevicesInfo') }}</text>
        </view>
      </view>

    <!-- 扫码领货（默认折叠） -->
    <view class="scan-fold">
      <view class="scan-fold-header" :class="{ expanded: !scanSectionCollapsed }" @click="toggleScanSection">
        <view class="scan-fold-left">
          <uni-icons type="scan" size="18" color="var(--color-primary)" />
          <text class="scan-fold-title">{{ $t('stock.scanPickupAction') }}</text>
        </view>
        <view class="scan-fold-right">
          <view class="scan-fold-scan-btn" @click.stop="startScanFromCollapsed">
            <uni-icons type="scan" size="16" color="#ffffff" />
            <text class="scan-fold-scan-text">{{ $t('stock.scanNow') }}</text>
          </view>
          <uni-icons :type="scanSectionCollapsed ? 'arrow-down' : 'arrow-up'" size="18" color="#6b7280" />
        </view>
      </view>

      <view v-if="!scanSectionCollapsed" class="scan-fold-body">
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
                    <text class="detail-label">{{ $t('stock.macAddress1') }}:</text>
                    <text class="detail-value mac-value">{{ formatMacAddress(parsedBarcode.mac1) }}</text>
                  </view>
                  
                  <view v-if="parsedBarcode.mac2" class="detail-item">
                    <text class="detail-label">{{ $t('stock.macAddress2') }}:</text>
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

        <!-- 出库仓库选择 -->
        <view v-if="availablePackages.length > 0" class="work-order-section">
          <view class="section-title">{{ $t('stock.selectCheckoutWarehouse') }}</view>
          <picker @change="onWarehouseChange" :value="selectedWarehouseIndex" :range="warehouseOptions">
            <view class="picker-input">
              <text>{{ selectedWarehouse ? selectedWarehouse.warehouse_name : $t('common.pleaseSelect') }}</text>
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
      </view>
	    </view>

	    <!-- 我的设备列表 -->
	    <view class="history-section">
	      <view class="section-title">
	        <text>{{ $t('stock.myDevicesList') }}</text>
	        <view class="refresh-icon" @click="refreshPickupHistory">
	          <uni-icons type="refreshempty" size="20" color="#2563eb" />
	        </view>
	      </view>

      <view class="pickup-toolbar">
        <input
          class="pickup-search"
          v-model="pickupSearch"
          :placeholder="$t('stock.pickupSearchPlaceholder')"
          confirm-type="search"
          @confirm="onPickupSearch"
        />
        <view class="pickup-toolbar-actions">
          <button class="pickup-search-btn" @click="onPickupSearch">{{ $t('common.search') }}</button>
          <button v-if="pickupSearch" class="pickup-clear-btn" @click="clearPickupSearch">{{ $t('common.clear') }}</button>
        </view>
      </view>

      <view class="pickup-tabs">
        <view
          v-for="t in pickupTabOptions"
          :key="t.key"
          class="pickup-tab"
          :class="{ active: pickupTab === t.key }"
          @click="switchPickupTab(t.key)"
        >
          <text class="pickup-tab-label">{{ t.label }}</text>
          <text class="pickup-tab-count">{{ t.count }}</text>
        </view>
      </view>
      
      <view v-if="pickupLoading" class="empty-state">
        <text>{{ $t('common.loading') }}</text>
      </view>

      <view v-else-if="pickupHistory.length === 0" class="empty-state">
        <text>{{ $t('stock.noPickupRecords') }}</text>
      </view>
      
      <view v-else class="history-list">
        <view v-for="record in pickupHistory" :key="record.id" class="history-item" @click="openDeviceDetail(record)">
          <view class="history-header">
            <text class="history-sn">{{ record.serial_number || record.main_device_barcode }}</text>
            <text class="history-time">{{ formatTime(record.pickup_time) }}</text>
          </view>
          <view class="history-detail">
            <text class="history-barcode">{{ $t('stock.packageLabel') }}: {{ record.package_name }}</text>
            <text class="history-status" :class="historyStatusClass(record)">
              {{ getHistoryStatusText(record) }}
            </text>
          </view>
          
          <!-- 次要信息（可选）：条码与MAC -->
          <view
            v-if="(record.main_device_barcode && record.main_device_barcode !== record.serial_number) || record.mac_address_1 || record.mac_address_2"
            class="history-parsed-info"
          >
            <view
              v-if="record.main_device_barcode && record.main_device_barcode !== record.serial_number"
              class="parsed-info-item"
            >
              <text class="parsed-label">{{ $t('stock.barcodeLabel') }}:</text>
              <text class="parsed-value">{{ record.main_device_barcode }}</text>
            </view>
            <view v-if="record.mac_address_1" class="parsed-info-item">
              <text class="parsed-label">{{ $t('stock.macAddress1') }}:</text>
              <text class="parsed-value">{{ formatMacAddress(record.mac_address_1) }}</text>
            </view>
            <view v-if="record.mac_address_2" class="parsed-info-item">
              <text class="parsed-label">{{ $t('stock.macAddress2') }}:</text>
              <text class="parsed-value">{{ formatMacAddress(record.mac_address_2) }}</text>
            </view>
          </view>
        </view>

        <view class="history-load-more" v-if="pickupHasMore">
          <button class="load-more-btn" :disabled="pickupLoadingMore" @click="loadMorePickupHistory">
            {{ pickupLoadingMore ? $t('common.loading') : $t('stock.loadMore') }}
          </button>
        </view>
	      </view>
	    </view>
    </scroll-view>

    <!-- Loading遮罩 -->
    <view v-if="loading" class="loading-mask">
      <view class="loading-content">
        <text>{{ $t('stock.processing') }}</text>
      </view>
    </view>

    <!-- 设备详情 Bottom Sheet -->
    <view class="device-modal-mask" v-if="deviceDetailVisible" @click="closeDeviceDetail">
      <view class="device-modal" @click.stop>
        <view class="device-modal-header">
          <text class="device-modal-title">{{ $t('stock.deviceDetailsTitle') }}</text>
          <view class="device-modal-close" @click="closeDeviceDetail">
            <uni-icons type="closeempty" size="20" color="#6b7280" />
          </view>
        </view>

        <view class="device-modal-body" v-if="deviceDetailRecord">
          <view class="device-summary">
            <view class="summary-row">
              <text class="summary-label">{{ $t('stock.serialNumber') }}</text>
              <view class="summary-value-wrap">
                <text class="summary-value mono">{{ deviceDetailSn }}</text>
                <text class="summary-action" @click="copyDeviceSn">{{ $t('stock.copySn') }}</text>
              </view>
            </view>
            <view v-if="deviceDetailRecord.package_name" class="summary-row">
              <text class="summary-label">{{ $t('stock.packageLabel') }}</text>
              <text class="summary-value">{{ deviceDetailRecord.package_name }}</text>
            </view>
            <view class="summary-row">
              <text class="summary-label">{{ $t('common.status') }}</text>
              <text class="status-badge" :class="deviceStatusBadgeClass">{{ deviceStatusBadgeText }}</text>
            </view>
            <view v-if="deviceDetailRecord.return_document_number" class="summary-row">
              <text class="summary-label">{{ $t('stock.returnDocumentNumber') }}</text>
              <text class="summary-value mono">{{ deviceDetailRecord.return_document_number }}</text>
            </view>
            <view v-if="deviceDetailRecord.return_warehouse_name" class="summary-row">
              <text class="summary-label">{{ $t('stock.returnWarehouseLabel') }}</text>
              <text class="summary-value">{{ deviceDetailRecord.return_warehouse_name }}</text>
            </view>
            <view v-if="deviceDetailRecord.equipment_instance && deviceDetailRecord.equipment_instance.warehouse_name" class="summary-row">
              <text class="summary-label">{{ $t('stock.warehouse') }}</text>
              <text class="summary-value">{{ deviceDetailRecord.equipment_instance.warehouse_name }}</text>
            </view>
          </view>

          <view class="device-section">
            <view class="device-section-title-row">
              <text class="device-section-title">{{ $t('stock.deviceBindingsTitle') }}</text>
              <view class="device-section-action" @click="refreshDeviceDetailPreview">
                <uni-icons type="refreshempty" size="18" color="#2563eb" />
              </view>
            </view>

            <view v-if="deviceDetailPreviewLoading" class="device-loading">
              <text>{{ $t('common.loading') }}</text>
            </view>

            <view v-else>
              <view v-if="deviceDetailPreviewAction === 'unbind_blocked'" class="return-hint-card">
                <view class="hint-header warning">
                  <text class="hint-title">{{ $t('stock.unbindBlockedTitle') }}</text>
                  <text class="hint-desc">{{ $t('stock.unbindBlockedTip') }}</text>
                </view>
              </view>

              <view v-if="deviceDetailPreviewAction === 'need_unbind'" class="return-hint-card">
                <view class="hint-header info">
                  <text class="hint-title">{{ $t('stock.needUnbindTitle') }}</text>
                  <text class="hint-desc">{{ $t('stock.needUnbindTip') }}</text>
                </view>
              </view>

              <view
                v-if="deviceDetailBindings.length > 0"
                class="bind-list"
              >
                <view
                  v-for="(b, idx) in deviceDetailBindings"
                  :key="`${b.inspection_id || idx}`"
                  class="bind-item"
                >
                  <view class="bind-head">
                    <text class="bind-title">{{ bindingTitle(b) }}</text>
                    <text class="status-tag" :class="inspectionStatusTagClass(b.inspection_status)">
                      {{ inspectionStatusText(b.inspection_status) }}
                    </text>
                  </view>
                  <view class="bind-meta">
                    <text class="meta-item">{{ $t('stock.sectorBandLabel') }}: {{ sectorBandText(b) }}</text>
                    <text v-if="bindingSiteName(b)" class="meta-item">{{ $t('stock.siteLabel') }}: {{ bindingSiteName(b) }}</text>
                  </view>
                  <text v-if="deviceDetailPreviewAction === 'unbind_blocked'" class="bind-reason">{{ bindingReasonText(b) }}</text>
                </view>
              </view>

              <view v-else class="device-empty">
                <text v-if="deviceDetailPreviewAction === 'error'">
                  {{ deviceDetailPreviewData.detail || deviceDetailPreviewData.message || $t('messages.operationFailed') }}
                </text>
                <text v-else-if="deviceDetailPreviewAction === 'no_active_pickup'">
                  {{ $t('stock.noReturnablePickup') }}
                </text>
                <text v-else>
                  {{ $t('stock.noBindings') }}
                </text>
              </view>
            </view>
          </view>
        </view>

        <view class="device-modal-footer">
          <button class="modal-btn btn-secondary" :disabled="deviceDetailActionLoading" @click="closeDeviceDetail">
            {{ $t('common.close') }}
          </button>
          <button
            v-if="canDeviceUnbind"
            class="modal-btn btn-warning"
            :disabled="deviceDetailActionLoading"
            @click="doDeviceUnbind"
          >
            {{ $t('stock.oneClickUnbind') }}
          </button>
          <button
            v-if="canOpenReturnFromDetail"
            class="modal-btn btn-primary"
            :disabled="deviceDetailActionLoading"
            @click="openReturnFromDetail"
          >
            {{ $t('stock.returnModalTitle') }}
          </button>
        </view>
      </view>
    </view>

	    <!-- 退库弹窗（流程收敛在扫码领料页） -->
	    <view class="return-modal-mask" v-if="returnModalVisible" @click="closeReturnModal">
	      <view class="return-modal" @click.stop>
	        <view class="return-modal-header">
	          <text class="return-modal-title">{{ $t('stock.returnModalTitle') }}</text>
	          <view class="return-modal-close" @click="closeReturnModal">
	            <text class="close-text">×</text>
	          </view>
	        </view>

	        <view class="return-modal-body" v-if="returnRecord">
	          <view class="return-summary">
	            <view class="summary-row">
	              <text class="summary-label">{{ $t('stock.serialNumber') }}</text>
	              <view class="summary-value-wrap">
	                <text class="summary-value mono">{{ returnSummarySn }}</text>
	                <text class="summary-action" @click="copyReturnSn">{{ $t('stock.copySn') }}</text>
	              </view>
	            </view>
	            <view v-if="returnRecord.package_name" class="summary-row">
	              <text class="summary-label">{{ $t('stock.packageLabel') }}</text>
	              <text class="summary-value">{{ returnRecord.package_name }}</text>
	            </view>
	            <view class="summary-row">
	              <text class="summary-label">{{ $t('common.status') }}</text>
	              <text class="status-badge" :class="returnStatusBadgeClass">{{ returnStatusBadgeText }}</text>
	            </view>
	            <view v-if="returnRecord.return_document_number" class="summary-row">
	              <text class="summary-label">{{ $t('stock.returnDocumentNumber') }}</text>
	              <text class="summary-value mono">{{ returnRecord.return_document_number }}</text>
	            </view>
	            <view v-if="returnRecord.return_warehouse_name" class="summary-row">
	              <text class="summary-label">{{ $t('stock.returnWarehouseLabel') }}</text>
	              <text class="summary-value">{{ returnRecord.return_warehouse_name }}</text>
	            </view>
	            <view v-if="returnRecord.return_reject_reason" class="summary-reject-box">
	              <text class="reject-icon">⚠️</text>
	              <text class="reject-text">{{ $t('stock.rejectReason') }}: {{ returnRecord.return_reject_reason }}</text>
	            </view>
	          </view>

	          <view v-if="returnPreviewLoading" class="return-loading">
	            <text>{{ $t('stock.processing') }}</text>
	          </view>

	          <view v-else>
	            <view v-if="returnPreviewAction === 'no_active_pickup'" class="return-hint-card">
	              <text>{{ $t('stock.noReturnablePickup') }}</text>
	            </view>

	            <view v-else-if="returnPreviewAction === 'already_requested'" class="return-hint-card">
	              <view class="hint-header info">
	                <text class="hint-title">{{ $t('stock.alreadyReturnRequested') }}</text>
	                <text class="hint-desc">{{ $t('stock.returnNeedWarehouseConfirmTip') }}</text>
	              </view>
	              <view class="kv-list">
	                <view class="kv-row" v-if="returnPreviewData.return_document_number">
	                  <text class="kv-label">{{ $t('stock.returnDocumentNumber') }}</text>
	                  <text class="kv-value mono">{{ returnPreviewData.return_document_number }}</text>
	                </view>
	                <view class="kv-row" v-if="returnPreviewData.return_status">
	                  <text class="kv-label">{{ $t('common.status') }}</text>
	                  <text class="kv-value">{{ statusTextForReturn(returnPreviewData.return_status) }}</text>
	                </view>
	              </view>
	              <view v-if="canCancelReturn" class="cancel-section">
	                <text class="cancel-label">{{ $t('stock.cancelReasonOptional') }}</text>
	                <input class="cancel-input" v-model="cancelReason" :placeholder="$t('stock.cancelReasonOptional')" />
	              </view>
	            </view>

            <view v-else-if="returnPreviewAction === 'unbind_blocked'" class="return-hint-card">
              <view class="hint-header warning">
                <text class="hint-title">{{ $t('stock.unbindBlockedTitle') }}</text>
                <text class="hint-desc">{{ $t('stock.unbindBlockedTip') }}</text>
              </view>
              <view
	                v-if="returnPreviewData.blocked_bindings && returnPreviewData.blocked_bindings.length > 0"
	                class="bind-list"
	              >
	                <view v-for="(b, idx) in returnPreviewData.blocked_bindings" :key="idx" class="bind-item">
	                  <view class="bind-head">
	                    <text class="bind-title">{{ bindingTitle(b) }}</text>
	                    <text class="status-tag" :class="inspectionStatusTagClass(b.inspection_status)">{{ inspectionStatusText(b.inspection_status) }}</text>
	                  </view>
	                  <view class="bind-meta">
	                    <text class="meta-item">{{ $t('stock.sectorBandLabel') }}: {{ sectorBandText(b) }}</text>
	                    <text v-if="bindingSiteName(b)" class="meta-item">{{ $t('stock.siteLabel') }}: {{ bindingSiteName(b) }}</text>
	                  </view>
	                  <text class="bind-reason">{{ bindingReasonText(b) }}</text>
	                </view>
	              </view>
	            </view>

            <view v-else-if="returnPreviewAction === 'need_unbind'" class="return-hint-card">
              <view class="hint-header info">
                <text class="hint-title">{{ $t('stock.needUnbindTitle') }}</text>
                <text class="hint-desc">{{ $t('stock.needUnbindTip') }}</text>
              </view>
	              <view v-if="returnPreviewData.need_unbind && returnPreviewData.need_unbind.length > 0" class="bind-list">
	                <view v-for="(b, idx) in returnPreviewData.need_unbind" :key="idx" class="bind-item">
	                  <view class="bind-head">
	                    <text class="bind-title">{{ bindingTitle(b) }}</text>
	                    <text class="status-tag" :class="inspectionStatusTagClass(b.inspection_status)">{{ inspectionStatusText(b.inspection_status) }}</text>
	                  </view>
	                  <view class="bind-meta">
	                    <text class="meta-item">{{ $t('stock.sectorBandLabel') }}: {{ sectorBandText(b) }}</text>
	                    <text v-if="bindingSiteName(b)" class="meta-item">{{ $t('stock.siteLabel') }}: {{ bindingSiteName(b) }}</text>
	                  </view>
	                </view>
	              </view>
              <view class="hint-actions">
                <button class="modal-btn btn-outline" :disabled="returnActionLoading" @click="doReturnUnbind">
                  {{ $t('stock.oneClickUnbind') }}
                </button>
                <button class="modal-btn btn-secondary" :disabled="returnActionLoading" @click="refreshReturnPreview">
                  {{ $t('common.refresh') }}
                </button>
              </view>
            </view>

	            <view v-else-if="returnPreviewAction === 'preview_ok'" class="return-preview-ok">
	              <view class="hint-header info">
	                <text class="hint-title">{{ $t('stock.returnRequestReadyTitle') }}</text>
	                <text class="hint-desc">{{ $t('stock.returnNeedWarehouseConfirmTip') }}</text>
	              </view>
	              <view class="return-doc">
	                <text>{{ $t('stock.documentNumber') }}: {{ returnPreviewData.out_document_number }}</text>
	              </view>

              <view class="return-warehouse-section">
                <text class="section-title-sm">{{ $t('stock.selectReturnWarehouse') }}</text>
                <picker
                  @change="onReturnWarehouseChange"
                  :value="returnSelectedWarehouseIndex"
                  :range="returnWarehouseOptions"
                >
                  <view class="picker-input">
                    <text>{{ selectedReturnWarehouse ? selectedReturnWarehouse.warehouse_name : $t('common.pleaseSelect') }}</text>
                    <text class="picker-arrow">▼</text>
                  </view>
                </picker>
              </view>

              <view class="items-list">
                <view v-for="item in (returnPreviewData.items || [])" :key="item.item_id" class="item-card">
                  <view class="item-header">
                    <text class="item-name">{{ item.equipment_name }}</text>
                    <text class="item-quantity">{{ item.quantity }} {{ item.unit }}</text>
                  </view>
                  <text class="item-code">{{ $t('stock.codeLabel') }}: {{ item.equipment_code }}</text>
                </view>
              </view>
            </view>

            <view v-else-if="returnPreviewAction === 'error'" class="return-hint-card">
              <text>{{ returnPreviewData.detail || returnPreviewData.message || $t('messages.operationFailed') }}</text>
            </view>

            <view v-else class="return-hint-card">
              <text>{{ $t('stock.responseUnknown') }}</text>
            </view>
          </view>
        </view>

        <view class="return-modal-footer">
          <button class="modal-btn btn-secondary" :disabled="returnActionLoading" @click="closeReturnModal">
            {{ $t('common.cancel') }}
          </button>
          <button
            v-if="returnPreviewAction === 'preview_ok'"
            class="modal-btn btn-primary"
            :disabled="returnActionLoading"
            @click="submitReturnRequest"
          >
            {{ $t('stock.submitReturnRequest') }}
          </button>
          <button
            v-if="canCancelReturn"
            class="modal-btn btn-danger"
            :disabled="returnActionLoading"
            @click="cancelReturnRequest"
          >
            {{ $t('stock.cancelReturnRequest') }}
          </button>
        </view>
      </view>
    </view>
  </view>
</template>

<script>
import { parseBarcode, formatMacAddress, getParseResultSummary, isValidParseResult } from '@/utils/barcode-parser.js'
import { buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
import { useUserStore } from '@/stores/user'
import { useLanguageStore } from '@/stores/language'
import { getCurrentInstance, watch, onMounted } from 'vue'

export default {
  setup() {
    const userStore = useUserStore()
    const languageStore = useLanguageStore()
    const { appContext } = getCurrentInstance()
    const { $t } = appContext.config.globalProperties

    // 进入页面时设置标题
    onMounted(() => {
      uni.setNavigationBarTitle({
        title: $t('stock.scanPickup')
      })
    })

    // 语言切换时更新标题
    watch(() => languageStore.currentLocale, () => {
      uni.setNavigationBarTitle({
        title: $t('stock.scanPickup')
      })
    })

    return {
      userStore
    }
  },
  
  data() {
    return {
      scanResult: '',
      parsedBarcode: null, // 解析后的条码信息
      // 扫码领货区域折叠状态（默认折叠）
      scanSectionCollapsed: true,
      selectedPackageIndex: 0,
      selectedWorkOrderIndex: 0,
      selectedWarehouseIndex: 0,
      availablePackages: [],
      myWorkOrders: [],
      warehouses: [],
      pickupHistory: [],
      loading: false,
      confirming: false,
      userLocation: null,
      // My Pickups 分页/搜索/分组
      pickupTab: 'picked',
      pickupSearch: '',
      pickupPage: 1,
      pickupPageSize: 20,
      pickupTotal: 0,
      pickupHasMore: false,
      pickupLoading: false,
      pickupLoadingMore: false,
      pickupTabCounts: {
        picked: 0,
        pending_receive: 0,
        installed: 0,
        returned: 0,
      },

      // 退库弹窗状态
      returnModalVisible: false,
      returnRecord: null,
      returnPreviewAction: '',
      returnPreviewData: {},
      returnPreviewLoading: false,
      returnActionLoading: false,
      returnSelectedWarehouseIndex: 0,
      cancelReason: '',

      // 设备详情 Bottom Sheet
      deviceDetailVisible: false,
      deviceDetailRecord: null,
      deviceDetailPreviewAction: '',
      deviceDetailPreviewData: {},
      deviceDetailPreviewLoading: false,
      deviceDetailPreviewReqId: 0,
      deviceDetailActionLoading: false,
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
    },

    warehouseOptions() {
      return this.warehouses.map(w => w.warehouse_name)
    },

    selectedWarehouse() {
      return this.warehouses[this.selectedWarehouseIndex] || null
    },

    returnWarehouseOptions() {
      return this.warehouses.map(w => w.warehouse_name)
    },

    selectedReturnWarehouse() {
      return this.warehouses[this.returnSelectedWarehouseIndex] || null
    },

    pickupTabOptions() {
      const c = this.pickupTabCounts || {}
      return [
        { key: 'picked', label: this.$t('stock.pickupTabPicked'), count: Number(c.picked || 0) },
        { key: 'installed', label: this.$t('stock.pickupTabInstalled'), count: Number(c.installed || 0) },
        { key: 'pending_receive', label: this.$t('stock.pickupTabPendingReceive'), count: Number(c.pending_receive || 0) },
        { key: 'returned', label: this.$t('stock.pickupTabReturned'), count: Number(c.returned || 0) },
      ]
    },

    canCancelReturn() {
      return (
        this.returnPreviewAction === 'already_requested' &&
        this.returnPreviewData?.return_status === 'pending_receive' &&
        !!this.returnPreviewData?.return_transaction_id
      )
    },

	    returnSummarySn() {
	      return (this.returnRecord?.serial_number || this.returnRecord?.main_device_barcode || '').trim()
	    },

	    returnStatusBadgeText() {
	      if (!this.returnRecord) return '-'
	      if (this.returnRecord.is_returned) return this.$t('stock.statusReturned')
	      if (this.returnRecord.return_status) return this.statusTextForReturn(this.returnRecord.return_status)
	      return this.$t('stock.returnNotRequested')
	    },

	    returnStatusBadgeClass() {
	      if (!this.returnRecord) return 'none'
	      if (this.returnRecord.is_returned) return 'done'
	      const s = (this.returnRecord.return_status || '').toString()
	      if (s === 'pending_receive') return 'pending'
	      if (s === 'rejected') return 'rejected'
	      if (s === 'canceled') return 'canceled'
	      return 'none'
	    },

    deviceDetailSn() {
      return (this.deviceDetailRecord?.serial_number || this.deviceDetailRecord?.main_device_barcode || '').trim()
    },

    deviceStatusBadgeText() {
      if (!this.deviceDetailRecord) return '-'
      if (this.deviceDetailRecord.is_returned) return this.$t('stock.statusReturned')
      if (this.deviceDetailRecord.return_status) return this.statusTextForReturn(this.deviceDetailRecord.return_status)
      if (this.deviceDetailRecord.pickup_group === 'installed') return this.$t('stock.statusInstalled')
      return this.deviceDetailRecord.is_confirmed ? this.$t('stock.statusConfirmed') : this.$t('stock.statusPending')
    },

    deviceStatusBadgeClass() {
      if (!this.deviceDetailRecord) return 'none'
      if (this.deviceDetailRecord.is_returned) return 'done'
      const s = (this.deviceDetailRecord.return_status || '').toString()
      if (s === 'pending_receive') return 'pending'
      if (s === 'rejected') return 'rejected'
      if (s === 'canceled') return 'canceled'
      return 'none'
    },

    deviceDetailBindings() {
      if (this.deviceDetailPreviewAction === 'need_unbind') return this.deviceDetailPreviewData?.need_unbind || []
      if (this.deviceDetailPreviewAction === 'unbind_blocked') return this.deviceDetailPreviewData?.blocked_bindings || []
      return []
    },

    canDeviceUnbind() {
      if (this.deviceDetailActionLoading) return false
      if (!this.deviceDetailRecord) return false
      if (this.deviceDetailPreviewAction === 'need_unbind') return true
      return this.deviceDetailRecord.binding_state === 'need_unbind'
    },

    canOpenReturnFromDetail() {
      if (this.deviceDetailActionLoading) return false
      if (!this.deviceDetailRecord) return false
      return this.deviceDetailRecord.pickup_group !== 'returned'
    }
	  },
  
  onLoad() {
    // 权限检查：勘察员不能访问我的设备功能
    if (this.userStore.userInfo?.role === 'surveyor') {
      uni.showToast({
        title: this.$t('stock.surveyorNoPermission'),
        icon: 'none'
      })
      setTimeout(() => {
        uni.navigateBack()
      }, 1500)
      return
    }

    this.loadMyWorkOrders()
    this.loadWarehouses()
    this.loadPickupHistory()
    this.getCurrentLocation()
  },

  onReachBottom() {
    if (this.pickupHasMore && !this.pickupLoading && !this.pickupLoadingMore) {
      this.loadMorePickupHistory()
    }
  },
  
  methods: {
    toggleScanSection() {
      this.scanSectionCollapsed = !this.scanSectionCollapsed
    },

    startScanFromCollapsed() {
      if (this.scanSectionCollapsed) this.scanSectionCollapsed = false
      this.startScan()
    },

    openDeviceDetail(record) {
      if (!record) return
      this.deviceDetailRecord = record
      this.deviceDetailVisible = true
      this.deviceDetailPreviewAction = ''
      this.deviceDetailPreviewData = {}
      this.deviceDetailPreviewLoading = false
      this.deviceDetailActionLoading = false
      this.refreshDeviceDetailPreview()
    },

    closeDeviceDetail() {
      this.deviceDetailVisible = false
      this.deviceDetailRecord = null
      this.deviceDetailPreviewAction = ''
      this.deviceDetailPreviewData = {}
      this.deviceDetailPreviewLoading = false
      this.deviceDetailActionLoading = false
    },

    copyDeviceSn() {
      const sn = (this.deviceDetailSn || '').trim()
      if (!sn) return
      uni.setClipboardData({
        data: sn,
        success: () => {
          uni.showToast({ title: this.$t('stock.copySn'), icon: 'success' })
        }
      })
    },

    async refreshDeviceDetailPreview() {
      if (!this.deviceDetailRecord) return
      const barcode = (this.deviceDetailSn || '').trim()
      if (!barcode) {
        this.deviceDetailPreviewAction = 'error'
        this.deviceDetailPreviewData = { detail: this.$t('stock.scanResultEmpty') }
        return
      }

      const reqId = (this.deviceDetailPreviewReqId || 0) + 1
      this.deviceDetailPreviewReqId = reqId
      this.deviceDetailPreviewLoading = true
      try {
        const parsed = parseBarcode(barcode)
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/scan-return/preview'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: {
              barcode,
              parsed_barcode: parsed && parsed.success ? parsed : null,
              gps_location: this.userLocation
            },
            success: resolve,
            fail: reject
          })
        })
        if (this.deviceDetailPreviewReqId !== reqId) return

        if (res.statusCode !== 200) {
          const detail = res.data?.detail || res.data?.message || this.$t('messages.requestFailedWithCode', { code: res.statusCode })
          this.deviceDetailPreviewAction = 'error'
          this.deviceDetailPreviewData = { detail }
          return
        }

        this.deviceDetailPreviewAction = res.data?.action || ''
        this.deviceDetailPreviewData = res.data || {}
      } catch (error) {
        if (this.deviceDetailPreviewReqId !== reqId) return
        const msg = error?.data?.detail || this.$t('messages.networkError')
        this.deviceDetailPreviewAction = 'error'
        this.deviceDetailPreviewData = { detail: msg }
      } finally {
        if (this.deviceDetailPreviewReqId === reqId) this.deviceDetailPreviewLoading = false
      }
    },

    openReturnFromDetail() {
      const record = this.deviceDetailRecord
      if (!record) return
      this.closeDeviceDetail()
      setTimeout(() => {
        this.openReturnModal(record)
      }, 100)
    },

    async doDeviceUnbind() {
      const sn = (this.deviceDetailPreviewData?.sn || this.deviceDetailSn || '').trim()
      if (!sn) return

      uni.showModal({
        title: this.$t('stock.oneClickUnbind'),
        content: this.$t('stock.unbindWillClearAndDelete'),
        confirmText: this.$t('common.confirm'),
        cancelText: this.$t('common.cancel'),
        success: async (r) => {
          if (!r.confirm) return
          this.deviceDetailActionLoading = true
          try {
            const ret = await new Promise((resolve, reject) => {
              uni.request({
                url: buildApiUrl('/api/stock/scan-return/unbind'),
                method: 'POST',
                header: getAuthHeaders(this.userStore.token),
                data: { sn },
                success: resolve,
                fail: reject
              })
            })
            if (ret.statusCode === 200) {
              uni.showToast({ title: this.$t('messages.operationSuccess'), icon: 'success' })
              await this.refreshDeviceDetailPreview()
              await this.loadPickupHistory(true, 1)
              this.syncDeviceDetailRecordFromHistory()
            } else {
              const msg = ret.data?.detail || ret.data?.message || this.$t('messages.operationFailed')
              uni.showToast({ title: msg, icon: 'none' })
            }
          } catch (error) {
            const msg = error?.data?.detail || this.$t('messages.operationFailed')
            uni.showToast({ title: msg, icon: 'none' })
          } finally {
            this.deviceDetailActionLoading = false
          }
        }
      })
    },

    async startScan() {
      try {
        this.scanSectionCollapsed = false
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
	            message += `\n${this.$t('stock.macAddress1')}: ${this.formatMacAddress(parsedData.mac1)}`
	          }
	          if (parsedData.mac2) {
	            message += `\n${this.$t('stock.macAddress2')}: ${this.formatMacAddress(parsedData.mac2)}`
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

    onWarehouseChange(e) {
      this.selectedWarehouseIndex = Number(e.detail.value || 0)
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
          warehouse_id: this.selectedWarehouse?.id || 1,
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
              this.resetScan({ collapse: true })
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
              this.resetScan({ collapse: true })
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
	          errorMessage = this.$t('messages.serverErrorWithCode', { code: error.statusCode })
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
    
    resetScan(options = {}) {
      const collapse = !!options?.collapse
      this.scanResult = ''
      this.parsedBarcode = null
      this.availablePackages = []
      this.selectedPackageIndex = 0
      this.selectedWorkOrderIndex = 0
      this.selectedWarehouseIndex = 0
      if (collapse) this.scanSectionCollapsed = true
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

    async loadWarehouses() {
      try {
        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/warehouses'),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            success: resolve,
            fail: reject
          })
        })
        this.warehouses = response.data?.warehouses || []
        this.selectedWarehouseIndex = 0
      } catch (error) {
        console.error('加载仓库列表失败:', error)
      }
    },
    
    async loadPickupHistory(reset = true, targetPage = 1) {
      const wantReset = reset === true
      if (wantReset) {
        if (this.pickupLoading) return
        this.pickupLoading = true
      } else {
        if (this.pickupLoadingMore || this.pickupLoading) return
        if (!this.pickupHasMore) return
        this.pickupLoadingMore = true
      }

      try {
        const page = wantReset ? 1 : Number(targetPage || 1)
        const payload = {
          page,
          page_size: this.pickupPageSize,
          pickup_group: this.pickupTab,
        }
        const q = (this.pickupSearch || '').trim()
        if (q) payload.q = q

        const response = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/my-pickups'),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            data: payload,
            success: resolve,
            fail: reject
          })
        })

        if (response.statusCode !== 200) {
          const msg = response.data?.detail || response.data?.message || this.$t('messages.operationFailed')
          uni.showToast({ title: msg, icon: 'none' })
          return
        }

        const data = response.data || {}
        const records = data.pickup_records || []
        if (data.group_counts) {
          const c = data.group_counts || {}
          this.pickupTabCounts = {
            picked: Number(c.picked || 0),
            pending_receive: Number(c.pending_receive || 0),
            installed: Number(c.installed || 0),
            returned: Number(c.returned || 0),
          }
        }
        if (wantReset) {
          this.pickupHistory = records
        } else {
          this.pickupHistory = [...(this.pickupHistory || []), ...records]
        }

        this.pickupPage = data.page || page
        this.pickupTotal = data.total || 0
        this.pickupHasMore = !!data.has_more
      } catch (error) {
        console.error('加载领料记录失败:', error)
      } finally {
        if (wantReset) this.pickupLoading = false
        else this.pickupLoadingMore = false
      }
    },

    refreshPickupHistory() {
      this.loadPickupHistory(true, 1)
    },

    onPickupSearch() {
      this.loadPickupHistory(true, 1)
    },

    clearPickupSearch() {
      this.pickupSearch = ''
      this.loadPickupHistory(true, 1)
    },

    switchPickupTab(tabKey) {
      if (!tabKey || tabKey === this.pickupTab) return
      this.pickupTab = tabKey
      this.loadPickupHistory(true, 1)
    },

    loadMorePickupHistory() {
      const next = (this.pickupPage || 1) + 1
      this.loadPickupHistory(false, next)
    },

    syncReturnRecordFromHistory() {
      if (!this.returnRecord?.id) return
      const latest = (this.pickupHistory || []).find(r => r.id === this.returnRecord.id)
      if (latest) this.returnRecord = latest
    },

    syncDeviceDetailRecordFromHistory() {
      if (!this.deviceDetailRecord?.id) return
      const latest = (this.pickupHistory || []).find(r => r.id === this.deviceDetailRecord.id)
      if (latest) this.deviceDetailRecord = latest
    },

    getHistoryStatusText(record) {
      if (!record) return ''
      if (record.pickup_group === 'installed') return this.$t('stock.statusInstalled')
      if (record.is_returned) return this.$t('stock.statusReturned')
      if (record.return_status === 'pending_receive') return this.$t('stock.returnStatusPendingReceiveShort')
      if (record.return_status === 'rejected') return this.$t('stock.returnStatusRejectedShort')
      if (record.return_status === 'canceled') return this.$t('stock.returnStatusCanceledShort')
      return record.is_confirmed ? this.$t('stock.statusConfirmed') : this.$t('stock.statusPending')
    },

    historyStatusClass(record) {
      return {
        confirmed: record?.is_confirmed && !record?.return_status && !record?.is_returned,
        installed: record?.pickup_group === 'installed',
        'return-pending': record?.return_status === 'pending_receive',
        'return-rejected': record?.return_status === 'rejected',
        'return-canceled': record?.return_status === 'canceled',
        returned: record?.is_returned
      }
    },

	    bindingTitle(binding) {
	      const fallback = this.$t('stock.unknownWorkOrderOrSite')
	      if (!binding) return fallback
	      return binding.work_order_title || binding.site_name || fallback
	    },

	    bindingSiteName(binding) {
	      if (!binding) return ''
	      // 仅当存在工单标题时才额外展示站点名，避免重复
      if (binding.work_order_title && binding.site_name) return binding.site_name
      return ''
    },

    sectorBandText(binding) {
      const sector = (binding?.sector_id || '').toString().trim()
      const band = (binding?.band || '').toString().trim()
      if (!sector && !band) return this.$t('stock.sectorBandUnknown')
      if (sector && band) return `${sector} / ${band}`
      return `${sector || '-'} / ${band || '-'}`
    },

	    inspectionStatusText(status) {
	      const s = (status || '').toString()
	      const map = {
	        draft: this.$t('inspection.draft'),
	        in_progress: this.$t('inspection.inProgress'),
        submitted: this.$t('inspection.submitted'),
        under_review: this.$t('inspection.underReview'),
        approved: this.$t('inspection.approved'),
        rejected: this.$t('inspection.rejected'),
        completed: this.$t('inspection.completed'),
	      }
	      return map[s] || s || '-'
	    },

	    inspectionStatusTagClass(status) {
	      const s = (status || '').toString()
	      if (s === 'draft' || s === 'in_progress') return 'status-working'
	      if (s === 'rejected') return 'status-rejected'
	      if (s === 'submitted' || s === 'under_review') return 'status-review'
	      if (s === 'approved' || s === 'completed') return 'status-done'
	      return 'status-unknown'
	    },

	    bindingReasonText(binding) {
	      if (!binding) return '-'
	      const code = (binding.reason_code || '').toString()
	      const map = {
        other_inspector: this.$t('stock.unbindReasonOtherInspector'),
        inspection_locked: this.$t('stock.unbindReasonInspectionLocked'),
        status_not_supported: this.$t('stock.unbindReasonStatusNotSupported'),
      }
      return map[code] || binding.reason || '-'
    },

    statusTextForReturn(status) {
      const map = {
        pending_receive: this.$t('stock.returnStatusPendingReceive'),
        received: this.$t('stock.statusReturned'),
        rejected: this.$t('stock.returnStatusRejectedShort'),
        canceled: this.$t('stock.returnStatusCanceledShort')
      }
	      return map[status] || status
	    },

	    copyReturnSn() {
	      const sn = (this.returnSummarySn || '').trim()
	      if (!sn) return
	      uni.setClipboardData({
	        data: sn,
	        success: () => {
	          uni.showToast({ title: this.$t('stock.copySn'), icon: 'success' })
	        }
	      })
	    },

	    async openReturnModal(record) {
	      if (!record) return
	      this.returnRecord = record
	      this.returnModalVisible = true
      this.returnPreviewAction = ''
      this.returnPreviewData = {}
      this.cancelReason = ''
      this.returnSelectedWarehouseIndex = 0

      if (!this.warehouses || this.warehouses.length === 0) {
        await this.loadWarehouses()
      }
      await this.refreshReturnPreview()
    },

    closeReturnModal() {
      this.returnModalVisible = false
      this.returnRecord = null
      this.returnPreviewAction = ''
      this.returnPreviewData = {}
      this.cancelReason = ''
      this.returnSelectedWarehouseIndex = 0
      this.returnPreviewLoading = false
      this.returnActionLoading = false
    },

    onReturnWarehouseChange(e) {
      this.returnSelectedWarehouseIndex = Number(e.detail.value || 0)
    },

    async refreshReturnPreview() {
      if (!this.returnRecord) return
      const barcode = (this.returnRecord.serial_number || this.returnRecord.main_device_barcode || '').trim()
      if (!barcode) {
        this.returnPreviewAction = 'no_active_pickup'
        this.returnPreviewData = {}
        return
      }

      this.returnPreviewLoading = true
      try {
        const parsed = parseBarcode(barcode)
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/scan-return/preview'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: {
              barcode,
              parsed_barcode: parsed && parsed.success ? parsed : null,
              gps_location: this.userLocation
            },
            success: resolve,
            fail: reject
          })
        })
	        if (res.statusCode !== 200) {
	          const detail = res.data?.detail || res.data?.message || this.$t('messages.requestFailedWithCode', { code: res.statusCode })
	          uni.showToast({ title: detail, icon: 'none' })
	          this.returnPreviewAction = 'error'
	          this.returnPreviewData = { detail }
	          return
	        }

        this.returnPreviewAction = res.data?.action || ''
        this.returnPreviewData = res.data || {}

        // 默认退入原出库仓库
        if (this.returnPreviewAction === 'preview_ok' && this.returnPreviewData.out_warehouse_id && this.warehouses?.length) {
          const idx = this.warehouses.findIndex(w => w.id === this.returnPreviewData.out_warehouse_id)
          if (idx >= 0) this.returnSelectedWarehouseIndex = idx
        }
        // 已提交退库：回显退入仓库（来自 My Pickups）
        if (this.returnPreviewAction === 'already_requested' && this.returnRecord?.return_warehouse_id && this.warehouses?.length) {
          const idx = this.warehouses.findIndex(w => w.id === this.returnRecord.return_warehouse_id)
          if (idx >= 0) this.returnSelectedWarehouseIndex = idx
        }
      } catch (error) {
        const msg = error?.data?.detail || this.$t('messages.networkError')
        this.returnPreviewAction = 'error'
        this.returnPreviewData = { detail: msg }
        uni.showToast({ title: msg, icon: 'none' })
      } finally {
        this.returnPreviewLoading = false
      }
    },

    async doReturnUnbind() {
      const sn = (this.returnPreviewData?.sn || this.returnRecord?.serial_number || this.returnRecord?.main_device_barcode || '').trim()
      if (!sn) return

      uni.showModal({
        title: this.$t('stock.oneClickUnbind'),
        content: this.$t('stock.unbindWillClearAndDelete'),
        confirmText: this.$t('common.confirm'),
        cancelText: this.$t('common.cancel'),
        success: async (r) => {
          if (!r.confirm) return
          this.returnActionLoading = true
          try {
            const ret = await new Promise((resolve, reject) => {
              uni.request({
                url: buildApiUrl('/api/stock/scan-return/unbind'),
                method: 'POST',
                header: getAuthHeaders(this.userStore.token),
                data: { sn },
                success: resolve,
                fail: reject
              })
            })
            if (ret.statusCode === 200) {
              uni.showToast({ title: this.$t('messages.operationSuccess'), icon: 'success' })
              await this.refreshReturnPreview()
              await this.loadPickupHistory()
              this.syncReturnRecordFromHistory()
            } else {
              uni.showToast({ title: this.$t('messages.operationFailed'), icon: 'none' })
            }
          } catch (error) {
            const msg = error?.data?.detail || this.$t('messages.operationFailed')
            uni.showToast({ title: msg, icon: 'none' })
          } finally {
            this.returnActionLoading = false
          }
        }
      })
    },

    async submitReturnRequest() {
      if (this.returnPreviewAction !== 'preview_ok') return

      const barcode = (this.returnRecord?.serial_number || this.returnRecord?.main_device_barcode || '').trim()
      if (!barcode) return

      if (!this.selectedReturnWarehouse) {
        uni.showToast({ title: this.$t('stock.selectReturnWarehouse'), icon: 'none' })
        return
      }

      this.returnActionLoading = true
      try {
        const parsed = parseBarcode(barcode)
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/scan-return/request'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: {
              barcode,
              parsed_barcode: parsed && parsed.success ? parsed : null,
              return_warehouse_id: this.selectedReturnWarehouse.id,
              gps_location: this.userLocation
            },
            success: resolve,
            fail: reject
          })
        })
        if (res.statusCode !== 200) {
          const detail = res.data?.detail || res.data?.message || this.$t('messages.operationFailed')
          uni.showToast({ title: detail, icon: 'none' })
          return
        }

	        const data = res.data || {}
	        uni.showToast({ title: this.$t('stock.returnRequestSuccessTitle'), icon: 'success' })

	        // 回显到弹窗摘要（避免分页/分组导致列表中找不到该条记录）
	        if (this.returnRecord) {
	          this.returnRecord.return_status = data.return_status || 'pending_receive'
	          this.returnRecord.return_document_number = data.return_document_number || this.returnRecord.return_document_number
	          this.returnRecord.return_warehouse_id = data.return_warehouse_id || this.returnRecord.return_warehouse_id
	          this.returnRecord.return_warehouse_name =
	            data.return_warehouse_name ||
	            this.selectedReturnWarehouse?.warehouse_name ||
	            this.returnRecord.return_warehouse_name
	          this.returnRecord.return_reject_reason = null
	        }

	        // 申请后刷新列表与预览（变为 already_requested）
	        await this.loadPickupHistory()
	        this.syncReturnRecordFromHistory()
	        await this.refreshReturnPreview()

        // 提示单号
        if (data.return_document_number) {
          uni.showModal({
            title: this.$t('stock.returnRequestSuccessTitle'),
            content: `${this.$t('stock.returnDocumentNumber')}: ${data.return_document_number}\n${this.$t('stock.returnStatusPendingReceive')}`,
            showCancel: false
          })
        }
      } catch (error) {
        const msg = error?.data?.detail || this.$t('messages.operationFailed')
        uni.showToast({ title: msg, icon: 'none' })
      } finally {
        this.returnActionLoading = false
      }
    },

    async cancelReturnRequest() {
      if (!this.canCancelReturn) return
      const returnTransactionId = this.returnPreviewData?.return_transaction_id
      if (!returnTransactionId) return
      uni.showModal({
        title: this.$t('common.hint'),
        content: this.$t('stock.cancelReturnConfirm'),
        confirmText: this.$t('common.confirm'),
        cancelText: this.$t('common.cancel'),
        success: async (r) => {
          if (!r.confirm) return
          this.returnActionLoading = true
          try {
            const res = await new Promise((resolve, reject) => {
              uni.request({
                url: buildApiUrl('/api/stock/scan-return/cancel'),
                method: 'POST',
                header: getAuthHeaders(this.userStore.token),
                data: {
                  return_transaction_id: returnTransactionId,
                  reason: (this.cancelReason || '').trim()
                },
                success: resolve,
                fail: reject
              })
            })
	            if (res.statusCode === 200) {
	              uni.showToast({ title: this.$t('messages.operationSuccess'), icon: 'success' })
	              this.cancelReason = ''
	              if (this.returnRecord) {
	                this.returnRecord.return_status = 'canceled'
	                this.returnRecord.return_reject_reason = null
	              }
	              await this.loadPickupHistory()
	              this.syncReturnRecordFromHistory()
	              await this.refreshReturnPreview()
	            } else {
	              uni.showToast({ title: this.$t('messages.operationFailed'), icon: 'none' })
	            }
          } catch (error) {
            const msg = error?.data?.detail || this.$t('messages.operationFailed')
            uni.showToast({ title: msg, icon: 'none' })
          } finally {
            this.returnActionLoading = false
          }
        }
      })
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
.container { background-color: var(--bg-page); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

.page-content { flex: 1; height: 0; min-height: 0; padding: 20rpx; }

.header {
  background: var(--bg-elevated);
  padding: 30rpx;
  border-radius: 12rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow-card);
  
  .scan-info {
    .info-text {
      font-size: 28rpx;
      color: var(--text-secondary);
    }
  }
}

.scan-fold {
  margin-bottom: 20rpx;
}

.scan-fold-header {
  background: var(--bg-elevated);
  padding: 22rpx 24rpx;
  border-radius: 12rpx;
  box-shadow: var(--shadow-card);
  display: flex;
  align-items: center;
  justify-content: space-between;

  &:active { opacity: 0.92; }

  .scan-fold-left {
    display: flex;
    align-items: center;
    gap: 12rpx;
  }

  .scan-fold-title {
    font-size: 30rpx;
    font-weight: 600;
    color: var(--text-primary);
  }

  .scan-fold-right {
    display: flex;
    align-items: center;
    gap: 12rpx;
  }

  .scan-fold-scan-btn {
    display: flex;
    align-items: center;
    gap: 8rpx;
    padding: 10rpx 16rpx;
    border-radius: 999rpx;
    background: var(--color-primary);
  }

  .scan-fold-scan-btn:active { opacity: 0.85; }

  .scan-fold-scan-text {
    font-size: 24rpx;
    font-weight: 600;
    color: #ffffff;
    line-height: 1;
  }
}

.scan-fold-body {
  margin-top: 14rpx;
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
	    
	    .refresh-icon {
	      width: 76rpx;
	      height: 76rpx;
	      display: flex;
	      align-items: center;
	      justify-content: center;
	      border-radius: 12rpx;
	      border: 1rpx solid #e5e7eb;
	      background: #ffffff;
	    }

	    .refresh-icon:active { opacity: 0.85; }
	  }

  .pickup-toolbar {
    display: flex;
    align-items: center;
    gap: 12rpx;
    margin-bottom: 16rpx;

    .pickup-search {
      flex: 1;
      min-height: 76rpx;
      padding: 0 18rpx;
      border-radius: 12rpx;
      border: 1rpx solid #e5e7eb;
      background: #f9fafb;
      font-size: 26rpx;
      color: var(--text-primary);
    }

    .pickup-toolbar-actions {
      display: flex;
      gap: 12rpx;
      align-items: center;
      flex-shrink: 0;
    }

    .pickup-search-btn,
    .pickup-clear-btn {
      min-height: 76rpx;
      padding: 0 20rpx;
      border-radius: 12rpx;
      font-size: 26rpx;
      border: none;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }

    .pickup-search-btn { background: var(--color-primary); color: #ffffff; }
    .pickup-clear-btn { background: #f3f4f6; color: #374151; }
  }

  .pickup-tabs {
    display: flex;
    flex-wrap: nowrap;
    width: 100%;
    margin-bottom: 16rpx;
    border: 1rpx solid #e5e7eb;
    border-radius: 14rpx;
    overflow: hidden;
    background: #f3f4f6;

    .pickup-tab {
      flex: 1;
      min-height: 96rpx;
      padding: 10rpx 8rpx;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 8rpx;
      color: #374151;

      &:active { opacity: 0.85; }

      &:not(:last-child) {
        border-right: 1rpx solid #e5e7eb;
      }

      &.active {
        background: var(--color-primary);
        color: #ffffff;
      }
    }

	    .pickup-tab-label {
	      font-size: 24rpx;
	      font-weight: 600;
	      line-height: 1.2;
	      text-align: center;
	      width: 100%;
	    }

	    .pickup-tab-count {
      min-width: 44rpx;
      height: 36rpx;
      padding: 0 12rpx;
      border-radius: 999rpx;
      background: rgba(0, 0, 0, 0.06);
      color: #374151;
      font-size: 22rpx;
      font-weight: 600;
	      display: inline-flex;
	      align-items: center;
	      justify-content: center;
	      text-align: center;
	    }

    .pickup-tab.active .pickup-tab-count {
      background: rgba(255, 255, 255, 0.25);
      color: #ffffff;
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
      &:active { opacity: 0.88; }
      
      .history-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 12rpx;
        
        .history-sn { font-size: 30rpx; color: var(--text-primary); font-weight: 600; }
        
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

          &.return-pending {
            color: #f59e0b;
          }

          &.return-rejected {
            color: #ef4444;
          }

          &.return-canceled {
            color: #6b7280;
          }

          &.installed {
            color: #2563eb;
          }

          &.returned {
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

.history-load-more {
  margin-top: 14rpx;
  display: flex;
  justify-content: center;
}

.load-more-btn {
  min-height: 76rpx;
  padding: 0 28rpx;
  border-radius: 12rpx;
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  color: var(--text-primary);
  font-size: 26rpx;

  &:disabled {
    color: #9ca3af;
    border-color: #e5e7eb;
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

/* 设备详情 Bottom Sheet */
.device-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 10000;
}

.device-modal {
  width: 100%;
  max-height: 86vh;
  background: var(--bg-elevated);
  border-radius: 24rpx 24rpx 0 0;
  overflow: hidden;
  box-shadow: 0 -4rpx 16rpx rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
}

.device-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 22rpx 24rpx;
  border-bottom: 1rpx solid #e5e7eb;
}

.device-modal-title {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--text-primary);
}

.device-modal-close {
  width: 72rpx;
  height: 72rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 999rpx;
  background: #f9fafb;
}

.device-modal-close:active { background: #f3f4f6; }

.device-modal-body {
  padding: 20rpx 24rpx;
  overflow: auto;
  flex: 1;
}

.device-summary {
  background: var(--bg-page);
  border-radius: 12rpx;
  padding: 16rpx 18rpx;
  margin-bottom: 16rpx;
}

.device-section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-bottom: 12rpx;
}

.device-section-title {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--text-primary);
}

.device-section-action {
  width: 76rpx;
  height: 76rpx;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12rpx;
  border: 1rpx solid #e5e7eb;
  background: #ffffff;
}

.device-section-action:active { opacity: 0.85; }

.device-loading {
  padding: 20rpx 0;
  text-align: center;
  color: var(--text-secondary);
}

.device-empty {
  margin-top: 12rpx;
  padding: 18rpx;
  background: var(--bg-page);
  border-radius: 12rpx;
  color: var(--text-secondary);
  font-size: 26rpx;
  text-align: center;
  line-height: 1.4;
}

.device-modal-footer {
  padding: 18rpx 24rpx env(safe-area-inset-bottom);
  border-top: 1rpx solid #e5e7eb;
  display: flex;
  gap: 16rpx;
  flex-wrap: wrap;
}

.device-modal-footer .modal-btn {
  flex: 1;
  min-width: 220rpx;
}

.btn-warning {
  background: #f59e0b;
  color: #ffffff;
}

/* 退库弹窗 */
.return-modal-mask {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10001;
}

.return-modal {
  width: 88%;
  max-height: 84vh;
  background: var(--bg-elevated);
  border-radius: 16rpx;
  overflow: hidden;
  box-shadow: var(--shadow-card);
  display: flex;
  flex-direction: column;
}

.return-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 24rpx 24rpx;
  border-bottom: 1rpx solid #e5e7eb;
}

.return-modal-title {
  font-size: 32rpx;
  font-weight: 600;
  color: var(--text-primary);
}

.return-modal-close {
  padding: 8rpx;
}

.close-text {
  font-size: 38rpx;
  line-height: 38rpx;
  color: #9ca3af;
}

.return-modal-body {
  padding: 20rpx 24rpx;
  overflow: auto;
  flex: 1;
}

.return-summary {
  background: var(--bg-page);
  border-radius: 12rpx;
  padding: 16rpx 18rpx;
  margin-bottom: 16rpx;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  margin-bottom: 12rpx;
}

.summary-row:last-child {
  margin-bottom: 0;
}

.summary-label {
  font-size: 24rpx;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.summary-value-wrap {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12rpx;
  max-width: 72%;
}

.summary-value {
  font-size: 26rpx;
  font-weight: 600;
  color: var(--text-primary);
  text-align: right;
  word-break: break-all;
}

.mono { font-family: monospace; }

.summary-action {
  font-size: 22rpx;
  color: var(--color-primary);
  border: 1rpx solid var(--color-primary);
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  white-space: nowrap;
}

.status-badge {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  background: #f3f4f6;
  color: #374151;
  white-space: nowrap;
}

.status-badge.none { background: #e0e7ff; color: #3730a3; }
.status-badge.pending { background: #fef3c7; color: #b45309; }
.status-badge.rejected { background: #fee2e2; color: #b91c1c; }
.status-badge.canceled { background: #e5e7eb; color: #4b5563; }
.status-badge.done { background: #dcfce7; color: #166534; }

.summary-reject-box {
  margin-top: 12rpx;
  padding: 14rpx;
  background: #fef2f2;
  border: 1rpx solid #fca5a5;
  border-radius: 12rpx;
  display: flex;
  align-items: flex-start;
  gap: 10rpx;
}

.reject-icon { font-size: 28rpx; line-height: 28rpx; }
.reject-text { flex: 1; font-size: 24rpx; color: #b91c1c; line-height: 1.4; }

.return-loading {
  padding: 20rpx 0;
  text-align: center;
  color: var(--text-secondary);
}

.return-hint-card {
  padding: 18rpx;
  background: var(--bg-page);
  border-radius: 12rpx;
  color: var(--text-primary);
}

.return-hint-sub {
  margin-top: 10rpx;
  color: var(--text-secondary);
  font-size: 26rpx;
}

.kv-list {
  margin-top: 10rpx;
  padding-top: 10rpx;
  border-top: 1rpx solid #e5e7eb;
}

.kv-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  padding: 10rpx 0;
}

.kv-label {
  font-size: 24rpx;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.kv-value {
  font-size: 26rpx;
  color: var(--text-primary);
  font-weight: 600;
  text-align: right;
  word-break: break-all;
  max-width: 72%;
}

.hint-header {
  margin-bottom: 14rpx;
}

.hint-title {
  display: block;
  font-size: 30rpx;
  font-weight: 600;
  color: var(--text-primary);
}

.hint-desc {
  display: block;
  margin-top: 10rpx;
  font-size: 26rpx;
  color: var(--text-secondary);
  line-height: 1.4;
}

.hint-header.warning .hint-title { color: #b45309; }
.hint-header.info .hint-title { color: #2563eb; }

.hint-actions {
  display: flex;
  gap: 16rpx;
  margin-top: 16rpx;
}

.cancel-section {
  margin-top: 16rpx;
}

.cancel-label {
  display: block;
  font-size: 26rpx;
  color: var(--text-secondary);
  margin-bottom: 8rpx;
}

.cancel-input {
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  border-radius: 10rpx;
  padding: 18rpx 16rpx;
  font-size: 26rpx;
  color: var(--text-primary);
}

.section-title-sm {
  font-size: 28rpx;
  font-weight: 600;
  color: var(--text-primary);
  margin: 14rpx 0 12rpx;
  display: block;
}

.return-doc {
  color: var(--text-secondary);
  font-size: 26rpx;
  margin-bottom: 8rpx;
}

.bind-list { margin-top: 12rpx; }
.bind-item {
  padding: 14rpx;
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
  margin-bottom: 12rpx;
}

.bind-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12rpx;
}

.bind-title {
  flex: 1;
  font-size: 28rpx;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
}

.bind-tag {
  font-size: 22rpx;
  color: #334155;
  background: #f1f5f9;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  white-space: nowrap;
}

.status-tag {
  font-size: 22rpx;
  background: #f1f5f9;
  color: #334155;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  white-space: nowrap;
}

.status-tag.status-working { background: #dbeafe; color: #1d4ed8; }
.status-tag.status-review { background: #fef3c7; color: #b45309; }
.status-tag.status-done { background: #dcfce7; color: #166534; }
.status-tag.status-rejected { background: #fee2e2; color: #b91c1c; }
.status-tag.status-unknown { background: #f3f4f6; color: #4b5563; }

.bind-meta {
  margin-top: 10rpx;
}

.meta-item {
  display: block;
  font-size: 24rpx;
  color: var(--text-secondary);
  margin-top: 6rpx;
}

.bind-reason {
  margin-top: 10rpx;
  color: #ef4444;
  font-size: 24rpx;
  line-height: 1.4;
  display: block;
}

.return-modal-footer {
  padding: 18rpx 24rpx;
  border-top: 1rpx solid #e5e7eb;
  display: flex;
  gap: 16rpx;
}

.modal-btn {
  flex: 1;
  min-height: 88rpx;
  padding: 0 24rpx;
  border-radius: 12rpx;
  font-size: 30rpx;
  font-weight: 500;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.btn-secondary {
  background: #f3f4f6;
  color: #374151;
}

.btn-primary {
  background: var(--color-primary);
  color: #ffffff;
}

.btn-danger {
  background: #ef4444;
  color: #ffffff;
}
</style>
