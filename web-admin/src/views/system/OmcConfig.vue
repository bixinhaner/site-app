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
      v-if="!canManageOmc"
      type="error"
      title="当前账号无 OMC 配置管理权限"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card v-loading="loading">
      <el-form :model="form" label-width="140px" :disabled="!canManageOmc">
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
        <el-form-item label="手工确认开关">
          <el-switch
            v-model="form.manual_confirm_enabled"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            开启后，工单审核台将显示“手工确认已上线/已激活”按钮（适用于项目服务器无法与 OMC 通信的场景）。
          </div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-loading="loading" class="mt16">
      <template #header>SSV 创建规则</template>
      <el-form :model="form" label-width="180px" :disabled="!canManageOmc">
        <el-form-item label="站点设备激活即可创建SSV">
          <el-switch
            v-model="form.ssv_create_by_ever_activated_only"
            active-text="开启"
            inactive-text="关闭"
          />
          <div class="tip">
            关闭后：沿用旧规则，仅当站点状态为 <code>operational</code> 时允许创建 SSV。
          </div>
          <div class="tip">
            开启后：不再判断站点状态，只要站点设备全部 <code>ever_activated</code> 即允许创建 SSV；包括 <code>maintenance</code> 等非运营中状态。
          </div>
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
  manual_confirm_enabled: false,
  ssv_create_by_ever_activated_only: false,
})

const canManageOmc = computed(() => userStore.hasPermission('system:mobile-settings:write'))

const loadConfig = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/omc/config')
    form.value.base_url = res.base_url || ''
    form.value.username = res.username || ''
    form.value.password = ''
    form.value.timeout_seconds = res.timeout_seconds || 10
    form.value.manual_confirm_enabled = !!res.manual_confirm_enabled
    form.value.ssv_create_by_ever_activated_only = !!res.ssv_create_by_ever_activated_only
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '加载 OMC 配置失败')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!canManageOmc.value) {
    ElMessage.error('当前账号无权限保存配置')
    return
  }
  try {
    saving.value = true
    const payload = {
      base_url: form.value.base_url,
      username: form.value.username,
      password: form.value.password || undefined,
      timeout_seconds: form.value.timeout_seconds || 10,
      manual_confirm_enabled: !!form.value.manual_confirm_enabled,
      ssv_create_by_ever_activated_only: !!form.value.ssv_create_by_ever_activated_only,
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
  if (!canManageOmc.value) {
    ElMessage.error('当前账号无权限测试连接')
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
  if (canManageOmc.value) {
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
.mt16 { margin-top: 16px; }
.tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
</style>
