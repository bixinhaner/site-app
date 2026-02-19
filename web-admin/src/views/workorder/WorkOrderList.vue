<template>
  <div class="page">
    <div class="page-header">
      <h1>工单列表</h1>
      <div class="header-actions">
        <el-input
          v-model="searchKeyword"
          placeholder="搜索工单标题/描述/站点名称/编码（动态生效）"
          style="width: 240px"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-select v-model="statusFilter" clearable placeholder="状态" style="width: 140px">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
        <el-tooltip
          v-if="statusInFilter.length > 0 && !statusFilter"
          :content="`当前按多状态筛选：${statusInFilter.join(' / ')}`"
          placement="bottom"
        >
          <el-tag closable @close="clearStatusInFilter">多状态筛选中</el-tag>
        </el-tooltip>
        <el-select v-model="typeFilter" clearable placeholder="类型" style="width: 180px">
          <el-option v-for="t in filterTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
        <el-popover placement="bottom" :width="280" trigger="click">
          <template #reference>
            <el-button>
              <el-icon><Sort /></el-icon>
              排序
            </el-button>
          </template>
          <div class="sort-panel">
            <el-form label-width="72px" size="small">
              <el-form-item label="字段">
                <el-select v-model="sortBy" style="width: 100%">
                  <el-option label="创建时间" value="created_at" />
                  <el-option label="更新时间" value="updated_at" />
                  <el-option label="分配时间" value="assigned_at" />
                  <el-option label="截止时间" value="due_date" />
                  <el-option label="优先级" value="priority" />
                  <el-option label="状态" value="status" />
                  <el-option label="类型" value="type" />
                  <el-option label="站点编码" value="site_code" />
                  <el-option label="站点名称" value="site_name" />
                </el-select>
              </el-form-item>
              <el-form-item label="方向">
                <el-radio-group v-model="sortOrder">
                  <el-radio-button label="desc">降序</el-radio-button>
                  <el-radio-button label="asc">升序</el-radio-button>
                </el-radio-group>
              </el-form-item>
              <el-form-item label=" ">
                <el-button size="small" @click="resetSort">恢复默认</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-popover>
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建工单</el-button>
      </div>
    </div>
    
    <!-- 批量操作栏 -->
    <el-card v-if="selectedWorkOrders.length > 0" class="batch-operations">
      <div class="batch-info">
        <span>已选择 {{ selectedWorkOrders.length }} 个工单</span>
        <div class="batch-actions">
          <el-button size="small" @click="clearSelection">取消选择</el-button>
          <!-- <el-button size="small" type="primary" @click="showBatchStatusDialog = true">批量修改状态</el-button> -->
          <el-button size="small" type="warning" @click="showBatchAssignDialog = true">批量重新分配</el-button>
          <el-button size="small" type="info" @click="showBatchPriorityDialog = true">批量修改优先级</el-button>
          <el-button size="small" type="danger" @click="confirmBatchDelete">批量删除</el-button>
        </div>
      </div>
    </el-card>
    <el-card>
      <el-table 
        :data="items" 
        v-loading="loading" 
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="title" label="标题" min-width="220">
          <template #default="{ row }">
            <div>
              <div class="title-with-duplicate">
                <span>{{ row.title }}</span>
                <el-tooltip
                  v-if="row.has_duplicate_photos"
                  content="存在重复图片，请进入审核台详情查看来源信息"
                  placement="top"
                >
                  <el-icon class="duplicate-warning-icon"><WarningFilled /></el-icon>
                </el-tooltip>
                <el-tooltip
                  v-if="row.has_similar_photos"
                  content="存在极度相似图片，请进入审核台详情核验"
                  placement="top"
                >
                  <el-icon class="similar-warning-icon"><WarningFilled /></el-icon>
                </el-tooltip>
              </div>
              <div class="work-order-id">ID: {{ row.id }}</div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="160">
          <template #default="{ row }">{{ typeText(row.type) }}</template>
        </el-table-column>
        <el-table-column prop="site_name" label="站点" width="160">
          <template #default="{ row }">{{ row.site_name || row.site_id }}</template>
        </el-table-column>
        <el-table-column prop="assignee_name" label="分配给" width="140" />
        <el-table-column prop="priority" label="优先级" width="100">
          <template #default="{ row }"><el-tag>{{ priorityText(row.priority) }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="160">
          <template #default="{ row }">
            <el-tag>{{ statusText(row.status, row.type) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="assigned_at" label="分配时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.assigned_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" size="small" @click="openEdit(row)" v-if="canEdit(row)">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-button link type="primary" size="small" @click="openReview(row)">
              <el-icon><Stamp /></el-icon>审核
            </el-button>
            <el-button link type="danger" size="small" @click="confirmDelete(row)" v-if="canDelete(row)">
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="load"
          @current-change="load"
        />
      </div>
    </el-card>
  </div>

  <el-dialog v-model="createVisible" title="新建工单" width="560px">
    <el-form :model="createForm" label-width="96px" :rules="rules" ref="formRef">
      <el-form-item label="站点" prop="site_id">
        <el-select v-model="createForm.site_id" filterable placeholder="选择站点" style="width: 100%" @visible-change="v=> v && loadSites()" @change="onTypeOrSiteChange">
          <el-option v-for="s in siteOptions" :key="s.id" :label="s.site_name + ' ('+ s.site_code +')'" :value="s.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型" prop="type">
        <el-select v-model="createForm.type" placeholder="选择类型" style="width: 100%" @change="onTypeOrSiteChange">
          <el-option v-for="t in createTypes" :key="t.value" :label="t.label" :value="t.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="分配给" prop="assigned_to">
        <el-select v-model="createForm.assigned_to" filterable placeholder="选择人员" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题" prop="title">
        <el-input v-model="createForm.title" placeholder="请输入标题" />
      </el-form-item>
      <el-form-item label="检查模板">
        <el-select v-model="createForm.template_id" clearable filterable placeholder="自动推荐(可不选)" style="width: 100%" @visible-change="v => v && loadTemplates()">
          <el-option v-for="tpl in templateOptions" :key="tpl.id" :label="tpl.template_name" :value="tpl.id" />
        </el-select>
      </el-form-item>
      <el-form-item v-if="createForm.type === 'equipment_replacement'" label="更换设备位" prop="replacement_targets">
        <el-select
          v-model="createForm.replacement_targets"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          placeholder="请选择要更换的设备位（可多选）"
          style="width: 100%"
          :loading="replacementTargetsLoading"
          @visible-change="v => v && loadReplacementTargets()"
        >
          <el-option v-for="opt in replacementTargetOptions" :key="opt.key" :label="opt.label" :value="opt.key" />
        </el-select>
        <div class="form-hint">按站点规划生成的设备位（sector_id + band），支持多选。</div>
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="createForm.priority" placeholder="选择优先级" style="width: 100%">
          <el-option label="低" value="low" />
          <el-option label="普通" value="normal" />
          <el-option label="高" value="high" />
          <el-option label="紧急" value="urgent" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止时间">
        <el-date-picker v-model="createForm.due_date" type="datetime" style="width: 100%" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="createForm.description" type="textarea" :rows="3" placeholder="可填工单描述" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="createVisible=false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
    </template>
  </el-dialog>

  <!-- 重复安装工单提示对话框 -->
  <el-dialog v-model="dupVisible" title="该站点已存在安装工单" width="720px">
    <el-alert type="warning" :closable="false" show-icon style="margin-bottom:8px"
      title="确认后仍可继续创建，但请避免重复派单。" />
    <div style="margin-bottom:12px; color:#606266;">
      站点：<b>{{ dupSiteDisplay }}</b>
    </div>
    <el-table :data="dupExisting" size="small" style="width:100%" v-if="dupExisting && dupExisting.length">
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column prop="status" label="状态" width="120">
        <template #default="{ row }">
          <el-tag>{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="assigner_name" label="创建者" width="140" />
      <el-table-column prop="assignee_name" label="分配给" width="140" />
      <el-table-column prop="assigned_at" label="分配时间" width="180">
        <template #default="{ row }">{{ formatDateTime(row.assigned_at) }}</template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="dupVisible=false">取消</el-button>
      <el-button type="primary" :loading="creating" @click="confirmDuplicateCreate">确认继续创建</el-button>
    </template>
  </el-dialog>

  <!-- 编辑工单对话框 -->
  <el-dialog v-model="editVisible" title="编辑工单" width="560px">
    <el-form :model="editForm" label-width="96px" :rules="rules" ref="editFormRef">
      <el-form-item label="站点" prop="site_id">
        <el-input :model-value="editSiteDisplay" disabled />
      </el-form-item>
      <el-form-item label="类型" prop="type">
        <el-input :model-value="typeText(editForm.type)" disabled />
      </el-form-item>
      <el-form-item label="检查模板">
        <el-input :model-value="editTemplateDisplay" disabled />
      </el-form-item>
      <el-form-item label="分配给" prop="assigned_to">
        <el-select v-model="editForm.assigned_to" filterable placeholder="选择人员" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题" prop="title">
        <el-input v-model="editForm.title" placeholder="请输入标题" />
      </el-form-item>
      <el-form-item label="优先级">
        <el-select v-model="editForm.priority" placeholder="选择优先级" style="width: 100%">
          <el-option label="低" value="low" />
          <el-option label="普通" value="normal" />
          <el-option label="高" value="high" />
          <el-option label="紧急" value="urgent" />
        </el-select>
      </el-form-item>
      <el-form-item label="截止时间">
        <el-date-picker v-model="editForm.due_date" type="datetime" style="width: 100%" />
      </el-form-item>
      <el-form-item label="描述">
        <el-input v-model="editForm.description" type="textarea" :rows="3" placeholder="可填工单描述" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="editVisible=false">取消</el-button>
      <el-button type="primary" :loading="updating" @click="submitUpdate">保存</el-button>
    </template>
  </el-dialog>

  <!-- 批量修改状态对话框（暂时隐藏） -->
  <!-- <el-dialog v-model="showBatchStatusDialog" title="批量修改状态" width="400px">
    <el-form label-width="80px">
      <el-form-item label="新状态">
        <el-select v-model="batchStatusValue" placeholder="选择状态" style="width: 100%">
          <el-option v-for="s in statuses" :key="s.value" :label="s.label" :value="s.value" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchStatusDialog = false">取消</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchStatus">确认修改</el-button>
    </template>
  </el-dialog> -->

  <!-- 批量重新分配对话框 -->
  <el-dialog v-model="showBatchAssignDialog" title="批量重新分配" width="400px">
    <el-form label-width="80px">
      <el-form-item label="分配给">
        <el-select v-model="batchAssignValue" filterable placeholder="选择人员" style="width: 100%" @visible-change="v=> v && loadUsers()">
          <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchAssignDialog = false">取消</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchAssign">确认分配</el-button>
    </template>
  </el-dialog>

  <!-- 批量修改优先级对话框 -->
  <el-dialog v-model="showBatchPriorityDialog" title="批量修改优先级" width="400px">
    <el-form label-width="80px">
      <el-form-item label="优先级">
        <el-select v-model="batchPriorityValue" placeholder="选择优先级" style="width: 100%">
          <el-option label="低" value="low" />
          <el-option label="普通" value="normal" />
          <el-option label="高" value="high" />
          <el-option label="紧急" value="urgent" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="showBatchPriorityDialog = false">取消</el-button>
      <el-button type="primary" :loading="batchLoading" @click="executeBatchPriority">确认修改</el-button>
    </template>
  </el-dialog>

  <!-- 批量操作错误详情对话框 -->
  <el-dialog v-model="showErrorDialog" title="批量操作结果" width="600px">
    <el-alert 
      v-if="batchResult.updated_count > 0"
      :title="`成功处理 ${batchResult.updated_count} 个工单`" 
      type="success" 
      :closable="false"
      style="margin-bottom: 16px"
    />
    <el-alert 
      v-if="batchResult.error_count > 0"
      :title="`失败 ${batchResult.error_count} 个工单`" 
      type="error" 
      :closable="false"
      style="margin-bottom: 16px"
    />
    <div v-if="batchResult.errors && batchResult.errors.length > 0" style="margin-top: 16px">
      <div style="font-weight: bold; margin-bottom: 8px; color: #606266;">失败详情：</div>
      <el-scrollbar max-height="300px">
        <ul style="margin: 0; padding-left: 20px; color: #909399; font-size: 14px;">
          <li v-for="(error, index) in batchResult.errors" :key="index" style="margin-bottom: 8px;">
            {{ error }}
          </li>
        </ul>
      </el-scrollbar>
    </div>
    <template #footer>
      <el-button type="primary" @click="showErrorDialog = false">确定</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import request from '@/utils/request'
import { workOrderAPI } from '../../api/workorder'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Edit, Delete, Search, Refresh, Plus, Sort, WarningFilled } from '@element-plus/icons-vue'
import { createDebouncedTracker } from '@/utils/operationTrack'

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const items = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const statusFilter = ref('')
const statusInFilter = ref([])
const typeFilter = ref('')
const searchKeyword = ref('')
const sortBy = ref('created_at')
const sortOrder = ref('desc')

const trackSearchDebounced = createDebouncedTracker(800)
const trackSearch = () => {
  trackSearchDebounced({
    module: '工单管理',
    action: '查询',
    object_type: '工单',
    data: {
      keyword: searchKeyword.value || undefined,
      status: statusFilter.value || undefined,
      status_in: statusInFilter.value.length ? statusInFilter.value.join(',') : undefined,
      type: typeFilter.value || undefined,
      sort_by: sortBy.value || undefined,
      sort_order: sortOrder.value || undefined,
    },
  })
}

// 批量操作相关
const selectedWorkOrders = ref([])
const batchLoading = ref(false)
const showBatchStatusDialog = ref(false)
const showBatchAssignDialog = ref(false)
const showBatchPriorityDialog = ref(false)
const batchStatusValue = ref('')
const batchAssignValue = ref('')
const batchPriorityValue = ref('')
const showErrorDialog = ref(false)
const batchResult = ref({ updated_count: 0, error_count: 0, errors: [] })

const statuses = [
  { label: '待分配', value: 'PENDING' },
  { label: '已分配', value: 'ACTIVE' },
  { label: '已提交', value: 'SUBMITTED' },
  { label: '审核中', value: 'UNDER_REVIEW' },
  { label: '已通过/待上线', value: 'APPROVED' },
  { label: '已开通(上线阶段)', value: 'ACTIVATED' },
  { label: '已驳回', value: 'REJECTED' },
  { label: '已完成', value: 'COMPLETED' }
]
const statusValueSet = new Set(statuses.map(s => s.value))
const INSTALLED_SITE_PRESET_STATUSES = ['SUBMITTED', 'UNDER_REVIEW', 'APPROVED', 'ACTIVATED']

const parseCsvQuery = (value) => {
  const raw = String(_firstQueryValue(value) || '').trim()
  if (!raw) return []
  return raw.split(',').map(v => v.trim()).filter(Boolean)
}

const normalizeStatusList = (list) => {
  const out = []
  for (const s of list || []) {
    if (statusValueSet.has(s) && !out.includes(s)) out.push(s)
  }
  return out
}
// 类型显示映射（用于表格/详情友好显示历史类型）
const typeLabelMap = {
  opening_inspection: '新站安装',
  equipment_replacement: '设备更换',
  maintenance: '维护检查',
  power_issue: '断电问题',
  transmission_issue: '传输问题',
  gps_issue: 'GPS问题',
  signal_issue: '信号问题',
  site_survey: '站点勘查',
  ssv: 'SSV 验收',
}
	
// 创建工单可选类型
const createTypes = [
  { label: '站点勘查', value: 'site_survey' },
  { label: '新站安装', value: 'opening_inspection' },
  { label: '设备更换', value: 'equipment_replacement' },
  { label: 'SSV 验收', value: 'ssv' },
]

// 顶部筛选可选类型
const filterTypes = [
  { label: '站点勘查', value: 'site_survey' },
  { label: '新站安装', value: 'opening_inspection' },
  { label: '设备更换', value: 'equipment_replacement' },
  { label: 'SSV 验收', value: 'ssv' },
]

const resetSort = () => {
  sortBy.value = 'created_at'
  sortOrder.value = 'desc'
}

const load = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value,
    }
    if (searchKeyword.value) params.keyword = searchKeyword.value
    if (statusFilter.value) {
      params.status = statusFilter.value
    } else if (statusInFilter.value.length > 0) {
      params.status_in = statusInFilter.value.join(',')
    }
    if (typeFilter.value) params.type = typeFilter.value
    if (sortBy.value) params.sort_by = sortBy.value
    if (sortOrder.value) params.sort_order = sortOrder.value

    const response = await workOrderAPI.searchWorkOrders(params)
    const list = Array.isArray(response?.work_orders) ? response.work_orders : []
    items.value = list
    total.value = typeof response?.total === 'number' ? response.total : list.length
  } catch (e) {
    console.error(e)
    ElMessage.error('加载工单失败')
  } finally {
    loading.value = false
  }
}

