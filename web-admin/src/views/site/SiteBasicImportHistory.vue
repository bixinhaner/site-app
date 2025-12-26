<template>
  <div class="page">
    <div class="page-header">
      <h1>导入历史</h1>
      <div class="header-actions">
        <el-button @click="goBack"><el-icon><Back /></el-icon>返回</el-button>
        <el-button type="primary" @click="loadData"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="items" border v-loading="loading">
        <el-table-column prop="batch_id" label="批次ID" min-width="220" />
        <el-table-column prop="file_name" label="文件名" min-width="200" />
        <el-table-column label="动作" width="110">
          <template #default="{ row }">
            <el-tag :type="row.action === 'import' ? 'success' : 'info'">{{ row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operator_name" label="操作人" width="140" />
        <el-table-column prop="created_at" label="时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="统计" min-width="220">
          <template #default="{ row }">
            共 {{ row.total_rows || 0 }} / 成功 {{ row.success_count || 0 }} / 失败 {{ row.failed_count || 0 }}
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, prev, pager, next"
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          @current-change="onPageChange"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import siteBasicApi from '../../api/siteBasic'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const goBack = () => router.back()

const formatDateTime = (val) => {
  if (!val) return '-'
  const d = new Date(val)
  if (Number.isNaN(d.getTime())) return String(val)
  return d.toLocaleString('zh-CN')
}

const loadData = async () => {
  try {
    loading.value = true
    const res = await siteBasicApi.listImportHistory({ page: page.value, page_size: pageSize.value })
    items.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

const onPageChange = (p) => {
  page.value = p
  loadData()
}

onMounted(loadData)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.pager { margin-top: 12px; display:flex; justify-content: flex-end; }
</style>
