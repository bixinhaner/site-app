<template>
  <div class="page">
    <div class="page-header">
      <h1>检查审核台</h1>
      <div>
        <el-button @click="refresh"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    
    <!-- 筛选表单 -->
    <el-card style="margin-bottom: 16px;" v-if="inspection">
      <el-form inline>
        <el-form-item label="设备SN">
          <el-input 
            v-model="filterForm.equipment_sn" 
            placeholder="输入设备序列号搜索"
            clearable
            @clear="handleFilter"
            style="width: 200px;"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="绑定状态">
          <el-select v-model="filterForm.binding_status" placeholder="全部" clearable style="width: 120px;">
            <el-option label="全部" value="" />
            <el-option label="已绑定" value="bound" />
            <el-option label="未绑定" value="unbound" />
          </el-select>
        </el-form-item>
        
        <el-form-item>
          <el-button type="primary" @click="handleFilter">
            <el-icon><Search /></el-icon> 查询
          </el-button>
          <el-button @click="handleResetFilter">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
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
          <el-table-column prop="sector_id" label="扇区" width="80" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.sector_id" size="small" type="info">
                扇区{{ row.sector_id }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="band" label="频段" width="100" align="center">
            <template #default="{ row }">
              <el-tag v-if="row.band" size="small" effect="plain">
                {{ row.band }}
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column prop="equipment_sn" label="设备SN" width="150" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-if="row.equipment_sn" class="equipment-cell">
                <el-icon color="#67c23a" :size="16"><CircleCheck /></el-icon>
                <span class="equipment-sn">{{ row.equipment_sn }}</span>
                <el-button 
                  link 
                  type="primary" 
                  size="small" 
                  @click="copyToClipboard(row.equipment_sn)"
                >
                  <el-icon><CopyDocument /></el-icon>
                </el-button>
              </div>
              <el-tag v-else-if="row.sector_id && row.band" type="warning" size="small">
                未绑定
              </el-tag>
              <span v-else>-</span>
            </template>
          </el-table-column>
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
import { ref, onMounted, reactive } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleCheck, CopyDocument, Search } from '@element-plus/icons-vue'

const route = useRoute()
const loading = ref(false)
const inspection = ref(null)
const commentsText = ref('')
const items = ref([])
const allItems = ref([]) // 存储所有检查项，用于筛选
const itemsLoading = ref(false)
const summary = ref(null)

// 筛选表单
const filterForm = reactive({
  equipment_sn: '',
  binding_status: ''
})

const refresh = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    loading.value = true
    inspection.value = await request.get(`/api/inspections/detail/${id}`)
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
    await request.post(`/api/inspections/detail/${inspection.value.id}/review`, {
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

const copyToClipboard = (text) => {
  navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('设备SN已复制到剪贴板')
  }).catch(() => {
    ElMessage.error('复制失败')
  })
}

const loadItems = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    itemsLoading.value = true
    const data = await request.get(`/api/inspections/detail/${id}/items`)
    allItems.value = data // 保存原始数据
    applyFilter() // 应用筛选
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查项失败')
  } finally {
    itemsLoading.value = false
  }
}

// 应用筛选
const applyFilter = () => {
  let filtered = [...allItems.value]
  
  // 按设备SN筛选
  if (filterForm.equipment_sn) {
    filtered = filtered.filter(item => 
      item.equipment_sn && item.equipment_sn.toLowerCase().includes(filterForm.equipment_sn.toLowerCase())
    )
  }
  
  // 按绑定状态筛选
  if (filterForm.binding_status === 'bound') {
    filtered = filtered.filter(item => item.equipment_sn)
  } else if (filterForm.binding_status === 'unbound') {
    filtered = filtered.filter(item => item.sector_id && item.band && !item.equipment_sn)
  }
  
  items.value = filtered
}

// 处理筛选
const handleFilter = () => {
  applyFilter()
}

// 重置筛选
const handleResetFilter = () => {
  filterForm.equipment_sn = ''
  filterForm.binding_status = ''
  applyFilter()
}

const loadSummary = async () => {
  const id = route.query.inspectionId
  if (!id) return
  try {
    summary.value = await request.get(`/api/inspections/detail/${id}/review-summary`)
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
    await request.post(`/api/inspections/detail/${inspection.value.id}/items/${row.id}/review`, {
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
    await request.post(`/api/inspections/detail/${inspection.value.id}/photos/${photo.id}/review`, {
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

.equipment-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}

.equipment-sn {
  font-family: 'Courier New', monospace;
  font-weight: 500;
  color: #409eff;
}
</style>
