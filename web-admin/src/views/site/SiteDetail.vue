<template>
  <div class="page">
    <div class="page-header">
      <h1>站点详情</h1>
      <el-button @click="$router.back()"><el-icon><Back /></el-icon>返回</el-button>
    </div>
    <el-card v-loading="loading">
      <div class="info-grid" v-if="site">
        <div class="item"><span class="label">站点名称</span><span class="value">{{ site.site_name }}</span></div>
        <div class="item"><span class="label">站点编码</span><span class="value">{{ site.site_code }}</span></div>
        <div class="item"><span class="label">类型</span><span class="value">{{ site.site_type || '-' }}</span></div>
        <div class="item"><span class="label">状态</span><span class="value">{{ site.status }}</span></div>
        <div class="item"><span class="label">地址</span><span class="value">{{ site.address || '-' }}</span></div>
        <div class="item"><span class="label">指派给</span><span class="value">{{ assigneeName }}</span></div>
      </div>
      <div class="actions">
        <el-button type="primary" @click="openAssign" :disabled="!canAssign"><el-icon><User /></el-icon>分配/变更负责人</el-button>
      </div>
    </el-card>

    <el-dialog v-model="assignVisible" title="分配站点" width="420px">
      <el-select v-model="selectedAssignee" placeholder="选择人员" style="width: 100%" filterable @visible-change="v=> v && loadUsers()">
        <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
      </el-select>
      <template #footer>
        <el-button @click="assignVisible = false">取消</el-button>
        <el-button type="primary" :loading="assigning" @click="confirmAssign">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import apiClient from '../../api/auth'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../../stores/user'

const route = useRoute()
const loading = ref(false)
const site = ref(null)
const userStore = useUserStore()
const userOptions = ref([])
const assignVisible = ref(false)
const assigning = ref(false)
const selectedAssignee = ref(null)

const load = async () => {
  try {
    loading.value = true
    const res = await apiClient.get(`/api/sites/${route.params.id}`)
    site.value = res
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点详情失败')
  } finally {
    loading.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await apiClient.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = res || []
  } catch (e) {
    // 可能无权限
  }
}

const assigneeName = computed(() => {
  if (!site.value || !site.value.assigned_to) return '-'
  const u = userOptions.value.find(u => u.id === site.value.assigned_to)
  return u ? (u.full_name || u.username) : site.value.assigned_to
})

const canAssign = computed(() => userStore.isAdmin || userStore.user?.role === 'manager')

const openAssign = () => {
  selectedAssignee.value = site.value?.assigned_to || null
  assignVisible.value = true
  loadUsers()
}

const confirmAssign = async () => {
  if (!selectedAssignee.value) {
    ElMessage.warning('请选择人员')
    return
  }
  try {
    assigning.value = true
    await apiClient.put(`/api/sites/${route.params.id}` , { assigned_to: selectedAssignee.value })
    ElMessage.success('分配成功')
    assignVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error('分配失败')
  } finally {
    assigning.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.info-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.item .label { color: var(--text-secondary); margin-right:8px; }
.item .value { color: var(--text-primary); font-weight: 500; }
.actions { margin-top: 16px; }
</style>