const openReview = (row) => {
  router.push({ name: 'WorkOrderReview', query: { id: row.id } })
}

// Create dialog state
const createVisible = ref(false)
const creating = ref(false)
const createForm = ref({
  site_id: null,
  type: '',
  assigned_to: null,
  title: '',
  priority: 'normal',
  due_date: null,
  description: '',
  template_id: null,
  // 设备更换工单：多选设备位（用 key 数组承载，提交时转换为 [{sector_id, band}]）
  replacement_targets: [],
})
const siteOptions = ref([])
const userOptions = ref([])
const templateOptions = ref([])
const formRef = ref()

// 设备更换：设备位候选项（来自站点规划）
const replacementTargetOptions = ref([])
const replacementTargetsLoading = ref(false)
const lastReplacementTargetsSiteId = ref(null)

// 重复安装工单对话框
const dupVisible = ref(false)
const dupExisting = ref([])
const dupPayload = ref(null)
const dupSiteName = ref('')
const dupSiteCode = ref('')
const dupSiteDisplay = computed(() => {
  if (dupSiteName.value && dupSiteCode.value) return `${dupSiteName.value} (${dupSiteCode.value})`
  return dupSiteName.value || dupSiteCode.value || '-'
})

// Edit dialog state
const editVisible = ref(false)
const updating = ref(false)
const editForm = ref({ id: '', site_id: null, type: '', assigned_to: null, title: '', priority: 'normal', due_date: null, description: '' })
const editFormRef = ref()

