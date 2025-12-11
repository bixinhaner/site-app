<template>
  <div class="page">
    <div class="page-header">
      <h1>仓库管理</h1>
      <div class="header-actions">
        <el-button @click="load"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增仓库</el-button>
      </div>
    </div>
    <el-card>
      <el-table :data="warehouses" v-loading="loading" stripe>
        <el-table-column prop="warehouse_code" label="仓库编码" width="160" />
        <el-table-column prop="warehouse_name" label="仓库名称" min-width="200" />
        <el-table-column prop="address" label="地址" min-width="240" />
        <el-table-column prop="contact_person" label="联系人" width="120" />
        <el-table-column prop="contact_phone" label="电话" width="140" />
        <el-table-column prop="manager_name" label="管理员" width="140" />
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="openEdit(row)">
              编辑
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="formVisible"
      :title="editingId ? '编辑仓库' : '新增仓库'"
      width="520px"
      @close="resetForm"
    >
      <el-form :model="form" :rules="rules" ref="formRef" label-width="100px">
        <el-form-item label="仓库编码" prop="warehouse_code">
          <el-input v-model="form.warehouse_code" placeholder="唯一编码" />
        </el-form-item>
        <el-form-item label="仓库名称" prop="warehouse_name">
          <el-input v-model="form.warehouse_name" placeholder="显示名称" />
        </el-form-item>
        <el-form-item label="地址">
          <el-input v-model="form.address" placeholder="地址" />
        </el-form-item>
        <el-form-item label="联系人">
          <el-input v-model="form.contact_person" placeholder="联系人" />
        </el-form-item>
        <el-form-item label="电话">
          <el-input v-model="form.contact_phone" placeholder="联系电话" />
        </el-form-item>
        <el-form-item label="管理员">
          <el-select v-model="form.manager_id" clearable filterable placeholder="选择管理员" @visible-change="v=> v && loadUsers()">
            <el-option v-for="u in userOptions" :key="u.id" :label="u.full_name || u.username" :value="u.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">
          {{ editingId ? '保存修改' : '保存' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { stockApi } from '../../api/stock'
import { ElMessage } from 'element-plus'
import request from '@/utils/request'

const loading = ref(false)
const warehouses = ref([])
const formVisible = ref(false)
const saving = ref(false)
const formRef = ref()
const editingId = ref(null)
const form = ref({
  warehouse_code: '',
  warehouse_name: '',
  address: '',
  contact_person: '',
  contact_phone: '',
  manager_id: null
})
const rules = {
  warehouse_code: [{ required: true, message: '请输入仓库编码', trigger: 'blur' }],
  warehouse_name: [{ required: true, message: '请输入仓库名称', trigger: 'blur' }]
}
const userOptions = ref([])

const load = async () => {
  try {
    loading.value = true
    const res = await stockApi.getWarehouses()
    warehouses.value = res?.warehouses || []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载仓库失败')
  } finally {
    loading.value = false
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

const openCreate = () => {
  editingId.value = null
  resetForm()
  formVisible.value = true
}

const openEdit = (row) => {
  editingId.value = row.id
  form.value = {
    warehouse_code: row.warehouse_code,
    warehouse_name: row.warehouse_name,
    address: row.address,
    contact_person: row.contact_person,
    contact_phone: row.contact_phone,
    manager_id: row.manager_id || null
  }
  if (formRef.value) formRef.value.clearValidate()
  formVisible.value = true
}

const resetForm = () => {
  form.value = {
    warehouse_code: '',
    warehouse_name: '',
    address: '',
    contact_person: '',
    contact_phone: '',
    manager_id: null
  }
  if (formRef.value) formRef.value.clearValidate()
}

const submit = async () => {
  try {
    await formRef.value.validate()
    saving.value = true
    if (editingId.value) {
      await stockApi.updateWarehouse(editingId.value, form.value)
      ElMessage.success('更新成功')
    } else {
      await stockApi.createWarehouse(form.value)
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    resetForm()
    await load()
  } catch (e) {
    if (e !== 'cancel') {
      console.error(e)
      ElMessage.error(e?.response?.data?.detail || '保存失败')
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page { padding: 24px; }
.page-header { display:flex; justify-content: space-between; align-items:center; margin-bottom: 16px; }
</style>
