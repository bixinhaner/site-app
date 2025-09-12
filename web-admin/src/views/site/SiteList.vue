<template>
  <div class="page">
    <div class="page-header">
      <h1>站点列表</h1>
      <div class="header-actions">
        <el-input v-model="keyword" placeholder="搜索站点名称/编码/区域" clearable style="width: 300px" @keyup.enter="loadSites" />
        <el-button type="primary" @click="loadSites">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
      </div>
    </div>

    <el-card>
      <el-table :data="sites" v-loading="loading" stripe>
        <el-table-column prop="site_code" label="站点编码" width="140" />
        <el-table-column prop="site_name" label="站点名称" min-width="180" />
        <el-table-column prop="site_type" label="类型" width="120" />
        <el-table-column prop="city" label="城市" width="120" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag>{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="viewDetail(row)">
              <el-icon><View /></el-icon>
              详情
            </el-button>
            <el-button link type="success" size="small" @click="assignSite(row)">
              <el-icon><User /></el-icon>
              分配
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import apiClient from '../../api/auth'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const loading = ref(false)
const sites = ref([])
const keyword = ref('')

const loadSites = async () => {
  try {
    loading.value = true
    const res = await apiClient.get('/api/sites/', { params: { limit: 50 } })
    sites.value = res || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点失败')
  } finally {
    loading.value = false
  }
}

const viewDetail = (row) => {
  router.push({ name: 'SiteDetail', params: { id: row.id } })
}

const assignSite = (row) => {
  ElMessage.info('分配功能稍后实现')
}

onMounted(loadSites)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>