const validateReplacementTargets = (rule, value, callback) => {
  if (createForm.value.type !== 'equipment_replacement') {
    callback()
    return
  }
  if (Array.isArray(value) && value.length > 0) {
    callback()
    return
  }
  callback(new Error('请选择要更换的设备位'))
}

const rules = {
  site_id: [{ required: true, message: '请选择站点', trigger: 'change' }],
  type: [{ required: true, message: '请选择类型', trigger: 'change' }],
  assigned_to: [{ required: true, message: '请选择分配对象', trigger: 'change' }],
  title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
  replacement_targets: [{ validator: validateReplacementTargets, trigger: 'change' }],
}

const openCreate = () => {
  // reset form
  createForm.value = {
    site_id: null,
    type: '',
    assigned_to: null,
    title: '',
    priority: 'normal',
    due_date: null,
    description: '',
    template_id: null,
    replacement_targets: [],
  }
  templateOptions.value = []
  replacementTargetOptions.value = []
  lastReplacementTargetsSiteId.value = null
  createVisible.value = true
}

const _firstQueryValue = (v) => (Array.isArray(v) ? v[0] : v)

const applyListFiltersFromRoute = () => {
  const q = route.query || {}
  if (String(_firstQueryValue(q.create) || '') === '1') return

  const preset = String(_firstQueryValue(q.preset) || '').trim()
  if (preset === 'installed_sites') {
    currentPage.value = 1
    typeFilter.value = 'opening_inspection'
    statusFilter.value = ''
    statusInFilter.value = [...INSTALLED_SITE_PRESET_STATUSES]
    return
  }

  const hasFilterQuery = ['type', 'status', 'status_in'].some((key) => {
    const val = String(_firstQueryValue(q[key]) || '').trim()
    return !!val
  })
  if (!hasFilterQuery) return

  currentPage.value = 1
  typeFilter.value = String(_firstQueryValue(q.type) || '').trim()

  const statusList = normalizeStatusList(parseCsvQuery(q.status_in))
  if (statusList.length > 0) {
    statusFilter.value = ''
    statusInFilter.value = statusList
    return
  }

  const status = String(_firstQueryValue(q.status) || '').trim()
  if (statusValueSet.has(status)) {
    statusFilter.value = status
    statusInFilter.value = []
    return
  }
  statusFilter.value = ''
  statusInFilter.value = []
}

