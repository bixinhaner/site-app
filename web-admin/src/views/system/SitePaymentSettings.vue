<template>
  <div class="page">
    <div class="page-header">
      <h1>站点付款规则</h1>
      <div class="header-actions">
        <el-button @click="loadSettings" :loading="loading">
          <el-icon><Refresh /></el-icon>刷新
        </el-button>
        <el-button @click="addRule">
          <el-icon><Plus /></el-icon>新增规则
        </el-button>
        <el-button type="primary" @click="saveSettings" :loading="saving">
          <el-icon><Document /></el-icon>保存
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mb16"
      title="比例金额按“站点合同金额”计算；如果站点未填写合同金额，对应比例节点会保持“待补充金额基数”。"
    />

    <el-card v-loading="loading">
      <el-form :model="form" label-width="140px">
        <el-form-item label="配置版本">
          <el-input-number v-model="form.config_version" :min="1" />
          <div class="tip">保存时会按当前版本落库；如需强制递增，我可以后续再加并发校验。</div>
        </el-form-item>
        <el-form-item label="币种">
          <el-input v-model="form.currency" maxlength="10" placeholder="例如 USD / CNY / UGX" style="max-width: 240px;" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt16" v-loading="loading">
      <template #header>
        <div class="table-header">
          <span>规则列表</span>
          <span class="tip">节点是否付款、付款比例/金额、是否依赖开站工单最终 approve、warning 折减都在这里配置。</span>
        </div>
      </template>

      <el-empty v-if="!form.rules.length" description="暂无付款规则，点击右上角“新增规则”开始配置" />

      <div v-else class="rule-list">
        <div v-for="(rule, index) in form.rules" :key="rule.local_id" class="rule-card">
          <div class="rule-card-head">
            <div class="rule-card-title">规则 {{ index + 1 }}</div>
            <el-button link type="danger" @click="removeRule(index)">删除</el-button>
          </div>

          <el-form :model="rule" label-width="140px" class="rule-form">
            <el-form-item label="规则名称">
              <el-input v-model="rule.name" maxlength="100" placeholder="例如：安装完成 40%" />
            </el-form-item>
            <el-form-item label="节点">
              <el-select v-model="rule.milestone_code" style="width: 100%">
                <el-option
                  v-for="option in milestoneOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item label="是否付款">
              <el-switch v-model="rule.enabled" active-text="付款" inactive-text="不付款" />
            </el-form-item>
            <el-form-item label="金额方式">
              <el-radio-group v-model="rule.amount_type">
                <el-radio label="ratio">比例</el-radio>
                <el-radio label="fixed">固定金额</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="rule.amount_type === 'ratio' ? '付款比例(%)' : '付款金额'">
              <el-input-number
                v-model="rule.amount_value"
                :min="0"
                :precision="2"
                :step="rule.amount_type === 'ratio' ? 5 : 100"
              />
            </el-form-item>
            <el-form-item label="依赖开站工单最终 approve">
              <el-switch v-model="rule.requires_work_order_approved" />
            </el-form-item>
            <el-form-item label="warning 折减">
              <div class="inline-row">
                <el-switch v-model="rule.warning_discount_enabled" />
                <el-input-number
                  v-model="rule.warning_discount_ratio"
                  :min="0"
                  :max="100"
                  :precision="2"
                  :disabled="!rule.warning_discount_enabled"
                />
                <span class="suffix-text">%</span>
              </div>
            </el-form-item>
            <el-form-item label="排序">
              <el-input-number v-model="rule.sort_order" :min="1" :step="10" />
            </el-form-item>
            <el-form-item label="备注 / 条件说明">
              <el-input v-model="rule.remark" type="textarea" :rows="2" placeholder="例如：客户已书面确认后才可申请收款" />
            </el-form-item>
          </el-form>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Document, Plus, Refresh } from '@element-plus/icons-vue'
import request from '@/utils/request'

const loading = ref(false)
const saving = ref(false)
const form = ref({
  config_version: 1,
  currency: 'USD',
  rules: [],
})
const milestoneOptions = ref([])

const createRule = (rule = {}, index = 0) => ({
  local_id: `${rule.id || rule.milestone_code || 'rule'}_${Date.now()}_${index}_${Math.random().toString(16).slice(2, 8)}`,
  id: rule.id || '',
  name: rule.name || '',
  milestone_code: rule.milestone_code || 'install_started',
  enabled: rule.enabled !== false,
  amount_type: rule.amount_type || 'ratio',
  amount_value: Number(rule.amount_value || 0),
  requires_work_order_approved: !!rule.requires_work_order_approved,
  warning_discount_enabled: !!rule.warning_discount_enabled,
  warning_discount_ratio: Number(rule.warning_discount_ratio ?? 100),
  sort_order: Number(rule.sort_order || ((index + 1) * 10)),
  remark: rule.remark || '',
})

const normalizedCurrency = computed(() => String(form.value.currency || '').trim().toUpperCase() || 'USD')

const loadSettings = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/system/site-payment-settings')
    form.value.config_version = Number(res?.config_version || 1)
    form.value.currency = res?.currency || 'USD'
    form.value.rules = Array.isArray(res?.rules) ? res.rules.map((rule, index) => createRule(rule, index)) : []
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : []
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || '加载站点付款规则失败')
  } finally {
    loading.value = false
  }
}

const addRule = () => {
  form.value.rules.push(createRule({}, form.value.rules.length))
}

const removeRule = (index) => {
  form.value.rules.splice(index, 1)
}

const saveSettings = async () => {
  const payloadRules = form.value.rules.map((rule, index) => ({
    id: rule.id || undefined,
    name: String(rule.name || '').trim(),
    milestone_code: String(rule.milestone_code || '').trim(),
    enabled: !!rule.enabled,
    amount_type: rule.amount_type,
    amount_value: Number(rule.amount_value || 0),
    requires_work_order_approved: !!rule.requires_work_order_approved,
    warning_discount_enabled: !!rule.warning_discount_enabled,
    warning_discount_ratio: Number(rule.warning_discount_ratio ?? 100),
    sort_order: Number(rule.sort_order || ((index + 1) * 10)),
    remark: String(rule.remark || '').trim() || undefined,
  }))

  const invalid = payloadRules.find((rule) => !rule.name || !rule.milestone_code)
  if (invalid) {
    ElMessage.warning('请先补全规则名称和节点')
    return
  }

  try {
    saving.value = true
    const res = await request.put('/api/system/site-payment-settings', {
      config_version: Number(form.value.config_version || 1),
      currency: normalizedCurrency.value,
      rules: payloadRules,
    })
    form.value.config_version = Number(res?.config_version || form.value.config_version || 1)
    form.value.currency = res?.currency || normalizedCurrency.value
    form.value.rules = Array.isArray(res?.rules) ? res.rules.map((rule, index) => createRule(rule, index)) : []
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : milestoneOptions.value
    ElMessage.success('保存成功')
  } catch (error) {
    console.error(error)
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') {
      ElMessage.error(detail)
      return
    }
    ElMessage.error('保存站点付款规则失败')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadSettings()
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

.mt16 {
  margin-top: 16px;
}

.table-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rule-card {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  padding: 16px;
  background: #fafafa;
}

.rule-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.rule-card-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.rule-form {
  max-width: 720px;
}

.tip {
  font-size: 12px;
  color: #909399;
}

.inline-row {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}

.suffix-text {
  color: #606266;
}
</style>
