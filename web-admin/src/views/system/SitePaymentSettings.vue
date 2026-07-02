<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('sitePaymentSettings.pageTitle') }}</h1>
      <div class="header-actions">
        <el-button @click="loadSettings" :loading="loading">
          <el-icon><Refresh /></el-icon>{{ t('sitePaymentSettings.actions.refresh') }}
        </el-button>
        <el-button @click="addProfile">
          <el-icon><Plus /></el-icon>{{ t('sitePaymentSettings.actions.addProfile') }}
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

    <el-alert
      v-if="!subcontractorCategory"
      type="warning"
      :closable="false"
      show-icon
      class="mb16"
      :title="t('sitePaymentSettings.subcontractorMissingTip')"
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

    <div v-loading="loading" class="profile-list">
      <el-empty v-if="!form.profiles.length" :description="t('sitePaymentSettings.empty')" />

      <section v-for="(profile, profileIndex) in form.profiles" :key="profile.local_id" class="profile-section">
        <div class="profile-head">
          <div>
            <div class="profile-title">{{ profile.name || t('sitePaymentSettings.profileCardTitle', { index: profileIndex + 1 }) }}</div>
            <div class="profile-subtitle">{{ profileScopeText(profile) }}</div>
          </div>
          <div class="profile-actions">
            <el-button size="small" @click="copyDefaultRules(profileIndex)">
              {{ t('sitePaymentSettings.actions.copyDefaultRules') }}
            </el-button>
            <el-button size="small" @click="addRule(profile)">
              <el-icon><Plus /></el-icon>{{ t('sitePaymentSettings.actions.addRule') }}
            </el-button>
            <el-button
              v-if="profile.scope_type !== 'default'"
              link
              type="danger"
              @click="removeProfile(profileIndex)"
            >
              {{ t('sitePaymentSettings.actions.delete') }}
            </el-button>
          </div>
        </div>

        <el-form :model="profile" label-width="150px" class="profile-form">
          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.profileName')">
                <el-input v-model="profile.name" maxlength="100" />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.scope')">
                <el-select v-model="profile.scope_type" :disabled="profile.scope_type === 'default'" @change="onScopeChange(profile)">
                  <el-option
                    :label="t('sitePaymentSettings.scope.default')"
                    value="default"
                    :disabled="profile.scope_type !== 'default'"
                  />
                  <el-option :label="t('sitePaymentSettings.scope.subcontractor')" value="subcontractor" />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.subcontractor')">
                <el-select
                  v-model="profile.subcontractor_option_id"
                  filterable
                  clearable
                  :disabled="profile.scope_type !== 'subcontractor'"
                  :placeholder="t('sitePaymentSettings.fields.subcontractorPlaceholder')"
                  @change="syncSubcontractorMeta(profile)"
                >
                  <el-option
                    v-for="option in subcontractorOptions"
                    :key="option.id"
                    :label="option.name"
                    :value="option.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="16">
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.enabled')">
                <el-switch
                  v-model="profile.enabled"
                  :disabled="profile.scope_type === 'default'"
                  :active-text="t('sitePaymentSettings.fields.enabledOn')"
                  :inactive-text="t('sitePaymentSettings.fields.enabledOff')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.amountBase')">
                <el-radio-group v-model="profile.contract_amount_source">
                  <el-radio label="site">{{ t('sitePaymentSettings.fields.amountBaseSite') }}</el-radio>
                  <el-radio label="profile_fixed">{{ t('sitePaymentSettings.fields.amountBaseProfile') }}</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
            <el-col :span="8">
              <el-form-item :label="t('sitePaymentSettings.fields.profileAmount')">
                <el-input-number
                  v-model="profile.profile_contract_amount"
                  :min="0"
                  :precision="2"
                  :step="100"
                  :disabled="profile.contract_amount_source !== 'profile_fixed'"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item :label="t('sitePaymentSettings.fields.remark')">
            <el-input
              v-model="profile.remark"
              type="textarea"
              :rows="2"
              :placeholder="t('sitePaymentSettings.fields.profileRemarkPlaceholder')"
            />
          </el-form-item>
        </el-form>

        <div v-if="!profile.rules.length" class="rule-empty">
          {{ t('sitePaymentSettings.emptyRules') }}
        </div>

        <div v-else class="rule-list">
          <div v-for="(rule, ruleIndex) in profile.rules" :key="rule.local_id" class="rule-card">
            <div class="rule-card-head">
              <div class="rule-card-title">{{ t('sitePaymentSettings.ruleCardTitle', { index: ruleIndex + 1 }) }}</div>
              <el-button link type="danger" @click="removeRule(profile, ruleIndex)">
                {{ t('sitePaymentSettings.actions.delete') }}
              </el-button>
            </div>

            <el-form :model="rule" label-width="140px" class="rule-form">
              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.name')">
                    <el-input v-model="rule.name" maxlength="100" :placeholder="t('sitePaymentSettings.fields.namePlaceholder')" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
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
                </el-col>
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.amountType')">
                    <el-radio-group v-model="rule.amount_type">
                      <el-radio label="ratio">{{ t('sitePaymentSettings.fields.amountTypeRatio') }}</el-radio>
                      <el-radio label="fixed">{{ t('sitePaymentSettings.fields.amountTypeFixed') }}</el-radio>
                    </el-radio-group>
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item :label="rule.amount_type === 'ratio' ? t('sitePaymentSettings.fields.amountRatio') : t('sitePaymentSettings.fields.amountFixed')">
                    <el-input-number
                      v-model="rule.amount_value"
                      :min="0"
                      :precision="2"
                      :step="rule.amount_type === 'ratio' ? 5 : 100"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.ruleEnabled')">
                    <el-switch
                      v-model="rule.enabled"
                      :active-text="t('sitePaymentSettings.fields.enabledOn')"
                      :inactive-text="t('sitePaymentSettings.fields.enabledOff')"
                    />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.sortOrder')">
                    <el-input-number v-model="rule.sort_order" :min="1" :step="10" />
                  </el-form-item>
                </el-col>
              </el-row>

              <el-row :gutter="16">
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.requiresApprove')">
                    <el-switch v-model="rule.requires_work_order_approved" />
                  </el-form-item>
                </el-col>
                <el-col :span="8">
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
                </el-col>
                <el-col :span="8">
                  <el-form-item :label="t('sitePaymentSettings.fields.remark')">
                    <el-input v-model="rule.remark" :placeholder="t('sitePaymentSettings.fields.remarkPlaceholder')" />
                  </el-form-item>
                </el-col>
              </el-row>
            </el-form>
          </div>
        </div>
      </section>
    </div>
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
  config_version: 2,
  currency: 'USD',
  profiles: [],
})
const milestoneOptions = ref([])
const currencyOptions = ref([])
const subcontractorCategory = ref(null)
const subcontractorOptions = ref([])
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