const clearStatusInFilter = () => {
  statusInFilter.value = []
}

const ensureSiteOption = async (siteId) => {
  if (!siteId) return
  const exists = siteOptions.value.some(s => s.id === siteId)
  if (exists) return
  try {
    const s = await request.get(`/api/sites/${siteId}`)
    if (s && s.id != null) {
      siteOptions.value.push(s)
    }
  } catch (e) {
    // ignore
  }
}

const openCreateWithPreset = async ({ siteId, type, title } = {}) => {
  openCreate()
  if (siteId) createForm.value.site_id = siteId
  if (type) createForm.value.type = type
  if (title) createForm.value.title = title

  // preload options for better UX
  await Promise.allSettled([loadSites(), loadUsers()])
  if (siteId) await ensureSiteOption(siteId)
  await onTypeOrSiteChange()
}

let applyCreatePrefillBusy = false
const applyCreatePrefillFromRoute = async () => {
  if (applyCreatePrefillBusy) return
  const q = route.query || {}
  if (String(_firstQueryValue(q.create) || '') !== '1') return

  const siteId = Number(_firstQueryValue(q.site_id))
  if (!Number.isFinite(siteId) || siteId <= 0) return

  const type = String(_firstQueryValue(q.type) || 'site_survey')
  const isResurvey = String(_firstQueryValue(q.resurvey) || '') === '1'

  applyCreatePrefillBusy = true
  try {
    // 尝试获取站点信息用于拼标题/展示（即使失败也不阻塞创建）
    let s = null
    try {
      s = await request.get(`/api/sites/${siteId}`)
    } catch (e) {
      s = null
    }
    const siteCode = s?.site_code ? String(s.site_code) : ''
    const baseTitle = type === 'site_survey' ? '站点勘查' : '工单'
    const prefix = isResurvey ? '补勘-' : ''
    const title = siteCode ? `${prefix}${baseTitle}-${siteCode}` : `${prefix}${baseTitle}`

    await openCreateWithPreset({ siteId, type, title })

    // 清理 query，避免刷新/返回时重复弹窗
    const nextQuery = { ...q }
    delete nextQuery.create
    delete nextQuery.site_id
    delete nextQuery.type
    delete nextQuery.resurvey
    router.replace({ query: nextQuery })
  } finally {
    applyCreatePrefillBusy = false
  }
}

