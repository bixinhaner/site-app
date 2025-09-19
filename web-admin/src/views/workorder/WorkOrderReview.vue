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
          <el-descriptions-item label="状态"><el-tag>{{ statusText(order.status) }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="分配时间">{{ formatDateTime(order.assigned_at) }}</el-descriptions-item>
          <el-descriptions-item label="提交时间">{{ formatDateTime(order.submitted_at) }}</el-descriptions-item>
        </el-descriptions>

        <el-divider />
        <div class="section-header">
          <h3>检查项审核</h3>
          <div v-if="summary">
            <el-tag type="success">通过 {{ summary.pass_count }}</el-tag>
            <el-tag type="warning" style="margin-left:8px;">警告 {{ summary.warning_count }}</el-tag>
            <el-tag type="danger" style="margin-left:8px;">不合格 {{ summary.fail_count }}</el-tag>
            <el-tag style="margin-left:8px;">待审 {{ summary.pending_count }}</el-tag>
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
              <el-tag v-if="row.status === 'completed'" type="success" size="small">已完成</el-tag>
              <el-tag v-else-if="row.status === 'pending'" type="info" size="small">待处理</el-tag>
              <el-tag v-else size="small">{{ row.status }}</el-tag>
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
              <el-button link type="success" size="small" @click="reviewItem(row, 'pass')">通过</el-button>
              <el-button link type="warning" size="small" @click="reviewItem(row, 'warning')">警告</el-button>
              <el-button link type="danger" size="small" @click="reviewItem(row, 'fail')">不合格</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-divider />
        <div class="section-header">
          <h3>照片审核</h3>
        </div>
        <el-table :data="photos" size="small" stripe v-loading="photosLoading">
          <el-table-column prop="original_name" label="文件名" min-width="200" />
          <el-table-column label="预览" width="120">
            <template #default="{ row }">
              <el-image 
                :src="getImageUrl(row.file_path)" 
                :preview-src-list="[getImageUrl(row.file_path)]"
                style="width: 80px; height: 60px; border-radius: 4px;"
                fit="cover"
                preview-teleported
              />
            </template>
          </el-table-column>
          <el-table-column prop="taken_at" label="拍摄时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.taken_at) }}</template>
          </el-table-column>
          <el-table-column label="位置信息" width="160">
            <template #default="{ row }">
              <div v-if="row.latitude && row.longitude">
                <div>{{ row.latitude.toFixed(6) }}</div>
                <div>{{ row.longitude.toFixed(6) }}</div>
              </div>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="review_status" label="审核结果" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.review_status === 'approved'" type="success">通过</el-tag>
              <el-tag v-else-if="row.review_status === 'rejected'" type="danger">驳回</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="viewPhotoDetail(row)">详情</el-button>
              <el-button link type="success" size="small" @click="reviewPhoto(row, 'approved')">通过</el-button>
              <el-button link type="danger" size="small" @click="reviewPhoto(row, 'rejected')">驳回</el-button>
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
              <el-button type="success" :disabled="!canFinalReview" @click="finalReview('approve')">通过</el-button>
              <el-button type="danger" :disabled="!canFinalReview" @click="finalReview('reject')">驳回</el-button>
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
            <el-tag v-if="selectedItem.status === 'completed'" type="success" size="small">已完成</el-tag>
            <el-tag v-else-if="selectedItem.status === 'pending'" type="info" size="small">待处理</el-tag>
            <el-tag v-else size="small">{{ selectedItem.status }}</el-tag>
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
            <el-table-column prop="field_name" label="字段名称" width="200" />
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
                  :preview-src-list="selectedItem.photos.map(p => getImageUrl(p.file_path))"
                  style="width: 100%; height: 120px;"
                  fit="cover"
                  preview-teleported
                />
                <div class="photo-info">
                  <div class="photo-name">{{ photo.original_name }}</div>
                  <div class="photo-time">{{ formatDateTime(photo.taken_at) }}</div>
                  <div v-if="photo.latitude && photo.longitude" class="photo-location">
                    {{ photo.latitude.toFixed(6) }}, {{ photo.longitude.toFixed(6) }}
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
        <el-button v-if="selectedItem && !selectedItem.review_status" type="success" @click="reviewItem(selectedItem, 'pass')">通过</el-button>
        <el-button v-if="selectedItem && !selectedItem.review_status" type="warning" @click="reviewItem(selectedItem, 'warning')">警告</el-button>
        <el-button v-if="selectedItem && !selectedItem.review_status" type="danger" @click="reviewItem(selectedItem, 'fail')">不合格</el-button>
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
              <el-descriptions-item label="审核状态">
                <el-tag v-if="selectedPhoto.review_status === 'approved'" type="success">通过</el-tag>
                <el-tag v-else-if="selectedPhoto.review_status === 'rejected'" type="danger">驳回</el-tag>
                <span v-else>待审</span>
              </el-descriptions-item>
              <el-descriptions-item label="审核意见">{{ selectedPhoto.review_comments || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </div>
      <template #footer>
        <el-button @click="photoDetailVisible = false">关闭</el-button>
        <el-button v-if="selectedPhoto && !selectedPhoto.review_status" type="success" @click="reviewPhoto(selectedPhoto, 'approved')">通过</el-button>
        <el-button v-if="selectedPhoto && !selectedPhoto.review_status" type="danger" @click="reviewPhoto(selectedPhoto, 'rejected')">驳回</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '../../api/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ZoomIn, ZoomOut, FullScreen, Aim } from '@element-plus/icons-vue'

const route = useRoute()
const loading = ref(false)
const order = ref(null)
const items = ref([])
const photos = ref([])
const itemsLoading = ref(false)
const photosLoading = ref(false)
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

const statuses = [
  { label: '待分配', value: 'PENDING' },
  { label: '已分配', value: 'ACTIVE' },
  { label: '已提交', value: 'SUBMITTED' },
  { label: '审核中', value: 'UNDER_REVIEW' },
  { label: '已通过', value: 'APPROVED' },
  { label: '已驳回', value: 'REJECTED' },
  { label: '已完成', value: 'COMPLETED' }
]
const types = [
  { label: '新站点设备安装', value: 'opening_inspection' },
  { label: '维护检查', value: 'maintenance' },
  { label: '断电问题', value: 'power_issue' },
  { label: '传输问题', value: 'transmission_issue' },
  { label: 'GPS问题', value: 'gps_issue' },
  { label: '信号问题', value: 'signal_issue' }
]

const canStartReview = computed(() => order.value && order.value.status === 'SUBMITTED')
const canFinalReview = computed(() => order.value && ['SUBMITTED','UNDER_REVIEW'].includes(order.value.status))

const refresh = async () => {
  const id = route.query.id
  if (!id) return
  try {
    loading.value = true
    // 先加载工单信息
    order.value = await apiClient.get(`/api/work-orders/${id}`)
    // 然后基于工单信息加载相关数据
    await Promise.all([loadItems(), loadPhotos(), loadSummary()])
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
      items.value = await apiClient.get(`/api/inspections/detail/${order.value.inspection_id}/items`)
    } else {
      // 否则加载工单自己的检查项
      items.value = await apiClient.get(`/api/work-orders/${id}/items`)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查项失败')
  } finally {
    itemsLoading.value = false
  }
}

const loadPhotos = async () => {
  const id = route.query.id
  if (!id) return
  try {
    photosLoading.value = true
    // 如果工单有关联的检查，优先加载检查的照片
    if (order.value && order.value.inspection_id) {
      const inspection = await apiClient.get(`/api/inspections/detail/${order.value.inspection_id}`)
      photos.value = inspection.photos || []
    } else {
      // 否则加载工单自己的照片
      photos.value = await apiClient.get(`/api/work-orders/${id}/photos`)
    }
  } catch (e) {
    // ignore
  } finally {
    photosLoading.value = false
  }
}

const loadSummary = async () => {
  const id = route.query.id
  if (!id) return
  try {
    summary.value = await apiClient.get(`/api/work-orders/${id}/review-summary`)
  } catch (e) {
    // ignore
  }
}

const startReview = async () => {
  const id = route.query.id
  try {
    await apiClient.post(`/api/work-orders/${id}/review/start`)
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
    const { value } = await ElMessageBox.prompt('请输入审核意见', '检查项审核', {
      confirmButtonText: '提交',
      cancelButtonText: '取消'
    })
    // 如果工单有关联的检查，调用检查项审核API
    if (order.value && order.value.inspection_id) {
      await apiClient.post(`/api/inspections/detail/${order.value.inspection_id}/items/${row.id}/review`, { action, comments: value || undefined })
    } else {
      // 否则调用工单项审核API
      await apiClient.post(`/api/work-orders/${id}/items/${row.id}/review`, { action, comments: value || undefined })
    }
    ElMessage.success('已提交')
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
    await apiClient.post(`/api/work-orders/${id}/review`, { action, comments: comments.value || undefined })
    ElMessage.success('审核已提交')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '审核失败')
  }
}

const reviewPhoto = async (row, action) => {
  const id = route.query.id
  try {
    const { value } = await ElMessageBox.prompt('请输入审核意见', '照片审核', {
      confirmButtonText: '提交',
      cancelButtonText: '取消'
    })
    // 如果工单有关联的检查，调用检查照片审核API
    if (order.value && order.value.inspection_id) {
      await apiClient.post(`/api/inspections/detail/${order.value.inspection_id}/photos/${row.id}/review`, { action, comments: value || undefined })
    } else {
      // 否则调用工单照片审核API
      await apiClient.post(`/api/work-orders/${id}/photos/${row.id}/review`, { action, comments: value || undefined })
    }
    ElMessage.success('已提交')
    await loadPhotos()
    // 如果在详情弹窗中审核，关闭弹窗
    if (photoDetailVisible.value) {
      photoDetailVisible.value = false
    }
  } catch (e) {
    if (e === 'cancel') return
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  }
}

const getImageUrl = (filePath) => {
  if (!filePath) return ''
  // 如果文件路径以uploads开头，需要添加后端URL前缀
  if (filePath.startsWith('uploads/')) {
    return `http://localhost:8000/${filePath}`
  }
  return filePath
}

const viewItemDetail = (item) => {
  selectedItem.value = item
  itemDetailVisible.value = true
}

const viewPhotoDetail = (photo) => {
  selectedPhoto.value = photo
  photoDetailVisible.value = true
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

const statusText = (v) => (statuses.find(s => s.value === v)?.label || v)
const typeText = (v) => (types.find(t => t.value === v)?.label || v)
const priorityText = (v) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[v] || v)
const formatDateTime = (val) => (val ? new Date(val).toLocaleString() : '-')

onMounted(refresh)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.section-header { display:flex; justify-content: space-between; align-items:center; margin: 8px 0; }

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
