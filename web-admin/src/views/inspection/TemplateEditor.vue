<template>
  <div class="template-editor">
    <div class="editor-header">
      <div class="header-left">
        <el-button @click="goBack" size="small">
          <el-icon><ArrowLeft /></el-icon>
          返回
        </el-button>
        <div class="template-title">
          <h2>{{ isNewTemplate ? '新建检查模板' : template?.template_name || '加载中...' }}</h2>
          <p v-if="!isNewTemplate">编辑检查模板结构和内容</p>
        </div>
      </div>
      
      <div class="header-actions">
        <el-button @click="previewTemplate" v-if="!isNewTemplate">
          <el-icon><View /></el-icon>
          预览
        </el-button>
        <el-button 
          type="primary" 
          @click="saveTemplate"
          :loading="saving"
        >
          <el-icon><Check /></el-icon>
          {{ isNewTemplate ? '创建模板' : '保存更改' }}
        </el-button>
      </div>
    </div>

    <div class="editor-content">
      <el-row :gutter="20">
        <!-- 左侧：模板编辑器 -->
        <el-col :span="16">
          <el-card class="editor-card">
            <template #header>
              <div class="card-header">
                <span>模板结构编辑</span>
                <el-button size="small" @click="addCategory">
                  <el-icon><Plus /></el-icon>
                  添加分类
                </el-button>
              </div>
            </template>
            
            <div v-if="loading" class="loading-container">
              <el-skeleton :rows="8" animated />
            </div>
            
            <div v-else class="categories-editor">
              <!-- 模板基本信息 -->
              <el-form :model="templateForm" label-width="120px" class="template-basic-form">
                <el-form-item label="模板名称" required>
                  <el-input 
                    v-model="templateForm.template_name" 
                    placeholder="请输入模板名称"
                  />
                </el-form-item>
                <el-form-item label="模板描述">
                  <el-input 
                    v-model="templateForm.description" 
                    type="textarea"
                    :rows="2"
                    placeholder="请输入模板描述"
                  />
                </el-form-item>
              </el-form>
              
              <!-- 检查分类列表 -->
              <div class="categories-list">
                <div 
                  v-for="(category, categoryIndex) in templateData.check_categories" 
                  :key="category.category_id"
                  class="category-item"
                >
                  <div class="category-header">
                    <div class="category-title">
                      <el-input 
                        v-model="category.category_name" 
                        placeholder="分类名称"
                        size="small"
                      />
                      <el-select
                        v-model="category.level_type"
                        placeholder="检查级别"
                        size="small"
                        style="margin-left: 12px; width: 120px;"
                        @change="onLevelTypeChange(category)"
                      >
                        <el-option label="站点级" value="site" />
                        <el-option label="扇区级" value="sector" />
                        <el-option label="小区级" value="cell" />
                      </el-select>
                      
                      <el-tag 
                        :type="category.cell_specific ? 'danger' : (category.sector_specific ? 'warning' : 'success')"
                        size="small"
                        style="margin-left: 8px;"
                      >
                        {{ category.cell_specific ? '小区级' : (category.sector_specific ? '扇区级' : '站点级') }}
                      </el-tag>
                    </div>
                    
                    <div class="category-actions">
                      <el-button 
                        size="small" 
                        @click="addItem(categoryIndex)"
                      >
                        <el-icon><Plus /></el-icon>
                        添加检查项
                      </el-button>
                      <el-button 
                        size="small" 
                        type="danger" 
                        @click="removeCategory(categoryIndex)"
                      >
                        <el-icon><Delete /></el-icon>
                        删除分类
                      </el-button>
                    </div>
                  </div>
                  
                  <div class="category-description">
                    <el-input 
                      v-model="category.description" 
                      placeholder="分类描述（可选）"
                      size="small"
                    />
                  </div>
                  
                  <!-- 检查项列表 -->
                  <div class="items-list">
                    <div 
                      v-for="(item, itemIndex) in category.items" 
                      :key="item.item_id"
                      class="item-row"
                    >
                      <div class="item-basic">
                        <el-input 
                          v-model="item.item_name" 
                          placeholder="检查项名称"
                          size="small"
                        />
                        
                        <el-select 
                          v-model="item.required_type" 
                          placeholder="要求类型"
                          size="small"
                          style="width: 120px; margin-left: 8px;"
                        >
                          <el-option label="仅拍照" value="photo" />
                          <el-option label="仅数据" value="data" />
                          <el-option label="拍照+数据" value="both" />
                        </el-select>
                        
                        <el-button 
                          size="small" 
                          type="danger" 
                          @click="removeItem(categoryIndex, itemIndex)"
                          style="margin-left: 8px;"
                        >
                          <el-icon><Delete /></el-icon>
                        </el-button>
                      </div>
                      
                      <div class="item-description">
                        <el-input 
                          v-model="item.description" 
                          placeholder="检查项描述（可选）"
                          size="small"
                        />
                      </div>

                      <!-- 字段配置（高级） -->
                      <el-card class="fields-card" shadow="never">
                        <template #header>
                          <div class="card-header">
                            <span>字段配置（可选）</span>
                            <el-button size="small" @click="addField(categoryIndex, itemIndex)"><el-icon><Plus /></el-icon> 添加字段</el-button>
                          </div>
                        </template>
                        <div v-if="!item.fields || item.fields.length === 0" class="empty-fields">暂无字段，点击“添加字段”新增</div>
                        <div v-for="(field, fieldIndex) in (item.fields || (item.fields = []))" :key="field.field_id || fieldIndex" class="field-row">
                          <div class="field-line">
                            <el-input v-model="field.field_id" size="small" placeholder="字段ID（英文）" style="width: 180px" />
                            <el-input v-model="field.label" size="small" placeholder="显示名称" style="width: 180px; margin-left:8px;" />
                            <el-select v-model="field.type" size="small" placeholder="类型" style="width: 160px; margin-left:8px;">
                              <el-option label="文本" value="text" />
                              <el-option label="数字" value="number" />
                              <el-option label="布尔" value="boolean" />
                              <el-option label="单选" value="select_single" />
                              <el-option label="多选" value="select_multi" />
                              <el-option label="日期" value="date" />
                              <el-option label="时间" value="time" />
                              <el-option label="日期时间" value="datetime" />
                              <el-option label="富文本" value="rich_text" />
                            </el-select>
                            <el-checkbox v-model="field.required" style="margin-left:12px;">必填</el-checkbox>
                            <el-button size="small" type="danger" @click="removeField(categoryIndex, itemIndex, fieldIndex)" style="margin-left:8px;"><el-icon><Delete /></el-icon></el-button>
                          </div>
                          <div class="field-advanced">
                            <!-- 选项配置 -->
                            <div v-if="['select_single','select_multi'].includes(field.type)" class="options-line">
                              <el-tag type="info" size="small">选项</el-tag>
                              <el-input v-model="field._newOptionLabel" size="small" placeholder="标签" style="width: 160px; margin-left:8px;" />
                              <el-input v-model="field._newOptionValue" size="small" placeholder="值" style="width: 160px; margin-left:8px;" />
                              <el-button size="small" @click="addOption(field)">添加</el-button>
                              <div class="option-list" v-if="field.options && field.options.length">
                                <el-tag 
                                  v-for="(opt, oi) in field.options" :key="oi" closable @close="removeOption(field, oi)" style="margin:4px;">
                                  {{ opt.label || opt }} ({{ opt.value || opt }})
                                </el-tag>
                              </div>
                            </div>
                            <!-- 约束配置 -->
                            <div class="constraints">
                              <el-tag type="info" size="small">约束</el-tag>
                              <template v-if="field.type==='number'">
                                <el-input-number v-model="(field.constraints || (field.constraints={})).min" :step="1" size="small" placeholder="最小值" style="margin-left:8px;" />
                                <el-input-number v-model="(field.constraints || (field.constraints={})).max" :step="1" size="small" placeholder="最大值" style="margin-left:8px;" />
                              </template>
                              <template v-else-if="field.type==='text' || field.type==='rich_text'">
                                <el-input-number v-model="(field.constraints || (field.constraints={})).min_length" :step="1" size="small" placeholder="最短" style="margin-left:8px;" />
                                <el-input-number v-model="(field.constraints || (field.constraints={})).max_length" :step="1" size="small" placeholder="最长" style="margin-left:8px;" />
                                <el-input v-model="(field.constraints || (field.constraints={})).pattern" size="small" placeholder="正则表达式" style="width: 220px; margin-left:8px;" />
                              </template>
                            </div>
                          </div>
                        </div>
                      </el-card>
                    </div>
                    
                    <div v-if="category.items.length === 0" class="no-items">
                      暂无检查项，点击"添加检查项"按钮添加
                    </div>
                  </div>
                </div>
                
                <div v-if="templateData.check_categories.length === 0" class="no-categories">
                  暂无检查分类，点击"添加分类"按钮添加
                </div>
              </div>
            </div>
          </el-card>
        </el-col>
        
        <!-- 右侧：属性面板和预览 -->
        <el-col :span="8">
          <el-card class="properties-card">
            <template #header>
              <span>模板统计</span>
            </template>
            
            <div class="template-stats">
              <div class="stat-item">
                <div class="stat-label">检查分类</div>
                <div class="stat-value">{{ templateData.check_categories.length }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">检查项总数</div>
                <div class="stat-value">{{ getTotalItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">站点级检查项</div>
                <div class="stat-value">{{ getSiteLevelItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">扇区级检查项</div>
                <div class="stat-value">{{ getSectorLevelItems() }}</div>
              </div>
              
              <div class="stat-item">
                <div class="stat-label">小区级检查项</div>
                <div class="stat-value">{{ getCellLevelItems() }}</div>
              </div>
            </div>
          </el-card>
          
          <el-card class="help-card" style="margin-top: 20px;">
            <template #header>
              <span>检查级别说明</span>
            </template>
            
            <div class="help-content">
              <div class="help-item">
                <el-tag type="success" size="small">站点级</el-tag>
                <span>整个站点检查一次（如：供电、环境）</span>
              </div>
              
              <div class="help-item">
                <el-tag type="warning" size="small">扇区级</el-tag>
                <span>每个扇区独立检查（如：天线安装）</span>
              </div>
              
              <div class="help-item">
                <el-tag type="danger" size="small">小区级</el-tag>
                <span>每个小区（扇区×频段）独立检查（如：功率测试）</span>
              </div>
            </div>
          </el-card>
          
          <el-card class="json-preview-card" style="margin-top: 20px;">
            <template #header>
              <div class="card-header">
                <span>JSON 预览</span>
                <el-button size="small" @click="copyJson">
                  <el-icon><DocumentCopy /></el-icon>
                  复制
                </el-button>
              </div>
            </template>
            
            <pre class="json-content">{{ JSON.stringify(templateData, null, 2) }}</pre>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { 
  ArrowLeft, Check, View, Plus, Delete, DocumentCopy 
} from '@element-plus/icons-vue'
import { templateAPI } from '../../api/templates'

const route = useRoute()
const router = useRouter()

// 响应式数据
const loading = ref(false)
const saving = ref(false)
const template = ref(null)

const templateForm = reactive({
  template_name: '',
  description: ''
})

const templateData = reactive({
  check_categories: []
})

// 计算属性
const isNewTemplate = computed(() => route.params.id === 'new')

// 方法
const loadTemplate = async () => {
  if (isNewTemplate.value) {
    // 新建模板，初始化空数据
    templateForm.template_name = '新检查模板'
    templateForm.description = ''
    templateData.check_categories = []
    return
  }
  
  loading.value = true
  try {
    const response = await templateAPI.getTemplate(route.params.id)
    template.value = response
    
    templateForm.template_name = response.template_name
    templateForm.description = response.template_data.description || ''
    
    // 深拷贝模板数据并处理 level_type
    templateData.check_categories = JSON.parse(
      JSON.stringify(response.template_data.check_categories || [])
    )
    
    // 为现有类别设置 level_type
    templateData.check_categories.forEach(category => {
      if (!category.level_type) {
        if (category.cell_specific) {
          category.level_type = 'cell'
        } else if (category.sector_specific) {
          category.level_type = 'sector'
        } else {
          category.level_type = 'site'
        }
      }
    })
  } catch (error) {
    console.error('加载模板失败:', error)
    ElMessage.error('加载模板失败')
    goBack()
  } finally {
    loading.value = false
  }
}

const saveTemplate = async () => {
  if (!templateForm.template_name.trim()) {
    ElMessage.error('请输入模板名称')
    return
  }
  
  if (templateData.check_categories.length === 0) {
    const confirmed = await ElMessageBox.confirm(
      '模板中没有检查分类，确认保存吗？',
      '确认保存',
      { type: 'warning' }
    ).catch(() => false)
    
    if (!confirmed) return
  }
  
  saving.value = true
  try {
    const templatePayload = {
      template_name: templateForm.template_name,
      template_data: {
        description: templateForm.description,
        check_categories: templateData.check_categories
      }
    }
    
    if (isNewTemplate.value) {
      const newTemplate = await templateAPI.createTemplate(templatePayload)
      ElMessage.success('模板创建成功')
      
      // 跳转到编辑页面
      router.replace({ name: 'TemplateEditor', params: { id: newTemplate.id } })
    } else {
      await templateAPI.updateTemplate(route.params.id, templatePayload)
      ElMessage.success('模板保存成功')
      
      // 重新加载模板数据
      loadTemplate()
    }
  } catch (error) {
    console.error('保存模板失败:', error)
    ElMessage.error('保存模板失败')
  } finally {
    saving.value = false
  }
}

const addCategory = () => {
  const newCategory = {
    category_id: `category_${Date.now()}`,
    category_name: '新检查分类',
    description: '',
    sector_specific: false,
    cell_specific: false,
    level_type: 'site', // 默认为站点级
    items: []
  }
  
  templateData.check_categories.push(newCategory)
}

// 处理检查级别变更
const onLevelTypeChange = (category) => {
  switch (category.level_type) {
    case 'site':
      category.sector_specific = false
      category.cell_specific = false
      break
    case 'sector':
      category.sector_specific = true
      category.cell_specific = false
      break
    case 'cell':
      category.sector_specific = false
      category.cell_specific = true
      break
  }
}

const removeCategory = async (categoryIndex) => {
  try {
    await ElMessageBox.confirm(
      '确认删除这个检查分类吗？',
      '删除确认',
      { type: 'warning' }
    )
    
    templateData.check_categories.splice(categoryIndex, 1)
    ElMessage.success('分类已删除')
  } catch (error) {
    // 用户取消
  }
}

const addItem = (categoryIndex) => {
  const newItem = {
    item_id: `item_${Date.now()}`,
    item_name: '新检查项',
    description: '',
    required_type: 'photo',
    assigned_role: 'inspector',
    status: 'pending'
  }
  
  templateData.check_categories[categoryIndex].items.push(newItem)
}

const removeItem = async (categoryIndex, itemIndex) => {
  try {
    await ElMessageBox.confirm(
      '确认删除这个检查项吗？',
      '删除确认',
      { type: 'warning' }
    )
    
    templateData.check_categories[categoryIndex].items.splice(itemIndex, 1)
    ElMessage.success('检查项已删除')
  } catch (error) {
    // 用户取消
  }
}

// 字段编辑方法
const addField = (categoryIndex, itemIndex) => {
  const item = templateData.check_categories[categoryIndex].items[itemIndex]
  if (!item.fields) item.fields = []
  item.fields.push({ field_id: `field_${Date.now()}`, label: '新字段', type: 'text', required: false, options: [], constraints: {} })
}

const removeField = (categoryIndex, itemIndex, fieldIndex) => {
  const item = templateData.check_categories[categoryIndex].items[itemIndex]
  if (!item.fields) return
  item.fields.splice(fieldIndex, 1)
}

const addOption = (field) => {
  if (!field._newOptionLabel && !field._newOptionValue) return
  if (!field.options) field.options = []
  field.options.push({ label: field._newOptionLabel || String(field._newOptionValue || ''), value: field._newOptionValue || field._newOptionLabel })
  field._newOptionLabel = ''
  field._newOptionValue = ''
}

const removeOption = (field, index) => {
  field.options.splice(index, 1)
}

const previewTemplate = () => {
  ElMessageBox.alert(
    JSON.stringify(templateData, null, 2),
    '模板预览',
    {
      customClass: 'json-preview-dialog'
    }
  )
}

const copyJson = async () => {
  try {
    await navigator.clipboard.writeText(JSON.stringify(templateData, null, 2))
    ElMessage.success('JSON 已复制到剪贴板')
  } catch (error) {
    ElMessage.error('复制失败')
  }
}

const goBack = () => {
  router.push({ name: 'InspectionTemplates' })
}

// 统计方法
const getTotalItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + category.items.length
  }, 0)
}

const getSiteLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (!category.sector_specific && !category.cell_specific ? category.items.length : 0)
  }, 0)
}

const getSectorLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (category.sector_specific ? category.items.length : 0)
  }, 0)
}

const getCellLevelItems = () => {
  return templateData.check_categories.reduce((total, category) => {
    return total + (category.cell_specific ? category.items.length : 0)
  }, 0)
}

// 生命周期
onMounted(() => {
  loadTemplate()
})
</script>

<style scoped>
.template-editor {
  padding: 20px;
  min-height: calc(100vh - 140px);
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e6e6e6;
}

.header-left {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.template-title h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  font-weight: 600;
}

.template-title p {
  margin: 0;
  color: #666;
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.editor-content {
  min-height: 600px;
}

.editor-card,
.properties-card,
.json-preview-card {
  border: 1px solid #e6e6e6;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.loading-container {
  padding: 20px;
}

.template-basic-form {
  margin-bottom: 24px;
  padding-bottom: 16px;
  border-bottom: 1px solid #f0f0f0;
}

.categories-list {
  space-y: 20px;
}

.category-item {
  background: #fafafa;
  border: 1px solid #e6e6e6;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}

.category-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.category-title {
  flex: 1;
  display: flex;
  align-items: center;
}

.category-description {
  margin-bottom: 16px;
}

.items-list {
  space-y: 8px;
}

.item-row {
  background: white;
  border: 1px solid #e6e6e6;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 8px;
}

.fields-card {
  margin-top: 8px;
}
.field-row { border-top: 1px dashed #eee; padding-top: 8px; margin-top: 8px; }
.field-line { display:flex; align-items:center; }
.field-advanced { padding-left: 0; margin-top: 8px; }
.constraints { margin-top: 6px; display:flex; align-items:center; gap:8px; }
.options-line { margin-top: 6px; display:flex; align-items:center; flex-wrap: wrap; }
.empty-fields { color:#999; padding: 8px 0; }

.item-basic {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.item-basic .el-input {
  flex: 1;
}

.no-categories,
.no-items {
  text-align: center;
  color: #999;
  padding: 40px 20px;
  background: #f9f9f9;
  border-radius: 6px;
  border: 1px dashed #ddd;
}

.template-stats {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: #f9f9f9;
  border-radius: 6px;
}

.stat-label {
  font-size: 14px;
  color: #666;
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: #409eff;
}

.json-content {
  font-size: 12px;
  line-height: 1.5;
  max-height: 300px;
  overflow-y: auto;
  background: #f9f9f9;
  padding: 12px;
  border-radius: 4px;
  margin: 0;
}

.help-content {
  background: #f0f9ff;
  border: 1px solid #bfdbfe;
  border-radius: 6px;
  padding: 16px;
  margin-bottom: 16px;
}

.help-item {
  margin-bottom: 12px;
  padding: 8px 12px;
  background: #ffffff;
  border-radius: 4px;
  border-left: 3px solid #3b82f6;
}

.help-item:last-child {
  margin-bottom: 0;
}

.help-item strong {
  color: #1e40af;
  font-weight: 600;
}
</style>

<style>
.json-preview-dialog .el-message-box__message {
  font-family: 'Courier New', monospace;
  white-space: pre-wrap;
  max-height: 400px;
  overflow-y: auto;
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
}
</style>