const loadSites = async () => {
  try {
    const res = await request.get('/api/sites/', { params: { limit: 100 } })
    siteOptions.value = Array.isArray(res) ? res : []
  } catch (e) {
    // ignore
  }
}

const loadUsers = async () => {
  try {
    const res = await request.get('/api/users/', { params: { limit: 100 } })
    userOptions.value = Array.isArray(res) ? res : []
  } catch (e) {
    // ignore (权限不足时隐藏选项)
  }
}

const loadTemplates = async () => {
  if (!createForm.value.type) return
  try {
    const params = { task_type: createForm.value.type, limit: 100 }
    const list = await request.get('/api/inspections/templates', { params })
    templateOptions.value = Array.isArray(list) ? list : []
  } catch (e) {
    // ignore (权限不足等)
  }
}

const _parseReplacementTargetKey = (key) => {
  const raw = String(key || '').trim()
  const parts = raw.split('__')
  if (parts.length !== 2) return null
  const sectorId = String(parts[0] || '').trim()
  const band = String(parts[1] || '').trim()
  if (!sectorId || !band) return null
  return { sector_id: sectorId, band }
}

const loadReplacementTargets = async () => {
  const siteId = createForm.value.site_id
  if (!siteId) {
    replacementTargetOptions.value = []
    createForm.value.replacement_targets = []
    lastReplacementTargetsSiteId.value = null
    return
  }
  if (lastReplacementTargetsSiteId.value === siteId && replacementTargetOptions.value.length > 0) return
  replacementTargetsLoading.value = true
  try {
    const planning = await request.get(`/api/sites/${siteId}/planning`)
    const sectors = Array.isArray(planning?.sectors) ? planning.sectors : []
    const globalBands = Array.isArray(planning?.bands) ? planning.bands : []
    const opts = []

    for (const s of sectors) {
      const sectorId = String(s?.sector_index ?? '').trim()
      if (!sectorId) continue
      const bands = Array.isArray(s?.bands) && s.bands.length ? s.bands : globalBands
      for (const b of bands || []) {
        const band = String(b ?? '').trim()
        if (!band) continue
        const key = `${sectorId}__${band}`
        opts.push({ key, label: `扇区 ${sectorId} / Band ${band}` })
      }
    }

    replacementTargetOptions.value = opts
    lastReplacementTargetsSiteId.value = siteId

    // 清理不再存在的已选项
    const valid = new Set(opts.map(o => o.key))
    const picked = Array.isArray(createForm.value.replacement_targets) ? createForm.value.replacement_targets : []
    createForm.value.replacement_targets = picked.filter(k => valid.has(k))
  } catch (e) {
    console.error(e)
    replacementTargetOptions.value = []
    lastReplacementTargetsSiteId.value = null
    ElMessage.warning('站点规划未找到或无权限，无法加载设备位')
  } finally {
    replacementTargetsLoading.value = false
  }
}

