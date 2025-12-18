<template>
  <div class="template-management">
    <div class="page-header">
      <h2>检查模板管理</h2>
      <p>管理检查模板和绑定规则</p>
    </div>

    <div class="action-bar">
      <div class="search-section">
        <el-input
          v-model="searchQuery"
          placeholder="搜索模板名称"
          clearable
          @keyup.enter="handleSearch"
          style="width: 300px; margin-right: 16px;"
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
        <el-button @click="handleSearch">
          <el-icon><Search /></el-icon>
          搜索
        </el-button>
      </div>
      
      <div class="action-buttons">
        <el-button type="primary" @click="handleCreateTemplate">
          <el-icon><Plus /></el-icon>
          新建模板
        </el-button>
        <el-button @click="handleImportTemplate">
          <el-icon><Upload /></el-icon>
          导入模板(JSON)
        </el-button>
      </div>
    </div>

    <el-table 
      :data="templates" 
      v-loading="loading"
      border
      style="width: 100%"
    >
      <el-table-column prop="template_name" label="模板名称" min-width="200">
        <template #default="{ row }">
          <div class="template-name">
            <strong>{{ row.template_name }}</strong>
            <div class="template-id">ID: {{ row.id }}</div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="工单统计" width="120">
        <template #default="{ row }">
          <div class="workorder-stats">
            <el-tag size="small" type="success">
              {{ row.active_work_orders_count }} 进行中
            </el-tag>
            <el-tag size="small" type="info">
              {{ row.work_orders_count }} 总计
            </el-tag>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column label="模板内容预览" min-width="300">
        <template #default="{ row }">
          <div class="template-preview">
            <div class="categories-count">
              {{ getCategoriesCount(row.template_data) }} 个检查分类
            </div>
            <div class="items-preview">
              <el-tag
                v-for="category in getPreviewCategories(row.template_data)"
                :key="category.category_id"
                size="small"
                style="margin-right: 8px; margin-bottom: 4px;"
              >
                {{ category.category_name }} ({{ category.items.length }})
              </el-tag>
            </div>
          </div>
        </template>
      </el-table-column>
      
      <el-table-column prop="creator_name" label="创建者" width="100" />
      
      <el-table-column prop="updated_at" label="更新时间" width="150">
        <template #default="{ row }">
          {{ formatDateTime(row.updated_at) }}
        </template>
      </el-table-column>
      
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <div class="op-actions">
            <el-button link type="primary" size="small" @click="handlePreviewTemplate(row)">
              <el-icon><View /></el-icon>预览
            </el-button>
            <el-button link type="primary" size="small" @click="handleEditTemplate(row)">
              <el-icon><Edit /></el-icon>编辑
            </el-button>
            <el-tooltip content="绑定管理" placement="top">
              <el-button link type="warning" size="small" @click="handleManageBindings(row)">
                <el-icon><Link /></el-icon>绑定
              </el-button>
            </el-tooltip>
            <el-button link type="info" size="small" @click="handleExportTemplate(row)">
              <el-icon><Download /></el-icon>导出
            </el-button>
            <el-button link type="danger" size="small" @click="handleDeleteTemplate(row)">
              <el-icon><Delete /></el-icon>删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        @size-change="handleSizeChange"
        @current-change="handleCurrentChange"
      />
    </div>

    <!-- 创建/编辑模板对话框 -->
    <el-dialog
      v-model="templateDialogVisible"
      :title="isEditingTemplate ? '编辑模板' : '创建模板'"
      width="500px"
    >
      <el-form
        ref="templateFormRef"
        :model="templateForm"
        :rules="templateRules"
        label-width="120px"
      >
        <el-form-item label="模板名称" prop="template_name">
          <el-input v-model="templateForm.template_name" placeholder="请输入模板名称" />
        </el-form-item>
        
        <el-form-item label="模板说明">
          <el-input
            v-model="templateForm.description"
            type="textarea"
            :rows="3"
            placeholder="请输入模板说明（可选）"
          />
        </el-form-item>
      </el-form>
      
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="templateDialogVisible = false">取消</el-button>
          <el-button 
            type="primary" 
            @click="handleSaveTemplate"
            :loading="saving"
          >
            {{ isEditingTemplate ? '更新' : '创建' }}
          </el-button>
        </span>
      </template>
    </el-dialog>

    <!-- 绑定管理对话框 -->
    <el-dialog
      v-model="bindingDialogVisible"
      :title="`${currentTemplate?.template_name} - 绑定管理`"
      width="90%"
      top="5vh"
    >
      <BindingManagement
        v-if="bindingDialogVisible && currentTemplate"
        :template="currentTemplate"
        @close="bindingDialogVisible = false"
        @refresh="loadTemplates"
      />
    </el-dialog>

    <!-- 导入模板对话框 -->
    <el-dialog
      v-model="importDialogVisible"
      title="导入检查模板(JSON)"
      width="600px"
    >
      <p class="hint">
        请选择从本系统导出的模板 JSON 文件，或符合结构的自定义模板 JSON 文件。
      </p>
      <el-form
        :model="importForm"
        label-width="120px"
        style="margin-top: 12px;"
      >
        <el-form-item label="选择文件">
          <input
            type="file"
            accept=".json,application/json"
            @change="handleImportFileChange"
          />
          <div v-if="importFileName" class="file-name">已选择：{{ importFileName }}</div>
        </el-form-item>
        <el-form-item label="模板名称(可选)">
          <el-input
            v-model="importForm.template_name"
            placeholder="请输入新模板名称（必填且唯一）"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <span class="dialog-footer">
          <el-button @click="importDialogVisible = false">取消</el-button>
          <el-button
            type="primary"
            :loading="importing"
            @click="confirmImportTemplate"
          >
            确认导入
          </el-button>
        </span>
      </template>
    </el-dialog>

    <TemplatePreviewDrawer
      v-model="previewVisible"
      :content="previewContent"
      :loading="previewLoading"
      :error="previewError"
      :disabled="false"
      :title="previewTitle"
    />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Upload, View, Edit, Link, Download, Delete } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { templateAPI } from '../../api/templates'
