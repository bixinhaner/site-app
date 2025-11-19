<template>
  <div class="page">
    <div class="page-header">
      <h1>OMC API 配置</h1>
      <div class="header-actions">
        <el-button @click="loadConfig" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button @click="testConnection" :loading="testing">
          <el-icon><Cpu /></el-icon>测试连接
        </el-button>
        <el-button type="primary" @click="save" :loading="saving">
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!isAdmin"
      type="error"
      title="仅管理员(admin)可以查看和修改 OMC 配置"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card v-loading="loading">
      <el-form :model="form" label-width="140px" :disabled="!isAdmin">
        <el-form-item label="OMC 基础地址">
          <el-input
            v-model="form.base_url"
            placeholder="例如：http://172.21.175.129:8081"
          />
          <div class="tip">
            后端会在此基础上拼接 <code>/northboundApi/v1/...</code> 路径。
          </div>
        </el-form-item>
        <el-form-item label="API 用户名">
          <el-input
            v-model="form.username"
            placeholder="用于调用 OMC API 的用户名"
          />
        </el-form-item>
        <el-form-item label="API 密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="用于调用 OMC API 的密码（留空则保持不变）"
            show-password
          />
        </el-form-item>
        <el-form-item label="超时时间(秒)">
          <el-input-number v-model="form.timeout_seconds" :min="3" :max="60" />
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document, Cpu } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()
const loading = ref(false)
const saving = ref(false)
const testing = ref(false)
const form = ref({
  base_url: '',
  username: '',
  password: '',
  timeout_seconds: 10,
})

const isAdmin = computed(() => userStore.user?.role === 'admin')

const loadConfig = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/omc/config')
    form.value.base_url = res.base_url || ''
    form.value.username = res.username || ''
    form.value.password = ''
    form.value.timeout_seconds = res.timeout_seconds || 10
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载 OMC 配置失败')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!isAdmin.value) {
    ElMessage.error('只有管理员可以保存配置')
    return
  }
  try {
    saving.value = true
    const payload = {
      base_url: form.value.base_url,
      username: form.value.username,
      password: form.value.password || undefined,
      timeout_seconds: form.value.timeout_seconds || 10,
    }
    await request.put('/api/omc/config', payload)
    ElMessage.success('保存成功')
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    let msg = '保存失败'
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('；')
    }
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

const testConnection = async () => {
  if (!isAdmin.value) {
    ElMessage.error('只有管理员可以测试连接')
    return
  }
  try {
    testing.value = true
    const res = await request.post('/api/omc/test')
    if (res?.success) {
      ElMessage.success(res.message || 'OMC API 测试成功')
    } else {
      ElMessage.error(res?.message || 'OMC API 测试失败')
    }
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    let msg = 'OMC API 测试失败'
    if (typeof detail === 'string') {
      msg = detail
    } else if (Array.isArray(detail)) {
      msg = detail.map(d => d.msg || JSON.stringify(d)).join('；')
    }
    ElMessage.error(msg)
  } finally {
    testing.value = false
  }
}

onMounted(() => {
  if (isAdmin.value) {
    loadConfig()
  }
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.header-actions {
  display: flex;
  gap: 12px;
}
.mb16 { margin-bottom: 16px; }
.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
