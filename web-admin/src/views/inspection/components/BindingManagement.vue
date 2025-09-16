<template>
  <div class="binding-management">
    <div class="binding-header">
      <div class="template-info">
        <h3>{{ template.template_name }}</h3>
        <p>模板绑定规则管理</p>
      </div>
      
      <el-button type="primary" @click="showCreateDialog">
        <el-icon><Plus /></el-icon>
        新增绑定
      </el-button>
    </div>

    <div class="binding-actions">
      <el-switch
        v-model="activeOnly"
        active-text="仅显示活跃绑定"
        @change="loadBindings"
      />
      
      <div class="resolver-test-btn">
        <el-button type="success" @click="showResolverTest">
          <el-icon><Tools /></el-icon>
          解析测试
        </el-button>
      </div>
    </div>

    <el-table 
      :data="bindings" 
      v-loading="loading"
      border
      row-key="id"
      @sort-change="handleSortChange"
    >
      <el-table-column label="拖拽" width="60">
        <template #default>
          <el-icon class="drag-handle"><Rank /></el-icon>
        </template>
      </el-table-column>
      
      <el-table-column label="绑定条件" min-width="300">
        <template #default="{ row }">
          <div class="binding-conditions">
            <el-tag v-if="row.site_id" type="warning" size="small">
              站点: {{ row.site_name || row.site_id }}
            </el-tag>
            <el-tag v-if="row.site_type" type="info" size="small">
              类型: {{ SITE_TYPE_LABELS[row.site_type] || row.site_type }}
            </el-tag>
            <el-tag v-if="row.task_type" type="success" size="small">
              任务: {{ TASK_TYPE_LABELS[row.task_type] || row.task_type }}
            </el-tag>
            <el-tag v-if="row.region" type="primary" size="small">
              区域: {{ row.region }}
            </el-tag>
            <el-tag v-if="row.customer" type="danger" size="small">
              客户: {{ row.customer }}
            </el-tag>
            <el-tag 
              v-for="tag in (row.tags || [])" 
              :key="tag" 
              size="small"
            >
              {{ tag }}
            </el-tag>
            <el-tag v-if="!hasAnyCondition(row)" type="info" size="small">
              通用绑定
            </el-tag>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column 
        prop="priority" 
        label="优先级" 
        width="100" 
        sortable="custom"
      >
        <template #default="{ row }">
          <el-tag :type="getPriorityType(row.priority)" size="small">
            {{ row.priority }}
          </el-tag>
        </template>
      </el-table-column>
      
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-switch
            v-model="row.active"
            @change="handleToggleActive(row)"
          />
        </template>
      </el-table-column>
      
      <el-table-column label="有效期" width="200">
        <template #default="{ row }">
          <div class="validity-period">
            <div v-if="row.valid_from || row.valid_to">
              <div v-if="row.valid_from">
                从: {{ formatDate(row.valid_from) }}
              </div>
              <div v-if="row.valid_to">
                到: {{ formatDate(row.valid_to) }}
              </div>
            </div>
            <el-tag v-else type="info" size="small">永久有效</el-tag>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="notes" label="备注" min-width="150">
        <template #default="{ row }">
          <span class="binding-notes">{{ row.notes || '-' }}</span>
        </template>
      </el-table-column>
      
      <el-table-column label="创建信息" width="150">
        <template #default="{ row }">
          <div class="creation-info">
            <div>{{ row.creator_name || '-' }}</div>
            <div class="created-at">{{ formatDateTime(row.created_at) }}</div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="editBinding(row)">
            编辑
          </el-button>
          <el-button 
            size="small" 
            type="danger" 
            @click="deleteBinding(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建/编辑绑定对话框 -->
    <el-dialog
      v-model="bindingDialogVisible"
      :title="isEditingBinding ? '编辑绑定' : '创建绑定'"
      width="600px"
    >
      <el-form
        ref="bindingFormRef"
        :model="bindingForm"
        :rules="bindingRules"
        label-width="120px"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="站点ID" prop="site_id">
              <el-input-number 
                v-model="bindingForm.site_id" 
                placeholder="留空表示不限制"
                :min="1"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="站点类型">
              <el-select 
                v-model="bindingForm.site_type" 
                placeholder="留空表示不限制"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="(label, value) in SITE_TYPE_LABELS"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="任务类型">
              <el-select 
                v-model="bindingForm.task_type" 
                placeholder="留空表示不限制"
                clearable
                style="width: 100%"
              >
                <el-option
                  v-for="(label, value) in TASK_TYPE_LABELS"
                  :key="value"
                  :label="label"
                  :value="value"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="区域">
              <el-input 
                v-model="bindingForm.region" 
                placeholder="留空表示不限制"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户">
              <el-input 
                v-model="bindingForm.customer" 
                placeholder="留空表示不限制"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="优先级" prop="priority">
              <el-input-number 
                v-model="bindingForm.priority" 
                :min="1" 
                :max="100"
                controls-position="right"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="标签">
          <el-input 
            v-model="bindingForm.tagsInput" 
            placeholder="多个标签用逗号分隔"
          />
        </el-form-item>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="生效时间">
              <el-date-picker
                v-model="bindingForm.valid_from"
                type="datetime"
                placeholder="留空表示立即生效"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="失效时间">
              <el-date-picker
                v-model="bindingForm.valid_to"
                type="datetime"
                placeholder="留空表示永不失效"
                style="width: 100%"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="启用状态">
          <el-switch v-model="bindingForm.active" />
        </el-form-item>
        
        <el-form-item label="备注">
          <el-input
            v-model="bindingForm.notes"
            type="textarea"
            :rows="3"
            placeholder="绑定规则说明"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <div class="dialog-footer">
          <el-button @click="bindingDialogVisible = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="saveBinding"
            :loading="saving"
          >
            {{ isEditingBinding ? '更新' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>

    <!-- 解析测试对话框 -->
    <ResolverTestPanel 
      v-model="resolverTestVisible"
      @test="handleResolverTest"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Tools, Rank } from '@element-plus/icons-vue'
import { bindingAPI, TASK_TYPE_LABELS, SITE_TYPE_LABELS } from '../../../api/templates'
import ResolverTestPanel from './ResolverTestPanel.vue'

// Props
const props = defineProps({
  template: {
    type: Object,
    required: true
  }
})

// Emits
const emit = defineEmits(['close', 'refresh'])

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const bindings = ref([])
const activeOnly = ref(false)

const bindingDialogVisible = ref(false)
const resolverTestVisible = ref(false)
const isEditingBinding = ref(false)
const currentBinding = ref(null)

// 表单相关
const bindingFormRef = ref()
const bindingForm = reactive({
  site_id: null,
  site_type: '',
  task_type: '',
  region: '',
  customer: '',
  priority: 50,
  active: true,
  valid_from: null,
  valid_to: null,
  notes: '',
  tagsInput: ''
})

const bindingRules = {
  priority: [
    { required: true, message: '请输入优先级', trigger: 'blur' },
    { type: 'number', min: 1, max: 100, message: '优先级范围为 1-100', trigger: 'blur' }
  ]
}

// 方法
const loadBindings = async () => {
  loading.value = true
  try {
    const response = await bindingAPI.getTemplateBindings(props.template.id, {
      active_only: activeOnly.value
    })
    bindings.value = response
  } catch (error) {
    console.error('加载绑定列表失败:', error)
    ElMessage.error('加载绑定列表失败')
  } finally {
    loading.value = false
  }
}

const showCreateDialog = () => {
  isEditingBinding.value = false
  resetBindingForm()
  bindingDialogVisible.value = true
}

const editBinding = (binding) => {
  isEditingBinding.value = true
  currentBinding.value = binding
  
  // 填充表单
  bindingForm.site_id = binding.site_id
  bindingForm.site_type = binding.site_type || ''
  bindingForm.task_type = binding.task_type || ''
  bindingForm.region = binding.region || ''
  bindingForm.customer = binding.customer || ''
  bindingForm.priority = binding.priority
  bindingForm.active = binding.active
  bindingForm.valid_from = binding.valid_from ? new Date(binding.valid_from) : null
  bindingForm.valid_to = binding.valid_to ? new Date(binding.valid_to) : null
  bindingForm.notes = binding.notes || ''
  bindingForm.tagsInput = (binding.tags || []).join(', ')
  
  bindingDialogVisible.value = true
}

const deleteBinding = async (binding) => {
  try {
    await ElMessageBox.confirm(
      `确认删除这个绑定规则吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await bindingAPI.deleteBinding(props.template.id, binding.id)
    ElMessage.success('绑定规则删除成功')
    loadBindings()
    emit('refresh')
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除绑定失败:', error)
      ElMessage.error('删除绑定失败')
    }
  }
}

const saveBinding = async () => {
  try {
    await bindingFormRef.value.validate()
    
    saving.value = true
    
    const bindingData = {
      site_id: bindingForm.site_id || null,
      site_type: bindingForm.site_type || null,
      task_type: bindingForm.task_type || null,
      region: bindingForm.region || null,
      customer: bindingForm.customer || null,
      priority: bindingForm.priority,
      active: bindingForm.active,
      valid_from: bindingForm.valid_from || null,
      valid_to: bindingForm.valid_to || null,
      notes: bindingForm.notes || null,
      tags: bindingForm.tagsInput ? 
        bindingForm.tagsInput.split(',').map(t => t.trim()).filter(t => t) : 
        null
    }
    
    if (isEditingBinding.value) {
      await bindingAPI.updateBinding(
        props.template.id, 
        currentBinding.value.id, 
        bindingData
      )
      ElMessage.success('绑定规则更新成功')
    } else {
      await bindingAPI.createBinding(props.template.id, bindingData)
      ElMessage.success('绑定规则创建成功')
    }
    
    bindingDialogVisible.value = false
    loadBindings()
    emit('refresh')
  } catch (error) {
    console.error('保存绑定失败:', error)
    ElMessage.error('保存绑定失败')
  } finally {
    saving.value = false
  }
}

const handleToggleActive = async (binding) => {
  try {
    await bindingAPI.updateBinding(
      props.template.id,
      binding.id,
      { active: binding.active }
    )
    
    ElMessage.success(
      binding.active ? '绑定已启用' : '绑定已禁用'
    )
    emit('refresh')
  } catch (error) {
    console.error('切换绑定状态失败:', error)
    // 回滚状态
    binding.active = !binding.active
    ElMessage.error('切换绑定状态失败')
  }
}

const handleSortChange = ({ prop, order }) => {
  if (prop === 'priority') {
    bindings.value.sort((a, b) => {
      const result = order === 'descending' ? 
        b.priority - a.priority : 
        a.priority - b.priority
      return result
    })
  }
}

const showResolverTest = () => {
  resolverTestVisible.value = true
}

const handleResolverTest = async (context) => {
  // 由 ResolverTestPanel 处理
}

const resetBindingForm = () => {
  bindingForm.site_id = null
  bindingForm.site_type = ''
  bindingForm.task_type = ''
  bindingForm.region = ''
  bindingForm.customer = ''
  bindingForm.priority = 50
  bindingForm.active = true
  bindingForm.valid_from = null
  bindingForm.valid_to = null
  bindingForm.notes = ''
  bindingForm.tagsInput = ''
}

// 辅助方法
const hasAnyCondition = (binding) => {
  return binding.site_id || binding.site_type || binding.task_type || 
         binding.region || binding.customer || (binding.tags && binding.tags.length > 0)
}

const getPriorityType = (priority) => {
  if (priority >= 80) return 'danger'
  if (priority >= 60) return 'warning'
  if (priority >= 40) return 'success'
  return 'info'
}

const formatDate = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleDateString('zh-CN')
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return ''
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 组件挂载
onMounted(() => {
  loadBindings()
})
</script>

<style scoped>
.binding-management {
  padding: 0;
}

.binding-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
}

.template-info h3 {
  margin: 0 0 4px 0;
  font-size: 18px;
}

.template-info p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.binding-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.binding-conditions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.validity-period {
  font-size: 12px;
  line-height: 1.4;
}

.creation-info {
  font-size: 12px;
  line-height: 1.4;
}

.created-at {
  color: #999;
  margin-top: 2px;
}

.binding-notes {
  font-size: 12px;
  color: #666;
}

.drag-handle {
  cursor: move;
  color: #ccc;
}

.drag-handle:hover {
  color: #409eff;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>