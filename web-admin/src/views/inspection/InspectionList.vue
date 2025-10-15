<template>
  <div class="page">
    <div class="page-header">
      <h1>检查记录</h1>
      <div class="header-actions">
        <el-select v-model="status" clearable placeholder="状态筛选" style="width: 160px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="site_name" label="站点" width="160" />
        <el-table-column prop="inspector_name" label="检查员" width="120" />
        <el-table-column prop="inspection_type" label="类型" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }"><el-tag>{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="completion_rate" label="完成率%" width="120" />
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="review(row)"><el-icon><Stamp /></el-icon>审核</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import request from '@/utils/request'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const status = ref('')
const statuses = [
  { label: '草稿', value: 'draft' },
  { label: '进行中', value: 'in_progress' },
  { label: '已提交', value: 'submitted' },
  { label: '待审核', value: 'under_review' },
  { label: '已通过', value: 'approved' },
  { label: '已驳回', value: 'rejected' }
]

const load = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/inspections/', { params: status.value ? { status: status.value } : {} })
    items.value = res || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载检查记录失败')
  } finally {
    loading.value = false
  }
}

const review = (row) => {
  router.push({ name: 'InspectionReview', query: { inspectionId: row.id } })
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>

