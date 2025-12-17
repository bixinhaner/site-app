<template>
  <div class="page">
    <div class="page-header">
      <h1>工单审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <template v-if="order">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="标题">{{ order.title }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeText(order.type) }}</el-descriptions-item>
          <el-descriptions-item label="站点">{{ order.site_name || order.site_id }}</el-descriptions-item>
          <el-descriptions-item label="分配给">{{ order.assignee_name }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ priorityText(order.priority) }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag>{{ statusText(order.status, order.type) }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分配时间">{{ formatDateTime(order.assigned_at) }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatDateTime(order.submitted_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />

        <!-- 开站工单设备状态，仅对 opening_inspection 展示 -->
        <el-card
          v-if="order.type === 'opening_inspection'"
          class="mb16"
          v-loading="deviceStatusLoading"
        >
          <template #header>
            <div class="card-header">
              <span>开站设备在线 / 激活状态</span>
              <div>
                <span v-if="deviceStatusCheckedAt" style="margin-right: 12px; color: #909399;">
                  最近检查时间：{{ formatDateTime(deviceStatusCheckedAt) }}
                </span>
                <el-button size="small" @click="loadDeviceStatus(false)">加载</el-button>
                <el-button
                  size="small"
                  type="primary"
                  :disabled="deviceRefreshCooldown > 0"
                  @click="loadDeviceStatus(true)"
                >
                  <span v-if="deviceRefreshCooldown > 0">
                    刷新状态 ({{ deviceRefreshCooldown }}s)
                  </span>
                  <span v-else>
                    刷新状态
                  </span>
                </el-button>
              </div>
            </div>
          </template>
          <el-empty v-if="!devices.length && !deviceStatusLoading" description="暂无绑定设备记录" />
          <el-table v-else :data="devices" size="small" stripe>
            <el-table-column prop="sn" label="设备 SN" min-width="180" />
            <el-table-column prop="equipment_type" label="设备类型" width="120" />
            <el-table-column prop="equipment_model" label="设备型号" min-width="160" />
            <el-table-column label="扇区信息" min-width="160">
              <template #default="{ row }">
                扇区 {{ row.sector_id || '-' }} / Band {{ row.band || '-' }} / Cell {{ row.cell_id || '-' }}
              </template>
            </el-table-column>
            <el-table-column label="在线状态" width="200">
              <template #default="{ row }">
                <div class="status-cell">
                  <el-tag :type="onlineRealtimeTagType(row.online)" size="small" class="mr4">
                    {{ onlineRealtimeText(row.online) }}
                  </el-tag>
                  <el-tag :type="everOnlineTagType(row.ever_online)" size="small">
                    {{ everOnlineText(row.ever_online) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="激活状态" width="220">
              <template #default="{ row }">
                <div class="status-cell">
                  <el-tag :type="activeRealtimeTagType(row.activated)" size="small" class="mr4">
                    {{ activeRealtimeText(row.activated) }}
                  </el-tag>
                  <el-tag :type="everActiveTagType(row.ever_activated)" size="small">
                    {{ everActiveText(row.ever_activated) }}
                  </el-tag>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="安装人" width="140">
              <template #default="{ row }">
                {{ row.installer_name || row.installer_id || '-' }}
              </template>
            </el-table-column>
            <el-table-column prop="bound_at" label="绑定时间" width="180">
              <template #default="{ row }">
                {{ formatDateTime(row.bound_at) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <div class="section-header">
          <h3>检查项审核</h3>
          <div v-if="summary">
            <el-tag type="success">通过 {{ summary.pass_count }}</el-tag>
            <el-tag type="warning" style="margin-left:8px;">警告 {{ summary.warning_count }}</el-tag>
            <el-tag type="danger" style="margin-left:8px;">不合格 {{ summary.fail_count }}</el-tag>
            <el-tag style="margin-left:8px;">待审 {{ summary.pending_count }}</el-tag>
            <!-- 审核状态提示 -->
            <el-alert 
              v-if="hasPendingItems" 
              style="margin-left:16px; display:inline-block;" 
              type="warning" 
              size="small"
              :closable="false"
              :title="`还有 ${pendingItemsCount} 项检查项未完成审核，请先完成所有检查项的审核！`"
            />
            <el-alert 
              v-else-if="hasFailedItems" 
              style="margin-left:16px; display:inline-block;" 
              type="error" 
              size="small"
              :closable="false"
              title="存在不合格检查项，工单无法通过审核！"
            />
            <el-alert 
              v-else-if="!hasPendingItems && !hasFailedItems" 
              style="margin-left:16px; display:inline-block;" 
              type="success" 
              size="small"
              :closable="false"
              title="所有检查项已审核完成，可以进行最终审核"
            />
          </div>
        </div>
        <el-table :data="items" size="small" stripe v-loading="itemsLoading">
          <el-table-column prop="item_name" label="检查项" min-width="220" />
          <el-table-column prop="required_type" label="类型" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.required_type === 'photo'" type="info" size="small">照片</el-tag>
              <el-tag v-else-if="row.required_type === 'data'" type="warning" size="small">数据</el-tag>
              <el-tag v-else-if="row.required_type === 'both'" type="primary" size="small">数据+照片</el-tag>
              <span v-else>{{ row.required_type }}</span>
            </template>
          </el-table-column>
          <el-table-column label="内容" width="200">
            <template #default="{ row }">
              <div>
                <div v-if="row.data_value && row.data_value.length > 0" style="margin-bottom: 4px;">
                  <el-tag size="small" type="success">数据: {{ row.data_value.length }}项</el-tag>
                </div>
                <div v-if="row.photos && row.photos.length > 0">
                  <el-tag size="small" type="info">照片: {{ row.photos.length }}张</el-tag>
                </div>
                <div v-if="(!row.data_value || row.data_value.length === 0) && (!row.photos || row.photos.length === 0)">
                  <el-tag size="small" type="warning">无内容</el-tag>
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="提交状态" width="120">
            <template #default="{ row }">
              <el-tag :type="checkItemStatusTagType(row.status)" size="small">
                {{ checkItemStatusText(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="review_status" label="审核结果" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.review_status === 'pass'" type="success">通过</el-tag>
              <el-tag v-else-if="row.review_status === 'warning'" type="warning">警告</el-tag>
              <el-tag v-else-if="row.review_status === 'fail'" type="danger">不合格</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="review_comments" label="审核意见" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="viewItemDetail(row)">详情</el-button>
              <el-button link type="success" size="small" :disabled="!canReviewCheckItem(row)" @click="reviewItem(row, 'pass')">通过</el-button>
              <el-button link type="warning" size="small" :disabled="!canReviewCheckItem(row)" @click="reviewItem(row, 'warning')">警告</el-button>
              <el-button link type="danger" size="small" :disabled="!canReviewCheckItem(row)" @click="reviewItem(row, 'fail')">不合格</el-button>
              <el-tooltip v-if="!canReviewCheckItem(row)" :content="checkItemReviewDisabledReason(row)" placement="top">
                <span class="help-tip">?</span>
              </el-tooltip>
            </template>
          </el-table-column>
        </el-table>


        <el-divider />
        <el-form label-width="100px">
          <el-form-item label="审核意见">
            <el-input v-model="comments" type="textarea" :rows="3" placeholder="请输入审核意见" />
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="primary" :disabled="!canStartReview" @click="startReview">认领审核</el-button>
              <el-button type="success" :disabled="!canApprove" @click="finalReview('approve')">
                {{ hasFailedItems ? '存在不合格检查项，无法通过' : '通过' }}
              </el-button>
              <el-button type="danger" :disabled="!canReject" @click="finalReview('reject')">驳回</el-button>
              <el-button type="info" @click="showAuditHistory">
                <el-icon><Clock /></el-icon>查看审核历史
              </el-button>
            </el-space>
          </el-form-item>
        </el-form>
      </template>
      <div v-else>请选择一条工单或从列表进入。</div>
    </el-card>

    <!-- 检查项详情弹窗 -->
    <el-dialog v-model="itemDetailVisible" title="检查项详情" width="800px">
      <div v-if="selectedItem">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="检查项名称">{{ selectedItem.item_name }}</el-descriptions-item>
          <el-descriptions-item label="类型">
            <el-tag v-if="selectedItem.required_type === 'photo'" type="info" size="small">照片</el-tag>
            <el-tag v-else-if="selectedItem.required_type === 'data'" type="warning" size="small">数据</el-tag>
            <el-tag v-else-if="selectedItem.required_type === 'both'" type="primary" size="small">数据+照片</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="checkItemStatusTagType(selectedItem.status)" size="small">
              {{ checkItemStatusText(selectedItem.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">{{ formatDateTime(selectedItem.checked_at) }}</el-descriptions-item>
          <el-descriptions-item label="审核状态">
            <el-tag v-if="selectedItem.review_status === 'pass'" type="success">通过</el-tag>
            <el-tag v-else-if="selectedItem.review_status === 'warning'" type="warning">警告</el-tag>
            <el-tag v-else-if="selectedItem.review_status === 'fail'" type="danger">不合格</el-tag>
            <span v-else>待审核</span>
          </el-descriptions-item>
          <el-descriptions-item label="审核意见">{{ selectedItem.review_comments || '-' }}</el-descriptions-item>
        </el-descriptions>

        <!-- 数据内容 -->
        <div v-if="selectedItem.data_value && selectedItem.data_value.length > 0" style="margin-top: 20px;">
          <h4>填写数据</h4>
          <el-table :data="selectedItem.data_value" size="small" border>
            <el-table-column label="字段名称" width="200">
              <template #default="{ row }">
                {{ resolveFieldLabel(row.field_name) }}
              </template>
            </el-table-column>
            <el-table-column prop="value" label="填写值" min-width="150" />
            <el-table-column prop="unit" label="单位" width="100" />
          </el-table>
        </div>

        <!-- 照片内容 -->
        <div v-if="selectedItem.photos && selectedItem.photos.length > 0" style="margin-top: 20px;">
          <h4>相关照片 ({{ selectedItem.photos.length }}张)</h4>
          <el-row :gutter="10">
            <el-col v-for="photo in selectedItem.photos" :key="photo.id" :span="8">
              <div class="photo-card">
                <el-image 
                  :src="getImageUrl(photo.file_path)" 
                  style="width: 100%; height: 120px; cursor: pointer;"
                  fit="cover"
                  @click="viewPhotoDetail(photo)"
                />
                <div class="photo-info">
                  <div class="photo-name">{{ photo.original_name }}</div>
                  <div class="photo-time">{{ formatDateTime(photo.taken_at) }}</div>
                  <div v-if="photo.latitude && photo.longitude" class="photo-location">
                    {{ photo.latitude.toFixed(6) }}, {{ photo.longitude.toFixed(6) }}
                  </div>
                  <div class="photo-actions" style="margin-top: 4px;">
                    <el-button type="primary" size="small" @click="viewPhotoDetail(photo)">详情</el-button>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>
        </div>

        <!-- 如果没有内容 -->
        <div v-if="(!selectedItem.data_value || selectedItem.data_value.length === 0) && (!selectedItem.photos || selectedItem.photos.length === 0)" style="margin-top: 20px;">
          <el-empty description="该检查项暂无提交内容" />
        </div>
      </div>
      <template #footer>
        <el-button @click="itemDetailVisible = false">关闭</el-button>
        <template v-if="selectedItem && (!selectedItem.review_status || selectedItem.review_status === 'pending')">
          <el-button type="success" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'pass')">通过</el-button>
          <el-button type="warning" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'warning')">警告</el-button>
          <el-button type="danger" :disabled="!canReviewCheckItem(selectedItem)" @click="reviewItem(selectedItem, 'fail')">不合格</el-button>
          <el-tooltip v-if="!canReviewCheckItem(selectedItem)" :content="checkItemReviewDisabledReason(selectedItem)" placement="top">
            <span class="help-tip">?</span>
          </el-tooltip>
        </template>
      </template>
    </el-dialog>

    <!-- 照片详情弹窗 -->
    <el-dialog v-model="photoDetailVisible" title="照片详情" width="1200px" :fullscreen="isFullscreen">
      <div v-if="selectedPhoto">
        <el-row :gutter="20">
          <el-col :span="isFullscreen ? 18 : 16">
            <div class="photo-container">
              <div class="photo-toolbar">
                <el-button-group>
                  <el-button size="small" @click="zoomIn"><el-icon><ZoomIn /></el-icon></el-button>
                  <el-button size="small" @click="zoomOut"><el-icon><ZoomOut /></el-icon></el-button>
                  <el-button size="small" @click="resetZoom">重置</el-button>
                  <el-button size="small" @click="toggleFullscreen">
                    <el-icon v-if="!isFullscreen"><FullScreen /></el-icon>
                    <el-icon v-else><Aim /></el-icon>
                  </el-button>
                  <el-button size="small" type="primary" @click="downloadPhoto">
                    <el-icon><Download /></el-icon>下载
                  </el-button>
                </el-button-group>
                <span class="zoom-info">{{ Math.round(zoomLevel * 100) }}%</span>
              </div>
              <div class="photo-viewer" @wheel="handleWheel" @mousedown="handleMouseDown" @mousemove="handleMouseMove" @mouseup="handleMouseUp" @mouseleave="handleMouseUp">
                <img 
                  ref="photoImage"
                  :src="getImageUrl(selectedPhoto.file_path)" 
                  :style="{
                    transform: `scale(${zoomLevel}) translate(${translateX}px, ${translateY}px)`,
                    cursor: isDragging ? 'grabbing' : 'grab',
                    maxWidth: 'none',
                    maxHeight: 'none'
                  }"
                  @dragstart.prevent
                />
              </div>
            </div>
          </el-col>
          <el-col :span="isFullscreen ? 6 : 8">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="文件名">{{ selectedPhoto.original_name }}</el-descriptions-item>
              <el-descriptions-item label="拍摄时间">{{ formatDateTime(selectedPhoto.taken_at) }}</el-descriptions-item>
              <el-descriptions-item label="文件大小">{{ formatFileSize(selectedPhoto.file_size) }}</el-descriptions-item>
              <el-descriptions-item label="纬度">{{ selectedPhoto.latitude || '-' }}</el-descriptions-item>
              <el-descriptions-item label="经度">{{ selectedPhoto.longitude || '-' }}</el-descriptions-item>
              <el-descriptions-item label="GPS精度">{{ selectedPhoto.gps_accuracy || '-' }}</el-descriptions-item>
              <el-descriptions-item label="地址">{{ selectedPhoto.address || '-' }}</el-descriptions-item>
              <el-descriptions-item label="水印">{{ selectedPhoto.has_watermark ? '是' : '否' }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="photoDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 审核历史弹窗 -->
    <el-dialog v-model="auditHistoryVisible" title="审核历史" width="900px">
      <el-tabs v-model="activeHistoryTab">
        <el-tab-pane label="工单操作历史" name="workorder">
          <el-timeline v-if="workOrderLogs.length > 0">
            <el-timeline-item
              v-for="log in workOrderLogs"
              :key="log.id"
              :timestamp="formatDateTime(log.created_at)"
              placement="top"
              :type="getLogType(log.action)"
            >
              <el-card>
                <template #header>
                  <div class="card-header">
                    <span><strong>{{ log.operator_name }}</strong> ({{ log.operator_username }})</span>
                    <el-tag :type="getActionTagType(log.action)" size="small">{{ getActionText(log.action) }}</el-tag>
                  </div>
                </template>
                <div v-if="log.from_status || log.to_status">
                  状态变更：
                  <el-tag v-if="log.from_status" size="small">{{ statusText(log.from_status) }}</el-tag>
                  <el-icon><Right /></el-icon>
                  <el-tag v-if="log.to_status" size="small" :type="getStatusTagType(log.to_status)">{{ statusText(log.to_status) }}</el-tag>
                </div>
                <div v-if="isAssigneeChange(log)" style="margin-top: 8px;">
                  指派变更：
                  <el-tag size="small">
                    {{ log.details?.old_assignee_name || log.details?.old_assignee_id || '-' }}
                  </el-tag>
                  <el-icon><Right /></el-icon>
                  <el-tag size="small" type="success">
                    {{ log.details?.new_assignee_name || log.details?.new_assignee_id || log.details?.new_assignee || '-' }}
                  </el-tag>
                </div>
                <div v-if="log.comments" style="margin-top: 8px;">
                  <strong>意见：</strong>{{ log.comments }}
                </div>
                <div v-if="log.details" style="margin-top: 8px; color: #909399; font-size: 12px;">
                  详情：<pre style="margin: 0;">{{ JSON.stringify(log.details, null, 2) }}</pre>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无操作历史" />
        </el-tab-pane>
        
        <el-tab-pane label="检查操作历史" name="inspection">
          <el-timeline v-if="inspectionLogs.length > 0">
            <el-timeline-item
              v-for="log in inspectionLogs"
              :key="log.id"
              :timestamp="formatDateTime(log.created_at)"
              placement="top"
              :type="getLogType(log.action)"
            >
              <el-card>
                <template #header>
                  <div class="card-header">
                    <span><strong>{{ log.operator_name }}</strong> ({{ log.operator_username }})</span>
                    <el-tag :type="getActionTagType(log.action)" size="small">{{ getActionText(log.action) }}</el-tag>
                  </div>
                </template>
                <div v-if="log.from_status || log.to_status">
                  状态变更：
                  <el-tag v-if="log.from_status" size="small">{{ log.from_status }}</el-tag>
                  <el-icon><Right /></el-icon>
                  <el-tag v-if="log.to_status" size="small">{{ log.to_status }}</el-tag>
                </div>
                <div v-if="log.comments" style="margin-top: 8px;">
                  <strong>意见：</strong>{{ log.comments }}
                </div>
                <div v-if="log.details" style="margin-top: 8px; color: #909399; font-size: 12px;">
                  详情：<pre style="margin: 0;">{{ JSON.stringify(log.details, null, 2) }}</pre>
                </div>
              </el-card>
            </el-timeline-item>
          </el-timeline>
          <el-empty v-else description="暂无操作历史" />
        </el-tab-pane>
      </el-tabs>
      
      <template #footer>
        <el-button @click="auditHistoryVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import config from '../../config/env.js'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ZoomIn, ZoomOut, FullScreen, Aim, Download, Clock, Right } from '@element-plus/icons-vue'

const route = useRoute()
const loading = ref(false)
const order = ref(null)
const items = ref([])
const itemsLoading = ref(false)
const summary = ref(null)
const comments = ref('')
const photoDetailVisible = ref(false)
const selectedPhoto = ref(null)
const itemDetailVisible = ref(false)
const selectedItem = ref(null)
const isFullscreen = ref(false)
const zoomLevel = ref(1)
const translateX = ref(0)
const translateY = ref(0)
const isDragging = ref(false)
const dragStart = ref({ x: 0, y: 0 })
const photoImage = ref(null)
const auditHistoryVisible = ref(false)
const workOrderLogs = ref([])
const inspectionLogs = ref([])
const activeHistoryTab = ref('workorder')

// 设备状态
const deviceStatusLoading = ref(false)
const devices = ref([])
const deviceStatusCheckedAt = ref(null)

const statuses = [
  { label: '待分配', value: 'PENDING' },
  { label: '已分配', value: 'ACTIVE' },
  { label: '已提交', value: 'SUBMITTED' },
  { label: '审核中', value: 'UNDER_REVIEW' },
  { label: '已通过/待上线', value: 'APPROVED' },
  { label: '已开通(上线阶段)', value: 'ACTIVATED' },
  { label: '已驳回', value: 'REJECTED' },
  { label: '已完成', value: 'COMPLETED' }
]
const types = [
  { label: '新站点设备安装', value: 'opening_inspection' },
  { label: '维护检查', value: 'maintenance' },
  { label: '断电问题', value: 'power_issue' },
  { label: '传输问题', value: 'transmission_issue' },
  { label: 'GPS问题', value: 'gps_issue' },
  { label: '信号问题', value: 'signal_issue' },
  { label: '站点勘察', value: 'site_survey' }
]

const canStartReview = computed(() => order.value && order.value.status === 'SUBMITTED')
const canFinalReview = computed(() => order.value && ['SUBMITTED','UNDER_REVIEW'].includes(order.value.status))

const checkItemStatusText = (status) => {
  const value = (status ?? '').toString()
  const mapping = {
    pending: '待处理',
    in_progress: '进行中',
    completed: '已完成',
    failed: '失败',
    skipped: '跳过',
  }
  return mapping[value] || (value || '-')
}

const checkItemStatusTagType = (status) => {
  const value = (status ?? '').toString()
  const mapping = {
    pending: 'info',
    in_progress: 'warning',
    completed: 'success',
    failed: 'danger',
    skipped: 'info',
  }
  return mapping[value] || 'info'
}

const canReviewCheckItem = (item) => {
  const status = (item?.status ?? '').toString()
  return status === 'completed'
}

const checkItemReviewDisabledReason = (item) => {
  const statusText = checkItemStatusText(item?.status)
  return `该检查项未完成提交（当前：${statusText}），无法审核`
}

// 检查是否有不合格的检查项
const hasFailedItems = computed(() => {
  return items.value.some(item => item.review_status === 'fail')
})

// 检查是否有未审核的检查项
const hasPendingItems = computed(() => {
  return items.value.some(item => !item.review_status || item.review_status === 'pending')
})

// 获取未审核检查项的数量
const pendingItemsCount = computed(() => {
  return items.value.filter(item => !item.review_status || item.review_status === 'pending').length
})

// 只有在没有不合格检查项时才能通过
const canApprove = computed(() => {
  return canFinalReview.value && !hasFailedItems.value && !hasPendingItems.value
})

// 允许直接驳回（即使存在未完成/未审核项）
const canReject = computed(() => {
  return canFinalReview.value
})

const refresh = async () => {
  const id = route.query.id
  if (!id) return
  try {
    loading.value = true
    // 先加载工单信息
    order.value = await request.get(`/api/work-orders/${id}`)
    // 然后基于工单信息加载相关数据
    await Promise.all([loadItems(), loadSummary(), loadDeviceStatus(false)])
  } catch (e) {
    console.error(e)
    ElMessage.error('加载工单失败')
  } finally {
    loading.value = false
  }
}

const loadItems = async () => {
  const id = route.query.id
  if (!id) return
  try {
    itemsLoading.value = true
    // 如果工单有关联的检查，优先加载检查的检查项
    if (order.value && order.value.inspection_id) {
      items.value = await request.get(`/api/inspections/detail/${order.value.inspection_id}/items`)
    } else {
      // 否则加载工单自己的检查项
      items.value = await request.get(`/api/work-orders/${id}/items`)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查项失败')
  } finally {
    itemsLoading.value = false
  }
}


const loadSummary = async () => {
  const id = route.query.id
  if (!id) return
  try {
    summary.value = await request.get(`/api/work-orders/${id}/review-summary`)
  } catch (e) {
    // ignore
  }
}

const startReview = async () => {
  const id = route.query.id
  try {
    await request.post(`/api/work-orders/${id}/review/start`)
    ElMessage.success('已进入审核中')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '认领失败')
  }
}

const reviewItem = async (row, action) => {
  const id = route.query.id
  try {
    let value = ''
    
    // 根据审核动作决定是否强制要求输入意见
    if (action === 'pass') {
      // 通过时，意见可选
      try {
        const result = await ElMessageBox.prompt('请输入审核意见（可选）', '检查项审核', {
          confirmButtonText: '提交',
          cancelButtonText: '取消',
          inputValidator: null // 不验证输入
        })
        value = result.value || ''
      } catch (e) {
        if (e === 'cancel') return
        throw e
      }
    } else {
      // 警告或不合格时，必须输入意见
      try {
        const result = await ElMessageBox.prompt('请输入审核意见（必填）', '检查项审核', {
          confirmButtonText: '提交',
          cancelButtonText: '取消',
          inputValidator: (val) => {
            if (!val || val.trim() === '') {
              return '请输入审核意见'
            }
            return true
          }
        })
        value = result.value
      } catch (e) {
        if (e === 'cancel') return
        throw e
      }
    }

    // 如果工单有关联的检查，调用检查项审核API
	    if (order.value && order.value.inspection_id) {
	      await request.post(`/api/inspections/detail/${order.value.inspection_id}/items/${row.id}/review`, { action, comments: value || undefined })
	    } else {
	      // 否则调用工单项审核API
	      await request.post(`/api/work-orders/${id}/items/${row.id}/review`, { action, comments: value || undefined })
	    }
	    ElMessage.success('已提交')
	    // 审核成功后自动关闭“检查项详情”弹窗（不切换下一条）
	    itemDetailVisible.value = false
	    await Promise.all([loadItems(), loadSummary()])
	  } catch (e) {
	    if (e === 'cancel') return
	    console.error(e)
	    ElMessage.error(e?.response?.data?.detail || '提交失败')
	  }
	}

const finalReview = async (action) => {
  const id = route.query.id
  try {
    await request.post(`/api/work-orders/${id}/review`, { action, comments: comments.value || undefined })
    ElMessage.success('审核已提交')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '审核失败')
  }
}


const getImageUrl = (filePath) => {
  if (!filePath) return ''
  // 如果文件路径以uploads开头，需要添加后端URL前缀
  if (filePath.startsWith('uploads/')) {
    return `${config.API_BASE_URL}/${filePath}`
  }
  return filePath
}

// 将后端存储的 field_name（通常是字段ID）转换为可读的显示名称
const resolveFieldLabel = (fieldName) => {
  const item = selectedItem.value
  if (!item || !Array.isArray(item.fields)) {
    // 没有字段定义时，退回显示原始字段名
    return fieldName
  }
  const def = item.fields.find(f => f.field_id === fieldName || f.label === fieldName)
  return def?.label || fieldName
}

const viewItemDetail = (item) => {
  selectedItem.value = item
  itemDetailVisible.value = true
}

const viewPhotoDetail = (photo) => {
  console.log('viewPhotoDetail called with photo:', photo)
  selectedPhoto.value = photo
  photoDetailVisible.value = true
  console.log('photoDetailVisible set to:', photoDetailVisible.value)
  // 重置查看器状态
  resetZoom()
  isFullscreen.value = false
}

const zoomIn = () => {
  zoomLevel.value = Math.min(zoomLevel.value * 1.5, 5)
}

const zoomOut = () => {
  zoomLevel.value = Math.max(zoomLevel.value / 1.5, 0.1)
}

const resetZoom = () => {
  zoomLevel.value = 1
  translateX.value = 0
  translateY.value = 0
}

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value
}

const downloadPhoto = async () => {
  if (!selectedPhoto.value) return
  
  try {
    // 获取图片URL
    const imageUrl = getImageUrl(selectedPhoto.value.file_path)
    
    // 创建一个临时的a标签进行下载
    const link = document.createElement('a')
    link.href = imageUrl
    
    // 生成文件名：原始文件名 + GPS坐标 + 时间戳
    const timestamp = selectedPhoto.value.taken_at ? 
      new Date(selectedPhoto.value.taken_at).toISOString().replace(/[:.]/g, '-').substring(0, 19) : 
      'unknown-time'
    
    const gpsInfo = selectedPhoto.value.latitude && selectedPhoto.value.longitude ? 
      `_GPS-${selectedPhoto.value.latitude.toFixed(6)}-${selectedPhoto.value.longitude.toFixed(6)}` : 
      ''
    
    const originalName = selectedPhoto.value.original_name || 'photo'
    const extension = originalName.split('.').pop() || 'jpg'
    const baseName = originalName.replace(/\.[^/.]+$/, "")
    
    link.download = `${baseName}_${timestamp}${gpsInfo}.${extension}`
    
    // 触发下载
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    
    ElMessage.success('照片下载成功')
  } catch (error) {
    console.error('下载照片失败:', error)
    ElMessage.error('下载照片失败')
  }
}

const handleWheel = (e) => {
  e.preventDefault()
  const delta = e.deltaY > 0 ? -1 : 1
  if (delta > 0) {
    zoomIn()
  } else {
    zoomOut()
  }
}

const handleMouseDown = (e) => {
  if (zoomLevel.value > 1) {
    isDragging.value = true
    dragStart.value = { x: e.clientX - translateX.value, y: e.clientY - translateY.value }
  }
}

const handleMouseMove = (e) => {
  if (isDragging.value && zoomLevel.value > 1) {
    translateX.value = e.clientX - dragStart.value.x
    translateY.value = e.clientY - dragStart.value.y
  }
}

const handleMouseUp = () => {
  isDragging.value = false
}

const formatFileSize = (size) => {
  if (!size) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(2)} KB`
  return `${(size / (1024 * 1024)).toFixed(2)} MB`
}

const statusText = (status, type) => {
  if (type === 'opening_inspection') {
    if (status === 'APPROVED') return '待上线 (80%)'
    if (status === 'ACTIVATED') return '已上线待激活 (90%)'
    if (status === 'COMPLETED') return '已激活 (100%)'
  }
  return statuses.find(s => s.value === status)?.label || status
}
const typeText = (v) => (types.find(t => t.value === v)?.label || v)
const priorityText = (v) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[v] || v)
const formatDateTime = (val) => (val ? new Date(val).toLocaleString() : '-')

const onlineRealtimeText = (val) => {
  if (val === true) return '当前在线'
  if (val === false) return '当前离线'
  return '待检测'
}
const onlineRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}
const everOnlineTagType = (val) => (val ? 'success' : 'info')
const everOnlineText = (val) => (val ? '曾上线' : '未曾上线')

const activeRealtimeText = (val) => {
  if (val === true) return '当前已激活'
  if (val === false) return '当前未激活'
  return '待检测'
}
const activeRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'warning'
  return 'info'
}
const everActiveTagType = (val) => (val ? 'success' : 'info')
const everActiveText = (val) => (val ? '曾激活' : '未曾激活')

const deviceRefreshCooldown = ref(0)
let deviceCooldownTimer = null

const loadDeviceStatus = async (refresh = false) => {
  if (refresh && deviceRefreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${deviceRefreshCooldown.value}s 后再刷新设备状态`)
    return
  }
  // 仅开站工单需要设备状态
  if (!order.value || order.value.type !== 'opening_inspection') {
    devices.value = []
    deviceStatusCheckedAt.value = null
    return
  }
  try {
    deviceStatusLoading.value = true
    const res = await request.get(`/api/sites/${order.value.site_id}/omc/devices`, {
      params: { refresh: refresh ? 1 : 0 }
    })
    devices.value = Array.isArray(res.devices) ? res.devices : []
    deviceStatusCheckedAt.value = res.checked_at || null

    if (refresh) {
      startDeviceCooldown()
    }
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载设备状态失败')
  } finally {
    deviceStatusLoading.value = false
  }
}

// 审核历史相关方法
const showAuditHistory = async () => {
  if (!route.query.id) {
    ElMessage.warning('请先选择工单')
    return
  }
  
  try {
    // request 的响应拦截器已经返回了 response.data，所以直接使用
    const data = await request.get(`/api/work-orders/${route.query.id}/audit-logs`)
    workOrderLogs.value = data.work_order_logs || []
    inspectionLogs.value = data.inspection_logs || []
    auditHistoryVisible.value = true
  } catch (error) {
    console.error('获取审核历史失败:', error)
    ElMessage.error('获取审核历史失败：' + (error.response?.data?.detail || error.message))
  }
}

const getActionText = (action) => {
  const actionMap = {
    'create': '创建',
    'assign': '分配',
    'change_assignee': '重新分配',
    'batch_assignee_change': '重新分配(批量)',
    'accept': '接受',
    'submit': '提交',
    'resubmit': '重新提交',
    'start_review': '开始审核',
    'final_review': '最终审核',
    'approve': '通过',
    'reject': '驳回',
    'update_status': '更新状态',
    'update': '更新',
    'delete': '删除',
    'mark_completed': '标记完成',
    'activate': '激活'
  }
  return actionMap[action] || action
}

const isAssigneeChange = (log) => {
  const action = log?.action
  if (!action) return false
  return ['change_assignee', 'batch_assignee_change'].includes(action)
}

const getActionTagType = (action) => {
  if (['approve', 'accept'].includes(action)) return 'success'
  if (['reject', 'delete'].includes(action)) return 'danger'
  if (['submit', 'resubmit', 'start_review'].includes(action)) return 'warning'
  return 'info'
}

const getLogType = (action) => {
  if (['approve', 'accept', 'mark_completed'].includes(action)) return 'success'
  if (['reject', 'delete'].includes(action)) return 'danger'
  if (['submit', 'resubmit'].includes(action)) return 'primary'
  return 'info'
}

const getStatusTagType = (status) => {
  if (['APPROVED', 'COMPLETED'].includes(status)) return 'success'
  if (['REJECTED'].includes(status)) return 'danger'
  if (['SUBMITTED', 'UNDER_REVIEW'].includes(status)) return 'warning'
  return 'info'
}

const startDeviceCooldown = () => {
  deviceRefreshCooldown.value = 10
  if (deviceCooldownTimer) return
  deviceCooldownTimer = setInterval(() => {
    if (deviceRefreshCooldown.value > 0) {
      deviceRefreshCooldown.value -= 1
    }
    if (deviceRefreshCooldown.value <= 0) {
      clearInterval(deviceCooldownTimer)
      deviceCooldownTimer = null
    }
  }, 1000)
}

onMounted(refresh)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.section-header { display:flex; justify-content: space-between; align-items:center; margin: 8px 0; }

.status-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}
.mr4 {
  margin-right: 4px;
}

.help-tip {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-left: 4px;
  border: 1px solid #dcdfe6;
  border-radius: 50%;
  color: #909399;
  font-size: 12px;
  line-height: 1;
  cursor: help;
}

/* 审核历史样式 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* 照片查看器样式 */
.photo-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  background: #f5f7fa;
}

.photo-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #dcdfe6;
}

.zoom-info {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.photo-viewer {
  height: 600px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #000;
  position: relative;
  user-select: none;
}

.photo-viewer img {
  display: block;
  transition: transform 0.2s ease;
  transform-origin: center center;
}

/* 全屏模式下的样式调整 */
:deep(.el-dialog.is-fullscreen) .photo-viewer {
  height: calc(100vh - 200px);
}

:deep(.el-dialog.is-fullscreen) .el-descriptions {
  height: calc(100vh - 200px);
  overflow-y: auto;
}

/* 检查项详情弹窗样式 */
.photo-card {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 10px;
  background: #fff;
}

.photo-info {
  padding: 8px;
  background: #f5f7fa;
}

.photo-name {
  font-size: 12px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.photo-time {
  font-size: 11px;
  color: #909399;
  margin-bottom: 2px;
}

.photo-location {
  font-size: 11px;
  color: #606266;
  font-family: monospace;
}
</style>
