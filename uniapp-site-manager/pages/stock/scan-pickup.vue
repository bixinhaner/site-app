<template>
  <view class="container">
    <CustomNavbar :title="$t('stock.scanPickup')" :showBack="true" variant="brand" />

	    <scroll-view class="page-content" scroll-y>
	      <view class="header">
	        <view class="scan-info">
	          <text class="info-text">
	            {{ legacyScanPickupEnabled ? $t('stock.myDevicesInfo') : $t('stock.myDevicesInfoLedger') }}
	          </text>
	        </view>
	      </view>

	    <!-- 扫码领货（默认折叠） -->
	    <view class="scan-fold" v-if="legacyScanPickupEnabled">
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

                  <view v-if="parsedBarcode.mac3" class="detail-item">
                    <text class="detail-label">{{ $t('stock.macAddress3') }}:</text>
                    <text class="detail-value mac-value">{{ formatMacAddress(parsedBarcode.mac3) }}</text>
                  </view>

                  <view v-if="parsedBarcode.mac4" class="detail-item">
                    <text class="detail-label">{{ $t('stock.macAddress4') }}:</text>
                    <text class="detail-value mac-value">{{ formatMacAddress(parsedBarcode.mac4) }}</text>
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
                  <text class="quantity-text">{{ item.quantity }} {{ displayUnit(item.unit) }}</text>
                  <text v-if="item.is_required" class="required-tag">{{ $t('stock.requiredTag') }}</text>
                </view>
              </view>
              <text class="item-code">{{ $t('stock.codeLabel') }}: {{ item.equipment_code }}</text>
            </view>
          </view>

          <!-- 线下单据（可选） -->
          <view class="offline-documents">
            <OfflineDocumentSection v-model="checkoutOfflineDocumentId" :disabled="confirming" />
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
            <view class="section-title-right">
              <view class="material-tabs">
                <view
                  class="material-tab"
                  :class="{ active: materialTab === 'main' }"
                  @click="switchMaterialTab('main')"
                >
                  <text>{{ $t('stock.mainDevice') }}</text>
                </view>
                <view
                  class="material-tab"
                  :class="{ active: materialTab === 'aux' }"
                  @click="switchMaterialTab('aux')"
                >
                  <text>{{ $t('stock.auxMaterial') }}</text>
                </view>
              </view>
		          <view class="refresh-icon" @click="refreshIssuedItems">
		            <uni-icons type="refreshempty" size="20" color="#2563eb" />
		          </view>
            </view>
		      </view>

	      <view class="pickup-toolbar">
	        <input
	          class="pickup-search"
	          v-model="pickupSearch"
	          :placeholder="issuedSearchPlaceholder"
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
	          v-for="t in visiblePickupTabOptions"
	          :key="t.key"
	          class="pickup-tab"
	          :class="{ active: pickupTab === t.key }"
	          @click="switchPickupTab(t.key)"
	        >
	          <text class="pickup-tab-label">{{ t.label }}</text>
	          <text class="pickup-tab-count">{{ t.count }}</text>
	        </view>
	      </view>
	      
	      <view v-if="issuedLoading" class="empty-state">
	        <text>{{ $t('common.loading') }}</text>
	      </view>

	      <view v-else-if="issuedItems.length === 0" class="empty-state">
	        <text>{{ $t('messages.noData') }}</text>
	      </view>
	      
	      <view v-else class="history-list">
	        <view v-for="record in issuedItems" :key="recordKey(record)" class="history-item" @click="openIssuedDetail(record)">
	          <view class="history-header">
              <view class="history-left">
                <text class="history-sn">{{ recordPrimaryText(record) }}</text>
                <text v-if="record.item_type === 'aux'" class="history-qty">{{ record.quantity }} {{ displayUnit(record.unit) || '' }}</text>
              </view>
	            <text class="history-time">{{ formatTime(record.operation_time) }}</text>
	          </view>
            <view class="history-sub">
              <text class="history-doc mono">{{ record.out_document_number || '-' }}</text>
              <text class="history-status" :class="historyStatusClass(record)">
                {{ getHistoryStatusText(record) }}
              </text>
            </view>
	          <view class="history-detail">
	            <text class="history-barcode">{{ recordSecondaryText(record) }}</text>
              <view class="history-tags">
                <text class="history-tag">{{ record.method_tag || '-' }}</text>
                <text class="history-tag">{{ record.source_tag || '-' }}</text>
              </view>
	          </view>
	        </view>

	        <view class="history-load-more" v-if="issuedHasMore">
	          <button class="load-more-btn" :disabled="issuedLoadingMore" @click="loadMoreIssuedItems">
	            {{ issuedLoadingMore ? $t('common.loading') : $t('stock.loadMore') }}
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
              <view class="summary-row">
                <text class="summary-label">{{ $t('stock.documentNumber') }}</text>
                <text class="summary-value mono">{{ deviceDetailOut?.document_number || deviceDetailRecord.out_document_number || '-' }}</text>
              </view>
              <view class="summary-tags">
                <text class="summary-tag">{{ deviceDetailOut?.method_tag || deviceDetailRecord.method_tag || '-' }}</text>
                <text class="summary-tag">{{ deviceDetailOut?.source_tag || deviceDetailRecord.source_tag || '-' }}</text>
              </view>
	            <view v-if="deviceDetailRecord.mac_address_1" class="summary-row">
	              <text class="summary-label">{{ $t('stock.macAddress1') }}</text>
	              <text class="summary-value mono">{{ formatMacAddress(deviceDetailRecord.mac_address_1) }}</text>
	            </view>
	            <view v-if="deviceDetailRecord.mac_address_2" class="summary-row">
	              <text class="summary-label">{{ $t('stock.macAddress2') }}</text>
	              <text class="summary-value mono">{{ formatMacAddress(deviceDetailRecord.mac_address_2) }}</text>
	            </view>
	            <view v-if="deviceDetailRecord.mac_address_3" class="summary-row">
	              <text class="summary-label">{{ $t('stock.macAddress3') }}</text>
	              <text class="summary-value mono">{{ formatMacAddress(deviceDetailRecord.mac_address_3) }}</text>
	            </view>
	            <view v-if="deviceDetailRecord.mac_address_4" class="summary-row">
	              <text class="summary-label">{{ $t('stock.macAddress4') }}</text>
	              <text class="summary-value mono">{{ formatMacAddress(deviceDetailRecord.mac_address_4) }}</text>
	            </view>
            <view class="summary-row">
              <text class="summary-label">{{ $t('common.status') }}</text>
              <text class="status-badge" :class="deviceStatusBadgeClass">{{ deviceStatusBadgeText }}</text>
            </view>
            <view class="summary-row">
              <text class="summary-label">{{ $t('stock.warehouse') }}</text>
              <text class="summary-value">{{ deviceDetailOut?.warehouse_name || deviceDetailRecord.warehouse_name || '-' }}</text>
            </view>
            <view class="summary-row">
              <text class="summary-label">{{ $t('common.time') }}</text>
              <text class="summary-value mono">{{ formatTime(deviceDetailOut?.operation_time || deviceDetailRecord.operation_time) || '-' }}</text>
            </view>
            <view v-if="deviceDetailRecord.return_document_number" class="summary-row">
              <text class="summary-label">{{ $t('stock.returnDocumentNumber') }}</text>
              <text class="summary-value mono">{{ deviceDetailRecord.return_document_number }}</text>
            </view>
	            <view v-if="deviceDetailRecord.return_warehouse_name" class="summary-row">
	              <text class="summary-label">{{ $t('stock.returnWarehouseLabel') }}</text>
	              <text class="summary-value">{{ deviceDetailRecord.return_warehouse_name }}</text>
	            </view>
	            <view v-if="showDeviceRejectReason" class="summary-reject-box">
	              <text class="reject-icon">!</text>
	              <view class="reject-content">
	                <text class="reject-title">{{ $t('stock.rejectReason') }}</text>
	                <text class="reject-text">{{ deviceRejectReasonText }}</text>
	              </view>
	            </view>
	          </view>

          <view class="device-section">
            <view class="device-section-title-row">
              <text class="device-section-title">{{ $t('stock.stockOutItemsTitle') }}</text>
              <view class="device-section-action" @click="loadDeviceDetailOut">
                <uni-icons type="refreshempty" size="18" color="#2563eb" />
              </view>
            </view>

            <view v-if="deviceDetailOutLoading" class="device-loading">
              <text>{{ $t('common.loading') }}</text>
            </view>

            <view v-else-if="!deviceDetailOut" class="device-empty">
              <text>{{ $t('messages.noData') }}</text>
            </view>

            <view v-else>
              <view v-if="deviceDetailOut.notes" class="out-notes">
                <text class="out-notes-label">{{ $t('common.comments') }}</text>
                <text class="out-notes-value">{{ deviceDetailOut.notes }}</text>
              </view>

              <view v-if="deviceDetailOut.items && deviceDetailOut.items.length > 0" class="out-items">
                <view v-for="it in deviceDetailOut.items" :key="it.item_id" class="out-item">
                  <view class="out-item-head">
                    <text class="out-item-name">{{ it.equipment_name || it.equipment_code || '-' }}</text>
                    <text class="out-item-tag" :class="{ main: it.is_main_device }">
                      {{ it.is_main_device ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
                    </text>
                  </view>
                  <view class="out-item-meta">
                    <text class="out-item-code mono">{{ it.equipment_code || '-' }}</text>
                    <text v-if="it.is_main_device" class="out-item-qty mono">{{ it.serial_number || '-' }}</text>
                    <text v-else class="out-item-qty">{{ it.quantity }} {{ displayUnit(it.unit) || '' }}</text>
                  </view>
                </view>
              </view>
              <view v-else class="device-empty">
                <text>{{ $t('messages.noData') }}</text>
              </view>
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

    <!-- 出库单详情 Bottom Sheet（辅料点击） -->
    <view class="device-modal-mask" v-if="outDetailVisible" @click="closeOutDetail">
      <view class="device-modal" @click.stop>
        <view class="device-modal-header">
          <text class="device-modal-title">{{ $t('stock.stockOutDetailsTitle') }}</text>
          <view class="device-modal-close" @click="closeOutDetail">
            <uni-icons type="closeempty" size="20" color="#6b7280" />
          </view>
        </view>

        <view class="device-modal-body">
          <view v-if="outDetailLoading" class="device-loading">
            <text>{{ $t('common.loading') }}</text>
          </view>
          <view v-else-if="!outDetailData" class="device-empty">
            <text>{{ $t('messages.noData') }}</text>
          </view>
          <view v-else>
            <view class="device-summary">
              <view class="summary-row">
                <text class="summary-label">{{ $t('stock.documentNumber') }}</text>
                <text class="summary-value mono">{{ outDetailData.document_number || '-' }}</text>
              </view>
              <view class="summary-tags">
                <text class="summary-tag">{{ outDetailData.method_tag || '-' }}</text>
                <text class="summary-tag">{{ outDetailData.source_tag || '-' }}</text>
              </view>
              <view class="summary-row">
                <text class="summary-label">{{ $t('stock.warehouse') }}</text>
                <text class="summary-value">{{ outDetailData.warehouse_name || '-' }}</text>
              </view>
              <view class="summary-row">
                <text class="summary-label">{{ $t('common.time') }}</text>
                <text class="summary-value mono">{{ formatTime(outDetailData.operation_time) || '-' }}</text>
              </view>
            </view>

            <view class="device-section">
              <view class="device-section-title-row">
                <text class="device-section-title">{{ $t('stock.stockOutItemsTitle') }}</text>
              </view>

              <view v-if="outDetailData.notes" class="out-notes">
                <text class="out-notes-label">{{ $t('common.comments') }}</text>
                <text class="out-notes-value">{{ outDetailData.notes }}</text>
              </view>

              <view v-if="outDetailData.items && outDetailData.items.length > 0" class="out-items">
                <view v-for="it in outDetailData.items" :key="it.item_id" class="out-item">
                  <view class="out-item-head">
                    <text class="out-item-name">{{ it.equipment_name || it.equipment_code || '-' }}</text>
                    <text class="out-item-tag" :class="{ main: it.is_main_device }">
                      {{ it.is_main_device ? $t('stock.mainDevice') : $t('stock.auxMaterial') }}
                    </text>
                  </view>
                  <view class="out-item-meta">
                    <text class="out-item-code mono">{{ it.equipment_code || '-' }}</text>
                    <text v-if="it.is_main_device" class="out-item-qty mono">{{ it.serial_number || '-' }}</text>
                    <text v-else class="out-item-qty">{{ it.quantity }} {{ displayUnit(it.unit) || '' }}</text>
                  </view>
                </view>
              </view>
              <view v-else class="device-empty">
                <text>{{ $t('messages.noData') }}</text>
              </view>
            </view>
          </view>
        </view>

        <view class="device-modal-footer">
          <button class="modal-btn btn-secondary" @click="closeOutDetail">
            {{ $t('common.close') }}
          </button>
        </view>
      </view>
    </view>

  </view>
</template>

	<script>
	import { parseBarcode, formatMacAddress, getParseResultSummary } from '@/utils/barcode-parser.js'
	import { scanAndParseDeviceCode, ScanDeviceCodeError } from '@/utils/scan-code.js'
	import { buildApiUrl, createRequestConfig, getAuthHeaders } from '@/config/api.js'
	import { getLocalizedStockUnit } from '@/utils/unit-i18n.js'
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
      scannedEquipmentInstance: null,
      // 扫码领货区域折叠状态（默认折叠）
      scanSectionCollapsed: true,
      selectedPackageIndex: 0,
      availablePackages: [],
      warehouses: [],
      loading: false,
      confirming: false,
      checkoutOfflineDocumentId: null,
      userLocation: null,
      // 我的设备（扁平列表）：主设备/辅料 + 状态分组
      materialTab: 'main', // main | aux
      issuedItems: [],
      pickupTab: 'picked',
      pickupSearch: '',
      issuedPage: 1,
      issuedPageSize: 20,
      issuedTotal: 0,
      issuedHasMore: false,
      issuedLoading: false,
      issuedLoadingMore: false,
	      issuedTabCounts: {
	        picked: 0,
	        pending_receive: 0,
	        rejected: 0,
	        installed: 0,
	        returned: 0,
	      },

      // 设备详情 Bottom Sheet
      deviceDetailVisible: false,
      deviceDetailRecord: null,
      deviceDetailPreviewAction: '',
      deviceDetailPreviewData: {},
      deviceDetailPreviewLoading: false,
      deviceDetailPreviewReqId: 0,
      deviceDetailActionLoading: false,

      // 出库单详情（用于展示明细）
      deviceDetailOutLoading: false,
      deviceDetailOut: null,
      outDetailVisible: false,
      outDetailRecord: null,
      outDetailLoading: false,
      outDetailData: null,
    }
  },
  
	  computed: {
	    legacyScanPickupEnabled() {
	      return this.userStore?.legacyScanPickupEnabled === true
	    },
	    selectedPackage() {
	      return this.availablePackages[this.selectedPackageIndex]
	    },

	    pickupTabOptions() {
	      const c = this.issuedTabCounts || {}
	      return [
	        { key: 'picked', label: this.$t('stock.pickupTabPicked'), count: Number(c.picked || 0) },
	        { key: 'installed', label: this.$t('stock.pickupTabInstalled'), count: Number(c.installed || 0) },
	        { key: 'pending_receive', label: this.$t('stock.pickupTabPendingReceive'), count: Number(c.pending_receive || 0) },
	        { key: 'rejected', label: this.$t('stock.pickupTabRejected'), count: Number(c.rejected || 0) },
	        { key: 'returned', label: this.$t('stock.pickupTabReturned'), count: Number(c.returned || 0) },
	      ]
	    },

    visiblePickupTabOptions() {
      if (this.materialTab === 'aux') {
        return this.pickupTabOptions.filter(t => t.key !== 'installed')
      }
      return this.pickupTabOptions
    },

    issuedSearchPlaceholder() {
      return this.$t('stock.pickupSearchPlaceholder')
    },

    deviceDetailSn() {
      return (this.deviceDetailRecord?.serial_number || this.deviceDetailRecord?.main_device_barcode || '').trim()
    },

	    deviceStatusBadgeText() {
	      if (!this.deviceDetailRecord) return '-'
	      if (this.deviceDetailRecord.is_returned) return this.$t('stock.statusReturned')
	      if (this.deviceDetailRecord.return_status) return this.statusTextForReturn(this.deviceDetailRecord.return_status)
	      const g = String(this.deviceDetailRecord.status_group || this.deviceDetailRecord.pickup_group || '').trim()
	      if (g === 'returned') return this.$t('stock.statusReturned')
	      if (g === 'pending_receive') return this.statusTextForReturn('pending_receive')
	      if (g === 'rejected') return this.$t('stock.returnStatusRejectedShort')
	      if (g === 'installed') return this.$t('stock.statusInstalled')
	      if (g === 'picked') return this.$t('stock.pickupTabPicked')
	      return '-'
	    },

    deviceStatusBadgeClass() {
      if (!this.deviceDetailRecord) return 'none'
      if (this.deviceDetailRecord.is_returned) return 'done'
      const s = (this.deviceDetailRecord.return_status || '').toString()
      if (s === 'pending_receive' || s === 'partially_received') return 'pending'
      if (s === 'received') return 'done'
      if (s === 'rejected') return 'rejected'
      if (s === 'canceled') return 'canceled'

	      const g = String(this.deviceDetailRecord.status_group || this.deviceDetailRecord.pickup_group || '').trim()
	      if (g === 'returned') return 'done'
	      if (g === 'pending_receive') return 'pending'
	      if (g === 'rejected') return 'rejected'
	      if (g === 'installed') return 'installed'
	      return 'none'
	    },
	
	    showDeviceRejectReason() {
	      if (!this.deviceDetailRecord) return false
	      const status = String(this.deviceDetailRecord.return_status || '').trim()
	      const g = String(this.deviceDetailRecord.status_group || this.deviceDetailRecord.pickup_group || '').trim()
	      return status === 'rejected' || g === 'rejected'
	    },

	    deviceRejectReasonText() {
	      const text = String(this.deviceDetailRecord?.return_reject_reason || '').trim()
	      if (text) return text
	      return this.$t('stock.returnRejectReasonEmpty')
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
      const g = String(this.deviceDetailRecord.status_group || this.deviceDetailRecord.pickup_group || '').trim()
      return g !== 'returned'
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

    this.loadWarehouses()
    this.loadIssuedItems()
    this.getCurrentLocation()
  },

  onReachBottom() {
    if (this.issuedHasMore && !this.issuedLoading && !this.issuedLoadingMore) {
      this.loadMoreIssuedItems()
    }
  },
  
  methods: {
    buildParsedBarcodeForBackend(barcode) {
      const raw = String(barcode || '').trim()
      if (!raw) return null
      // 仅在复合格式（包含逗号/冒号）时解析，以减少不必要解析与日志输出
      if (!raw.includes(',') && !raw.includes(':')) return null
      const parsed = parseBarcode(raw)
      return parsed && parsed.success ? parsed : null
    },

    toggleScanSection() {
      this.scanSectionCollapsed = !this.scanSectionCollapsed
    },

    startScanFromCollapsed() {
      if (this.scanSectionCollapsed) this.scanSectionCollapsed = false
      this.startScan()
    },

    filterActivePackages(packages) {
      const list = Array.isArray(packages) ? packages : []
      return list.filter((pkg) => {
        if (!pkg || typeof pkg !== 'object') return false
        const status = String(pkg.status || '').trim().toLowerCase()
        if (!status) return true
        return status === 'active'
      })
    },

    recordKey(record) {
      if (!record) return Math.random().toString(16).slice(2)
      const outId = String(record.out_transaction_id || '').trim()
      if (record.item_type === 'aux') {
        return `${outId}-${String(record.equipment_id || '')}`
      }
      return `${outId}-${String(record.serial_number || record.main_device_barcode || record.equipment_instance_id || '')}`
    },

    recordPrimaryText(record) {
      if (!record) return '-'
      if (record.item_type === 'aux') return record.equipment_name || record.equipment_code || '-'
      const sn = String(record.serial_number || record.main_device_barcode || '').trim()
      if (sn) return sn
      return record.equipment_name || record.equipment_code || record.out_document_number || '-'
    },

    recordSecondaryText(record) {
      if (!record) return '-'
      const warehouse = record.warehouse_name ? ` · ${record.warehouse_name}` : ''
      if (record.item_type === 'aux') {
        return `${record.equipment_code || '-'}${warehouse}`
      }
      return `${record.equipment_name || record.equipment_code || '-'}${warehouse}`
    },

    displayUnit(unit) {
      return getLocalizedStockUnit(unit, this.$t)
    },

    openIssuedDetail(record) {
      if (!record) return
      if (record.item_type === 'aux') this.openOutDetail(record)
      else this.openDeviceDetail(record)
    },

    switchMaterialTab(tab) {
      const next = String(tab || '').trim()
      if (!next || next === this.materialTab) return
      this.materialTab = next
      if (this.materialTab === 'aux' && this.pickupTab === 'installed') {
        this.pickupTab = 'picked'
      }
      this.loadIssuedItems(true, 1)
    },

    refreshIssuedItems() {
      this.loadIssuedItems(true, 1)
    },

    openDeviceDetail(record) {
      if (!record) return
      this.deviceDetailRecord = record
      this.deviceDetailVisible = true
      this.deviceDetailPreviewAction = ''
      this.deviceDetailPreviewData = {}
      this.deviceDetailPreviewLoading = false
      this.deviceDetailActionLoading = false
      this.deviceDetailOutLoading = false
      this.deviceDetailOut = null
      this.refreshDeviceDetailPreview()
      this.loadDeviceDetailOut()
    },

    closeDeviceDetail() {
      this.deviceDetailVisible = false
      this.deviceDetailRecord = null
      this.deviceDetailPreviewAction = ''
      this.deviceDetailPreviewData = {}
      this.deviceDetailPreviewLoading = false
      this.deviceDetailActionLoading = false
      this.deviceDetailOutLoading = false
      this.deviceDetailOut = null
    },

    async loadDeviceDetailOut() {
      const outId = String(this.deviceDetailRecord?.out_transaction_id || '').trim()
      if (!outId) return
      this.deviceDetailOutLoading = true
      try {
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl(`/api/stock/my-stock-outs/${outId}`),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            success: resolve,
            fail: reject
          })
        })
        if (res.statusCode !== 200) return
        this.deviceDetailOut = res.data || null
      } catch (e) {
        console.error('加载出库单详情失败:', e)
      } finally {
        this.deviceDetailOutLoading = false
      }
    },

    async openOutDetail(record) {
      this.outDetailRecord = record
      this.outDetailVisible = true
      this.outDetailLoading = true
      this.outDetailData = null
      try {
        const outId = String(record?.out_transaction_id || '').trim()
        if (!outId) return
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl(`/api/stock/my-stock-outs/${outId}`),
            method: 'GET',
            header: getAuthHeaders(this.userStore.token),
            success: resolve,
            fail: reject
          })
        })
        if (res.statusCode !== 200) return
        this.outDetailData = res.data || null
      } catch (e) {
        console.error('加载出库单详情失败:', e)
      } finally {
        this.outDetailLoading = false
      }
    },

    closeOutDetail() {
      this.outDetailVisible = false
      this.outDetailRecord = null
      this.outDetailLoading = false
      this.outDetailData = null
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
        const parsed = this.buildParsedBarcodeForBackend(barcode)
        const res = await new Promise((resolve, reject) => {
          uni.request({
            url: buildApiUrl('/api/stock/scan-return/preview'),
            method: 'POST',
            header: getAuthHeaders(this.userStore.token),
            data: {
              barcode,
              parsed_barcode: parsed,
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
      const outId = String(record.out_transaction_id || '').trim()
      const sn = String(record.serial_number || record.main_device_barcode || '').trim()
      if (!outId || !sn) {
        uni.showToast({ title: this.$t('messages.operationFailed'), icon: 'none' })
        return
      }
      this.closeDeviceDetail()
      setTimeout(() => {
        uni.navigateTo({
          url: `/pages/stock/returns/create?out_transaction_id=${encodeURIComponent(outId)}&sn=${encodeURIComponent(sn)}`
        })
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
	        const scanned = await scanAndParseDeviceCode()
	        if (!scanned.ok) {
	          if (scanned.error === ScanDeviceCodeError.UNSUPPORTED_SCAN_TYPE) {
	            uni.showToast({
	              title: this.$t('stock.unsupportedScanType', { type: scanned.scanType || 'UNKNOWN' }),
	              icon: 'none'
	            })
	            return
	          }
	          if (scanned.error === ScanDeviceCodeError.EMPTY_RESULT) {
	            uni.showToast({ title: this.$t('stock.scanResultEmpty'), icon: 'none' })
	            return
	          }
	          if (scanned.error === ScanDeviceCodeError.INVALID_BARCODE) {
	            uni.showToast({ title: scanned?.parsed?.error || this.$t('stock.invalidBarcode'), icon: 'none' })
	            return
	          }
	          uni.showToast({ title: this.$t('stock.scanFailed'), icon: 'none' })
	          return
	        }
	        
	        console.log('=== 扫码原始结果 ===')
	        console.log('scanType:', scanned.scanType)
	        console.log('raw:', scanned.raw)
	        console.log('raw类型:', typeof scanned.raw)
	        console.log('raw长度:', scanned.raw ? scanned.raw.length : 0)
	        
	        this.scanResult = scanned.raw
	        
	        console.log('=== 使用统一扫码策略结果 ===')
	        this.parsedBarcode = scanned.parsed
        
        console.log('=== 解析结果 ===')
        console.log('parsedBarcode:', JSON.stringify(this.parsedBarcode, null, 2))
        console.log('解析成功?:', this.parsedBarcode.success)
        console.log('SN:', this.parsedBarcode.sn)
        console.log('MAC1:', this.parsedBarcode.mac1)
        console.log('MAC2:', this.parsedBarcode.mac2)
        console.log('MAC3:', this.parsedBarcode.mac3)
        console.log('MAC4:', this.parsedBarcode.mac4)
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
      this.scannedEquipmentInstance = null
      this.availablePackages = []
      this.selectedPackageIndex = 0
      
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
        const statusCode = response.statusCode || response.status || 0
        this.scannedEquipmentInstance = equipmentData.equipment_instance || null
        const packageCandidates = Array.isArray(equipmentData?.available_packages)
          ? equipmentData.available_packages
          : []
        const activePackages = this.filterActivePackages(packageCandidates)

        const showIdentifyModal = (titleKey, hintKey, prefixLine = '') => {
          let message = ''
          if (prefixLine) message += `${prefixLine}\n`
          message += `${this.$t('stock.serialNumber')}: ${parsedData.sn}`
          if (parsedData.mac1) {
            message += `\n${this.$t('stock.macAddress1')}: ${this.formatMacAddress(parsedData.mac1)}`
          }
          if (parsedData.mac2) {
            message += `\n${this.$t('stock.macAddress2')}: ${this.formatMacAddress(parsedData.mac2)}`
          }
          if (parsedData.mac3) {
            message += `\n${this.$t('stock.macAddress3')}: ${this.formatMacAddress(parsedData.mac3)}`
          }
          if (parsedData.mac4) {
            message += `\n${this.$t('stock.macAddress4')}: ${this.formatMacAddress(parsedData.mac4)}`
          }
          message += `\n\n${this.$t(hintKey)}`

          uni.showModal({
            title: this.$t(titleKey),
            content: message,
            showCancel: true,
            confirmText: this.$t('stock.rescan'),
            cancelText: this.$t('stock.copySn'),
            success: (res) => {
              if (res.confirm) {
                this.resetScan()
              } else {
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

        if (statusCode && statusCode !== 200) {
          const detail = equipmentData?.detail || equipmentData?.message || this.$t('messages.requestFailedWithCode', { code: statusCode })
          if (statusCode === 404) {
            showIdentifyModal('stock.deviceNotInInventoryTitle', 'stock.deviceNotInInventoryHint')
          } else {
            uni.showToast({
              title: this.$t('messages.operationFailed') + ': ' + detail,
              icon: 'none'
            })
          }
          return
        }
        
        if (equipmentData.equipment && activePackages.length > 0) {
          console.log('=== 查询成功 ===')
          console.log('找到设备:', equipmentData.equipment.name)
          console.log('可用套装数量:', activePackages.length)
          
          this.availablePackages = activePackages
          this.selectedPackageIndex = 0
          
          uni.showToast({
            title: this.$t('stock.deviceRecognizedToast', { name: equipmentData.equipment.name }),
            icon: 'success'
          })
        } else if (equipmentData.equipment && activePackages.length === 0) {
          console.log('=== 查询失败：未配置套装 ===')
          showIdentifyModal(
            'stock.packageNotConfiguredTitle',
            'stock.packageNotConfiguredHint',
            this.$t('stock.deviceRecognizedToast', { name: equipmentData.equipment.name })
          )
        } else {
          console.log('=== 查询失败 ===')
          console.log('设备存在?:', !!equipmentData.equipment)
          console.log('套装存在?:', packageCandidates.length > 0)
          console.log('套装数量:', packageCandidates.length)
          showIdentifyModal('stock.deviceNotInInventoryTitle', 'stock.deviceNotInInventoryHint')
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
    
    async resolveCheckoutWarehouseId() {
      const name = this.scannedEquipmentInstance?.warehouse_name
      if (!name) return null
      let list = this.warehouses || []
      let matched = list.find(w => w.warehouse_name === name)
      if (!matched) {
        await this.loadWarehouses()
        list = this.warehouses || []
        matched = list.find(w => w.warehouse_name === name)
      }
      return matched?.id || null
    },
    
    async confirmPickup() {
      if (!this.selectedPackage) {
        uni.showToast({ title: this.$t('stock.pleaseSelectPackage'), icon: 'none' })
        return
      }

      const warehouseId = await this.resolveCheckoutWarehouseId()
      if (!warehouseId) {
        uni.showToast({ title: this.$t('stock.checkoutWarehouseMissing'), icon: 'none' })
        return
      }
      
      try {
        this.confirming = true
        
        const pickupData = {
          barcode: this.scanResult,
          parsed_barcode: this.parsedBarcode, // 传递解析后的数据
          package_id: this.selectedPackage.id,
          warehouse_id: warehouseId,
          gps_location: this.userLocation,
          offline_document_id: this.checkoutOfflineDocumentId || undefined,
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
        const statusCode = Number(response.statusCode || 0)

        // HTTP 非 200：优先按后端返回的 action 处理，否则提示错误信息
        if (statusCode && statusCode !== 200) {
          if (responseData?.action === 'select_package' && Array.isArray(responseData?.available_packages)) {
            const activePackages = this.filterActivePackages(responseData.available_packages)
            this.availablePackages = activePackages
            this.selectedPackageIndex = 0
            uni.showToast({
              title: responseData.message || this.$t('stock.pleaseSelectPackage'),
              icon: 'none',
              duration: 2500
            })
            return
          }

          const msg = responseData?.detail || responseData?.message || this.$t('messages.operationFailed')
          uni.showToast({
            title: this.$t('stock.pickupFailedPrefix') + msg,
            icon: 'none',
            duration: 3000
          })
          return
        }
        
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
        } else if (responseData.action === 'select_package' && Array.isArray(responseData?.available_packages)) {
          const activePackages = this.filterActivePackages(responseData.available_packages)
          this.availablePackages = activePackages
          this.selectedPackageIndex = 0
          uni.showToast({
            title: responseData.message || this.$t('stock.pleaseSelectPackage'),
            icon: 'none',
            duration: 2500
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
      this.scannedEquipmentInstance = null
      this.availablePackages = []
      this.selectedPackageIndex = 0
      this.checkoutOfflineDocumentId = null
      if (collapse) this.scanSectionCollapsed = true
    },
    
    getFormatName(format) {
      const map = {
        'sn_mac_comma': this.$t('stock.formatSnMacComma'),
        'sn_mac4_comma': this.$t('stock.formatSnMac4Comma'),
        'key_value_pairs': this.$t('stock.formatKeyValuePairs'),
        'pure_sn': this.$t('stock.formatPureSn')
      }
      return map[format] || this.$t('stock.formatUnknown')
    },
    
    formatMacAddress(mac) {
      return formatMacAddress(mac)
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
      } catch (error) {
        console.error('加载仓库列表失败:', error)
      }
    },
    
	    async loadIssuedItems(reset = true, targetPage = 1) {
	      const wantReset = reset === true

	      // 辅料不展示“已安装”
	      if (this.materialTab === 'aux' && this.pickupTab === 'installed') {
	        this.pickupTab = 'picked'
	      }

	      if (wantReset) {
	        if (this.issuedLoading) return
	        this.issuedLoading = true
	      } else {
	        if (this.issuedLoadingMore || this.issuedLoading) return
	        if (!this.issuedHasMore) return
	        this.issuedLoadingMore = true
	      }

	      try {
	        const page = wantReset ? 1 : Number(targetPage || 1)
	        const payload = {
	          page,
	          page_size: this.issuedPageSize,
	          item_type: this.materialTab,
	          status_group: this.pickupTab,
	        }
	        const q = (this.pickupSearch || '').trim()
	        if (q) payload.q = q

	        const url = buildApiUrl('/api/stock/my-issued-items')
	        const response = await new Promise((resolve, reject) => {
	          uni.request({
	            url,
	            method: 'GET',
	            header: getAuthHeaders(this.userStore.token),
	            data: payload,
	            success: resolve,
	            fail: reject
	          })
	        })

	        if (response.statusCode !== 200) {
	          console.warn('加载我的设备失败:', {
	            status: response.statusCode,
	            url,
	            payload,
	            data: response.data,
	          })

	          // 兼容：若后端未部署新接口，则回退到 /api/stock/my-pickups（仅主设备）
	          if (response.statusCode === 404 && this.materialTab === 'main') {
	            await this.loadIssuedItemsFromMyPickups(wantReset, page)
	            return
	          }

	          const msg = response.data?.detail || response.data?.message || this.$t('messages.operationFailed')
	          uni.showToast({ title: msg, icon: 'none' })
	          return
	        }

	        const data = response.data || {}
	        const records = Array.isArray(data.items) ? data.items : []
		        if (data.group_counts) {
		          const c = data.group_counts || {}
		          this.issuedTabCounts = {
		            picked: Number(c.picked || 0),
		            pending_receive: Number(c.pending_receive || 0),
		            rejected: Number(c.rejected || 0),
		            installed: Number(c.installed || 0),
		            returned: Number(c.returned || 0),
		          }
		        }
	        if (wantReset) {
	          this.issuedItems = records
	        } else {
	          this.issuedItems = [...(this.issuedItems || []), ...records]
	        }

	        this.issuedPage = data.page || page
	        this.issuedTotal = data.total || 0
	        this.issuedHasMore = !!data.has_more
	      } catch (error) {
	        console.error('加载我的设备失败:', error)
	      } finally {
	        if (wantReset) this.issuedLoading = false
	        else this.issuedLoadingMore = false
	      }
	    },

	    async loadIssuedItemsFromMyPickups(reset = true, targetPage = 1) {
	      const wantReset = reset === true
	      const page = wantReset ? 1 : Number(targetPage || 1)
	      const payload = {
	        page,
	        page_size: this.issuedPageSize,
	        pickup_group: this.pickupTab,
	      }
	      const q = (this.pickupSearch || '').trim()
	      if (q) payload.q = q

	      const url = buildApiUrl('/api/stock/my-pickups')
	      const response = await new Promise((resolve, reject) => {
	        uni.request({
	          url,
	          method: 'GET',
	          header: getAuthHeaders(this.userStore.token),
	          data: payload,
	          success: resolve,
	          fail: reject
	        })
	      })

	      if (response.statusCode !== 200) {
	        console.warn('回退加载我的设备失败:', {
	          status: response.statusCode,
	          url,
	          payload,
	          data: response.data,
	        })
	        const msg = response.data?.detail || response.data?.message || this.$t('messages.operationFailed')
	        uni.showToast({ title: msg, icon: 'none' })
	        return
	      }

	      const data = response.data || {}
	      const rows = Array.isArray(data.pickup_records) ? data.pickup_records : []
	      const records = rows.map((r) => {
	        const sn = String(r?.serial_number || r?.main_device_barcode || '').trim()
	        return {
	          item_type: 'main',
	          status_group: r?.pickup_group || 'picked',
	          source_tag: '扫码领料',
	          method_tag: '套装领料',
	          out_transaction_id: r?.transaction_id || null,
	          out_document_number: null,
	          warehouse_id: null,
	          warehouse_name: r?.equipment_instance?.warehouse_name || null,
	          operation_time: r?.pickup_time || null,
	          equipment_instance_id: r?.equipment_instance?.id || null,
	          serial_number: sn,
	          main_device_barcode: r?.main_device_barcode || null,
	          mac_address_1: r?.mac_address_1 || null,
	          mac_address_2: r?.mac_address_2 || null,
	          mac_address_3: r?.mac_address_3 || null,
	          mac_address_4: r?.mac_address_4 || null,
	          return_status: r?.return_status || null,
	          return_document_number: r?.return_document_number || null,
	          return_warehouse_id: r?.return_warehouse_id || null,
	          return_warehouse_name: r?.return_warehouse_name || null,
	          return_reject_reason: r?.return_reject_reason || null,
	          is_returned: !!r?.is_returned,
	        }
	      })

		      if (data.group_counts) {
		        const c = data.group_counts || {}
		        this.issuedTabCounts = {
		          picked: Number(c.picked || 0),
		          pending_receive: Number(c.pending_receive || 0),
		          rejected: Number(c.rejected || 0),
		          installed: Number(c.installed || 0),
		          returned: Number(c.returned || 0),
		        }
		      }

	      if (wantReset) {
	        this.issuedItems = records
	      } else {
	        this.issuedItems = [...(this.issuedItems || []), ...records]
	      }

	      this.issuedPage = data.page || page
	      this.issuedTotal = data.total || 0
	      this.issuedHasMore = !!data.has_more
	    },

	    // 兼容旧方法名
	    loadPickupHistory(reset = true, targetPage = 1) {
	      return this.loadIssuedItems(reset, targetPage)
	    },

	    refreshPickupHistory() {
	      this.loadIssuedItems(true, 1)
	    },

	    onPickupSearch() {
	      this.loadIssuedItems(true, 1)
	    },

	    clearPickupSearch() {
	      this.pickupSearch = ''
	      this.loadIssuedItems(true, 1)
	    },

	    switchPickupTab(tabKey) {
	      if (!tabKey || tabKey === this.pickupTab) return
	      if (this.materialTab === 'aux' && tabKey === 'installed') return
	      this.pickupTab = tabKey
	      this.loadIssuedItems(true, 1)
	    },

	    loadMoreIssuedItems() {
	      const next = (this.issuedPage || 1) + 1
	      this.loadIssuedItems(false, next)
	    },

	    // 兼容旧方法名
	    loadMorePickupHistory() {
	      this.loadMoreIssuedItems()
	    },

	    syncDeviceDetailRecordFromHistory() {
	      if (!this.deviceDetailRecord) return
	      const key = this.recordKey(this.deviceDetailRecord)
	      const latest = (this.issuedItems || []).find(r => this.recordKey(r) === key)
	      if (latest) this.deviceDetailRecord = { ...(this.deviceDetailRecord || {}), ...(latest || {}) }
	    },

	    getHistoryStatusText(record) {
	      if (!record) return ''
	      const g = String(record.status_group || record.pickup_group || '').trim()
	      if (g === 'installed') return this.$t('stock.pickupTabInstalled')
	      if (g === 'pending_receive') return this.$t('stock.pickupTabPendingReceive')
	      if (g === 'rejected') return this.$t('stock.pickupTabRejected')
	      if (g === 'returned') return this.$t('stock.pickupTabReturned')
	      return this.$t('stock.pickupTabPicked')
	    },

	    historyStatusClass(record) {
	      const g = String(record?.status_group || record?.pickup_group || '').trim()
	      return {
	        confirmed: g === 'picked',
	        installed: g === 'installed',
	        'return-pending': g === 'pending_receive',
	        'return-rejected': g === 'rejected',
	        returned: g === 'returned',
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
        partially_received: this.$t('stock.returnStatusPartiallyReceivedShort'),
        received: this.$t('stock.statusReturned'),
        rejected: this.$t('stock.returnStatusRejectedShort'),
        canceled: this.$t('stock.returnStatusCanceledShort')
      }
	      return map[status] || status
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

.offline-documents {
  margin-top: 24rpx;
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

      .section-title-right {
        display: flex;
        align-items: center;
        gap: 12rpx;
      }

      .material-tabs {
        display: flex;
        align-items: center;
        border: 1rpx solid #e5e7eb;
        border-radius: 999rpx;
        background: #f3f4f6;
        overflow: hidden;
      }

      .material-tab {
        padding: 10rpx 18rpx;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #374151;
        font-size: 24rpx;
        font-weight: 600;

        &:active { opacity: 0.85; }

        &.active {
          background: var(--color-primary);
          color: #ffffff;
        }
      }
	    
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
        align-items: flex-start;
        margin-bottom: 10rpx;

        .history-left {
          display: flex;
          align-items: baseline;
          gap: 12rpx;
          min-width: 0;
          flex: 1;
        }

        .history-sn {
          font-size: 30rpx;
          color: var(--text-primary);
          font-weight: 600;
          min-width: 0;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .history-qty {
          font-size: 24rpx;
          color: #6b7280;
          flex-shrink: 0;
        }
        
        .history-time {
          font-size: 24rpx;
          color: #6b7280;
          flex-shrink: 0;
        }
      }

      .history-sub {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12rpx;
        margin-bottom: 10rpx;

        .history-doc {
          font-size: 24rpx;
          color: #374151;
          min-width: 0;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .history-status {
          flex-shrink: 0;
          font-size: 24rpx;
          color: #f59e0b;

          &.confirmed { color: #10b981; }
          &.return-pending { color: #f59e0b; }
          &.return-rejected { color: #ef4444; }
          &.return-canceled { color: #6b7280; }
          &.installed { color: #2563eb; }
          &.returned { color: #10b981; }
        }
      }

      .history-detail {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12rpx;

        .history-barcode {
          font-size: 24rpx;
          color: #6b7280;
          min-width: 0;
          flex: 1;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .history-tags {
          display: flex;
          align-items: center;
          gap: 8rpx;
          flex-wrap: wrap;
          justify-content: flex-end;
          flex-shrink: 0;
        }

        .history-tag {
          font-size: 22rpx;
          padding: 4rpx 12rpx;
          border-radius: 999rpx;
          background: #eef2ff;
          color: #3730a3;
          line-height: 1.2;
          white-space: nowrap;
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
.status-badge.installed { background: #dbeafe; color: #1d4ed8; }
.status-badge.rejected { background: #fee2e2; color: #b91c1c; }
.status-badge.canceled { background: #e5e7eb; color: #4b5563; }
.status-badge.done { background: #dcfce7; color: #166534; }

.summary-tags {
  margin-top: 10rpx;
  display: flex;
  flex-wrap: wrap;
  gap: 8rpx;
  justify-content: flex-end;
}

.summary-tag {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  background: #eef2ff;
  color: #3730a3;
  line-height: 1.2;
  white-space: nowrap;
}

.out-notes {
  background: var(--bg-page);
  border-radius: 12rpx;
  padding: 14rpx 16rpx;
  margin-bottom: 12rpx;
}

.out-notes-label {
  display: block;
  font-size: 24rpx;
  color: var(--text-secondary);
  margin-bottom: 6rpx;
}

.out-notes-value {
  display: block;
  font-size: 26rpx;
  color: var(--text-primary);
  line-height: 1.45;
  word-break: break-word;
}

.out-items {
  display: flex;
  flex-direction: column;
  gap: 12rpx;
}

.out-item {
  padding: 14rpx 16rpx;
  background: #ffffff;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
}

.out-item-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
}

.out-item-name {
  flex: 1;
  min-width: 0;
  font-size: 28rpx;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.out-item-tag {
  font-size: 22rpx;
  padding: 4rpx 12rpx;
  border-radius: 999rpx;
  background: #f1f5f9;
  color: #334155;
  flex-shrink: 0;
  white-space: nowrap;
}

.out-item-tag.main {
  background: #dbeafe;
  color: #1d4ed8;
}

.out-item-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12rpx;
  margin-top: 10rpx;
}

.out-item-code {
  flex: 1;
  min-width: 0;
  font-size: 24rpx;
  color: #6b7280;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.out-item-qty {
  flex-shrink: 0;
  font-size: 26rpx;
  color: var(--text-primary);
  font-weight: 600;
  text-align: right;
}

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
.reject-content { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6rpx; }
.reject-title { font-size: 24rpx; color: #991b1b; font-weight: 700; }
.reject-text { flex: 1; font-size: 24rpx; color: #b91c1c; line-height: 1.4; word-break: break-all; }

.return-hint-card {
  padding: 18rpx;
  background: var(--bg-page);
  border-radius: 12rpx;
  color: var(--text-primary);
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
