<template>
  <div class="equipment-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>设备类型管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="showCreateDialog = true">
          <el-icon><Plus /></el-icon>
          新增设备类型
        </el-button>
        <el-button @click="loadEquipmentList" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 搜索和筛选 -->
    <el-card class="search-card">
      <div class="search-row">
        <div class="search-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索设备编码或名称"
            style="width: 300px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <el-select
            v-model="filterCategory"
            placeholder="设备类别"
            style="width: 150px"
            clearable
            @change="handleSearch"
          >
            <el-option label="主设备" value="main_device" />
            <el-option label="辅材" value="auxiliary" />
          </el-select>
          
          <el-select
            v-model="filterStatus"
            placeholder="状态"
            style="width: 120px"
            clearable
            @change="handleSearch"
          >
            <el-option label="活跃" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </div>
        
        <div class="search-right">
          <el-button type="primary" @click="handleSearch">
            <el-icon><Search /></el-icon>
            搜索
          </el-button>
          <el-button @click="resetSearch">重置</el-button>
        </div>
      </div>
    </el-card>

    <!-- 设备列表 -->
    <el-card class="table-card">
      <template #header>
        <div class="table-header">
          <span>设备列表</span>
          <div class="table-actions">
            <el-button 
              type="danger" 
              size="small"
              :disabled="!selectedRows.length"
              @click="handleBatchDelete"
            >
              <el-icon><Delete /></el-icon>
              批量删除 ({{ selectedRows.length }})
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        :data="equipmentList"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        
        <el-table-column prop="equipment_code" label="设备编码" width="140" />
        
        <el-table-column prop="equipment_name" label="设备名称" min-width="180" />
        
        <el-table-column prop="category" label="类别" width="100">
          <template #default="{ row }">
            <el-tag :type="row.category === 'main_device' ? 'primary' : 'success'" size="small">
              {{ row.category === 'main_device' ? '主设备' : '辅材' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="brand" label="品牌" width="120" />
        
        <el-table-column prop="model" label="型号" width="140" />
        
        <el-table-column prop="unit" label="单位" width="80" />
        
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag 
              :type="row.status === 'active' ? 'success' : 'info'" 
              size="small"
            >
              {{ row.status === 'active' ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click="handleEdit(row)"
              link
            >
              <el-icon><Edit /></el-icon>
              编辑
            </el-button>
            
            <el-button
              :type="row.status === 'active' ? 'warning' : 'success'"
              size="small"
              @click="toggleStatus(row)"
              link
            >
              <el-icon v-if="row.status === 'active'"><CircleClose /></el-icon>
              <el-icon v-else><CircleCheck /></el-icon>
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            
            <el-button
              type="danger"
              size="small"
              @click="handleDelete(row)"
              link
            >
              <el-icon><Delete /></el-icon>
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadEquipmentList"
          @current-change="loadEquipmentList"
        />
      </div>
    </el-card>

    <!-- 设备表单弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingEquipment ? '编辑设备' : '新增设备'"
      width="600px"
      @close="resetForm"
    >
      <el-form
        ref="equipmentFormRef"
        :model="equipmentForm"
        :rules="equipmentRules"
        label-width="120px"
        size="default"
      >
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备编码" prop="equipment_code">
              <el-input 
                v-model="equipmentForm.equipment_code" 
                placeholder="请输入设备编码"
                :disabled="!!editingEquipment"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="设备名称" prop="equipment_name">
              <el-input v-model="equipmentForm.equipment_name" placeholder="请输入设备名称" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="设备类别" prop="category">
              <el-select v-model="equipmentForm.category" style="width: 100%">
                <el-option label="主设备" value="main_device" />
                <el-option label="辅材" value="auxiliary" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="品牌" prop="brand">
              <el-input v-model="equipmentForm.brand" placeholder="请输入品牌" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="型号" prop="model">
              <el-input v-model="equipmentForm.model" placeholder="请输入型号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit">
              <el-select v-model="equipmentForm.unit" style="width: 100%">
                <el-option label="台" value="台" />
                <el-option label="套" value="套" />
                <el-option label="个" value="个" />
                <el-option label="副" value="副" />
                <el-option label="米" value="米" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="条码前缀">
              <el-input v-model="equipmentForm.barcode_prefix" placeholder="如: BST" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="规格描述">
          <el-input
            v-model="equipmentForm.specifications"
            type="textarea"
            :rows="3"
            placeholder="请输入设备规格描述"
          />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="equipmentForm.description"
            type="textarea"
            :rows="2"
            placeholder="设备描述信息"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            {{ editingEquipment ? '更新' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { equipmentApi } from '../../api/equipment'

// 响应式数据
const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const editingEquipment = ref(null)
const selectedRows = ref([])

// 列表数据
const equipmentList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 搜索条件
const searchKeyword = ref('')
const filterCategory = ref('')
const filterStatus = ref('')

// 表单数据
const equipmentFormRef = ref()
const equipmentForm = reactive({
  equipment_code: '',
  equipment_name: '',
  category: 'main_device',
  brand: '',
  model: '',
  unit: '台',
  barcode_prefix: '',
  specifications: '',
  description: ''
})

// 表单验证规则
const equipmentRules = {
  equipment_code: [
    { required: true, message: '请输入设备编码', trigger: 'blur' },
    { min: 2, max: 50, message: '编码长度在2到50个字符', trigger: 'blur' }
  ],
  equipment_name: [
    { required: true, message: '请输入设备名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度在2到100个字符', trigger: 'blur' }
  ],
  category: [
    { required: true, message: '请选择设备类别', trigger: 'change' }
  ],
  brand: [
    { required: true, message: '请输入品牌', trigger: 'blur' }
  ],
  unit: [
    { required: true, message: '请选择单位', trigger: 'change' }
  ],
}

// 加载设备列表
const loadEquipmentList = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    if (filterCategory.value) {
      params.category = filterCategory.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    const response = await equipmentApi.getEquipmentList(params)
    equipmentList.value = response
    total.value = response.length // 后端暂时没有返回总数
    
  } catch (error) {
    console.error('加载设备列表失败:', error)
    ElMessage.error('加载设备列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
  loadEquipmentList()
}

// 重置搜索
const resetSearch = () => {
  searchKeyword.value = ''
  filterCategory.value = ''
  filterStatus.value = ''
  currentPage.value = 1
  loadEquipmentList()
}

// 多选处理
const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

// 编辑设备
const handleEdit = (equipment) => {
  editingEquipment.value = equipment
  // 只复制可编辑的字段，避免发送系统字段导致500错误
  Object.assign(equipmentForm, {
    equipment_code: equipment.equipment_code,
    equipment_name: equipment.equipment_name,
    category: equipment.category,
    brand: equipment.brand || '',
    model: equipment.model || '',
    unit: equipment.unit || '台',
    barcode_prefix: equipment.barcode_prefix || '',
    specifications: equipment.specifications || '',
    description: equipment.description || ''
  })
  showCreateDialog.value = true
}

// 提交表单
const handleSubmit = async () => {
  try {
    const isValid = await equipmentFormRef.value.validate()
    if (!isValid) return
    
    submitting.value = true
    
    if (editingEquipment.value) {
      // 更新设备
      await equipmentApi.updateEquipment(editingEquipment.value.id, equipmentForm)
      ElMessage.success('设备更新成功')
    } else {
      // 创建设备
      await equipmentApi.createEquipment(equipmentForm)
      ElMessage.success('设备创建成功')
    }
    
    showCreateDialog.value = false
    loadEquipmentList()
  } catch (error) {
    console.error('保存设备失败:', error)
    ElMessage.error('操作失败: ' + error.message)
  } finally {
    submitting.value = false
  }
}

// 删除设备
const handleDelete = async (equipment) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除设备 "${equipment.equipment_name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await equipmentApi.deleteEquipment(equipment.id)
    ElMessage.success('设备删除成功')
    loadEquipmentList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除设备失败:', error)
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

// 批量删除
const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个设备吗？`,
      '确认批量删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const deletePromises = selectedRows.value.map(item => 
      equipmentApi.deleteEquipment(item.id)
    )
    
    await Promise.all(deletePromises)
    ElMessage.success('批量删除成功')
    loadEquipmentList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败: ' + error.message)
    }
  }
}

// 切换状态
const toggleStatus = async (equipment) => {
  try {
    const newStatus = equipment.status === 'active' ? 'inactive' : 'active'
    const action = newStatus === 'active' ? '启用' : '停用'
    
    await ElMessageBox.confirm(
      `确定要${action}设备 "${equipment.equipment_name}" 吗？`,
      `确认${action}`,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await equipmentApi.updateEquipment(equipment.id, { status: newStatus })
    ElMessage.success(`设备${action}成功`)
    loadEquipmentList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('状态切换失败:', error)
      ElMessage.error('操作失败: ' + error.message)
    }
  }
}

// 重置表单
const resetForm = () => {
  Object.assign(equipmentForm, {
    equipment_code: '',
    equipment_name: '',
    category: 'main_device',
    brand: '',
    model: '',
    unit: '台',
    barcode_prefix: '',
    specifications: '',
    description: ''
  })
  
  if (equipmentFormRef.value) {
    equipmentFormRef.value.clearValidate()
  }
}

onMounted(() => {
  loadEquipmentList()
})
</script>

<style scoped lang="scss">
.equipment-page {
  padding: 24px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  
  h1 {
    color: var(--text-primary);
    font-size: 28px;
    font-weight: 600;
    margin: 0;
  }
  
  .header-actions {
    display: flex;
    gap: 12px;
  }
}

.search-card {
  margin-bottom: 24px;
  border-radius: 8px;
  
  .search-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 16px;
    
    .search-left {
      display: flex;
      gap: 12px;
      flex: 1;
    }
    
    .search-right {
      display: flex;
      gap: 8px;
    }
  }
}

.table-card {
  border-radius: 8px;
  
  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.pagination-container {
  margin-top: 24px;
  display: flex;
  justify-content: flex-end;
}


.dialog-footer {
  text-align: right;
}

// 响应式设计
@media (max-width: 1200px) {
  .search-row {
    flex-direction: column;
    align-items: stretch;
    gap: 16px;
    
    .search-left {
      flex-direction: column;
    }
  }
}

@media (max-width: 768px) {
  .equipment-page {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .el-table {
    :deep(.el-table__body-wrapper) {
      overflow-x: auto;
    }
  }
}
</style>