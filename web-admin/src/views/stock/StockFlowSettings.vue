<template>
  <div class="page-container">
    <div class="page-header">
      <div class="title-block">
        <h2>库存流程设置</h2>
        <div class="subtitle">控制“申请→领料→确认出库”与“快速出库”等开关（默认全开）</div>
      </div>
      <div class="header-actions">
        <el-button @click="load" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" :loading="saving" @click="save">
          <el-icon><Check /></el-icon>
          保存
        </el-button>
      </div>
    </div>

    <el-card class="card hero" shadow="never" v-loading="loading">
      <div class="hero-inner">
        <div class="badge">
          <span class="dot" />
          <span>设置会立即影响接口权限与入口</span>
        </div>
        <div class="note">
          建议：生产环境保留“快速出库”给仓库/管理员作为兜底；若关闭申请流程，新流程页面将不可用。
        </div>
      </div>
    </el-card>

    <el-card class="card" shadow="never">
      <el-form label-width="240px" class="form">
        <el-form-item label="启用物料申请流程">
          <el-switch v-model="settings.enable_material_request" />
          <div class="help">关闭后：物料申请 / 自助领料 / 待确认出库接口将拒绝访问</div>
        </el-form-item>

        <el-form-item label="申请提交后需要仓库审批" :disabled="!settings.enable_material_request">
          <el-switch v-model="settings.request_requires_approval" :disabled="!settings.enable_material_request" />
          <div class="help">关闭后：提交即自动全量批准（不占用库存）</div>
        </el-form-item>

        <el-form-item label="领料单需要仓库确认出库" :disabled="!settings.enable_material_request">
          <el-switch v-model="settings.issue_requires_warehouse_confirm" :disabled="!settings.enable_material_request" />
          <div class="help">本项目默认应为开启：库存以仓库“确认出库”时扣减为准</div>
        </el-form-item>

        <el-divider />

        <el-form-item label="允许快速出库（无申请）">
          <el-switch v-model="settings.allow_quick_stock_out" />
          <div class="help">关闭后：快速出库（无申请）接口将返回“快捷出库已关闭”（旧流程扫码领货请到“系统配置 → 移动端配置”单独控制）</div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { stockApi } from '../../api/stock'

const loading = ref(false)
const saving = ref(false)

const settings = reactive({
  enable_material_request: true,
  request_requires_approval: true,
  allow_quick_stock_out: true,
  issue_requires_warehouse_confirm: true,
})

const extractError = (error) => {
  const detail = error?.response?.data?.detail
  if (!detail) return error?.message || '操作失败'
  if (typeof detail === 'string') return detail
  return detail?.message || '操作失败'
}

const load = async () => {
  try {
    loading.value = true
    const res = await stockApi.getFlowSettings()
    const s = res?.settings || {}
    settings.enable_material_request = !!s.enable_material_request
    settings.request_requires_approval = !!s.request_requires_approval
    settings.allow_quick_stock_out = !!s.allow_quick_stock_out
    settings.issue_requires_warehouse_confirm = !!s.issue_requires_warehouse_confirm
  } catch (error) {
    console.error('加载设置失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    loading.value = false
  }
}

const save = async () => {
  try {
    saving.value = true
    const res = await stockApi.updateFlowSettings({ settings: { ...settings } })
    const saved = res?.settings || {}
    settings.enable_material_request = !!saved.enable_material_request
    settings.request_requires_approval = !!saved.request_requires_approval
    settings.allow_quick_stock_out = !!saved.allow_quick_stock_out
    settings.issue_requires_warehouse_confirm = !!saved.issue_requires_warehouse_confirm
    ElMessage.success('保存成功')
  } catch (error) {
    console.error('保存设置失败:', error)
    ElMessage.error(extractError(error))
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  await load()
})
</script>

<style scoped lang="scss">
.title-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.subtitle {
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.2px;
}

.hero {
  border-radius: 16px;
  border: 1px solid rgba(229, 231, 235, 0.9);
  background:
    radial-gradient(900px 240px at 10% 0%, rgba(249, 115, 22, 0.14), transparent 60%),
    radial-gradient(900px 260px at 90% 20%, rgba(59, 130, 246, 0.08), transparent 60%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.98));
}

.hero-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid rgba(249, 115, 22, 0.25);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--text-secondary);
  font-size: 12px;
}

.badge .dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #fff, var(--primary-color));
  box-shadow: 0 0 0 4px rgba(249, 115, 22, 0.16);
}

.note {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
  max-width: 560px;
}

.form :deep(.el-form-item__content) {
  display: grid;
  grid-template-columns: auto 1fr;
  align-items: center;
  column-gap: 16px;
}

.help {
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 980px) {
  .hero-inner {
    flex-direction: column;
    align-items: flex-start;
  }
  .form :deep(.el-form-item__content) {
    grid-template-columns: 1fr;
    row-gap: 8px;
  }
}
</style>