const createProfile = (profile = {}, index = 0) => ({
  local_id: `${profile.id || profile.scope_type || 'profile'}_${Date.now()}_${index}_${Math.random().toString(16).slice(2, 8)}`,
  id: profile.id || '',
  name: profile.name || (index === 0 ? t('sitePaymentSettings.defaultProfileName') : ''),
  scope_type: profile.scope_type || (index === 0 ? 'default' : 'subcontractor'),
  subcontractor_option_id: profile.subcontractor_option_id ?? null,
  subcontractor_option_code: profile.subcontractor_option_code || '',
  subcontractor_option_name: profile.subcontractor_option_name || '',
  enabled: profile.enabled !== false,
  contract_amount_source: profile.contract_amount_source || 'site',
  profile_contract_amount: profile.profile_contract_amount ?? null,
  sort_order: Number(profile.sort_order ?? (index * 10)),
  remark: profile.remark || '',
  rules: Array.isArray(profile.rules) ? profile.rules.map((rule, ruleIndex) => createRule(rule, ruleIndex)) : [],
})

const defaultProfile = computed(() => form.value.profiles.find((profile) => profile.scope_type === 'default') || form.value.profiles[0])
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

const profileScopeText = (profile) => {
  if (profile.scope_type === 'default') return t('sitePaymentSettings.scope.default')
  return profile.subcontractor_option_name
    ? t('sitePaymentSettings.scope.subcontractorWithName', { name: profile.subcontractor_option_name })
    : t('sitePaymentSettings.scope.subcontractor')
}

const ensureDefaultProfile = () => {
  if (form.value.profiles.some((profile) => profile.scope_type === 'default')) return
  form.value.profiles.unshift(createProfile({
    id: 'default',
    name: t('sitePaymentSettings.defaultProfileName'),
    scope_type: 'default',
    rules: [],
  }, 0))
}

const loadSettings = async () => {
  try {
    loading.value = true
    const res = await request.get('/api/system/site-payment-settings')
    form.value.config_version = Number(res?.config_version || 2)
    form.value.currency = normalizeCurrencyCode(res?.currency) || 'USD'
    const profiles = Array.isArray(res?.profiles) && res.profiles.length
      ? res.profiles
      : [{
          id: 'default',
          name: t('sitePaymentSettings.defaultProfileName'),
          scope_type: 'default',
          rules: Array.isArray(res?.rules) ? res.rules : [],
        }]
    form.value.profiles = profiles.map((profile, index) => createProfile(profile, index))
    ensureDefaultProfile()
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : []
    currencyOptions.value = Array.isArray(res?.currency_options) ? res.currency_options : []
    subcontractorCategory.value = res?.subcontractor_category || null
    subcontractorOptions.value = Array.isArray(res?.subcontractor_options) ? res.subcontractor_options : []
  } catch (error) {
    console.error(error)
    ElMessage.error(error?.response?.data?.detail || t('sitePaymentSettings.messages.loadFailed'))
  } finally {
    loading.value = false
  }
}

const addProfile = () => {
  const profile = createProfile({
    name: t('sitePaymentSettings.newProfileName'),
    scope_type: 'subcontractor',
    rules: (defaultProfile.value?.rules || []).map((rule) => ({ ...rule })),
  }, form.value.profiles.length)
  form.value.profiles.push(profile)
}

const removeProfile = (index) => {
  form.value.profiles.splice(index, 1)
  ensureDefaultProfile()
}

