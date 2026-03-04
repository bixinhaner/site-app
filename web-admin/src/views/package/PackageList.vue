<template>
  <div class="package-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <h1>套装配置管理</h1>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新增套装
        </el-button>
        <el-button @click="loadPackageList" :loading="loading">
          <el-icon><Refresh /></el-icon>
          刷新
        </el-button>
      </div>
    </div>

    <!-- 搜索筛选 -->
    <el-card class="search-card">
      <div class="search-row">
        <div class="search-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索套装编码或名称"
            style="width: 300px"
            clearable
            @keyup.enter="handleSearch"
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
          
          <el-select
            v-model="filterSiteType"
            placeholder="适用类型"
            style="width: 150px"
            clearable
            @change="handleSearch"
          >
            <el-option label="宏站" value="macro" />
            <el-option label="微站" value="micro" />
            <el-option label="室分" value="indoor" />
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

    <!-- 套装列表 -->
    <el-card class="table-card">
      <template #header>
        <div class="table-header">
          <span>套装列表</span>
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
        :data="packageList"
        v-loading="loading"
        @selection-change="handleSelectionChange"
        stripe
        style="width: 100%"
      >
        <el-table-column type="selection" width="50" />
        
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="package-details">
              <h4>套装明细</h4>
              <el-table :data="row.items" size="small" style="margin: 16px 0;">
                <el-table-column prop="equipment_code" label="设备编码" width="120" />
                <el-table-column prop="equipment_name" label="设备名称" min-width="180" />
                <el-table-column prop="quantity" label="数量" width="80" />
                <el-table-column prop="unit" label="单位" width="80" />
              </el-table>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="package_code" label="套装编码" width="140" />
        
        <el-table-column prop="package_name" label="套装名称" min-width="200" />
        
        <el-table-column prop="main_equipment_name" label="主设备" width="160" />
        
        <el-table-column prop="site_type" label="适用类型" width="100">
          <template #default="{ row }">
            <el-tag :type="getSiteTypeColor(row.site_type)" size="small">
              {{ getSiteTypeText(row.site_type) }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column prop="total_items" label="设备数量" width="100">
          <template #default="{ row }">
            {{ row.items?.length || 0 }} 种
          </template>
        </el-table-column>
        
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
              {{ row.status === 'active' ? '活跃' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <div class="en-op-actions">
              <el-button type="primary" size="small" @click="handleEdit(row)" link>
                <el-icon><Edit /></el-icon>
                编辑
              </el-button>
              
              <el-button type="info" size="small" @click="handleCopy(row)" link>
                <el-icon><CopyDocument /></el-icon>
                复制
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
              
              <el-button type="danger" size="small" @click="handleDelete(row)" link>
                <el-icon><Delete /></el-icon>
                删除
              </el-button>
            </div>
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
          @size-change="loadPackageList"
          @current-change="loadPackageList"
        />
      </div>
    </el-card>

    <!-- 套装表单弹窗 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="editingPackage ? '编辑套装' : '新增套装'"
      width="800px"
      @close="resetForm"
    >
      <el-form
        ref="packageFormRef"
        :model="packageForm"
        :rules="packageRules"
        label-width="120px"
        size="default"
      >
        <!-- 基本信息 -->
        <div class="form-section">
          <h4>基本信息</h4>
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="套装编码" prop="package_code">
                <el-input 
                  v-model="packageForm.package_code" 
                  placeholder="请输入套装编码"
                  :disabled="!!editingPackage"
                />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="套装名称" prop="package_name">
                <el-input v-model="packageForm.package_name" placeholder="请输入套装名称" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="主设备" prop="main_equipment_id">
                <el-select 
                  v-model="packageForm.main_equipment_id" 
                  style="width: 100%"
                  placeholder="选择主设备"
                  filterable
                >
                  <el-option
                    v-for="eq in mainEquipmentList"
                    :key="eq.id"
                    :label="`${eq.equipment_name} (${eq.equipment_code})`"
                    :value="eq.id"
                  />
                </el-select>
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="适用类型" prop="site_type">
                <el-select v-model="packageForm.site_type" style="width: 100%">
                  <el-option label="宏站" value="macro" />
                  <el-option label="微站" value="micro" />
                  <el-option label="室分" value="indoor" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="套装描述">
            <el-input
              v-model="packageForm.description"
              type="textarea"
              :rows="2"
              placeholder="套装描述信息"
            />
          </el-form-item>
        </div>

        <!-- 设备明细 -->
        <div class="form-section">
          <div class="section-header">
            <h4>设备明细</h4>
            <el-button type="primary" size="small" @click="addEquipmentItem">
              <el-icon><Plus /></el-icon>
              添加辅材明细
            </el-button>
          </div>

          <el-table :data="packageForm.items" style="width: 100%" size="small">
            <el-table-column label="设备" min-width="200">
              <template #default="{ row, $index }">
                <el-input
                  v-if="isMainEquipmentItem(row)"
                  :model-value="getEquipmentDisplayText(row.equipment_id) || '-'"
                  disabled
                />
                <el-select
                  v-else
                  v-model="row.equipment_id"
                  placeholder="选择辅材"
                  style="width: 100%"
                  filterable
                  @change="updateEquipmentInfo(row, $index)"
                >
                  <el-option
                    v-for="eq in auxiliaryEquipmentOptions"
                    :key="eq.id"
                    :label="`${eq.equipment_name} (${eq.equipment_code})`"
                    :value="eq.id"
                    :disabled="isEquipmentOptionDisabled(eq.id, $index)"
                  />
                </el-select>
              </template>
            </el-table-column>
            
            <el-table-column label="数量" width="120">
              <template #default="{ row }">
                <el-input-number
                  v-model="row.quantity"
                  :min="1"
                  :max="999"
                  style="width: 100%"
                  size="small"
                />
              </template>
            </el-table-column>
            
            <el-table-column prop="unit" label="单位" width="80" />
            
            <el-table-column label="操作" width="80">
              <template #default="{ row, $index }">
                <el-button
                  type="danger"
                  size="small"
                  @click="removeEquipmentItem($index)"
                  link
                  :disabled="isMainEquipmentItem(row)"
                >
                  <el-icon><Delete /></el-icon>
                </el-button>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="!packageForm.items.length" class="empty-items">
            <p>暂无设备明细，请点击"添加辅材明细"按钮添加</p>
          </div>
        </div>
      </el-form>

      <template #footer>
        <div class="dialog-footer">
          <el-button @click="showCreateDialog = false">取消</el-button>
          <el-button type="primary" @click="handleSubmit" :loading="submitting">
            {{ editingPackage ? '更新' : '创建' }}
          </el-button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { equipmentApi } from '../../api/equipment'
import { trackOperation } from '@/utils/operationTrack'

// 响应式数据
const loading = ref(false)
const submitting = ref(false)
const showCreateDialog = ref(false)
const editingPackage = ref(null)
const selectedRows = ref([])

// 列表数据
const packageList = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)

// 搜索条件
const searchKeyword = ref('')
const filterSiteType = ref('')
const filterStatus = ref('')

// 设备选项
const mainEquipmentList = ref([])
const availableEquipment = ref([])
const auxiliaryEquipmentOptions = computed(() =>
  (availableEquipment.value || []).filter((eq) => eq.category === 'auxiliary'),
)

// 表单数据
const packageFormRef = ref()
const packageForm = reactive({
  package_code: '',
  package_name: '',
  main_equipment_id: null,
  site_type: 'macro',
  description: '',
  items: []
})

// 表单验证规则
const packageRules = {
  package_code: [
    { required: true, message: '请输入套装编码', trigger: 'blur' },
    { min: 2, max: 50, message: '编码长度在2到50个字符', trigger: 'blur' }
  ],
  package_name: [
    { required: true, message: '请输入套装名称', trigger: 'blur' },
    { min: 2, max: 100, message: '名称长度在2到100个字符', trigger: 'blur' }
  ],
  main_equipment_id: [
    { required: true, message: '请选择主设备', trigger: 'change' }
  ],
  site_type: [
    { required: true, message: '请选择适用类型', trigger: 'change' }
  ]
}

// 站点类型文本映射
const getSiteTypeText = (type) => {
  const typeMap = {
    'macro': '宏站',
    'micro': '微站', 
    'indoor': '室分'
  }
  return typeMap[type] || type
}

const getSiteTypeColor = (type) => {
  const colorMap = {
    'macro': 'primary',
    'micro': 'success',
    'indoor': 'warning'
  }
  return colorMap[type] || 'info'
}

const getEquipmentById = (equipmentId) => {
  if (!equipmentId) return null
  return (availableEquipment.value || []).find((eq) => eq.id === equipmentId) || null
}

const getEquipmentDisplayText = (equipmentId) => {
  const eq = getEquipmentById(equipmentId)
  if (!eq) return ''
  return `${eq.equipment_name} (${eq.equipment_code})`
}

const isMainEquipmentItem = (item) => {
  if (!item) return false
  return item.equipment_id === packageForm.main_equipment_id
}

const normalizePositiveInteger = (value, fallback = 1) => {
  const parsed = Number(value)
  if (!Number.isFinite(parsed) || parsed <= 0) return fallback
  return Math.floor(parsed)
}

const syncMainEquipmentItem = (newMainId = null, oldMainId = null) => {
  const mainId = newMainId ?? packageForm.main_equipment_id
  if (!mainId) return

  let mainIndex = packageForm.items.findIndex((it) => it.equipment_id === mainId)
  if (mainIndex === -1 && oldMainId) {
    const oldIndex = packageForm.items.findIndex((it) => it.equipment_id === oldMainId)
    if (oldIndex !== -1) {
      packageForm.items[oldIndex].equipment_id = mainId
      mainIndex = oldIndex
    }
  }

  if (mainIndex === -1) {
    packageForm.items.unshift({
      equipment_id: mainId,
      quantity: 1,
      unit: getEquipmentById(mainId)?.unit || '台',
    })
    mainIndex = 0
  }

  const mainItem = packageForm.items[mainIndex]
  mainItem.quantity = normalizePositiveInteger(mainItem.quantity, 1)
  mainItem.unit = getEquipmentById(mainId)?.unit || mainItem.unit || '台'

  if (mainIndex !== 0) {
    packageForm.items.splice(mainIndex, 1)
    packageForm.items.unshift(mainItem)
  }
}

const isEquipmentOptionDisabled = (equipmentId, rowIndex) => {
  if (!equipmentId) return false
  return packageForm.items.some((it, idx) => idx !== rowIndex && it.equipment_id === equipmentId)
}

// 加载套装列表
const loadPackageList = async () => {
  try {
    loading.value = true
    const params = {
      skip: (currentPage.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    
    if (searchKeyword.value) {
      params.search = searchKeyword.value
    }
    if (filterSiteType.value) {
      params.site_type = filterSiteType.value
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }
    
    const response = await equipmentApi.getPackageList(params)
    packageList.value = response
    total.value = response.length
    
  } catch (error) {
    console.error('加载套装列表失败:', error)
    ElMessage.error('加载套装列表失败: ' + error.message)
  } finally {
    loading.value = false
  }
}

// 加载设备选项
const loadEquipmentOptions = async () => {
  try {
    const response = await equipmentApi.getEquipmentList()
    availableEquipment.value = response
    mainEquipmentList.value = response.filter(eq => eq.category === 'main_device')
  } catch (error) {
    console.error('加载设备选项失败:', error)
  }
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
  trackOperation({
    module: '库存管理',
    action: '查询',
    object_type: '套装',
    data: {
      keyword: searchKeyword.value || undefined,
      site_type: filterSiteType.value || undefined,
      status: filterStatus.value || undefined,
    },
  })
  loadPackageList()
}

// 重置搜索
const resetSearch = () => {
  searchKeyword.value = ''
  filterSiteType.value = ''
  filterStatus.value = ''
  currentPage.value = 1
  trackOperation({
    module: '库存管理',
    action: '重置筛选',
    object_type: '套装',
  })
  loadPackageList()
}

// 多选处理
const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

// 新增套装
const handleCreate = () => {
  editingPackage.value = null
  resetForm()
  showCreateDialog.value = true
}

// 编辑套装
const handleEdit = (packageData) => {
  editingPackage.value = packageData
  Object.assign(packageForm, {
    ...packageData,
    items: packageData.items?.map(item => ({
      equipment_id: item.equipment_id,
      quantity: item.quantity,
      unit: item.unit
    })) || []
  })
  nextTick(() => syncMainEquipmentItem())
  showCreateDialog.value = true
}

// 复制套装
const handleCopy = (packageData) => {
  editingPackage.value = null
  Object.assign(packageForm, {
    ...packageData,
    package_code: packageData.package_code + '_copy',
    package_name: packageData.package_name + ' (副本)',
    items: packageData.items?.map(item => ({
      equipment_id: item.equipment_id,
      quantity: item.quantity,
      unit: item.unit
    })) || []
  })
  nextTick(() => syncMainEquipmentItem())
  showCreateDialog.value = true
}

// 提交表单
const handleSubmit = async () => {
  try {
    syncMainEquipmentItem()
    const isValid = await packageFormRef.value.validate()
    if (!isValid) return
    
    if (!packageForm.items.length) {
      ElMessage.warning('请至少添加一个设备明细')
      return
    }

    const mainId = packageForm.main_equipment_id
    const seen = new Set()
    for (const item of packageForm.items) {
      if (!item.equipment_id) {
        ElMessage.error('请完善辅材明细：设备不能为空')
        return
      }
      item.quantity = normalizePositiveInteger(item.quantity, 1)
      if (seen.has(item.equipment_id)) {
        ElMessage.error(`设备明细不允许重复：${getEquipmentDisplayText(item.equipment_id) || item.equipment_id}`)
        return
      }
      seen.add(item.equipment_id)

      if (item.equipment_id === mainId) {
        if (item.quantity <= 0) {
          ElMessage.error('主设备数量必须大于 0')
          return
        }
      } else {
        const eq = getEquipmentById(item.equipment_id)
        if (eq && eq.category !== 'auxiliary') {
          ElMessage.error('设备明细仅允许添加辅材')
          return
        }
      }
    }
    
    submitting.value = true
    
    if (editingPackage.value) {
      // 更新套装
      await equipmentApi.updatePackage(editingPackage.value.id, packageForm)
      ElMessage.success('套装更新成功')
    } else {
      // 创建套装
      await equipmentApi.createPackage(packageForm)
      ElMessage.success('套装创建成功')
    }
    
    showCreateDialog.value = false
    loadPackageList()
  } catch (error) {
    console.error('保存套装失败:', error)
    ElMessage.error('操作失败: ' + error.message)
  } finally {
    submitting.value = false
  }
}

// 删除套装
const handleDelete = async (packageData) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除套装 "${packageData.package_name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await equipmentApi.deletePackage(packageData.id)
    ElMessage.success('套装删除成功')
    loadPackageList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除套装失败:', error)
      ElMessage.error('删除失败: ' + error.message)
    }
  }
}

// 批量删除
const handleBatchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 个套装吗？`,
      '确认批量删除',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const deletePromises = selectedRows.value.map(item => 
      equipmentApi.deletePackage(item.id)
    )
    
    await Promise.all(deletePromises)
    ElMessage.success('批量删除成功')
    loadPackageList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除失败:', error)
      ElMessage.error('批量删除失败: ' + error.message)
    }
  }
}

// 切换状态
const toggleStatus = async (packageData) => {
  try {
    const newStatus = packageData.status === 'active' ? 'inactive' : 'active'
    const action = newStatus === 'active' ? '启用' : '停用'
    
    await ElMessageBox.confirm(
      `确定要${action}套装 "${packageData.package_name}" 吗？`,
      `确认${action}`,
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    await equipmentApi.updatePackage(packageData.id, { status: newStatus })
    ElMessage.success(`套装${action}成功`)
    loadPackageList()
  } catch (error) {
    if (error !== 'cancel') {
      console.error('状态切换失败:', error)
      ElMessage.error('操作失败: ' + error.message)
    }
  }
}

// 添加设备明细
const addEquipmentItem = () => {
  packageForm.items.push({
    equipment_id: null,
    quantity: 1,
    unit: '台'
  })
}

// 移除设备明细
const removeEquipmentItem = (index) => {
  const item = packageForm.items[index]
  if (isMainEquipmentItem(item)) {
    ElMessage.error('主设备明细不允许删除')
    return
  }
  packageForm.items.splice(index, 1)
}

// 更新设备信息
const updateEquipmentInfo = (item, index) => {
  const equipment = availableEquipment.value.find(eq => eq.id === item.equipment_id)
  if (equipment) {
    item.unit = equipment.unit
    item.equipment_name = equipment.equipment_name
    item.equipment_code = equipment.equipment_code
  }
}

// 重置表单
const resetForm = () => {
  editingPackage.value = null
  Object.assign(packageForm, {
    package_code: '',
    package_name: '',
    main_equipment_id: null,
    site_type: 'macro',
    description: '',
    items: []
  })

  if (packageFormRef.value) {
    packageFormRef.value.clearValidate()
  }
}

watch(
  () => packageForm.main_equipment_id,
  (newId, oldId) => {
    if (!newId) return
    syncMainEquipmentItem(newId, oldId)
  }
)

onMounted(async () => {
  await loadEquipmentOptions()
  loadPackageList()
})
</script>

<style scoped lang="scss">
.package-page {
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

.package-details {
  padding: 16px 48px;
  background: #f8fafc;
  
  h4 {
    color: var(--text-primary);
    margin: 0 0 16px 0;
    font-size: 16px;
  }
}

.form-section {
  margin-bottom: 24px;
  
  h4 {
    color: var(--text-primary);
    font-size: 16px;
    font-weight: 600;
    margin: 0 0 16px 0;
    padding-bottom: 8px;
    border-bottom: 1px solid var(--border-color);
  }
  
  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 16px;
    
    h4 {
      margin: 0;
      border: none;
      padding: 0;
    }
  }
}

.empty-items {
  text-align: center;
  padding: 40px;
  color: var(--text-light);
  background: #fafbfc;
  border-radius: 8px;
  border: 2px dashed #e2e8f0;
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
  .package-page {
    padding: 16px;
  }
  
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }
  
  .form-section {
    .section-header {
      flex-direction: column;
      align-items: flex-start;
      gap: 12px;
    }
  }
}
</style>
