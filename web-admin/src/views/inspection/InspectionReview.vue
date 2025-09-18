<template>
  <div class="page">
    <div class="page-header">
      <h1>检查审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <div v-if="inspection">
        <p><b>站点：</b>{{ inspection.site_name || inspection.site?.site_name || '-' }}</p>
        <p><b>检查员：</b>{{ inspection.inspector_name || inspection.inspector?.full_name || '-' }}</p>
        <p><b>状态：</b>{{ inspection.status }}</p>
        <el-form label-width="90px" style="max-width: 640px;">
          <el-form-item label="审核意见">
            <el-input v-model="commentsText" type="textarea" :rows="3" placeholder="可填写审核说明" />
          </el-form-item>
          <el-form-item>
            <el-space>
              <el-button type="success" @click="doReview('approve')" :disabled="!['submitted','under_review'].includes(inspection.status)">通过</el-button>
              <el-button type="danger" @click="doReview('reject')" :disabled="!['submitted','under_review'].includes(inspection.status)">驳回</el-button>
            </el-space>
          </el-form-item>
        </el-form>

        <el-divider />
        <div class="section-header">
          <h3>检查项审核</h3>
          <div class="summary" v-if="summary">
            <el-tag type="success">通过 {{ summary.pass_count }}</el-tag>
            <el-tag type="warning" style="margin-left:8px;">警告 {{ summary.warning_count }}</el-tag>
            <el-tag type="danger" style="margin-left:8px;">不合格 {{ summary.fail_count }}</el-tag>
            <el-tag style="margin-left:8px;">待审 {{ summary.pending_count }}</el-tag>
          </div>
        </div>
        <el-table :data="items" size="small" stripe v-loading="itemsLoading">
          <el-table-column prop="item_name" label="检查项" min-width="220" />
          <el-table-column prop="required_type" label="类型" width="100" />
          <el-table-column prop="status" label="提交状态" width="120" />
          <el-table-column prop="review_status" label="审核结果" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.review_status === 'pass'" type="success">通过</el-tag>
              <el-tag v-else-if="row.review_status === 'warning'" type="warning">警告</el-tag>
              <el-tag v-else-if="row.review_status === 'fail'" type="danger">不合格</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="review_comments" label="审核意见" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
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
        <el-table :data="inspection.photos || []" size="small" stripe>
          <el-table-column prop="original_name" label="文件名" min-width="200" />
          <el-table-column prop="taken_at" label="拍摄时间" width="180">
            <template #default="{ row }">{{ formatDateTime(row.taken_at) }}</template>
          </el-table-column>
          <el-table-column prop="review_status" label="审核结果" width="120">
            <template #default="{ row }">
              <el-tag v-if="row.review_status === 'approved'" type="success">通过</el-tag>
              <el-tag v-else-if="row.review_status === 'rejected'" type="danger">驳回</el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="review_comments" label="审核意见" min-width="200" show-overflow-tooltip />
          <el-table-column label="操作" width="200" fixed="right">
            <template #default="{ row }">
              <el-button link type="success" size="small" @click="reviewPhoto(row, 'approved')">通过</el-button>
              <el-button link type="danger" size="small" @click="reviewPhoto(row, 'rejected')">驳回</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
      <div v-else>请选择一条待审核检查或通过记录列表进入。</div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '../../api/auth'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const loading = ref(false)
const inspection = ref(null)
const commentsText = ref('')
const items = ref([])
const itemsLoading = ref(false)
const summary = ref(null)

const refresh = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    loading.value = true
    inspection.value = await apiClient.get(`/api/inspections/detail/${id}`)
    await Promise.all([loadItems(), loadSummary()])
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查详情失败')
  } finally {
    loading.value = false
  }
}

const doReview = async (action) => {
  try {
    await apiClient.post(`/api/inspections/detail/${inspection.value.id}/review`, {
      action,
      comments: commentsText.value || undefined
    })
    ElMessage.success('审核已提交')
    await refresh()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '审核失败')
  }
}

const formatDateTime = (val) => val ? new Date(val).toLocaleString() : '-'

const loadItems = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    itemsLoading.value = true
    items.value = await apiClient.get(`/api/inspections/detail/${id}/items`)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查项失败')
  } finally {
    itemsLoading.value = false
  }
}

const loadSummary = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    summary.value = await apiClient.get(`/api/inspections/detail/${id}/review-summary`)
  } catch (e) {
    // 可忽略
  }
}

const reviewItem = async (row, action) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入审核意见', '检查项审核', {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputPlaceholder: action === 'pass' ? '可填写通过说明' : (action === 'warning' ? '说明警告原因' : '说明不合格原因'),
    })
    await apiClient.post(`/api/inspections/detail/${inspection.value.id}/items/${row.id}/review`, {
      action,
      comments: value || undefined
    })
    ElMessage.success('已提交')
    await Promise.all([loadItems(), loadSummary()])
  } catch (e) {
    if (e === 'cancel') return
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  }
}

const reviewPhoto = async (photo, action) => {
  try {
    const { value } = await ElMessageBox.prompt('请输入审核意见', '照片审核', {
      confirmButtonText: '提交',
      cancelButtonText: '取消',
      inputPlaceholder: action === 'approved' ? '可填写通过说明' : '说明驳回原因',
    })
    await apiClient.post(`/api/inspections/detail/${inspection.value.id}/photos/${photo.id}/review`, {
      action,
      comments: value || undefined
    })
    ElMessage.success('已提交')
    await refresh()
  } catch (e) {
    if (e === 'cancel') return
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '提交失败')
  }
}

onMounted(refresh)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.section-header { display:flex; justify-content: space-between; align-items:center; margin: 8px 0; }
</style>
