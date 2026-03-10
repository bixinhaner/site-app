<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('siteDetail.pageTitle') }}</h1>
      <div class="header-actions">
        <el-button @click="$router.back()"><el-icon><Back /></el-icon>{{ t('siteDetail.actions.back') }}</el-button>
        <el-button @click="openSurveys"><el-icon><PictureFilled /></el-icon>{{ t('siteDetail.actions.surveyArchive') }}</el-button>
        <el-button @click="openOpeningArchives"><el-icon><DocumentAdd /></el-icon>{{ t('siteDetail.actions.openingArchive') }}</el-button>
        <template v-if="site && site.survey_required === false">
          <el-tooltip
            v-if="!canManageSite"
            :content="t('siteDetail.actions.createResurveyDisabledTip')"
            placement="top"
          >
            <span>
              <el-button type="success" disabled><el-icon><Plus /></el-icon>{{ t('siteDetail.actions.createResurvey') }}</el-button>
            </span>
          </el-tooltip>
          <el-button v-else type="success" @click="createResurvey"><el-icon><Plus /></el-icon>{{ t('siteDetail.actions.createResurvey') }}</el-button>
        </template>
        <el-button v-else type="success" @click="createSurvey"><el-icon><Plus /></el-icon>{{ t('siteDetail.actions.createSurvey') }}</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>{{ t('siteDetail.basic.title') }}</span>
          <div v-if="canManageSite" class="card-actions">
            <el-button
              v-if="canSkipSurvey"
              size="small"
              type="warning"
              @click="skipSurveyStage"
            >
              {{ t('siteDetail.basic.skipSurvey') }}
            </el-button>
            <el-tooltip
              v-if="showRequireSurvey && !canRequireSurvey"
              :content="requireSurveyDisableTip"
              placement="top"
            >
              <span>
                <el-button size="small" type="warning" disabled>{{ t('siteDetail.basic.requireSurvey') }}</el-button>
              </span>
            </el-tooltip>
            <el-button
              v-else-if="showRequireSurvey"
              size="small"
              type="warning"
              @click="requireSurveyStage"
            >
              {{ t('siteDetail.basic.requireSurvey') }}
            </el-button>
            <el-button size="small" type="primary" @click="openEdit">{{ t('siteDetail.basic.edit') }}</el-button>
            <el-tooltip
              v-if="deleteCheckLoaded && !deleteCheck.can_delete"
              :content="deleteDisableTip"
              placement="top"
            >
              <span>
                <el-button size="small" type="danger" disabled>{{ t('siteDetail.basic.delete') }}</el-button>
              </span>
            </el-tooltip>
            <el-button
              v-else
              size="small"
              type="danger"
              :loading="deleteCheckLoading"
              :disabled="!deleteCheckLoaded || !deleteCheck.can_delete"
              @click="openDelete"
            >
              {{ t('siteDetail.basic.delete') }}
            </el-button>
          </div>
        </div>
      </template>
      <div class="site-summary" v-if="site">
        <div class="summary-grid">
          <div class="summary-card summary-card-main">
            <div class="summary-label">{{ t('siteDetail.basic.siteName') }}</div>
            <div class="summary-primary">{{ site.site_name || placeholderText }}</div>
            <div class="summary-secondary">{{ t('siteDetail.basic.siteCode') }}: {{ site.site_code || placeholderText }}</div>
          </div>

          <div class="summary-card">
            <div class="summary-label">{{ t('siteDetail.basic.siteStatus') }}</div>
            <div class="summary-primary">
              <el-tag>{{ siteStatusText(site.status) }}</el-tag>
            </div>
            <div class="summary-secondary">{{ t('siteDetail.basic.siteType') }}: {{ site.site_type || placeholderText }}</div>
          </div>

          <div class="summary-card">
            <div class="summary-label">{{ t('siteDetail.basic.surveyRequirement') }}</div>
            <div class="summary-primary">
              <el-tag :type="site.survey_required === false ? 'info' : 'warning'">
                {{ site.survey_required === false ? t('siteDetail.basic.surveyNotRequired') : t('siteDetail.basic.surveyRequired') }}
              </el-tag>
            </div>
            <div class="summary-secondary">
              {{ t('siteDetail.basic.ssvStatus') }}:
              <el-tag :type="site.ssv_passed ? 'success' : 'info'" effect="plain" size="small" class="inline-tag">
                {{ site.ssv_passed ? t('siteDetail.basic.ssvPassed') : t('siteDetail.basic.ssvNotPassed') }}
              </el-tag>
            </div>
          </div>

          <div class="summary-card summary-card-wide">
            <div class="summary-label">{{ t('siteDetail.basic.address') }}</div>
            <div class="summary-primary">{{ site.address || placeholderText }}</div>
            <div class="summary-secondary">{{ t('siteDetail.basic.region') }}: {{ formatRegion(site) }}</div>
          </div>
        </div>

        <div v-if="hasSurveySkipRecord" class="skip-record">
          <div class="skip-record-head">
            <span>{{ t('siteDetail.basic.skipRecordTitle') }}</span>
            <el-tag type="info" effect="plain" size="small">{{ t('siteDetail.basic.skippedTag') }}</el-tag>
          </div>
          <div class="skip-record-grid">
            <div class="skip-record-item">
              <span class="skip-label">{{ t('siteDetail.basic.skippedAt') }}</span>
              <span class="skip-value">{{ site.survey_skipped_at ? formatDate(site.survey_skipped_at) : placeholderText }}</span>
            </div>
            <div class="skip-record-item">
              <span class="skip-label">{{ t('siteDetail.basic.skippedBy') }}</span>
              <span class="skip-value">{{ site.survey_skipped_by ? getUserName(site.survey_skipped_by) : placeholderText }}</span>
            </div>
            <div class="skip-record-item skip-record-item-wide">
              <span class="skip-label">{{ t('siteDetail.basic.skippedReason') }}</span>
              <span class="skip-value">{{ site.survey_skip_reason || t('siteDetail.basic.noReason') }}</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="site" class="milestone-panel">
        <div class="milestone-header">
          <span class="milestone-title">{{ t('siteDetail.milestones.title') }}</span>
          <el-tag size="small" :type="milestoneReachedCount ? 'success' : 'info'">
            {{ t('siteDetail.milestones.reachedCount', { count: milestoneReachedCount }) }}
          </el-tag>
        </div>
        <div class="milestone-subtitle">{{ t('siteDetail.milestones.subtitle') }}</div>
        <div class="milestone-grid">
          <div
            v-for="item in milestoneItems"
            :key="item.key"
            class="milestone-item"
            :class="{ reached: !!item.time }"
          >
            <div class="milestone-item-head">
              <span class="milestone-dot" :style="{ '--dot-color': item.color }" />
              <span class="milestone-name">{{ item.label }}</span>
              <el-tag size="small" effect="plain" :type="item.time ? 'success' : 'info'">
                {{ item.time ? t('siteDetail.milestones.reached') : t('siteDetail.milestones.pending') }}
              </el-tag>
            </div>
            <div class="milestone-desc">{{ item.desc }}</div>
            <div class="milestone-time">{{ item.time ? formatDate(item.time) : t('siteDetail.milestones.pending') }}</div>
          </div>
        </div>
      </div>
    </el-card>

    <el-dialog
      v-model="editVisible"
      :title="t('siteDetail.editDialog.title')"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form label-width="110px">
        <el-form-item :label="t('siteDetail.editDialog.siteCode')">
          <el-input :model-value="editForm.site_code" disabled />
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.siteName')" required>
          <el-input v-model="editForm.site_name" :placeholder="t('siteDetail.editDialog.requiredPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.siteType')">
          <el-input v-model="editForm.site_type" :placeholder="t('siteDetail.editDialog.siteTypePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.region')">
          <div class="row3">
            <el-input v-model="editForm.province" :placeholder="t('siteDetail.editDialog.province')" />
            <el-input v-model="editForm.city" :placeholder="t('siteDetail.editDialog.city')" />
            <el-input v-model="editForm.district" :placeholder="t('siteDetail.editDialog.district')" />
          </div>
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.address')">
          <el-input v-model="editForm.address" :placeholder="t('siteDetail.editDialog.addressPlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.coordinates')">
          <div class="row2">
            <el-input-number
              v-model="editForm.latitude"
              :min="-90"
              :max="90"
              :step="0.000001"
              :controls="false"
              :placeholder="t('siteDetail.editDialog.latitudePlaceholder')"
              style="width: 100%"
            />
            <el-input-number
              v-model="editForm.longitude"
              :min="-180"
              :max="180"
              :step="0.000001"
              :controls="false"
              :placeholder="t('siteDetail.editDialog.longitudePlaceholder')"
              style="width: 100%"
            />
          </div>
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.priority')">
          <el-select v-model="editForm.priority" :placeholder="t('siteDetail.editDialog.priority')" style="width: 100%">
            <el-option :label="t('siteDetail.editDialog.priorityOptions.high')" value="high" />
            <el-option :label="t('siteDetail.editDialog.priorityOptions.normal')" value="normal" />
            <el-option :label="t('siteDetail.editDialog.priorityOptions.low')" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.contact')">
          <div class="row2">
            <el-input v-model="editForm.contact_person" :placeholder="t('siteDetail.editDialog.contactName')" />
            <el-input v-model="editForm.contact_phone" :placeholder="t('siteDetail.editDialog.contactPhone')" />
          </div>
        </el-form-item>
        <el-form-item :label="t('siteDetail.editDialog.remark')">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">{{ t('siteDetail.common.cancel') }}</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">{{ t('siteDetail.common.save') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteVisible"
      :title="t('siteDetail.deleteDialog.title')"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        :title="t('siteDetail.deleteDialog.warning')"
      />
      <div style="margin-top: 12px;">
        <div>{{ t('siteDetail.deleteDialog.siteName') }}：{{ site?.site_name || placeholderText }}</div>
        <div>{{ t('siteDetail.deleteDialog.siteCode') }}：{{ site?.site_code || placeholderText }}</div>
      </div>
      <el-form label-width="110px" style="margin-top: 12px;">
        <el-form-item :label="t('siteDetail.deleteDialog.confirmCode')" required>
          <el-input v-model="deleteConfirmCode" :placeholder="t('siteDetail.deleteDialog.confirmCodePlaceholder')" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteVisible = false">{{ t('siteDetail.common.cancel') }}</el-button>
        <el-button
          type="danger"
          :loading="deleteSubmitting"
          :disabled="deleteConfirmCode !== (site?.site_code || '')"
          @click="submitDelete"
        >
          {{ t('siteDetail.deleteDialog.confirmDelete') }}
        </el-button>
      </template>
    </el-dialog>

    <el-card class="mt16" v-loading="workOrdersLoading">
      <template #header>
        <div class="card-header">
          <span>{{ t('siteDetail.workOrder.title') }}</span>
          <el-button type="primary" size="small" @click="showHistoryDialog">
            <el-icon><Document /></el-icon>{{ t('siteDetail.workOrder.historyButton') }}
          </el-button>
        </div>
      </template>
      <el-empty v-if="!currentWorkOrders.length" :description="t('siteDetail.workOrder.empty')" />
      <el-table v-else :data="currentWorkOrders" stripe>
        <el-table-column prop="title" :label="t('siteDetail.workOrder.columns.title')" min-width="180" />
        <el-table-column prop="type" :label="t('siteDetail.workOrder.columns.type')" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="t('siteDetail.workOrder.columns.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" :label="t('siteDetail.workOrder.columns.priority')" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.workOrder.columns.assignee')" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="assigned_at" :label="t('siteDetail.workOrder.columns.assignedAt')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.assigned_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.workOrder.columns.action')" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">{{ t('siteDetail.workOrder.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="mt16" v-loading="deviceStatusLoading">
      <template #header>
        <div class="card-header">
          <span>{{ t('siteDetail.device.title') }}</span>
          <div>
            <span v-if="deviceStatusCheckedAt" class="device-check-at">
              {{ t('siteDetail.device.checkedAt', { time: formatDate(deviceStatusCheckedAt) }) }}
            </span>
	            <el-button
	              size="small"
	              type="primary"
	              :disabled="deviceRefreshCooldown > 0"
	              @click="loadDeviceStatus(true)"
            >
              <span v-if="deviceRefreshCooldown > 0">
                {{ t('siteDetail.device.refreshCooldown', { seconds: deviceRefreshCooldown }) }}
              </span>
              <span v-else>
                {{ t('siteDetail.device.refresh') }}
              </span>
            </el-button>
          </div>
        </div>
      </template>
      <el-empty v-if="!devices.length && !deviceStatusLoading" :description="t('siteDetail.device.empty')" />
      <el-table v-else :data="devices" size="small" stripe>
        <el-table-column prop="sn" :label="t('siteDetail.device.columns.sn')" min-width="180" />
        <el-table-column prop="equipment_type" :label="t('siteDetail.device.columns.type')" width="120" />
        <el-table-column prop="equipment_model" :label="t('siteDetail.device.columns.model')" min-width="160" />
        <el-table-column :label="t('siteDetail.device.columns.sectorInfo')" min-width="160">
          <template #default="{ row }">
            {{ t('siteDetail.device.sectorInfoValue', { sector: row.sector_id || placeholderText, band: row.band || placeholderText, cell: row.cell_id || placeholderText }) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.device.columns.onlineStatus')" width="200">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="onlineRealtimeTagType(row.online)" size="small" class="mr4">
                {{ onlineRealtimeText(row.online) }}
              </el-tag>
              <el-tag :type="everOnlineTagType(row.ever_online)" size="small">
                {{ everOnlineText(row.ever_online) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.device.columns.activeStatus')" width="220">
          <template #default="{ row }">
            <div class="status-cell">
              <el-tag :type="activeRealtimeTagType(row.activated)" size="small" class="mr4">
                {{ activeRealtimeText(row.activated) }}
              </el-tag>
              <el-tag :type="everActiveTagType(row.ever_activated)" size="small">
                {{ everActiveText(row.ever_activated) }}
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.device.columns.installer')" width="140">
          <template #default="{ row }">
            {{ row.installer_name || row.installer_id || placeholderText }}
          </template>
        </el-table-column>
        <el-table-column prop="bound_at" :label="t('siteDetail.device.columns.boundAt')" width="180">
          <template #default="{ row }">
            {{ formatDate(row.bound_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="historyDialogVisible" :title="t('siteDetail.workOrder.historyTitle')" width="80%" :close-on-click-modal="false">
      <el-table :data="historyWorkOrders" v-loading="historyLoading" stripe max-height="500">
        <el-table-column prop="title" :label="t('siteDetail.workOrder.columns.title')" min-width="180" />
        <el-table-column prop="type" :label="t('siteDetail.workOrder.columns.type')" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" :label="t('siteDetail.workOrder.columns.status')" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" :label="t('siteDetail.workOrder.columns.priority')" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.workOrder.columns.assignee')" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" :label="t('siteDetail.workOrder.columns.completedAt')" width="160">
          <template #default="{ row }">
            {{ formatDate(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column :label="t('siteDetail.workOrder.columns.action')" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">{{ t('siteDetail.workOrder.view') }}</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyDialogVisible = false">{{ t('siteDetail.workOrder.close') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../../stores/user'
import { surveyArchivesApi } from '@/api/surveyArchives'
import { openingArchivesApi } from '@/api/openingArchives'

const route = useRoute()
const router = useRouter()
const { t, locale } = useI18n()
const loading = ref(false)
const site = ref(null)
const userStore = useUserStore()
const userOptions = ref([])
const dateLocale = computed(() => (locale.value === 'zh-CN' ? 'zh-CN' : locale.value))
const placeholderText = computed(() => t('siteDetail.basic.placeholder'))
const canManageSite = computed(() => userStore.hasPermission('sites:update:write'))
const canSkipSurvey = computed(() =>
  canManageSite.value &&
  !!site.value &&
  site.value.status === 'survey_pending' &&
  site.value.survey_required !== false
)

const showRequireSurvey = computed(() =>
  canManageSite.value &&
  !!site.value &&
  site.value.survey_required === false
)

const canRequireSurvey = computed(() =>
  showRequireSurvey.value &&
  site.value?.status === 'planning'
)

const requireSurveyDisableTip = computed(() => {
  if (!showRequireSurvey.value) return ''
  if (site.value?.status !== 'planning') return t('siteDetail.requireSurveyDisableTip.statusOnly')
  return t('siteDetail.requireSurveyDisableTip.noPlanningVersion')
})

const hasSurveySkipRecord = computed(() => (
  !!site.value && !!(site.value.survey_skipped_at || site.value.survey_skip_reason || site.value.survey_skipped_by)
))

const deleteCheckLoading = ref(false)
const deleteCheckLoaded = ref(false)
const deleteCheck = ref({ can_delete: false, total_related: 0, counts: {} })

const editVisible = ref(false)
const editSubmitting = ref(false)
const editForm = ref({
  site_code: '',
  site_name: '',
  site_type: '',
  province: '',
  city: '',
  district: '',
  address: '',
  latitude: null,
  longitude: null,
  priority: 'normal',
  contact_person: '',
  contact_phone: '',
  description: '',
})

const deleteVisible = ref(false)
const deleteSubmitting = ref(false)
const deleteConfirmCode = ref('')

// 工单相关
const workOrdersLoading = ref(false)
const currentWorkOrders = ref([])
const historyDialogVisible = ref(false)
const historyLoading = ref(false)
const historyWorkOrders = ref([])

// 设备状态
const deviceStatusLoading = ref(false)
const devices = ref([])
const deviceStatusCheckedAt = ref(null)
const milestoneData = ref({
  install_started_at: null,
  install_completed_at: null,
  online_at: null,
  activated_at: null,
  ssv_at: null,
})

const formatRegion = (record) => {
  if (!record) return placeholderText.value
  const segments = [record.province, record.city, record.district]
    .map((item) => String(item || '').trim())
    .filter(Boolean)
  return segments.length ? segments.join('/') : placeholderText.value
}

const milestoneItems = computed(() => [
  {
    key: 'install_started',
    label: t('siteDetail.milestones.installStarted.label'),
    desc: t('siteDetail.milestones.installStarted.desc'),
    time: milestoneData.value.install_started_at,
    color: '#0ea5e9',
  },
  {
    key: 'install_completed',
    label: t('siteDetail.milestones.installCompleted.label'),
    desc: t('siteDetail.milestones.installCompleted.desc'),
    time: milestoneData.value.install_completed_at,
    color: '#f97316',
  },
  {
    key: 'online',
    label: t('siteDetail.milestones.online.label'),
    desc: t('siteDetail.milestones.online.desc'),
    time: milestoneData.value.online_at,
    color: '#22c55e',
  },
  {
    key: 'activated',
    label: t('siteDetail.milestones.activated.label'),
    desc: t('siteDetail.milestones.activated.desc'),
    time: milestoneData.value.activated_at,
    color: '#ef4444',
  },
  {
    key: 'ssv',
    label: t('siteDetail.milestones.ssv.label'),
    desc: t('siteDetail.milestones.ssv.desc'),
    time: milestoneData.value.ssv_at,
    color: '#8b5cf6',
  },
])

const milestoneReachedCount = computed(() => milestoneItems.value.filter((item) => !!item.time).length)

const loadMilestones = async () => {
  try {
    const res = await request.get(`/api/sites/${route.params.id}/milestones`)
    milestoneData.value = {
      install_started_at: res?.install_started_at || null,
      install_completed_at: res?.install_completed_at || null,
      online_at: res?.online_at || null,
      activated_at: res?.activated_at || null,
      ssv_at: res?.ssv_at || null,
    }
  } catch (e) {
    console.error(e)
    milestoneData.value = {
      install_started_at: null,
      install_completed_at: null,
      online_at: null,
      activated_at: null,
      ssv_at: null,
    }
  }
}

const load = async () => {
  try {
    loading.value = true
    const res = await request.get(`/api/sites/${route.params.id}`)
    site.value = res
    await loadMilestones()
    if (canManageSite.value) {
      await loadDeleteCheck()
    }
    await loadWorkOrders()
    await loadDeviceStatus(false)
  } catch (e) {
    console.error(e)
    ElMessage.error(t('siteDetail.messages.loadSiteFailed'))
  } finally {
    loading.value = false
  }
}

const extractErrorDetail = (error) => {
  return error?.response?.data?.detail || error?.message || t('siteDetail.messages.networkError')
}

const skipSurveyStage = async () => {
  if (!site.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      t('siteDetail.prompts.skipSurveyMessage'),
      t('siteDetail.prompts.skipSurveyTitle'),
      {
        confirmButtonText: t('siteDetail.prompts.confirmSkip'),
        cancelButtonText: t('siteDetail.prompts.cancel'),
        inputType: 'textarea',
        inputPlaceholder: t('siteDetail.prompts.optionalPlaceholder'),
        inputValue: ''
      }
    )
    await request.post(`/api/sites/${route.params.id}/survey/skip`, { reason: value })
    ElMessage.success(t('siteDetail.messages.surveySkipSuccess'))
    await load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    console.error(e)
    ElMessage.error(t('siteDetail.messages.operationFailed', { detail: extractErrorDetail(e) }))
  }
}

const requireSurveyStage = async () => {
  if (!site.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      t('siteDetail.prompts.requireSurveyMessage'),
      t('siteDetail.prompts.requireSurveyTitle'),
      {
        confirmButtonText: t('siteDetail.prompts.confirmRequire'),
        cancelButtonText: t('siteDetail.prompts.cancel'),
        inputType: 'textarea',
        inputPlaceholder: t('siteDetail.prompts.optionalPlaceholder'),
        inputValue: ''
      }
    )
    await request.post(`/api/sites/${route.params.id}/survey/require`, { reason: value })
    ElMessage.success(t('siteDetail.messages.surveyRequireSuccess'))
    await load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    console.error(e)
    ElMessage.error(t('siteDetail.messages.operationFailed', { detail: extractErrorDetail(e) }))
  }
}

const loadDeleteCheck = async () => {
  try {
    deleteCheckLoading.value = true
    deleteCheckLoaded.value = false
    const res = await request.get(`/api/sites/${route.params.id}/delete-check`)
    deleteCheck.value = res || { can_delete: false, total_related: 0, counts: {} }
    deleteCheckLoaded.value = true
  } catch (e) {
    console.error(e)
    deleteCheck.value = { can_delete: false, total_related: 0, counts: {} }
    deleteCheckLoaded.value = true
  } finally {
    deleteCheckLoading.value = false
  }
}

const deleteDisableTip = computed(() => {
  const counts = deleteCheck.value?.counts || {}
  const labelMap = {
    work_orders: t('siteDetail.deleteCheck.counts.work_orders'),
    site_inspections: t('siteDetail.deleteCheck.counts.site_inspections'),
    inspections: t('siteDetail.deleteCheck.counts.inspections'),
    site_surveys: t('siteDetail.deleteCheck.counts.site_surveys'),
    site_survey_archives: t('siteDetail.deleteCheck.counts.site_survey_archives'),
    site_opening_archives: t('siteDetail.deleteCheck.counts.site_opening_archives'),
    site_ssv_archives: t('siteDetail.deleteCheck.counts.site_ssv_archives'),
    equipment_binding_history: t('siteDetail.deleteCheck.counts.equipment_binding_history'),
    site_planning: t('siteDetail.deleteCheck.counts.site_planning'),
    site_planning_cells: t('siteDetail.deleteCheck.counts.site_planning_cells'),
    base_station_devices: t('siteDetail.deleteCheck.counts.base_station_devices'),
    template_bindings: t('siteDetail.deleteCheck.counts.template_bindings'),
  }
  const pairs = Object.entries(counts)
    .filter(([, v]) => Number(v) > 0)
    .slice(0, 6)
    .map(([k, v]) => `${labelMap[k] || k} ${v}`)
  if (!pairs.length) return t('siteDetail.deleteCheck.blockedPrefix')
  return `${t('siteDetail.deleteCheck.blockedPrefix')}（${pairs.join('，')}）`
})

const openEdit = () => {
  if (!site.value) return
  editForm.value = {
    site_code: site.value.site_code || '',
    site_name: site.value.site_name || '',
    site_type: site.value.site_type || '',
    province: site.value.province || '',
    city: site.value.city || '',
    district: site.value.district || '',
    address: site.value.address || '',
    latitude: site.value.latitude ?? null,
    longitude: site.value.longitude ?? null,
    priority: site.value.priority || 'normal',
    contact_person: site.value.contact_person || '',
    contact_phone: site.value.contact_phone || '',
    description: site.value.description || '',
  }
  editVisible.value = true
}

const submitEdit = async () => {
  if (!site.value) return
  if (!editForm.value.site_name?.trim()) {
    ElMessage.warning(t('siteDetail.messages.siteNameRequired'))
    return
  }
  try {
    editSubmitting.value = true
    const payload = {
      site_name: editForm.value.site_name?.trim(),
      site_type: editForm.value.site_type?.trim() || null,
      province: editForm.value.province?.trim() || null,
      city: editForm.value.city?.trim() || null,
      district: editForm.value.district?.trim() || null,
      address: editForm.value.address?.trim() || null,
      latitude: editForm.value.latitude === null || editForm.value.latitude === '' ? null : editForm.value.latitude,
      longitude: editForm.value.longitude === null || editForm.value.longitude === '' ? null : editForm.value.longitude,
      priority: editForm.value.priority || null,
      contact_person: editForm.value.contact_person?.trim() || null,
      contact_phone: editForm.value.contact_phone?.trim() || null,
      description: editForm.value.description || null,
    }
    await request.put(`/api/sites/${route.params.id}`, payload)
    ElMessage.success(t('siteDetail.messages.saveSuccess'))
    editVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || t('siteDetail.messages.saveFailed'))
  } finally {
    editSubmitting.value = false
  }
}

const openDelete = () => {
  if (!site.value) return
  deleteConfirmCode.value = ''
  deleteVisible.value = true
}

const submitDelete = async () => {
  if (!site.value) return
  if (!deleteCheck.value?.can_delete) {
    ElMessage.error(t('siteDetail.messages.relatedDataCannotDelete'))
    return
  }
  if (deleteConfirmCode.value !== site.value.site_code) {
    ElMessage.warning(t('siteDetail.messages.codeMismatch'))
    return
  }
  try {
    deleteSubmitting.value = true
    await request.delete(`/api/sites/${route.params.id}`)
    ElMessage.success(t('siteDetail.messages.deleteSuccess'))
    deleteVisible.value = false
    router.push({ name: 'SiteList' })
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object') {
      ElMessage.error(detail.message || t('siteDetail.messages.deleteFailed'))
    } else {
      ElMessage.error(detail || t('siteDetail.messages.deleteFailed'))
    }
    await loadDeleteCheck()
  } finally {
    deleteSubmitting.value = false
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = res || []
  } catch (e) {
    // 可能无权限
  }
}

const loadWorkOrders = async () => {
  try {
    workOrdersLoading.value = true
    const res = await request.get('/api/work-orders/search', {
      params: {
        site_id: route.params.id,
        limit: 100
      }
    })
    const allWorkOrders = res.work_orders || []
    // 过滤出当前进行中的工单（未完成的）
    currentWorkOrders.value = allWorkOrders.filter(wo => 
      wo.status !== 'COMPLETED' && wo.status !== 'CANCELLED'
    )
  } catch (e) {
    console.error(e)
    ElMessage.error(t('siteDetail.workOrder.loadFailed'))
  } finally {
    workOrdersLoading.value = false
  }
}

const showHistoryDialog = async () => {
  historyDialogVisible.value = true
  try {
    historyLoading.value = true
    const res = await request.get('/api/work-orders/search', {
      params: {
        site_id: route.params.id,
        limit: 100
      }
    })
    const allWorkOrders = res.work_orders || []
    // 历史工单包括已完成和已取消的
    historyWorkOrders.value = allWorkOrders.filter(wo => 
      wo.status === 'COMPLETED' || wo.status === 'CANCELLED'
    )
  } catch (e) {
    console.error(e)
    ElMessage.error(t('siteDetail.workOrder.loadHistoryFailed'))
  } finally {
    historyLoading.value = false
  }
}

const getUserName = (userId) => {
  if (!userId) return placeholderText.value
  const user = userOptions.value.find(u => u.id === userId)
  return user ? (user.full_name || user.username) : userId
}

const formatDate = (dateStr) => {
  if (!dateStr) return placeholderText.value
  return new Date(dateStr).toLocaleString(dateLocale.value)
}

const formatWorkOrderType = (type) => {
  const map = {
    INSPECTION: t('siteDetail.workOrder.typeMap.INSPECTION'),
    INSTALLATION: t('siteDetail.workOrder.typeMap.INSTALLATION'),
    MAINTENANCE: t('siteDetail.workOrder.typeMap.MAINTENANCE'),
    REPAIR: t('siteDetail.workOrder.typeMap.REPAIR'),
  }
  return map[type] || type
}

const formatWorkOrderStatus = (status) => {
  const map = {
    PENDING: t('siteDetail.workOrder.statusMap.PENDING'),
    ASSIGNED: t('siteDetail.workOrder.statusMap.ASSIGNED'),
    ACCEPTED: t('siteDetail.workOrder.statusMap.ACCEPTED'),
    IN_PROGRESS: t('siteDetail.workOrder.statusMap.IN_PROGRESS'),
    SUBMITTED: t('siteDetail.workOrder.statusMap.SUBMITTED'),
    UNDER_REVIEW: t('siteDetail.workOrder.statusMap.UNDER_REVIEW'),
    APPROVED: t('siteDetail.workOrder.statusMap.APPROVED'),
    REJECTED: t('siteDetail.workOrder.statusMap.REJECTED'),
    COMPLETED: t('siteDetail.workOrder.statusMap.COMPLETED'),
    CANCELLED: t('siteDetail.workOrder.statusMap.CANCELLED'),
  }
  return map[status] || status
}

const siteStatusText = (status) => {
  const map = {
    survey_pending: t('siteMap.status.survey_pending'),
    planning: t('siteMap.status.planning'),
    planned: t('siteMap.status.planned'),
    construction: t('siteMap.status.construction'),
    pending_online: t('siteMap.status.pending_online'),
    online_pending_activation: t('siteMap.status.online_pending_activation'),
    operational: t('siteMap.status.operational'),
    maintenance: t('siteMap.status.maintenance'),
  }
  return map[status] || status
}

const formatPriority = (priority) => {
  const map = {
    HIGH: t('siteDetail.priorityMap.HIGH'),
    NORMAL: t('siteDetail.priorityMap.NORMAL'),
    LOW: t('siteDetail.priorityMap.LOW'),
  }
  return map[priority] || priority
}

const getStatusTagType = (status) => {
  const map = {
    'PENDING': 'info',
    'ASSIGNED': 'warning',
    'ACCEPTED': 'primary',
    'IN_PROGRESS': 'primary',
    'SUBMITTED': 'success',
    'UNDER_REVIEW': 'warning',
    'APPROVED': 'success',
    'REJECTED': 'danger',
    'COMPLETED': 'success',
    'CANCELLED': 'info'
  }
  return map[status] || 'info'
}

const getPriorityTagType = (priority) => {
  const map = {
    'HIGH': 'danger',
    'NORMAL': 'primary',
    'LOW': 'info'
  }
  return map[priority] || 'info'
}

const onlineRealtimeText = (val) => {
  if (val === true) return t('siteDetail.device.onlineCurrent')
  if (val === false) return t('siteDetail.device.onlineOffline')
  return t('siteDetail.device.pendingCheck')
}
const onlineRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}
const everOnlineTagType = (val) => (val ? 'success' : 'info')
const everOnlineText = (val) => (val ? t('siteDetail.device.everOnline') : t('siteDetail.device.neverOnline'))

const activeRealtimeText = (val) => {
  if (val === true) return t('siteDetail.device.activeCurrent')
  if (val === false) return t('siteDetail.device.activeInactive')
  return t('siteDetail.device.pendingCheck')
}
const activeRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'warning'
  return 'info'
}
const everActiveTagType = (val) => (val ? 'success' : 'info')
const everActiveText = (val) => (val ? t('siteDetail.device.everActive') : t('siteDetail.device.neverActive'))

const deviceRefreshCooldown = ref(0)
let deviceCooldownTimer = null

const loadDeviceStatus = async (refresh = false) => {
  if (refresh && deviceRefreshCooldown.value > 0) {
    ElMessage.warning(t('siteDetail.device.refreshWait', { seconds: deviceRefreshCooldown.value }))
    return
  }
  try {
    deviceStatusLoading.value = true
    const res = await request.get(`/api/sites/${route.params.id}/omc/devices`, {
      params: { refresh: refresh ? 1 : 0 }
    })
    devices.value = Array.isArray(res.devices) ? res.devices : []
    deviceStatusCheckedAt.value = res.checked_at || null

    if (refresh) {
      startDeviceCooldown()
    }
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || t('siteDetail.device.loadFailed'))
  } finally {
    deviceStatusLoading.value = false
  }
}

const viewWorkOrder = (workOrder) => {
  router.push({ name: 'WorkOrderReview', query: { id: workOrder.id } })
}

onMounted(() => {
  load()
  loadUsers()
  loadDeviceStatus(false)
})

const startDeviceCooldown = () => {
  deviceRefreshCooldown.value = 10
  if (deviceCooldownTimer) return
  deviceCooldownTimer = setInterval(() => {
    if (deviceRefreshCooldown.value > 0) {
      deviceRefreshCooldown.value -= 1
    }
    if (deviceRefreshCooldown.value <= 0) {
      clearInterval(deviceCooldownTimer)
      deviceCooldownTimer = null
    }
  }, 1000)
}

const openSurveys = async () => {
  try {
    const res = await surveyArchivesApi.page({
      page: 1,
      page_size: 1,
      site_id: route.params.id
    })
    const items = Array.isArray(res?.items) ? res.items : []
    if (!items.length) {
      ElMessage.info(t('siteDetail.messages.noSurveyArchive'))
      return
    }
    const archive = items[0]
    router.push({ name: 'SurveyArchiveDetail', params: { id: archive.id } })
  } catch (e) {
    console.error(e)
    ElMessage.error(t('siteDetail.messages.getSurveyArchiveFailed'))
  }
}

const openOpeningArchives = async () => {
  try {
    const res = await openingArchivesApi.page({
      page: 1,
      page_size: 1,
      site_id: route.params.id
    })
    const items = Array.isArray(res?.items) ? res.items : []
    if (!items.length) {
      ElMessage.info(t('siteDetail.messages.noOpeningArchive'))
      return
    }
    const archive = items[0]
    router.push({ name: 'OpeningArchiveDetail', params: { id: archive.id } })
  } catch (e) {
    console.error(e)
    ElMessage.error(t('siteDetail.messages.getOpeningArchiveFailed'))
  }
}

const createSurvey = () => {
  router.push({ name: 'WorkOrderList', query: { create: '1', site_id: route.params.id, type: 'site_survey' } })
}

const createResurvey = async () => {
  if (!site.value) return
  const parts = []
  if (site.value.survey_skipped_at) parts.push(`${t('siteDetail.basic.skippedAt')}：${formatDate(site.value.survey_skipped_at)}`)
  if (site.value.survey_skipped_by) parts.push(`${t('siteDetail.basic.skippedBy')}：${getUserName(site.value.survey_skipped_by)}`)
  if (site.value.survey_skip_reason) parts.push(`${t('siteDetail.basic.skippedReason')}：${site.value.survey_skip_reason}`)
  const skipInfo = parts.length ? `\n\n${parts.join('\n')}` : ''

  try {
    await ElMessageBox.confirm(
      t('siteDetail.prompts.createResurveyConfirm', { skipInfo }),
      t('siteDetail.prompts.createResurveyTitle'),
      { confirmButtonText: t('siteDetail.prompts.confirm'), cancelButtonText: t('siteDetail.prompts.cancel'), type: 'warning' }
    )
    router.push({ name: 'WorkOrderList', query: { create: '1', site_id: route.params.id, type: 'site_survey', resurvey: '1' } })
  } catch (e) {
    // cancel/close
  }
}
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 12px; }
.site-summary {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}
.summary-card {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: #fff;
  padding: 12px 14px;
}
.summary-card-main {
  background: linear-gradient(145deg, #eff6ff, #ffffff);
}
.summary-card-wide {
  grid-column: span 2;
}
.summary-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 8px;
}
.summary-primary {
  font-size: 20px;
  line-height: 1.3;
  font-weight: 700;
  color: #0f172a;
  word-break: break-word;
}
.summary-secondary {
  margin-top: 8px;
  font-size: 13px;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.inline-tag {
  vertical-align: middle;
}
.skip-record {
  border: 1px dashed #cbd5e1;
  border-radius: 10px;
  background: #f8fafc;
  padding: 10px 12px;
}
.skip-record-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
}
.skip-record-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.skip-record-item {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #fff;
  padding: 8px 10px;
}
.skip-record-item-wide {
  grid-column: span 1;
}
.skip-label {
  display: block;
  color: #64748b;
  font-size: 12px;
}
.skip-value {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 13px;
  font-weight: 600;
  word-break: break-word;
}
.mt16 { margin-top: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-actions { display: flex; gap: 8px; align-items: center; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; width: 100%; }
.status-cell { display: flex; align-items: center; gap: 4px; }
.mr4 { margin-right: 4px; }
.device-check-at {
  margin-right: 12px;
  color: #64748b;
  font-size: 13px;
}
.milestone-panel {
  margin-top: 18px;
  padding: 14px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  background: linear-gradient(180deg, #ffffff, #f8fbff);
}
.milestone-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 4px;
}
.milestone-title {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
}
.milestone-subtitle {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 10px;
}
.milestone-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
}
.milestone-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 10px 12px;
  background: #fff;
  transition: all 0.2s ease;
}
.milestone-item.reached {
  border-color: #bfdbfe;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.08);
}
.milestone-item-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.milestone-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--dot-color);
  box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.2);
}
.milestone-name {
  font-weight: 600;
  color: #111827;
}
.milestone-desc {
  margin-top: 8px;
  font-size: 12px;
  color: #6b7280;
}
.milestone-time {
  margin-top: 6px;
  font-size: 14px;
  font-weight: 600;
  color: #111827;
}
@media (max-width: 1200px) {
  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .summary-card-wide {
    grid-column: span 2;
  }
}
@media (max-width: 768px) {
  .page-header {
    align-items: stretch;
    flex-direction: column;
    gap: 10px;
  }
  .header-actions {
    flex-wrap: wrap;
  }
  .summary-grid {
    grid-template-columns: 1fr;
  }
  .summary-card-wide {
    grid-column: span 1;
  }
  .skip-record-grid {
    grid-template-columns: 1fr;
  }
  .milestone-grid {
    grid-template-columns: 1fr;
  }
}
</style>
