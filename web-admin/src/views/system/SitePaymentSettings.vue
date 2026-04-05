<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('sitePaymentSettings.pageTitle') }}</h1>
      <div class="header-actions">
        <el-button @click="loadSettings" :loading="loading">
          <el-icon><Refresh /></el-icon>{{ t('sitePaymentSettings.actions.refresh') }}
        </el-button>
        <el-button @click="addRule">
          <el-icon><Plus /></el-icon>{{ t('sitePaymentSettings.actions.addRule') }}
        </el-button>
        <el-button type="primary" @click="saveSettings" :loading="saving">
          <el-icon><Document /></el-icon>{{ t('sitePaymentSettings.actions.save') }}
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      class="mb16"
      :title="t('sitePaymentSettings.summaryAlert')"
    />

    <el-card v-loading="loading">
      <el-form :model="form" label-width="140px">
        <el-form-item :label="t('sitePaymentSettings.configVersion')">
          <el-input-number v-model="form.config_version" :min="1" />
          <div class="tip">{{ t('sitePaymentSettings.configVersionTip') }}</div>
        </el-form-item>
        <el-form-item :label="t('sitePaymentSettings.currency')">
          <el-select
            v-model="form.currency"
            filterable
            allow-create
            default-first-option
            :reserve-keyword="false"
            :placeholder="t('sitePaymentSettings.currencyPlaceholder')"
            style="max-width: 280px;"
          >
            <el-option
              v-for="option in mergedCurrencyOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <div class="tip">{{ t('sitePaymentSettings.currencyTip') }}</div>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt16" v-loading="loading">
      <template #header>
        <div class="table-header">
          <span>{{ t('sitePaymentSettings.rulesTitle') }}</span>
          <span class="tip">{{ t('sitePaymentSettings.rulesTip') }}</span>
        </div>
      </template>

      <el-empty v-if="!form.rules.length" :description="t('sitePaymentSettings.empty')" />

      <div v-else class="rule-list">
        <div v-for="(rule, index) in form.rules" :key="rule.local_id" class="rule-card">
          <div class="rule-card-head">
            <div class="rule-card-title">{{ t('sitePaymentSettings.ruleCardTitle', { index: index + 1 }) }}</div>
            <el-button link type="danger" @click="removeRule(index)">{{ t('sitePaymentSettings.actions.delete') }}</el-button>
          </div>

          <el-form :model="rule" label-width="140px" class="rule-form">
            <el-form-item :label="t('sitePaymentSettings.fields.name')">
              <el-input v-model="rule.name" maxlength="100" :placeholder="t('sitePaymentSettings.fields.namePlaceholder')" />
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.milestone')">
              <el-select v-model="rule.milestone_code" style="width: 100%">
                <el-option
                  v-for="option in milestoneOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.enabled')">
              <el-switch
                v-model="rule.enabled"
                :active-text="t('sitePaymentSettings.fields.enabledOn')"
                :inactive-text="t('sitePaymentSettings.fields.enabledOff')"
              />
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.amountType')">
              <el-radio-group v-model="rule.amount_type">
                <el-radio label="ratio">{{ t('sitePaymentSettings.fields.amountTypeRatio') }}</el-radio>
                <el-radio label="fixed">{{ t('sitePaymentSettings.fields.amountTypeFixed') }}</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item :label="rule.amount_type === 'ratio' ? t('sitePaymentSettings.fields.amountRatio') : t('sitePaymentSettings.fields.amountFixed')">
              <el-input-number
                v-model="rule.amount_value"
                :min="0"
                :precision="2"
                :step="rule.amount_type === 'ratio' ? 5 : 100"
              />
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.requiresApprove')">
              <el-switch v-model="rule.requires_work_order_approved" />
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.warningDiscount')">
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
            <el-form-item :label="t('sitePaymentSettings.fields.sortOrder')">
              <el-input-number v-model="rule.sort_order" :min="1" :step="10" />
            </el-form-item>
            <el-form-item :label="t('sitePaymentSettings.fields.remark')">
              <el-input v-model="rule.remark" type="textarea" :rows="2" :placeholder="t('sitePaymentSettings.fields.remarkPlaceholder')" />
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
import { useI18n } from 'vue-i18n'
import request from '@/utils/request'

const { t } = useI18n()
const loading = ref(false)
const saving = ref(false)
const form = ref({
  config_version: 1,
  currency: 'USD',
  rules: [],
})
const milestoneOptions = ref([])
const currencyOptions = ref([])
const fallbackCurrencyOptions = [
  'USD',
  'CNY',
  'EUR',
  'JPY',
  'IDR',
  'ZAR',
  'NGN',
  'EGP',
  'KES',
  'GHS',
  'TZS',
  'UGX',
  'XOF',
  'XAF',
  'ETB',
]

const normalizeCurrencyCode = (value) => String(value || '').trim().toUpperCase()

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

const normalizedCurrency = computed(() => normalizeCurrencyCode(form.value.currency) || 'USD')

const mergedCurrencyOptions = computed(() => {
  const seen = new Set()
  const list = []
  const pushCurrency = (value, label) => {
    const code = normalizeCurrencyCode(value)
    if (!code || seen.has(code)) return
    seen.add(code)
    list.push({
      value: code,
      label: normalizeCurrencyCode(label) || code,
    })
  }

  fallbackCurrencyOptions.forEach((code) => pushCurrency(code, code))
  ;(currencyOptions.value || []).forEach((item) => {
    if (typeof item === 'string') {
      pushCurrency(item, item)
      return
    }
    pushCurrency(item?.value, item?.label)
  })
  pushCurrency(form.value.currency, form.value.currency)
  return list
})

const loadSettings = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/system/site-payment-settings')
    form.value.config_version = Number(res?.config_version || 1)
    form.value.currency = normalizeCurrencyCode(res?.currency) || 'USD'
    form.value.rules = Array.isArray(res?.rules) ? res.rules.map((rule, index) => createRule(rule, index)) : []
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : []
    currencyOptions.value = Array.isArray(res?.currency_options) ? res.currency_options : []
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || t('sitePaymentSettings.messages.loadFailed'))
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
    ElMessage.warning(t('sitePaymentSettings.messages.incompleteRule'))
    return
  }
  if (normalizedCurrency.value.length > 20) {
    ElMessage.warning(t('sitePaymentSettings.messages.currencyTooLong'))
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
    form.value.currency = normalizeCurrencyCode(res?.currency) || normalizedCurrency.value
    form.value.rules = Array.isArray(res?.rules) ? res.rules.map((rule, index) => createRule(rule, index)) : []
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : milestoneOptions.value
    currencyOptions.value = Array.isArray(res?.currency_options) ? res.currency_options : currencyOptions.value
    ElMessage.success(t('sitePaymentSettings.messages.saveSuccess'))
  } catch (error) {
    console.error(error)
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') {
      ElMessage.error(detail)
      return
    }
    ElMessage.error(t('sitePaymentSettings.messages.saveFailed'))
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
