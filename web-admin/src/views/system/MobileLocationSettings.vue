<template>
  <div class="page">
    <div class="page-header">
      <h1>移动端配置</h1>
      <div class="header-actions">
        <el-button @click="loadConfig" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button
          type="primary"
          @click="save"
          :loading="saving"
          :disabled="!canEdit"
        >
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      v-if="!canEdit"
      type="warning"
      title="当前用户仅可查看配置，修改需要管理员或项目经理权限"
      :closable="false"
      show-icon
      class="mb16"
    />

    <el-card class="mb16" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>移动端定位模式</span>
        </div>
      </template>

      <el-form :model="form" label-width="140px" :disabled="!canEdit">
        <el-form-item label="定位模式">
          <el-radio-group v-model="form.mode">
            <el-radio label="baidu">Baidu 模式（uni + 百度逆地理，默认）</el-radio>
            <el-radio label="native">原生插件模式（仅使用原生定位插件）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="当前生效说明">
          <ul class="hint-list">
            <li>
              <strong>Baidu 模式：</strong>
              手机 App 使用 <code>uni.getLocation(wgs84)</code> 获取坐标，
              再通过后端代理调用百度逆地理接口获取地址信息。
            </li>
            <li>
              <strong>原生插件模式：</strong>
              手机 App 使用原生定位插件获取坐标和地址，不依赖百度服务。
            </li>
            <li>
              所有拍照、水印、工单上传等定位场景都会使用当前配置的模式。
            </li>
          </ul>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card>
      <template #header>
        <div class="card-header">
          <span>其他移动端配置（预留）</span>
        </div>
      </template>
      <p class="placeholder-text">
        此区域预留给未来更多移动端行为开关和选项（例如：是否强制 GPS、水印样式模板选择、离线缓存策略等），当前版本暂未启用。
      </p>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { mobileSettingsApi } from '@/api/system'

const userStore = useUserStore()

const loading = ref(false)
const saving = ref(false)

const form = ref({
  mode: 'baidu',
})

const canEdit = computed(() => {
  const role = userStore.user?.role
  return role === 'admin' || role === 'manager'
})

const loadConfig = async () => {
  try {
    loading.value = true
    const res = await mobileSettingsApi.getLocationMode()
    const mode = (res?.mode || '').toLowerCase()
    form.value.mode = mode === 'native' ? 'native' : 'baidu'
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    ElMessage.error(detail || '加载移动端定位配置失败')
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!canEdit.value) {
    ElMessage.error('只有管理员或项目经理可以保存配置')
    return
  }
  try {
    saving.value = true
    await mobileSettingsApi.updateLocationMode(form.value.mode)
    ElMessage.success('保存成功，重新打开手机 App 后生效')
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

onMounted(() => {
  loadConfig()
})
</script>

<style scoped>
.page {
  padding: 24px;
}

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

.mb16 {
  margin-bottom: 16px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hint-list {
  margin: 0;
  padding-left: 18px;
  color: #606266;
  font-size: 13px;
  line-height: 1.6;
}

.hint-list li + li {
  margin-top: 4px;
}

.hint-list code {
  font-family: Menlo, Monaco, Consolas, 'Courier New', monospace;
  font-size: 12px;
  background-color: #f5f7fa;
  padding: 2px 4px;
  border-radius: 3px;
}

.placeholder-text {
  font-size: 13px;
  color: #909399;
  margin: 0;
}
</style>