const onTypeOrSiteChange = async () => {
  // load candidate templates
  await loadTemplates()
  // try resolve default
  if (!createForm.value.site_id || !createForm.value.type) return

  if (createForm.value.type === 'equipment_replacement') {
    await loadReplacementTargets()
  } else {
    replacementTargetOptions.value = []
    createForm.value.replacement_targets = []
    lastReplacementTargetsSiteId.value = null
  }

  try {
    const body = { site_id: createForm.value.site_id, task_type: createForm.value.type }
    const res = await request.post('/api/inspections/templates/resolve', body)
    if (res?.success && res?.result?.template_id) {
      createForm.value.template_id = res.result.template_id
      // ensure recommended template appears in options for visible label
      const exists = templateOptions.value.some(t => t.id === res.result.template_id)
      if (!exists) {
        templateOptions.value.push({ id: res.result.template_id, template_name: res.result.template_name })
      }
    }
  } catch (e) {
    // ignore
  }
}

const submitCreate = () => {
  // 防止重复提交
  if (creating.value) return
  creating.value = true

  formRef.value.validate(async (valid) => {
    if (!valid) {
      creating.value = false
      return
    }
    try {
      // SSV 仅支持运营中的站点
      if (createForm.value.type === 'ssv') {
        const s = siteOptions.value.find(x => x.id === createForm.value.site_id)
        if (s && s.status !== 'operational') {
          ElMessage.error('SSV 工单仅支持运营中的站点')
          creating.value = false
          return
        }
      }
      const payload = { ...createForm.value }
      if (payload.type === 'equipment_replacement') {
        const keys = Array.isArray(payload.replacement_targets) ? payload.replacement_targets : []
        payload.replacement_targets = keys
          .map(_parseReplacementTargetKey)
          .filter(Boolean)
        if (!payload.replacement_targets.length) {
          ElMessage.error('设备更换工单必须选择要更换的设备位')
          creating.value = false
          return
        }
      } else {
        delete payload.replacement_targets
      }
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
      await request.post('/api/work-orders', payload)
      ElMessage.success('创建成功')
      createVisible.value = false
      await load()
    } catch (e) {
      console.error(e)
      const status = e?.response?.status
      const detail = e?.response?.data?.detail
      if (status === 409 && detail?.code === 'DUPLICATE_OPENING_ORDER' && detail?.require_confirm_duplicate) {
        dupExisting.value = Array.isArray(detail.existing_work_orders) ? detail.existing_work_orders : []
        dupPayload.value = { ...createForm.value, confirm_duplicate: true }
        dupSiteName.value = detail?.site_name || ''
        dupSiteCode.value = detail?.site_code || ''
        dupVisible.value = true
      } else {
        ElMessage.error((typeof detail === 'string' && detail) || detail?.message || '创建失败')
      }
    } finally {
      creating.value = false
    }
  })
}