import BindingManagement from './components/BindingManagement.vue'
import TemplatePreviewDrawer from './components/TemplatePreviewDrawer.vue'

const router = useRouter()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const templates = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')

// 对话框状态
const templateDialogVisible = ref(false)
const bindingDialogVisible = ref(false)
const isEditingTemplate = ref(false)
const currentTemplate = ref(null)

const importDialogVisible = ref(false)
const importing = ref(false)
const importForm = reactive({
  template_name: ''
})
const importFileName = ref('')
const importTemplateObject = ref(null)

const previewVisible = ref(false)
const previewLoading = ref(false)
const previewError = ref('')
const previewTitle = ref('模板预览')
const previewContent = ref(null)

// 表单数据
const templateFormRef = ref()
const templateForm = reactive({
  template_name: '',
  description: ''
})

// 表单验证规则
const templateRules = {
  template_name: [
    { required: true, message: '请输入模板名称', trigger: 'blur' },
    { min: 2, max: 100, message: '长度在 2 到 100 个字符', trigger: 'blur' }
  ]
}

// 方法
const loadTemplates = async () => {
  loading.value = true
  try {
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    
    if (searchQuery.value.trim()) {
      params.q = searchQuery.value.trim()
    }
    
    const response = await templateAPI.getTemplates(params)
    templates.value = response
    
    // 计算总数（这里简单处理，实际应该从API返回）
    total.value = response.length < pageSize.value ? 
      (currentPage.value - 1) * pageSize.value + response.length : 
      currentPage.value * pageSize.value + 1
    
  } catch (error) {
    console.error('加载模板列表失败:', error)
    ElMessage.error('加载模板列表失败')
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  currentPage.value = 1
  loadTemplates()
}

const handleSizeChange = (newSize) => {
  pageSize.value = newSize
  loadTemplates()
}

const handleCurrentChange = (newPage) => {
  currentPage.value = newPage
  loadTemplates()
}

const handleCreateTemplate = () => {
  isEditingTemplate.value = false
  templateForm.template_name = ''
  templateForm.description = ''
  templateDialogVisible.value = true
}

const handleEditTemplate = (template) => {
  router.push({ name: 'TemplateEditor', params: { id: template.id } })
}

const handlePreviewTemplate = async (templateRow) => {
  previewVisible.value = true
  previewLoading.value = true
  previewError.value = ''
  previewContent.value = null
  previewTitle.value = `模板预览 - ${templateRow?.template_name || ''}`

  try {
    const tpl = await templateAPI.getTemplate(templateRow.id)
    const categories = tpl?.template_data?.check_categories || []
    if (!categories.length) {
      ElMessage.warning('模板为空，暂无可预览内容')
    }

    previewContent.value = {
      meta: {
        template: {
          name: tpl?.template_name || templateRow?.template_name || '',
          version: tpl?.template_data?.template_version,
        },
      },
      check_categories: categories,
    }
  } catch (error) {
    console.error('加载模板预览失败:', error)
    previewError.value = '加载预览失败，请稍后重试'
    ElMessage.error(previewError.value)
  } finally {
    previewLoading.value = false
  }
}

const handleManageBindings = (template) => {
  currentTemplate.value = template
  bindingDialogVisible.value = true
}

const handleExportTemplate = async (template) => {
  try {
    const data = await templateAPI.exportTemplate(template.id)
    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json;charset=utf-8'
    })
    const link = document.createElement('a')
    const ts = new Date().toISOString().replace(/[:.]/g, '-')
    const filename = `template_${template.id}_${ts}.json`
    link.href = URL.createObjectURL(blob)
    link.download = filename
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    URL.revokeObjectURL(link.href)
    ElMessage.success('模板导出成功')
  } catch (error) {
    console.error('导出模板失败:', error)
    ElMessage.error('导出模板失败')
  }
}

