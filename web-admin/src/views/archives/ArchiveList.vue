<template>
  <div class="page">
    <div class="page-header">
      <h1>勘察档案（新）</h1>
      <div class="header-actions">
        <el-input v-model="keyword" placeholder="搜索站点名称/编码" clearable style="width: 260px" @keyup.enter.native="reload" />
        <el-button type="primary" @click="reload">
          <el-icon><Search /></el-icon>
          筛选
        </el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="items" v-loading="loading" stripe>
        <el-table-column prop="site_code" label="站点编码" width="140">
          <template #default="{ row }">{{ row.site_code || '-' }}</template>
        </el-table-column>
        <el-table-column prop="site_name" label="站点名称" min-width="180" />
        <el-table-column prop="current_version" label="版本" width="100" />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">
              <el-icon><View /></el-icon>
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next, jumper"
          :total="total"
          :current-page="page"
          :page-size="pageSize"
          :page-sizes="[10,20,50,100]"
          @current-change="p => { page = p; reload() }"
          @size-change="s => { pageSize = s; page = 1; reload() }"
        />
      </div>
    </el-card>
  </div>
 </template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { surveyArchivesApi } from '@/api/surveyArchives'

const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')

const reload = async () => {
  try {
    loading.value = true
    const res = await surveyArchivesApi.page({ page: page.value, page_size: pageSize.value, keyword: keyword.value || undefined })
    items.value = Array.isArray(res?.items) ? res.items : []
    total.value = Number(res?.total || 0)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

const formatDate = (v) => v ? new Date(v).toLocaleString() : '-'
const viewDetail = (row) => router.push({ name: 'SurveyArchiveDetail', params: { id: row.id } })

onMounted(reload)
</script>

<style scoped>
.page { padding: 16px; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; }
.header-actions { display: flex; gap: 8px; align-items: center; }
.pager { display: flex; justify-content: flex-end; padding-top: 8px; }
</style>