const confirmDuplicateCreate = async () => {
  if (!dupPayload.value) {
    dupVisible.value = false
    return
  }
  // 防止重复提交
  if (creating.value) return

  try {
    creating.value = true
    const payload = { ...dupPayload.value }
    if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
    await request.post('/api/work-orders', payload)
    ElMessage.success('创建成功')
    dupVisible.value = false
    createVisible.value = false
    await load()
  } catch (e) {
    console.error(e)
    const detail = e?.response?.data?.detail
    ElMessage.error((typeof detail === 'string' && detail) || detail?.message || '创建失败')
  } finally {
    creating.value = false
  }
}

// 权限检查函数
const canEdit = (row) => {
  // 只能编辑待分配和已分配状态的工单
  return ['PENDING', 'ACTIVE'].includes(row.status)
}

const canDelete = (row) => {
  // 只能删除待分配和已分配状态的工单
  return ['PENDING', 'ACTIVE'].includes(row.status)
}

// 编辑功能
const editSiteName = ref('')
const editSiteCode = ref('')
const editTemplateId = ref('')
const editTemplateName = ref('')
const editTemplateLoading = ref(false)
const editSiteDisplay = computed(() => {
  if (editSiteName.value && editSiteCode.value) return `${editSiteName.value} (${editSiteCode.value})`
  return editSiteName.value || editSiteCode.value || (editForm.value?.site_id ?? '-')
})
const editTemplateDisplay = computed(() => {
  if (editTemplateLoading.value) return '加载中...'
  return editTemplateName.value || '-'
})

const loadEditTemplate = async (row) => {
  editTemplateId.value = ''
  editTemplateName.value = ''
  editTemplateLoading.value = true
  try {
    let templateId = row?.extra_data?.template_id
    let inspectionId = row?.inspection_id
    if (!templateId && !inspectionId && row?.id) {
      const wo = await request.get(`/api/work-orders/${row.id}`)
      templateId = wo?.extra_data?.template_id
      inspectionId = wo?.inspection_id
    }
    if (!templateId && inspectionId) {
      const insp = await request.get(`/api/inspections/detail/${inspectionId}`)
      templateId = insp?.template_id
    }
    if (!templateId) {
      editTemplateName.value = '-'
      return
    }
    editTemplateId.value = templateId
    const tpl = await request.get(`/api/inspections/templates/${templateId}`)
    editTemplateName.value = tpl?.template_name || templateId
  } catch (e) {
    console.error(e)
    editTemplateName.value = '加载失败'
  } finally {
    editTemplateLoading.value = false
  }
}

const openEdit = (row) => {
  editSiteName.value = row?.site_name || ''
  editSiteCode.value = row?.site_code || ''
  editForm.value = {
    id: row.id,
    site_id: row.site_id,
    type: row.type,
    assigned_to: row.assigned_to,
    title: row.title,
    priority: row.priority,
    due_date: row.due_date ? new Date(row.due_date) : null,
    description: row.description || '',
  }
  editVisible.value = true
  loadEditTemplate(row)
}

const submitUpdate = () => {
  editFormRef.value.validate(async (valid) => {
    if (!valid) return
    try {
      updating.value = true
      const payload = { ...editForm.value }
      delete payload.id // 移除id字段
      // 后端更新接口不支持修改站点/类型（编辑弹窗仅展示且置灰）
      delete payload.site_id
      delete payload.type
      if (payload.due_date) payload.due_date = new Date(payload.due_date).toISOString()
      await request.put(`/api/work-orders/${editForm.value.id}`, payload)
      ElMessage.success('更新成功')
      editVisible.value = false
      await load()
    } catch (e) {
      console.error(e)
      ElMessage.error(e?.response?.data?.detail || '更新失败')
    } finally {
      updating.value = false
    }
  })
}