const handleImportTemplate = () => {
  importFileName.value = ''
  importTemplateObject.value = null
  importForm.template_name = ''
  importDialogVisible.value = true
}

const handleImportFileChange = (event) => {
  const file = event.target.files && event.target.files[0]
  if (!file) {
    importFileName.value = ''
    importTemplateObject.value = null
    return
  }
  importFileName.value = file.name
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const text = e.target.result
      const parsed = JSON.parse(text)
      importTemplateObject.value = parsed
    } catch (err) {
      importTemplateObject.value = null
      ElMessage.error('JSON 解析失败，请检查文件内容')
    }
  }
  reader.onerror = () => {
    importTemplateObject.value = null
    ElMessage.error('读取文件失败')
  }
  reader.readAsText(file, 'utf-8')
}

const confirmImportTemplate = async () => {
  if (!importTemplateObject.value) {
    ElMessage.warning('请先选择要导入的 JSON 文件')
    return
  }
  if (!importForm.template_name || !importForm.template_name.trim()) {
    ElMessage.warning('请填写新模板名称')
    return
  }

  const payload = {
    template_name: importForm.template_name.trim(),
    template: importTemplateObject.value
  }

  importing.value = true
  try {
    const res = await templateAPI.importTemplate(payload)
    ElMessage.success(`导入成功，已创建模板：${res.template_name}`)
    importDialogVisible.value = false
    await loadTemplates()
  } catch (error) {
    console.error('导入模板失败:', error)
    const detail = error?.response?.data?.detail
    if (typeof detail === 'string') {
      ElMessage.error(`导入失败：${detail}`)
    } else if (detail?.message) {
      ElMessage.error(`导入失败：${detail.message}`)
    } else {
      ElMessage.error('导入模板失败，请检查 JSON 结构')
    }
  } finally {
    importing.value = false
  }
}

const handleDeleteTemplate = async (template) => {
  try {
    await ElMessageBox.confirm(
      `确认删除模板 "${template.template_name}" 吗？`,
      '删除确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await templateAPI.deleteTemplate(template.id)
    ElMessage.success('模板删除成功')
    loadTemplates()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除模板失败:', error)
      ElMessage.error('删除模板失败')
    }
  }
}

const handleSaveTemplate = async () => {
  try {
    await templateFormRef.value.validate()
    
    saving.value = true
    
    const templateData = {
      template_name: templateForm.template_name,
      template_data: {
        description: templateForm.description || '',
        check_categories: []
      }
    }
    
    if (isEditingTemplate.value) {
      await templateAPI.updateTemplate(currentTemplate.value.id, templateData)
      ElMessage.success('模板更新成功')
    } else {
      const newTemplate = await templateAPI.createTemplate(templateData)
      ElMessage.success('模板创建成功')
      
      // 创建成功后跳转到编辑页面
      router.push({ name: 'TemplateEditor', params: { id: newTemplate.id } })
    }
    
    templateDialogVisible.value = false
    loadTemplates()
  } catch (error) {
    console.error('保存模板失败:', error)
    ElMessage.error('保存模板失败')
  } finally {
    saving.value = false
  }
}

// 辅助方法
const getCategoriesCount = (templateData) => {
  return templateData?.check_categories?.length || 0
}

const getPreviewCategories = (templateData) => {
  return templateData?.check_categories?.slice(0, 3) || []
}

const formatDateTime = (dateStr) => {
  if (!dateStr) return '-'
  return new Date(dateStr).toLocaleString('zh-CN')
}

// 组件挂载
onMounted(() => {
  loadTemplates()
})
</script>

<style scoped>
.template-management {
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0 0 8px 0;
  font-size: 24px;
  font-weight: 600;
}

.page-header p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-section {
  display: flex;
  align-items: center;
}

.action-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.template-name {
  line-height: 1.4;
}

.template-id {
  font-size: 12px;
  color: #999;
  margin-top: 2px;
}

.workorder-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-preview {
  line-height: 1.4;
}

.categories-count {
  font-weight: 500;
  margin-bottom: 8px;
}

.items-preview {
  display: flex;
  flex-wrap: wrap;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.hint {
  color: #909399;
  font-size: 13px;
}

.file-name {
  margin-top: 4px;
  font-size: 13px;
  color: #606266;
}

.op-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
}

.op-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
