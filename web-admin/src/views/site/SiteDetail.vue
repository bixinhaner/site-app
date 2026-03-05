<template>
  <div class="page">
    <div class="page-header">
      <h1>站点详情</h1>
      <div class="header-actions">
        <el-button @click="$router.back()"><el-icon><Back /></el-icon>返回</el-button>
        <el-button @click="openSurveys"><el-icon><PictureFilled /></el-icon>勘察档案</el-button>
        <el-button @click="openOpeningArchives"><el-icon><DocumentAdd /></el-icon>开站档案</el-button>
        <template v-if="site && site.survey_required === false">
          <el-tooltip
            v-if="!canManageSite"
            content="该站点已跳过勘察，仅管理员/经理可发起补勘工单"
            placement="top"
          >
            <span>
              <el-button type="success" disabled><el-icon><Plus /></el-icon>新建补勘</el-button>
            </span>
          </el-tooltip>
          <el-button v-else type="success" @click="createResurvey"><el-icon><Plus /></el-icon>新建补勘</el-button>
        </template>
        <el-button v-else type="success" @click="createSurvey"><el-icon><Plus /></el-icon>新建勘察</el-button>
      </div>
    </div>
    <el-card v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>站点基本信息</span>
          <div v-if="canManageSite" class="card-actions">
            <el-button
              v-if="canSkipSurvey"
              size="small"
              type="warning"
              @click="skipSurveyStage"
            >
              跳过勘察
            </el-button>
            <el-tooltip
              v-if="showRequireSurvey && !canRequireSurvey"
              :content="requireSurveyDisableTip"
              placement="top"
            >
              <span>
                <el-button size="small" type="warning" disabled>恢复需要勘察</el-button>
              </span>
            </el-tooltip>
            <el-button
              v-else-if="showRequireSurvey"
              size="small"
              type="warning"
              @click="requireSurveyStage"
            >
              恢复需要勘察
            </el-button>
            <el-button size="small" type="primary" @click="openEdit">编辑</el-button>
            <el-tooltip
              v-if="deleteCheckLoaded && !deleteCheck.can_delete"
              :content="deleteDisableTip"
              placement="top"
            >
              <span>
                <el-button size="small" type="danger" disabled>删除站点</el-button>
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
              删除站点
            </el-button>
          </div>
        </div>
      </template>
      <div class="info-grid" v-if="site">
        <div class="item"><span class="label">站点名称</span><span class="value">{{ site.site_name }}</span></div>
        <div class="item"><span class="label">站点编码</span><span class="value">{{ site.site_code }}</span></div>
        <div class="item"><span class="label">类型</span><span class="value">{{ site.site_type || '-' }}</span></div>
        <div class="item"><span class="label">状态</span><span class="value">{{ siteStatusText(site.status) }}</span></div>
        <div class="item">
          <span class="label">勘察要求</span>
          <span class="value">
            <el-tag :type="site.survey_required === false ? 'info' : 'warning'">
              {{ site.survey_required === false ? '无需勘察' : '需要勘察' }}
            </el-tag>
          </span>
        </div>
        <div
          v-if="site.survey_skipped_at || site.survey_skip_reason || site.survey_skipped_by"
          class="item"
        >
          <span class="label">跳过记录</span>
          <span class="value">
            <el-tag type="info">曾跳过</el-tag>
            <span v-if="site.survey_skipped_at" style="margin-left: 8px;">时间：{{ formatDate(site.survey_skipped_at) }}</span>
            <span v-if="site.survey_skipped_by" style="margin-left: 8px;">操作人：{{ getUserName(site.survey_skipped_by) }}</span>
            <span v-if="site.survey_skip_reason" style="margin-left: 8px;">原因：{{ site.survey_skip_reason }}</span>
          </span>
        </div>
        <div class="item"><span class="label">SSV</span><span class="value"><el-tag :type="site.ssv_passed ? 'success' : 'info'">{{ site.ssv_passed ? '已通过' : '未通过' }}</el-tag></span></div>
        <div class="item"><span class="label">地址</span><span class="value">{{ site.address || '-' }}</span></div>
      </div>
    </el-card>

    <!-- 编辑站点基本信息 -->
    <el-dialog
      v-model="editVisible"
      title="编辑站点基本信息"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form label-width="110px">
        <el-form-item label="站点编码">
          <el-input :model-value="editForm.site_code" disabled />
        </el-form-item>
        <el-form-item label="站点名称" required>
          <el-input v-model="editForm.site_name" placeholder="必填" />
        </el-form-item>
        <el-form-item label="类型">
          <el-input v-model="editForm.site_type" placeholder="macro/indoor..." />
        </el-form-item>
        <el-form-item label="省市区">
          <div class="row3">
            <el-input v-model="editForm.province" placeholder="省" />
            <el-input v-model="editForm.city" placeholder="市" />
            <el-input v-model="editForm.district" placeholder="区/县" />
          </div>
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="editForm.address" placeholder="详细地址" />
        </el-form-item>
        <el-form-item label="经纬度">
          <div class="row2">
            <el-input-number
              v-model="editForm.latitude"
              :min="-90"
              :max="90"
              :step="0.000001"
              :controls="false"
              placeholder="纬度 -90~90"
              style="width: 100%"
            />
            <el-input-number
              v-model="editForm.longitude"
              :min="-180"
              :max="180"
              :step="0.000001"
              :controls="false"
              placeholder="经度 -180~180"
              style="width: 100%"
            />
          </div>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editForm.priority" placeholder="优先级" style="width: 100%">
            <el-option label="high" value="high" />
            <el-option label="normal" value="normal" />
            <el-option label="low" value="low" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人">
          <div class="row2">
            <el-input v-model="editForm.contact_person" placeholder="姓名" />
            <el-input v-model="editForm.contact_phone" placeholder="电话" />
          </div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSubmitting" @click="submitEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 删除站点 -->
    <el-dialog
      v-model="deleteVisible"
      title="删除站点"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-alert
        type="warning"
        :closable="false"
        title="删除为物理删除，且仅允许删除无关联数据的站点。删除后不可恢复。"
      />
      <div style="margin-top: 12px;">
        <div>站点名称：{{ site?.site_name || '-' }}</div>
        <div>站点编码：{{ site?.site_code || '-' }}</div>
      </div>
      <el-form label-width="110px" style="margin-top: 12px;">
        <el-form-item label="确认站点编码" required>
          <el-input v-model="deleteConfirmCode" placeholder="请输入站点编码以确认删除" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deleteVisible = false">取消</el-button>
        <el-button
          type="danger"
          :loading="deleteSubmitting"
          :disabled="deleteConfirmCode !== (site?.site_code || '')"
          @click="submitDelete"
        >
          确认删除
        </el-button>
      </template>
    </el-dialog>

    <!-- 当前工单 -->
    <el-card class="mt16" v-loading="workOrdersLoading">
      <template #header>
        <div class="card-header">
          <span>当前工单</span>
          <el-button type="primary" size="small" @click="showHistoryDialog">
            <el-icon><Document /></el-icon>查看历史工单
          </el-button>
        </div>
      </template>
      <el-empty v-if="!currentWorkOrders.length" description="暂无进行中的工单" />
      <el-table v-else :data="currentWorkOrders" stripe>
        <el-table-column prop="title" label="工单标题" min-width="180" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指派给" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="assigned_at" label="分配时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.assigned_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 设备在线/激活状态 -->
    <el-card class="mt16" v-loading="deviceStatusLoading">
      <template #header>
        <div class="card-header">
          <span>设备在线 / 激活状态</span>
          <div>
	            <span v-if="deviceStatusCheckedAt" style="margin-right: 12px; color: #909399;">
	              最近检查时间：{{ formatDate(deviceStatusCheckedAt) }}
	            </span>
	            <el-button
	              size="small"
	              type="primary"
	              :disabled="deviceRefreshCooldown > 0"
	              @click="loadDeviceStatus(true)"
            >
              <span v-if="deviceRefreshCooldown > 0">
                刷新状态 ({{ deviceRefreshCooldown }}s)
              </span>
              <span v-else>
                刷新状态
              </span>
            </el-button>
          </div>
        </div>
      </template>
      <el-empty v-if="!devices.length && !deviceStatusLoading" description="暂无绑定设备记录" />
      <el-table v-else :data="devices" size="small" stripe>
        <el-table-column prop="sn" label="设备 SN" min-width="180" />
        <el-table-column prop="equipment_type" label="设备类型" width="120" />
        <el-table-column prop="equipment_model" label="设备型号" min-width="160" />
        <el-table-column label="扇区信息" min-width="160">
          <template #default="{ row }">
            扇区 {{ row.sector_id || '-' }} / Band {{ row.band || '-' }} / Cell {{ row.cell_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="在线状态" width="200">
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
        <el-table-column label="激活状态" width="220">
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
        <el-table-column label="安装人" width="140">
          <template #default="{ row }">
            {{ row.installer_name || row.installer_id || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="bound_at" label="绑定时间" width="180">
          <template #default="{ row }">
            {{ formatDate(row.bound_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 历史工单对话框 -->
    <el-dialog v-model="historyDialogVisible" title="历史工单" width="80%" :close-on-click-modal="false">
      <el-table :data="historyWorkOrders" v-loading="historyLoading" stripe max-height="500">
        <el-table-column prop="title" label="工单标题" min-width="180" />
        <el-table-column prop="type" label="类型" width="120">
          <template #default="{ row }">
            <el-tag>{{ formatWorkOrderType(row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">{{ formatWorkOrderStatus(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }">
            <el-tag :type="getPriorityTagType(row.priority)">{{ formatPriority(row.priority) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="指派给" width="120">
          <template #default="{ row }">
            {{ getUserName(row.assigned_to) }}
          </template>
        </el-table-column>
        <el-table-column prop="completed_at" label="完成时间" width="160">
          <template #default="{ row }">
            {{ formatDate(row.completed_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewWorkOrder(row)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="historyDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useUserStore } from '../../stores/user'
import { surveyArchivesApi } from '@/api/surveyArchives'
import { openingArchivesApi } from '@/api/openingArchives'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const site = ref(null)
const userStore = useUserStore()
const userOptions = ref([])
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
  if (site.value?.status !== 'planning') return '仅在规划阶段（planning）可恢复需要勘察'
  return '仅在未形成规划版本时可恢复需要勘察'
})

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

const load = async () => {
  try {
    loading.value = true
    const res = await request.get(`/api/sites/${route.params.id}`)
    site.value = res
    if (canManageSite.value) {
      await loadDeleteCheck()
    }
    await loadWorkOrders()
    await loadDeviceStatus(false)
  } catch (e) {
    console.error(e)
    ElMessage.error('加载站点详情失败')
  } finally {
    loading.value = false
  }
}

const extractErrorDetail = (error) => {
  return error?.response?.data?.detail || error?.message || '网络错误'
}

const skipSurveyStage = async () => {
  if (!site.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      '将站点标记为无需勘察，并进入规划阶段。原因（可选）：',
      '跳过勘察',
      {
        confirmButtonText: '确认跳过',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '可不填',
        inputValue: ''
      }
    )
    await request.post(`/api/sites/${route.params.id}/survey/skip`, { reason: value })
    ElMessage.success('已跳过勘察阶段')
    await load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    console.error(e)
    ElMessage.error('操作失败：' + extractErrorDetail(e))
  }
}

const requireSurveyStage = async () => {
  if (!site.value) return
  try {
    const { value } = await ElMessageBox.prompt(
      '将站点恢复为需要勘察，并回退到勘察阶段（survey_pending）。原因（可选）：',
      '恢复需要勘察',
      {
        confirmButtonText: '确认恢复',
        cancelButtonText: '取消',
        inputType: 'textarea',
        inputPlaceholder: '可不填',
        inputValue: ''
      }
    )
    await request.post(`/api/sites/${route.params.id}/survey/require`, { reason: value })
    ElMessage.success('已恢复为需要勘察')
    await load()
  } catch (e) {
    if (e === 'cancel' || e === 'close') return
    console.error(e)
    ElMessage.error('操作失败：' + extractErrorDetail(e))
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
    work_orders: '工单',
    site_inspections: '检查记录',
    inspections: '旧版检查记录',
    site_surveys: '勘察记录',
    site_survey_archives: '勘察档案',
    site_opening_archives: '开站档案',
    site_ssv_archives: 'SSV档案',
    equipment_binding_history: '设备绑定历史',
    site_planning: '规划版本',
    site_planning_cells: '规划小区',
    base_station_devices: '基站设备',
    template_bindings: '模板绑定',
  }
  const pairs = Object.entries(counts)
    .filter(([, v]) => Number(v) > 0)
    .slice(0, 6)
    .map(([k, v]) => `${labelMap[k] || k} ${v}`)
  if (!pairs.length) return '存在关联数据，禁止删除'
  return `存在关联数据，禁止删除（${pairs.join('，')}）`
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
    ElMessage.warning('请填写站点名称')
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
    ElMessage.success('保存成功')
    editVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '保存失败')
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
    ElMessage.error('站点存在关联数据，禁止删除')
    return
  }
  if (deleteConfirmCode.value !== site.value.site_code) {
    ElMessage.warning('站点编码不匹配')
    return
  }
  try {
    deleteSubmitting.value = true
    await request.delete(`/api/sites/${route.params.id}`)
    ElMessage.success('删除成功')
    deleteVisible.value = false
    router.push({ name: 'SiteList' })
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    if (detail && typeof detail === 'object') {
      ElMessage.error(detail.message || '删除失败')
    } else {
      ElMessage.error(detail || '删除失败')
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
    ElMessage.error('加载工单失败')
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
    ElMessage.error('加载历史工单失败')
  } finally {
    historyLoading.value = false
  }
}

const getUserName = (userId) => {
  if (!userId) return '-'
  const user = userOptions.value.find(u => u.id === userId)
  return user ? (user.full_name || user.username) : userId
}

const formatDate = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

const formatWorkOrderType = (type) => {
  const map = {
    'INSPECTION': '检查',
    'INSTALLATION': '安装',
    'MAINTENANCE': '维护',
    'REPAIR': '维修'
  }
  return map[type] || type
}

const formatWorkOrderStatus = (status) => {
  const map = {
    'PENDING': '待分配',
    'ASSIGNED': '已分配',
    'ACCEPTED': '已接受',
    'IN_PROGRESS': '进行中',
    'SUBMITTED': '已提交',
    'UNDER_REVIEW': '审核中',
    'APPROVED': '已批准',
    'REJECTED': '已拒绝',
    'COMPLETED': '已完成',
    'CANCELLED': '已取消'
  }
  return map[status] || status
}

const siteStatusText = (status) => {
  const map = {
    survey_pending: '勘察中',
    planning: '规划中',
    planned: '规划完成',
    construction: '施工中',
    pending_online: '待上线',
    online_pending_activation: '已上线待激活',
    operational: '已开通',
    maintenance: '维护中'
  }
  return map[status] || status
}

const formatPriority = (priority) => {
  const map = {
    'HIGH': '高',
    'NORMAL': '普通',
    'LOW': '低'
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
  if (val === true) return '当前在线'
  if (val === false) return '当前离线'
  return '待检测'
}
const onlineRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'danger'
  return 'info'
}
const everOnlineTagType = (val) => (val ? 'success' : 'info')
const everOnlineText = (val) => (val ? '曾上线' : '未曾上线')

const activeRealtimeText = (val) => {
  if (val === true) return '当前已激活'
  if (val === false) return '当前未激活'
  return '待检测'
}
const activeRealtimeTagType = (val) => {
  if (val === true) return 'success'
  if (val === false) return 'warning'
  return 'info'
}
const everActiveTagType = (val) => (val ? 'success' : 'info')
const everActiveText = (val) => (val ? '曾激活' : '未曾激活')

const deviceRefreshCooldown = ref(0)
let deviceCooldownTimer = null

const loadDeviceStatus = async (refresh = false) => {
  if (refresh && deviceRefreshCooldown.value > 0) {
    ElMessage.warning(`请等待 ${deviceRefreshCooldown.value}s 后再刷新设备状态`)
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
    ElMessage.error(e?.response?.data?.detail || '加载设备状态失败')
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
  // 默认加载一次设备ever状态，实时状态为“待检测”
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
      ElMessage.info('当前站点暂无勘察档案')
      return
    }
    const archive = items[0]
    router.push({ name: 'SurveyArchiveDetail', params: { id: archive.id } })
  } catch (e) {
    console.error(e)
    ElMessage.error('获取勘察档案失败')
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
      ElMessage.info('当前站点暂无开站档案')
      return
    }
    const archive = items[0]
    router.push({ name: 'OpeningArchiveDetail', params: { id: archive.id } })
  } catch (e) {
    console.error(e)
    ElMessage.error('获取开站档案失败')
  }
}

const createSurvey = () => {
  router.push({ name: 'WorkOrderList', query: { create: '1', site_id: route.params.id, type: 'site_survey' } })
}

const createResurvey = async () => {
  if (!site.value) return
  const parts = []
  if (site.value.survey_skipped_at) parts.push(`跳过时间：${formatDate(site.value.survey_skipped_at)}`)
  if (site.value.survey_skipped_by) parts.push(`操作人：${getUserName(site.value.survey_skipped_by)}`)
  if (site.value.survey_skip_reason) parts.push(`原因：${site.value.survey_skip_reason}`)
  const skipInfo = parts.length ? `\n\n${parts.join('\n')}` : ''

  try {
    await ElMessageBox.confirm(
      `确认新建补勘工单？创建成功后将自动把站点恢复为需要勘察（保留跳过记录）。${skipInfo}`,
      '新建补勘',
      { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
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
.info-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
.item .label { color: var(--text-secondary); margin-right:8px; }
.item .value { color: var(--text-primary); font-weight: 500; }
.mt16 { margin-top: 16px; }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-actions { display: flex; gap: 8px; align-items: center; }
.row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; width: 100%; }
.status-cell { display: flex; align-items: center; gap: 4px; }
.mr4 { margin-right: 4px; }
</style>
