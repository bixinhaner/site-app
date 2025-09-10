<template>
  <div class="page-container">
    <div class="page-header">
      <h2>设备套装配置</h2>
      <el-button type="primary" @click="showCreateDialog" v-if="userStore.canManageEquipment">
        <el-icon><Plus /></el-icon>
        新建套装
      </el-button>
    </div>

    <!-- 筛选条件 -->
    <div class="card">
      <el-row :gutter="20">
        <el-col :span="6">
          <el-input v-model="filters.search" placeholder="搜索套装名称..." clearable @change="loadPackageList">
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </el-col>
        <el-col :span="6">
          <el-input v-model="filters.site_type" placeholder="适用站点类型" clearable @change="loadPackageList" />
        </el-col>
      </el-row>
    </div>

    <!-- 套装列表 -->
    <div class="card">
      <el-table :data="packageList" style="width: 100%" v-loading="loading" expand-row-keys>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div style="padding: 20px;">
              <h4 style="margin-bottom: 16px;">套装明细:</h4>
              <el-table :data="row.items" size="small">
                <el-table-column prop="equipment_code" label="设备编码" width="120" />
                <el-table-column prop="equipment_name" label="设备名称" width="180" />
                <el-table-column prop="category" label="类别" width="100">
                  <template #default="{ row: item }">
                    <el-tag size="small" :type="item.category === 'main_device' ? 'primary' : 'success'">
                      {{ item.category === 'main_device' ? '主设备' : '辅材' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="quantity" label="数量" width="80" />
                <el-table-column prop="unit" label="单位" width="80" />
                <el-table-column prop="is_required" label="是否必需" width="100">
                  <template #default="{ row: item }">
                    <el-tag size="small" :type="item.is_required ? 'success' : 'info'">
                      {{ item.is_required ? '必需' : '可选' }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column prop="notes" label="备注" />
              </el-table>
            </div>
          </template>
        </el-table-column>
        
        <el-table-column prop="package_code" label="套装编码" width="120" />
        <el-table-column prop="package_name" label="套装名称" width="180" />
        <el-table-column prop="main_equipment_name" label="主设备" width="150" />
        <el-table-column prop="site_type" label="适用类型" width="120" />
        <el-table-column label="明细数量" width="100">
          <template #default="{ row }">
            {{ row.items?.length || 0 }} 种
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" v-if="userStore.canManageEquipment">
          <template #default="{ row }">
            <el-button size="small" @click="editPackage(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="deletePackage(row.id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 套装配置对话框 -->
    <el-dialog 
      v-model="showPackageDialog" 
      :title="editingPackageId ? '编辑套装' : '新建套装'" 
      width="800px"
    >
      <el-form :model="packageForm" label-width="120px">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="套装编码" required>
              <el-input v-model="packageForm.package_code" placeholder="如: PKG-5G-BASIC" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="套装名称" required>
              <el-input v-model="packageForm.package_name" placeholder="如: 5G基站标准配置" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="主设备" required>
              <el-select v-model="packageForm.main_equipment_id" placeholder="选择主设备">
                <el-option 
                  v-for="eq in mainDeviceOptions" 
                  :key="eq.id" 
                  :label="eq.equipment_name" 
                  :value="eq.id" 
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="适用站点类型">
              <el-input v-model="packageForm.site_type" placeholder="如: 5G基站" />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="套装描述">
          <el-input v-model="packageForm.description" type="textarea" :rows="2" />
        </el-form-item>
        
        <el-form-item label="套装明细">
          <div style="width: 100%;">
            <div style="margin-bottom: 16px;">
              <el-button size="small" @click="addPackageItem">
                <el-icon><Plus /></el-icon>
                添加设备
              </el-button>
            </div>
            
            <el-table :data="packageForm.items" size="small" border>
              <el-table-column label="设备" width="200">
                <template #default="{ row, $index }">
                  <el-select v-model="row.equipment_id" placeholder="选择设备">
                    <el-option 
                      v-for="eq in equipmentOptions" 
                      :key="eq.id" 
                      :label="eq.equipment_name" 
                      :value="eq.id"
                    />
                  </el-select>
                </template>
              </el-table-column>
              <el-table-column label="数量" width="100">
                <template #default="{ row }">
                  <el-input-number v-model="row.quantity" :min="1" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="必需" width="80">
                <template #default="{ row }">
                  <el-switch v-model="row.is_required" />
                </template>
              </el-table-column>
              <el-table-column label="备注">
                <template #default="{ row }">
                  <el-input v-model="row.notes" size="small" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="80">
                <template #default="{ row, $index }">
                  <el-button size="small" type="danger" @click="removePackageItem($index)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-form-item>
      </el-form>
      
      <template #footer>
        <el-button @click="showPackageDialog = false">取消</el-button>
        <el-button type="primary" @click="savePackage" :loading="savingPackage">保存套装</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search } from '@element-plus/icons-vue'
import { equipmentApi } from '../../api/equipment'
import { useUserStore } from '../../stores/user'

const userStore = useUserStore()

const loading = ref(false)
const savingPackage = ref(false)
const showPackageDialog = ref(false)
const editingPackageId = ref(null)
const packageList = ref([])
const equipmentOptions = ref([])
const filters = ref({
  search: '',
  site_type: ''
})

const packageForm = ref({
  package_code: '',
  package_name: '',
  main_equipment_id: null,
  site_type: '',
  description: '',
  items: []
})

const mainDeviceOptions = computed(() => 
  equipmentOptions.value.filter(eq => eq.category === 'main_device')
)

const formatDateTime = (dateString) => {
  if (!dateString) return '-'
  return new Date(dateString).toLocaleString('zh-CN')
}

const loadPackageList = async () => {
  try {
    loading.value = true
    const response = await equipmentApi.getPackageList(filters.value)
    packageList.value = response
  } catch (error) {
    console.error('加载套装列表失败:', error)
    ElMessage.error('加载套装列表失败')
  } finally {
    loading.value = false
  }
}

const loadEquipmentOptions = async () => {
  try {
    const response = await equipmentApi.getEquipmentList({ status: 'active' })
    equipmentOptions.value = response
  } catch (error) {
    console.error('加载设备选项失败:', error)
  }
}

const showCreateDialog = () => {
  editingPackageId.value = null
  packageForm.value = {
    package_code: '',
    package_name: '',
    main_equipment_id: null,
    site_type: '',
    description: '',
    items: []
  }
  showPackageDialog.value = true
}

const editPackage = async (pkg) => {
  editingPackageId.value = pkg.id
  try {
    const response = await equipmentApi.getPackageDetail(pkg.id)
    packageForm.value = {
      package_code: response.package_code,
      package_name: response.package_name,
      main_equipment_id: response.main_equipment?.id,
      site_type: response.site_type,
      description: response.description,
      items: response.items || []
    }
    showPackageDialog.value = true
  } catch (error) {
    ElMessage.error('加载套装详情失败')
  }
}

const addPackageItem = () => {
  packageForm.value.items.push({
    equipment_id: null,
    quantity: 1,
    is_required: true,
    notes: ''
  })
}

const removePackageItem = (index) => {
  packageForm.value.items.splice(index, 1)
}

const savePackage = async () => {
  if (!packageForm.value.package_code || !packageForm.value.package_name || !packageForm.value.main_equipment_id) {
    ElMessage.warning('请填写必填项')
    return
  }
  
  if (packageForm.value.items.length === 0) {
    ElMessage.warning('请至少添加一个设备明细')
    return
  }
  
  try {
    savingPackage.value = true
    
    if (editingPackageId.value) {
      await equipmentApi.updatePackage(editingPackageId.value, packageForm.value)
      ElMessage.success('套装更新成功')
    } else {
      await equipmentApi.createPackage(packageForm.value)
      ElMessage.success('套装创建成功')
    }
    
    showPackageDialog.value = false
    loadPackageList()
  } catch (error) {
    console.error('保存套装失败:', error)
    ElMessage.error('保存失败: ' + (error.response?.data?.detail || '网络错误'))
  } finally {
    savingPackage.value = false
  }
}

onMounted(() => {
  loadPackageList()
  loadEquipmentOptions()
})
</script>

<style lang="scss" scoped>
.el-select {
  width: 100%;
}

h4 {
  color: var(--text-primary);
  margin-bottom: 16px;
}
</style>