const addRule = (profile) => {
  profile.rules.push(createRule({}, profile.rules.length))
}

const removeRule = (profile, index) => {
  profile.rules.splice(index, 1)
}

const copyDefaultRules = (profileIndex) => {
  const target = form.value.profiles[profileIndex]
  const sourceRules = defaultProfile.value?.rules || []
  if (!target || target.scope_type === 'default') return
  target.rules = sourceRules.map((rule, index) => createRule({ ...rule }, index))
}

const onScopeChange = (profile) => {
  if (profile.scope_type === 'default') {
    profile.id = 'default'
    profile.subcontractor_option_id = null
    profile.subcontractor_option_code = ''
    profile.subcontractor_option_name = ''
  }
}

const syncSubcontractorMeta = (profile) => {
  const option = subcontractorOptions.value.find((item) => item.id === profile.subcontractor_option_id)
  profile.subcontractor_option_code = option?.code || ''
  profile.subcontractor_option_name = option?.name || ''
}

const buildRulePayload = (rule, index) => ({
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
})

const buildProfilePayload = (profile, index) => {
  if (profile.scope_type === 'subcontractor') syncSubcontractorMeta(profile)
  return {
    id: profile.scope_type === 'default' ? 'default' : (profile.id || undefined),
    name: String(profile.name || '').trim(),
    scope_type: profile.scope_type,
    subcontractor_option_id: profile.scope_type === 'subcontractor' ? profile.subcontractor_option_id : null,
    subcontractor_option_code: profile.scope_type === 'subcontractor' ? profile.subcontractor_option_code : undefined,
    subcontractor_option_name: profile.scope_type === 'subcontractor' ? profile.subcontractor_option_name : undefined,
    enabled: profile.scope_type === 'default' ? true : !!profile.enabled,
    contract_amount_source: profile.contract_amount_source,
    profile_contract_amount: profile.contract_amount_source === 'profile_fixed' ? profile.profile_contract_amount : null,
    sort_order: Number(profile.sort_order ?? (index * 10)),
    remark: String(profile.remark || '').trim() || undefined,
    rules: (profile.rules || []).map((rule, ruleIndex) => buildRulePayload(rule, ruleIndex)),
  }
}

const saveSettings = async () => {
  ensureDefaultProfile()
  const payloadProfiles = form.value.profiles.map((profile, index) => buildProfilePayload(profile, index))
  const invalidProfile = payloadProfiles.find((profile) => {
    if (!profile.name) return true
    if (profile.scope_type === 'subcontractor' && !profile.subcontractor_option_id) return true
    if (profile.contract_amount_source === 'profile_fixed' && (profile.profile_contract_amount === null || profile.profile_contract_amount === undefined || profile.profile_contract_amount === '')) return true
    return false
  })
  if (invalidProfile) {
    ElMessage.warning(t('sitePaymentSettings.messages.incompleteProfile'))
    return
  }

  const invalidRule = payloadProfiles
    .flatMap((profile) => profile.rules || [])
    .find((rule) => !rule.name || !rule.milestone_code)
  if (invalidRule) {
    ElMessage.warning(t('sitePaymentSettings.messages.incompleteRule'))
    return
  }
  if (normalizedCurrency.value.length > 20) {
    ElMessage.warning(t('sitePaymentSettings.messages.currencyTooLong'))
    return
  }

  try {
    saving.value = true
    const defaultRules = payloadProfiles.find((profile) => profile.scope_type === 'default')?.rules || []
    const res = await request.put('/api/system/site-payment-settings', {
      config_version: Number(form.value.config_version || 2),
      currency: normalizedCurrency.value,
      rules: defaultRules,
      profiles: payloadProfiles,
    })
    form.value.config_version = Number(res?.config_version || form.value.config_version || 2)
    form.value.currency = normalizeCurrencyCode(res?.currency) || normalizedCurrency.value
    form.value.profiles = Array.isArray(res?.profiles) ? res.profiles.map((profile, index) => createProfile(profile, index)) : form.value.profiles
    milestoneOptions.value = Array.isArray(res?.milestone_options) ? res.milestone_options : milestoneOptions.value
    currencyOptions.value = Array.isArray(res?.currency_options) ? res.currency_options : currencyOptions.value
    subcontractorCategory.value = res?.subcontractor_category || subcontractorCategory.value
    subcontractorOptions.value = Array.isArray(res?.subcontractor_options) ? res.subcontractor_options : subcontractorOptions.value
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

.profile-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}

.profile-section {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  background: #fff;
  padding: 16px;
}

.profile-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

.profile-title {
  font-size: 17px;
  font-weight: 600;
  color: #1f2937;
}

.profile-subtitle,
.tip,
.rule-empty {
  font-size: 12px;
  color: #909399;
}

.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.profile-form {
  border-bottom: 1px solid #ebeef5;
  margin-bottom: 16px;
  padding-bottom: 4px;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.rule-card {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 14px;
  background: #fafafa;
}

.rule-card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.rule-card-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.inline-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.suffix-text {
  color: #606266;
}

.rule-empty {
  padding: 12px 0;
}
</style>