// 删除功能
const confirmDelete = async (row) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除工单"${row.title}"吗？删除后无法恢复。`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning',
        confirmButtonClass: 'el-button--danger'
      }
    )
    await deleteWorkOrder(row.id)
  } catch (e) {
    // 用户取消删除
  }
}

const deleteWorkOrder = async (id) => {
  try {
    await request.delete(`/api/work-orders/${id}`)
    ElMessage.success('删除成功')
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '删除失败')
  }
}

const statusText = (status, type) => {
  if (type === 'opening_inspection' || type === 'equipment_replacement') {
    if (status === 'APPROVED') return '待上线 (80%)'
    if (status === 'ACTIVATED') return '已上线待激活 (90%)'
    if (status === 'COMPLETED') return '已激活 (100%)'
  }
  return statuses.find(s => s.value === status)?.label || status
}
const typeText = (v) => (typeLabelMap[v] || v)
const priorityText = (v) => ({ low: '低', normal: '普通', high: '高', urgent: '紧急' }[v] || v)
const formatDateTime = (val) => (val ? new Date(val).toLocaleString() : '-')

// 批量操作相关函数
const handleSelectionChange = (selection) => {
  selectedWorkOrders.value = selection
}

const clearSelection = () => {
  selectedWorkOrders.value = []
}

const confirmBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedWorkOrders.value.length} 个工单吗？\n\n注意：只能删除"待分配"或"已分配"状态的工单。`,
      '确认批量删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    await executeBatchDelete()
  } catch (e) {
    // 用户取消删除
  }
}

const executeBatchDelete = async () => {
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'delete')
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(`成功删除 ${result.updated_count} 个工单`)
    }
    
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error('批量删除失败: ' + e.message)
  } finally {
    batchLoading.value = false
  }
}

const executeBatchStatus = async () => {
  if (!batchStatusValue.value) {
    ElMessage.warning('请选择新状态')
    return
  }
  
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_status', batchStatusValue.value)
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(`成功修改 ${result.updated_count} 个工单状态`)
    }
    
    showBatchStatusDialog.value = false
    batchStatusValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error('批量修改状态失败: ' + e.message)
  } finally {
    batchLoading.value = false
  }
}

const executeBatchAssign = async () => {
  if (!batchAssignValue.value) {
    ElMessage.warning('请选择分配人员')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要重新分配选中的 ${selectedWorkOrders.value.length} 个工单吗？\n\n注意：只能重新分配"待分配"或"已分配"状态的工单。`,
      '确认批量重新分配',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_assignee', batchAssignValue.value.toString())
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(`成功重新分配 ${result.updated_count} 个工单`)
    }
    
    showBatchAssignDialog.value = false
    batchAssignValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error('批量重新分配失败: ' + (e.message || e))
    }
  } finally {
    batchLoading.value = false
  }
}

const executeBatchPriority = async () => {
  if (!batchPriorityValue.value) {
    ElMessage.warning('请选择优先级')
    return
  }
  
  try {
    batchLoading.value = true
    const workOrderIds = selectedWorkOrders.value.map(wo => wo.id)
    const result = await workOrderAPI.batchOperation(workOrderIds, 'change_priority', batchPriorityValue.value)
    
    // 保存结果用于详情对话框
    batchResult.value = result
    
    if (result.error_count > 0) {
      // 有失败的工单，显示详情对话框
      showErrorDialog.value = true
    } else {
      // 全部成功
      ElMessage.success(`成功修改 ${result.updated_count} 个工单优先级`)
    }
    
    showBatchPriorityDialog.value = false
    batchPriorityValue.value = ''
    clearSelection()
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error('批量修改优先级失败: ' + e.message)
  } finally {
    batchLoading.value = false
  }
}

onMounted(load)

watch(() => route.query, () => {
  applyListFiltersFromRoute()
  applyCreatePrefillFromRoute()
}, { immediate: true })

watch(statusFilter, (val) => {
  if (val && statusInFilter.value.length) {
    statusInFilter.value = []
  }
})

// 动态筛选/排序：变化时回到第 1 页并刷新
watch([searchKeyword, statusFilter, typeFilter, statusInFilter], () => {
  currentPage.value = 1
  trackSearch()
  load()
})

watch([sortBy, sortOrder], () => {
  currentPage.value = 1
  trackSearch()
  load()
})
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
.header-actions { display:flex; gap: 8px; align-items:center; }
.pagination { margin-top: 12px; display:flex; justify-content: flex-end; }
.sort-panel :deep(.el-radio-group) { width: 100%; }
.sort-panel :deep(.el-radio-button) { width: 50%; }
.sort-panel :deep(.el-radio-button__inner) { width: 100%; text-align: center; }
.work-order-id { 
  font-size: 12px; 
  color: #909399; 
  margin-top: 4px; 
  font-family: 'Courier New', monospace;
}

.title-with-duplicate {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.duplicate-warning-icon {
  color: #e6a23c;
  font-size: 15px;
}

.similar-warning-icon {
  color: #f56c6c;
  font-size: 15px;
}

.batch-operations {
  margin-bottom: 16px;
  background-color: #f0f9ff;
  border: 1px solid #0ea5e9;
}

.batch-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.batch-actions {
  display: flex;
  gap: 8px;
}

.form-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.4;
  color: #909399;
}
</style>
