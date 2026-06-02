<template>
  <div class="page site-group-settings">
    <div class="page-header">
      <div>
        <h1>站点分组设置</h1>
        <div class="page-subtitle">维护站点统计和筛选使用的业务维度</div>
      </div>
      <div class="header-actions">
        <el-button @click="loadCategories" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
        <el-button type="primary" @click="openCreateCategory">
          <el-icon><Plus /></el-icon>
          新增维度
        </el-button>
      </div>
    </div>

    <div class="summary-strip">
      <div class="summary-item">
        <span class="summary-label">启用维度</span>
        <strong>{{ activeCategoryCount }}</strong>
      </div>
      <div class="summary-item">
        <span class="summary-label">全部维度</span>
        <strong>{{ categories.length }}</strong>
      </div>
      <div class="summary-item">
        <span class="summary-label">启用选项</span>
        <strong>{{ activeOptionCount }}</strong>
      </div>
      <div class="summary-item summary-wide">
        <span class="summary-label">默认统计维度</span>
        <strong>{{ defaultCategory?.name || '未设置' }}</strong>
      </div>
    </div>

    <div class="settings-workspace" v-loading="loading">
      <aside class="category-panel">
        <div class="panel-head">
          <span>分组维度</span>
          <el-tag size="small" type="info" effect="plain">{{ categories.length }}</el-tag>
        </div>

        <el-empty v-if="!categories.length" description="暂无维度" :image-size="88" />

        <div v-else class="category-list">
          <button
            v-for="category in sortedCategories"
            :key="category.id"
            class="category-item"
            :class="{ active: category.id === selectedCategoryId, inactive: !category.is_active }"
            type="button"
            @click="selectCategory(category.id)"
          >
            <span class="category-main">
              <span class="category-name" :title="category.name">{{ category.name }}</span>
              <span class="category-code">{{ category.code }}</span>
            </span>
            <span class="category-meta">
              <el-tag v-if="category.is_default" size="small" type="warning" effect="light">默认</el-tag>
              <el-tag size="small" :type="category.is_active ? 'success' : 'info'" effect="plain">
                {{ category.is_active ? '启用' : '停用' }}
              </el-tag>
              <span class="option-count">{{ category.options?.length || 0 }} 项</span>
            </span>
          </button>
        </div>
      </aside>

      <section v-if="selectedCategory" class="detail-panel">
        <div class="detail-head">
          <div class="detail-title">
            <el-icon><CollectionTag /></el-icon>
            <span>{{ selectedCategory.name }}</span>
            <el-tag v-if="selectedCategory.is_default" size="small" type="warning">默认统计</el-tag>
            <el-tag size="small" :type="selectedCategory.is_active ? 'success' : 'info'">
              {{ selectedCategory.is_active ? '启用' : '停用' }}
            </el-tag>
            <el-tag size="small" :type="selectedCategory.assignment_mode === 'derived' ? 'primary' : 'info'" effect="plain">
              {{ selectedCategory.assignment_mode === 'derived' ? '字段派生' : '手工维护' }}
            </el-tag>
          </div>
          <div class="detail-actions">
            <el-button
              v-if="categoryForm.assignment_mode === 'derived'"
              :loading="deriving"
              @click="previewDerived"
            >
              预览派生
            </el-button>
            <el-button
              v-if="categoryForm.assignment_mode === 'derived'"
              type="success"
              :loading="deriving"
              @click="syncDerived"
            >
              同步分组
            </el-button>
            <el-button
              v-if="!selectedCategory.is_default"
              :disabled="!categoryForm.is_active"
              @click="setDefaultCategory"
            >
              <el-icon><Star /></el-icon>
              设为默认
            </el-button>
            <el-button type="primary" :loading="savingCategory" @click="saveCategory">
              <el-icon><Check /></el-icon>
              保存维度
            </el-button>
          </div>
        </div>

        <el-form class="category-form" :model="categoryForm" label-position="top">
          <div class="form-grid">
            <el-form-item label="维度名称" required>
              <el-input v-model="categoryForm.name" maxlength="100" placeholder="例如：交付范围" />
            </el-form-item>
            <el-form-item label="维度编码">
              <el-input v-model="categoryForm.code" maxlength="80" placeholder="留空时按名称生成" />
            </el-form-item>
            <el-form-item label="排序">
              <el-input-number v-model="categoryForm.sort_order" :step="10" :min="0" />
            </el-form-item>
            <el-form-item label="状态">
              <div class="switch-row">
                <el-switch
                  v-model="categoryForm.is_active"
                  active-text="启用"
                  inactive-text="停用"
                />
                <el-switch
                  v-model="categoryForm.is_default"
                  :disabled="!categoryForm.is_active"
                  active-text="默认"
                  inactive-text="非默认"
                />
              </div>
            </el-form-item>
          </div>
          <el-form-item label="说明">
            <el-input
              v-model="categoryForm.description"
              type="textarea"
              :rows="2"
              maxlength="500"
              show-word-limit
              placeholder="例如：用于区分不同交付范围或项目批次"
            />
          </el-form-item>
          <div class="derive-config">
            <div class="derive-row">
              <el-form-item label="维护方式">
                <el-radio-group v-model="categoryForm.assignment_mode" @change="ensureDerivedDefaults(categoryForm)">
                  <el-radio label="manual">手工分组</el-radio>
                  <el-radio label="derived">按字段自动分组</el-radio>
                </el-radio-group>
              </el-form-item>
              <el-form-item v-if="categoryForm.assignment_mode === 'derived'" label="来源字段" required>
                <el-select
                  v-model="categorySourceKey"
                  filterable
                  placeholder="选择站点或 LLD 字段"
                  style="width: 100%"
                >
                  <el-option
                    v-for="field in sourceFields"
                    :key="sourceFieldKey(field)"
                    :label="sourceFieldLabel(field)"
                    :value="sourceFieldKey(field)"
                  />
                </el-select>
              </el-form-item>
            </div>
            <div v-if="categoryForm.assignment_mode === 'derived'" class="derive-row">
              <el-form-item label="归类策略">
                <el-select v-model="categoryForm.source_config.strategy" style="width: 100%">
                  <el-option label="按字段值匹配/自动创建选项" value="field_value" />
                  <el-option label="按关键词规则匹配到选项" value="rules" />
                </el-select>
              </el-form-item>
              <el-form-item label="同步设置">
                <div class="switch-row">
                  <el-switch
                    v-model="categoryForm.source_config.create_missing_options"
                    :disabled="categoryForm.source_config.strategy !== 'field_value'"
                    active-text="自动创建缺失选项"
                  />
                  <el-switch v-model="derivedOverwrite" active-text="覆盖已有站点分组" />
                </div>
              </el-form-item>
            </div>
            <el-alert
              v-if="categoryForm.assignment_mode === 'derived'"
              type="info"
              :closable="false"
              show-icon
              class="derive-tip"
              title="字段派生只会从白名单字段读取数据。一个站点匹配到多个选项时会进入冲突列表，不会自动写入。"
            />
          </div>
        </el-form>

        <div class="option-toolbar">
          <div>
            <h2>选项</h2>
            <span>{{ activeSelectedOptionCount }}/{{ selectedOptions.length }} 启用</span>
          </div>
          <el-button type="primary" plain @click="openCreateOption">
            <el-icon><Plus /></el-icon>
            新增选项
          </el-button>
        </div>

        <el-table :data="selectedOptions" size="small" border>
          <el-table-column label="选项" min-width="180">
            <template #default="{ row }">
              <div class="option-name-cell">
                <span class="color-dot" :style="{ backgroundColor: row.color || '#909399' }" />
                <span class="text-ellipsis" :title="row.name">{{ row.name }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="code" label="编码" min-width="150" />
          <el-table-column prop="sort_order" label="排序" width="90" align="right" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag size="small" :type="row.is_active ? 'success' : 'info'" effect="plain">
                {{ row.is_active ? '启用' : '停用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            v-if="categoryForm.assignment_mode === 'derived' && categoryForm.source_config.strategy === 'rules'"
            label="匹配关键词"
            min-width="220"
          >
            <template #default="{ row }">
              <el-input
                :model-value="getRuleKeywords(categoryForm, row)"
                placeholder="例如：TDD,NR-TDD"
                @update:model-value="value => updateRuleKeywords(categoryForm, row, value)"
              />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openEditOption(row)">
                <el-icon><EditPen /></el-icon>
                编辑
              </el-button>
              <el-button
                link
                :type="row.is_active ? 'danger' : 'success'"
                @click="toggleOptionActive(row)"
              >
                <el-icon><Switch /></el-icon>
                {{ row.is_active ? '停用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section v-else class="detail-panel empty-detail">
        <el-empty description="请选择或新增一个分组维度" />
      </section>
    </div>

    <el-dialog v-model="categoryDialog.visible" title="新增维度" width="720px">
      <el-form :model="categoryDialog.form" label-position="top">
        <div class="form-grid dialog-grid">
          <el-form-item label="维度名称" required>
            <el-input v-model="categoryDialog.form.name" maxlength="100" placeholder="例如：施工批次" />
          </el-form-item>
          <el-form-item label="维度编码">
            <el-input v-model="categoryDialog.form.code" maxlength="80" placeholder="batch" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="categoryDialog.form.sort_order" :step="10" :min="0" />
          </el-form-item>
          <el-form-item label="状态">
            <div class="switch-row">
              <el-switch v-model="categoryDialog.form.is_active" active-text="启用" inactive-text="停用" />
              <el-switch
                v-model="categoryDialog.form.is_default"
                :disabled="!categoryDialog.form.is_active"
                active-text="默认"
                inactive-text="非默认"
              />
            </div>
          </el-form-item>
        </div>
        <el-form-item label="说明">
          <el-input
            v-model="categoryDialog.form.description"
            type="textarea"
            :rows="2"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>
        <div class="derive-config dialog-derive-config">
          <div class="derive-row">
            <el-form-item label="维护方式">
              <el-radio-group v-model="categoryDialog.form.assignment_mode" @change="ensureDerivedDefaults(categoryDialog.form)">
                <el-radio label="manual">手工分组</el-radio>
                <el-radio label="derived">按字段自动分组</el-radio>
              </el-radio-group>
            </el-form-item>
            <el-form-item v-if="categoryDialog.form.assignment_mode === 'derived'" label="来源字段" required>
              <el-select
                v-model="dialogSourceKey"
                filterable
                placeholder="选择站点或 LLD 字段"
                style="width: 100%"
              >
                <el-option
                  v-for="field in sourceFields"
                  :key="sourceFieldKey(field)"
                  :label="sourceFieldLabel(field)"
                  :value="sourceFieldKey(field)"
                />
              </el-select>
            </el-form-item>
          </div>
          <div v-if="categoryDialog.form.assignment_mode === 'derived'" class="derive-row">
            <el-form-item label="归类策略">
              <el-select v-model="categoryDialog.form.source_config.strategy" style="width: 100%">
                <el-option label="按字段值匹配/自动创建选项" value="field_value" />
                <el-option label="按关键词规则匹配到选项" value="rules" />
              </el-select>
            </el-form-item>
            <el-form-item label="缺失选项">
              <el-switch
                v-model="categoryDialog.form.source_config.create_missing_options"
                :disabled="categoryDialog.form.source_config.strategy !== 'field_value'"
                active-text="自动创建"
              />
            </el-form-item>
          </div>
        </div>

        <div class="initial-options-head">
          <span>初始选项</span>
          <el-button link type="primary" @click="addInitialOption">
            <el-icon><Plus /></el-icon>
            添加
          </el-button>
        </div>
        <div class="initial-options">
          <div
            v-for="(option, index) in categoryDialog.form.options"
            :key="option.local_id"
            class="initial-option-row"
            :class="{ 'with-keywords': categoryDialog.form.assignment_mode === 'derived' && categoryDialog.form.source_config.strategy === 'rules' }"
          >
            <el-input v-model="option.name" maxlength="100" placeholder="选项名称" />
            <el-input v-model="option.code" maxlength="80" placeholder="编码" />
            <el-input
              v-if="categoryDialog.form.assignment_mode === 'derived' && categoryDialog.form.source_config.strategy === 'rules'"
              v-model="option.keywords"
              maxlength="200"
              placeholder="关键词"
            />
            <el-color-picker v-model="option.color" />
            <el-input-number v-model="option.sort_order" :min="0" :step="10" />
            <el-button link type="danger" @click="removeInitialOption(index)">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="categoryDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="categoryDialog.saving" @click="createCategory">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="optionDialog.visible" :title="optionDialog.form.id ? '编辑选项' : '新增选项'" width="520px">
      <el-form :model="optionDialog.form" label-position="top">
        <el-form-item label="选项名称" required>
          <el-input v-model="optionDialog.form.name" maxlength="100" placeholder="例如：TDD" />
        </el-form-item>
        <el-form-item label="选项编码">
          <el-input v-model="optionDialog.form.code" maxlength="80" placeholder="留空时按名称生成" />
        </el-form-item>
        <div class="form-grid option-dialog-grid">
          <el-form-item label="颜色">
            <el-color-picker v-model="optionDialog.form.color" />
          </el-form-item>
          <el-form-item label="排序">
            <el-input-number v-model="optionDialog.form.sort_order" :min="0" :step="10" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="optionDialog.form.is_active" active-text="启用" inactive-text="停用" />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="optionDialog.visible = false">取消</el-button>
        <el-button type="primary" :loading="optionDialog.saving" @click="saveOption">
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deriveDialog.visible" title="字段派生预览" width="920px">
      <div v-if="deriveDialog.result" class="derive-result">
        <div class="derive-stats">
          <div class="derive-stat">
            <span>总站点</span>
            <strong>{{ deriveDialog.result.requested_count }}</strong>
          </div>
          <div class="derive-stat">
            <span>可建议</span>
            <strong>{{ deriveDialog.result.suggested_count }}</strong>
          </div>
          <div class="derive-stat">
            <span>可写入</span>
            <strong>{{ deriveDialog.result.assigned_count }}</strong>
          </div>
          <div class="derive-stat">
            <span>冲突</span>
            <strong>{{ deriveDialog.result.conflict_count }}</strong>
          </div>
          <div class="derive-stat">
            <span>跳过</span>
            <strong>{{ deriveDialog.result.skipped_count }}</strong>
          </div>
        </div>
        <el-alert
          v-for="warning in deriveDialog.result.warnings || []"
          :key="warning"
          class="derive-warning"
          type="warning"
          show-icon
          :closable="false"
          :title="warning"
        />
        <el-table :data="deriveDialog.result.samples || []" size="small" border max-height="420">
          <el-table-column prop="site_code" label="站点编码" width="150" />
          <el-table-column prop="site_name" label="站点名称" min-width="180" />
          <el-table-column label="来源值" min-width="180">
            <template #default="{ row }">
              {{ (row.source_values || []).join(', ') || '-' }}
            </template>
          </el-table-column>
          <el-table-column prop="option_name" label="目标分组" width="130" />
          <el-table-column label="动作" width="110">
            <template #default="{ row }">
              <el-tag size="small" :type="deriveActionType(row.action)">
                {{ deriveActionLabel(row.action) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="说明" min-width="180" />
        </el-table>
      </div>
      <template #footer>
        <el-button @click="deriveDialog.visible = false">关闭</el-button>
        <el-button
          type="success"
          :loading="deriving"
          :disabled="!deriveDialog.result || deriveDialog.result.assigned_count <= 0"
          @click="syncDerived"
        >
          按当前预览同步
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Check,
  Close,
  CollectionTag,
  EditPen,
  Plus,
  Refresh,
  Star,
  Switch,
} from '@element-plus/icons-vue'
import siteGroupsApi from '@/api/siteGroups'

const loading = ref(false)
const savingCategory = ref(false)
const categories = ref([])
const selectedCategoryId = ref(null)
const sourceFields = ref([])
const derivedOverwrite = ref(false)
const deriving = ref(false)

const categoryForm = reactive({
  name: '',
  code: '',
  description: '',
  sort_order: 0,
  is_active: true,
  is_default: false,
  assignment_mode: 'manual',
  source_type: null,
  source_field: null,
  source_config: {
    strategy: 'field_value',
    create_missing_options: true,
    rules: [],
  },
})

const categoryDialog = reactive({
  visible: false,
  saving: false,
  form: {
    name: '',
    code: '',
    description: '',
    sort_order: 0,
    is_active: true,
    is_default: false,
    assignment_mode: 'manual',
    source_type: null,
    source_field: null,
    source_config: {
      strategy: 'field_value',
      create_missing_options: true,
      rules: [],
    },
    options: [],
  },
})

const optionDialog = reactive({
  visible: false,
  saving: false,
  form: {
    id: null,
    name: '',
    code: '',
    color: '#2563eb',
    sort_order: 10,
    is_active: true,
  },
})

const deriveDialog = reactive({
  visible: false,
  result: null,
})

const sortedCategories = computed(() => {
  return [...categories.value].sort((a, b) => {
    const ao = Number(a.sort_order || 0)
    const bo = Number(b.sort_order || 0)
    if (ao !== bo) return ao - bo
    return Number(a.id || 0) - Number(b.id || 0)
  })
})

const selectedCategory = computed(() => {
  return categories.value.find(item => item.id === selectedCategoryId.value) || null
})

const selectedOptions = computed(() => {
  return [...(selectedCategory.value?.options || [])].sort((a, b) => {
    const ao = Number(a.sort_order || 0)
    const bo = Number(b.sort_order || 0)
    if (ao !== bo) return ao - bo
    return Number(a.id || 0) - Number(b.id || 0)
  })
})

const sourceFieldKey = (field) => `${field.source_type}:${field.source_field}`

const sourceFieldLabel = (field) => {
  const prefix = field.source_type === 'lld_cell_field' ? 'LLD' : '站点'
  return `${prefix} · ${field.label}`
}

const applySourceKey = (form, key) => {
  const [sourceType, sourceField] = String(key || '').split(':')
  form.source_type = sourceType || null
  form.source_field = sourceField || null
}

const categorySourceKey = computed({
  get: () => categoryForm.source_type && categoryForm.source_field
    ? `${categoryForm.source_type}:${categoryForm.source_field}`
    : '',
  set: (value) => applySourceKey(categoryForm, value),
})

const dialogSourceKey = computed({
  get: () => categoryDialog.form.source_type && categoryDialog.form.source_field
    ? `${categoryDialog.form.source_type}:${categoryDialog.form.source_field}`
    : '',
  set: (value) => applySourceKey(categoryDialog.form, value),
})

const defaultCategory = computed(() => categories.value.find(item => item.is_default) || null)
const activeCategoryCount = computed(() => categories.value.filter(item => item.is_active).length)
const activeOptionCount = computed(() => {
  return categories.value.reduce((total, category) => {
    return total + (category.options || []).filter(option => option.is_active).length
  }, 0)
})
const activeSelectedOptionCount = computed(() => selectedOptions.value.filter(option => option.is_active).length)

const defaultSourceConfig = () => ({
  strategy: 'field_value',
  create_missing_options: true,
  rules: [],
})

const normalizeSourceConfig = (value = {}) => {
  const source = value && typeof value === 'object' ? value : {}
  const strategy = source.strategy === 'rules' ? 'rules' : 'field_value'
  const rawRules = Array.isArray(source.rules) ? source.rules : []
  return {
    strategy,
    create_missing_options: source.create_missing_options !== false,
    rules: rawRules
      .map((rule) => ({
        option_id: rule.option_id || null,
        option_code: String(rule.option_code || '').trim(),
        option_name: String(rule.option_name || '').trim(),
        keywords: Array.isArray(rule.keywords)
          ? rule.keywords.map(item => String(item || '').trim()).filter(Boolean)
          : String(rule.keywords || '').split(',').map(item => item.trim()).filter(Boolean),
        match: rule.match === 'exact' ? 'exact' : 'contains',
      }))
      .filter(rule => rule.keywords.length > 0),
  }
}

const assignSourceConfig = (target, config) => {
  const normalized = normalizeSourceConfig(config)
  target.source_config.strategy = normalized.strategy
  target.source_config.create_missing_options = normalized.create_missing_options
  target.source_config.rules = normalized.rules
}

const ensureDerivedDefaults = (form) => {
  if (form.assignment_mode !== 'derived') return
  if (!form.source_config) {
    form.source_config = defaultSourceConfig()
  } else {
    assignSourceConfig(form, form.source_config)
  }
  if (!form.source_type || !form.source_field) {
    const first = sourceFields.value[0]
    if (first) {
      form.source_type = first.source_type
      form.source_field = first.source_field
    }
  }
}

const getRuleKeywords = (form, option) => {
  const config = normalizeSourceConfig(form.source_config)
  const rule = config.rules.find(item => {
    if (item.option_id && option.id && Number(item.option_id) === Number(option.id)) return true
    if (item.option_code && item.option_code === option.code) return true
    return item.option_name && item.option_name === option.name
  })
  return (rule?.keywords || []).join(', ')
}

const updateRuleKeywords = (form, option, value) => {
  assignSourceConfig(form, form.source_config)
  const keywords = String(value || '').split(',').map(item => item.trim()).filter(Boolean)
  const rules = form.source_config.rules || []
  const index = rules.findIndex(item => {
    if (item.option_id && option.id && Number(item.option_id) === Number(option.id)) return true
    if (item.option_code && item.option_code === option.code) return true
    return item.option_name && item.option_name === option.name
  })
  if (!keywords.length) {
    if (index >= 0) rules.splice(index, 1)
    return
  }
  const nextRule = {
    option_id: option.id || null,
    option_code: option.code || '',
    option_name: option.name || '',
    keywords,
    match: 'contains',
  }
  if (index >= 0) {
    rules.splice(index, 1, nextRule)
  } else {
    rules.push(nextRule)
  }
}

const syncCategoryForm = () => {
  const category = selectedCategory.value
  if (!category) {
    categoryForm.name = ''
    categoryForm.code = ''
    categoryForm.description = ''
    categoryForm.sort_order = 0
    categoryForm.is_active = true
    categoryForm.is_default = false
    categoryForm.assignment_mode = 'manual'
    categoryForm.source_type = null
    categoryForm.source_field = null
    assignSourceConfig(categoryForm, defaultSourceConfig())
    return
  }
  categoryForm.name = category.name || ''
  categoryForm.code = category.code || ''
  categoryForm.description = category.description || ''
  categoryForm.sort_order = Number(category.sort_order || 0)
  categoryForm.is_active = category.is_active !== false
  categoryForm.is_default = Boolean(category.is_default)
  categoryForm.assignment_mode = category.assignment_mode === 'derived' ? 'derived' : 'manual'
  categoryForm.source_type = category.source_type || null
  categoryForm.source_field = category.source_field || null
  assignSourceConfig(categoryForm, category.source_config || defaultSourceConfig())
}

const loadCategories = async () => {
  try {
    loading.value = true
    const res = await siteGroupsApi.listCategories({ include_inactive: true })
    categories.value = Array.isArray(res) ? res : []
    if (!categories.value.length) {
      selectedCategoryId.value = null
      syncCategoryForm()
      return
    }
    const stillExists = categories.value.some(item => item.id === selectedCategoryId.value)
    if (!stillExists) {
      selectedCategoryId.value = sortedCategories.value[0]?.id || null
    }
    syncCategoryForm()
  } catch (error) {
    console.error('加载站点分组失败:', error)
    ElMessage.error('加载站点分组失败')
  } finally {
    loading.value = false
  }
}

const loadSourceFields = async () => {
  try {
    const res = await siteGroupsApi.listSourceFields()
    sourceFields.value = Array.isArray(res) ? res : []
  } catch (error) {
    console.error('加载派生字段失败:', error)
    ElMessage.error('加载派生字段失败')
  }
}

const selectCategory = (categoryId) => {
  selectedCategoryId.value = categoryId
  syncCategoryForm()
}

const buildCategoryPayload = (form) => ({
  name: String(form.name || '').trim(),
  code: String(form.code || '').trim() || null,
  description: String(form.description || '').trim() || null,
  sort_order: Number(form.sort_order || 0),
  is_active: Boolean(form.is_active),
  is_default: Boolean(form.is_active && form.is_default),
  assignment_mode: form.assignment_mode === 'derived' ? 'derived' : 'manual',
  source_type: form.assignment_mode === 'derived' ? form.source_type : null,
  source_field: form.assignment_mode === 'derived' ? form.source_field : null,
  source_config: form.assignment_mode === 'derived' ? normalizeSourceConfig(form.source_config) : null,
})

const validateCategoryPayload = (payload) => {
  if (!payload.name) {
    ElMessage.warning('请填写维度名称')
    return false
  }
  if (payload.assignment_mode === 'derived' && (!payload.source_type || !payload.source_field)) {
    ElMessage.warning('请选择派生来源字段')
    return false
  }
  return true
}

const saveCategory = async () => {
  const category = selectedCategory.value
  if (!category) return
  const payload = buildCategoryPayload(categoryForm)
  if (!validateCategoryPayload(payload)) return

  try {
    savingCategory.value = true
    await siteGroupsApi.updateCategory(category.id, payload)
    ElMessage.success('维度已保存')
    await loadCategories()
    selectedCategoryId.value = category.id
    syncCategoryForm()
  } catch (error) {
    console.error('保存维度失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存维度失败')
  } finally {
    savingCategory.value = false
  }
}

const setDefaultCategory = async () => {
  const category = selectedCategory.value
  if (!category) return
  try {
    savingCategory.value = true
    await siteGroupsApi.updateCategory(category.id, { is_default: true, is_active: true })
    ElMessage.success('默认维度已更新')
    await loadCategories()
    selectedCategoryId.value = category.id
    syncCategoryForm()
  } catch (error) {
    console.error('设置默认维度失败:', error)
    ElMessage.error(error.response?.data?.detail || '设置默认维度失败')
  } finally {
    savingCategory.value = false
  }
}

const createInitialOption = (index = 0) => ({
  local_id: `${Date.now()}_${index}_${Math.random().toString(16).slice(2, 8)}`,
  name: '',
  code: '',
  keywords: '',
  color: '#2563eb',
  sort_order: (index + 1) * 10,
  is_active: true,
})

const openCreateCategory = () => {
  categoryDialog.form.name = ''
  categoryDialog.form.code = ''
  categoryDialog.form.description = ''
  categoryDialog.form.sort_order = (categories.value.length + 1) * 10
  categoryDialog.form.is_active = true
  categoryDialog.form.is_default = categories.value.length === 0
  categoryDialog.form.assignment_mode = 'manual'
  categoryDialog.form.source_type = null
  categoryDialog.form.source_field = null
  assignSourceConfig(categoryDialog.form, defaultSourceConfig())
  categoryDialog.form.options = [createInitialOption(0)]
  categoryDialog.visible = true
}

const addInitialOption = () => {
  categoryDialog.form.options.push(createInitialOption(categoryDialog.form.options.length))
}

const removeInitialOption = (index) => {
  categoryDialog.form.options.splice(index, 1)
}

const buildOptionPayload = (option) => ({
  name: String(option.name || '').trim(),
  code: String(option.code || '').trim() || null,
  color: String(option.color || '').trim() || null,
  sort_order: Number(option.sort_order || 0),
  is_active: option.is_active !== false,
})

const createCategory = async () => {
  if (
    categoryDialog.form.assignment_mode === 'derived'
    && categoryDialog.form.source_config.strategy === 'rules'
  ) {
    categoryDialog.form.source_config.rules = categoryDialog.form.options
      .filter(option => String(option.name || '').trim() && String(option.keywords || '').trim())
      .map(option => ({
        option_name: String(option.name || '').trim(),
        option_code: String(option.code || '').trim(),
        keywords: String(option.keywords || '').split(',').map(item => item.trim()).filter(Boolean),
        match: 'contains',
      }))
  }
  const payload = {
    ...buildCategoryPayload(categoryDialog.form),
    options: categoryDialog.form.options
      .map(buildOptionPayload)
      .filter(option => option.name),
  }
  if (!validateCategoryPayload(payload)) return

  try {
    categoryDialog.saving = true
    const created = await siteGroupsApi.createCategory(payload)
    ElMessage.success('维度已创建')
    categoryDialog.visible = false
    await loadCategories()
    selectedCategoryId.value = created?.id || null
    syncCategoryForm()
  } catch (error) {
    console.error('创建维度失败:', error)
    ElMessage.error(error.response?.data?.detail || '创建维度失败')
  } finally {
    categoryDialog.saving = false
  }
}

const openCreateOption = () => {
  optionDialog.form.id = null
  optionDialog.form.name = ''
  optionDialog.form.code = ''
  optionDialog.form.color = '#2563eb'
  optionDialog.form.sort_order = (selectedOptions.value.length + 1) * 10
  optionDialog.form.is_active = true
  optionDialog.visible = true
}

const openEditOption = (option) => {
  optionDialog.form.id = option.id
  optionDialog.form.name = option.name || ''
  optionDialog.form.code = option.code || ''
  optionDialog.form.color = option.color || '#2563eb'
  optionDialog.form.sort_order = Number(option.sort_order || 0)
  optionDialog.form.is_active = option.is_active !== false
  optionDialog.visible = true
}

const saveOption = async () => {
  const category = selectedCategory.value
  if (!category) return
  const payload = buildOptionPayload(optionDialog.form)
  if (!payload.name) {
    ElMessage.warning('请填写选项名称')
    return
  }

  try {
    optionDialog.saving = true
    if (optionDialog.form.id) {
      await siteGroupsApi.updateOption(optionDialog.form.id, payload)
    } else {
      await siteGroupsApi.createOption(category.id, payload)
    }
    ElMessage.success('选项已保存')
    optionDialog.visible = false
    const categoryId = category.id
    await loadCategories()
    selectedCategoryId.value = categoryId
    syncCategoryForm()
  } catch (error) {
    console.error('保存选项失败:', error)
    ElMessage.error(error.response?.data?.detail || '保存选项失败')
  } finally {
    optionDialog.saving = false
  }
}

const toggleOptionActive = async (option) => {
  if (option.is_active) {
    try {
      await ElMessageBox.confirm(
        '停用后已分配站点会保留原值，但常规统计和筛选不再显示该选项。',
        '停用选项',
        { type: 'warning' },
      )
    } catch {
      return
    }
  }
  try {
    await siteGroupsApi.updateOption(option.id, { is_active: !option.is_active })
    ElMessage.success(option.is_active ? '选项已停用' : '选项已启用')
    const categoryId = selectedCategoryId.value
    await loadCategories()
    selectedCategoryId.value = categoryId
    syncCategoryForm()
  } catch (error) {
    console.error('更新选项状态失败:', error)
    ElMessage.error(error.response?.data?.detail || '更新选项状态失败')
  }
}

const derivePayload = (dryRun, categoryPayload = null) => {
  const payload = {
    dry_run: dryRun,
    overwrite: Boolean(derivedOverwrite.value),
    create_missing_options: categoryForm.source_config?.create_missing_options !== false,
  }
  if (dryRun && categoryPayload) {
    payload.assignment_mode = categoryPayload.assignment_mode
    payload.source_type = categoryPayload.source_type
    payload.source_field = categoryPayload.source_field
    payload.source_config = categoryPayload.source_config
  }
  return payload
}

const previewDerived = async () => {
  const category = selectedCategory.value
  if (!category) return
  const payload = buildCategoryPayload(categoryForm)
  if (!validateCategoryPayload(payload)) return

  try {
    deriving.value = true
    const result = await siteGroupsApi.deriveCategory(category.id, derivePayload(true, payload))
    deriveDialog.result = result
    deriveDialog.visible = true
  } catch (error) {
    console.error('预览派生失败:', error)
    ElMessage.error(error.response?.data?.detail || '预览派生失败')
  } finally {
    deriving.value = false
  }
}

const syncDerived = async () => {
  const category = selectedCategory.value
  if (!category) return
  const payload = buildCategoryPayload(categoryForm)
  if (!validateCategoryPayload(payload)) return

  try {
    await ElMessageBox.confirm(
      derivedOverwrite.value
        ? '同步会按当前来源字段重算站点分组，并覆盖已有分组。是否继续？'
        : '同步只会写入尚未分组的站点；已有分组会进入冲突，不会覆盖。是否继续？',
      '同步字段派生分组',
      { type: 'warning' },
    )
  } catch {
    return
  }

  try {
    deriving.value = true
    await siteGroupsApi.updateCategory(category.id, payload)
    const result = await siteGroupsApi.deriveCategory(category.id, derivePayload(false))
    deriveDialog.result = result
    deriveDialog.visible = true
    ElMessage.success(`已同步 ${result.assigned_count || 0} 个站点`)
    await loadCategories()
    selectedCategoryId.value = category.id
    syncCategoryForm()
  } catch (error) {
    console.error('同步派生分组失败:', error)
    ElMessage.error(error.response?.data?.detail || '同步派生分组失败')
  } finally {
    deriving.value = false
  }
}

const deriveActionLabel = (action) => {
  const labels = {
    assign: '写入',
    overwrite: '覆盖',
    unchanged: '不变',
    conflict: '冲突',
    skipped: '跳过',
  }
  return labels[action] || action || '-'
}

const deriveActionType = (action) => {
  if (action === 'assign' || action === 'overwrite') return 'success'
  if (action === 'unchanged') return 'info'
  if (action === 'conflict') return 'warning'
  return 'info'
}

onMounted(async () => {
  await loadSourceFields()
  await loadCategories()
})
</script>

<style scoped>
.site-group-settings {
  --panel-border: #e5e7eb;
  --panel-muted: #f6f8fb;
  --text-muted: #667085;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
}

.page-subtitle {
  margin-top: 6px;
  color: var(--text-muted);
  font-size: 13px;
}

.header-actions,
.detail-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.summary-item {
  min-height: 72px;
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
}

.summary-label {
  color: var(--text-muted);
  font-size: 13px;
}

.summary-item strong {
  color: #111827;
  font-size: 22px;
  line-height: 1.1;
  word-break: break-word;
}

.settings-workspace {
  display: grid;
  grid-template-columns: minmax(260px, 320px) minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.category-panel,
.detail-panel {
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  background: #fff;
}

.category-panel {
  overflow: hidden;
}

.panel-head,
.detail-head,
.option-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--panel-border);
}

.panel-head {
  font-weight: 600;
  color: #1f2937;
}

.category-list {
  display: flex;
  flex-direction: column;
  padding: 8px;
  gap: 6px;
  max-height: calc(100vh - 290px);
  overflow: auto;
}

.category-item {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  padding: 11px 10px;
  text-align: left;
  cursor: pointer;
}

.category-item:hover {
  background: var(--panel-muted);
}

.category-item.active {
  border-color: #2f80ed;
  background: #eff6ff;
}

.category-item.inactive {
  opacity: 0.72;
}

.category-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.category-name,
.text-ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-name {
  color: #1f2937;
  font-weight: 600;
}

.category-code {
  color: var(--text-muted);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.category-meta {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.option-count {
  color: var(--text-muted);
  font-size: 12px;
}

.detail-panel {
  min-width: 0;
  padding-bottom: 16px;
}

.empty-detail {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.detail-title {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
  color: #111827;
  font-size: 18px;
  font-weight: 700;
}

.detail-title > span:first-of-type {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.category-form {
  padding: 16px;
}

.form-grid {
  display: grid;
  grid-template-columns: minmax(180px, 1.4fr) minmax(160px, 1fr) 130px minmax(210px, 1fr);
  gap: 14px;
}

.dialog-grid {
  grid-template-columns: minmax(180px, 1.4fr) minmax(160px, 1fr) 120px minmax(190px, 1fr);
}

.option-dialog-grid {
  grid-template-columns: 100px 150px minmax(120px, 1fr);
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 32px;
  flex-wrap: wrap;
}

.derive-config {
  border: 1px solid #dbe4f0;
  border-radius: 8px;
  background: #f8fbff;
  padding: 14px 14px 6px;
  margin-top: 12px;
}

.dialog-derive-config {
  margin-bottom: 14px;
}

.derive-row {
  display: grid;
  grid-template-columns: minmax(240px, 1fr) minmax(260px, 1.2fr);
  gap: 14px;
}

.derive-tip {
  margin-bottom: 8px;
}

.option-toolbar {
  border-top: 1px solid var(--panel-border);
  background: #fbfcfe;
}

.option-toolbar h2 {
  margin: 0 0 4px;
  color: #1f2937;
  font-size: 16px;
}

.option-toolbar span {
  color: var(--text-muted);
  font-size: 13px;
}

.option-name-cell {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.color-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.12);
  flex: 0 0 auto;
}

.initial-options-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 2px 0 10px;
  color: #1f2937;
  font-weight: 600;
}

.initial-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.initial-option-row {
  display: grid;
  grid-template-columns: minmax(130px, 1.1fr) minmax(120px, 1fr) 42px 120px 32px;
  align-items: center;
  gap: 8px;
}

.initial-option-row.with-keywords {
  grid-template-columns: minmax(130px, 1.1fr) minmax(120px, 1fr) minmax(130px, 1fr) 42px 120px 32px;
}

.derive-result {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.derive-stats {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.derive-stat {
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.derive-stat span {
  display: block;
  color: var(--text-muted);
  font-size: 12px;
  margin-bottom: 6px;
}

.derive-stat strong {
  color: #111827;
  font-size: 20px;
}

.derive-warning {
  margin-bottom: 0;
}

@media (max-width: 1080px) {
  .summary-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .settings-workspace {
    grid-template-columns: 1fr;
  }

  .category-list {
    max-height: none;
  }

  .form-grid,
  .dialog-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .page-header,
  .detail-head {
    flex-direction: column;
    align-items: stretch;
  }

  .summary-strip,
  .form-grid,
  .dialog-grid,
  .derive-row,
  .option-dialog-grid,
  .derive-stats,
  .initial-option-row {
    grid-template-columns: 1fr;
  }

  .initial-option-row {
    align-items: stretch;
  }
}
</style>
