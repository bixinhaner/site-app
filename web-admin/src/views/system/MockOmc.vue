<template>
  <div class="page" v-loading="loading">
    <div class="page-header">
      <h1>模拟 OMC 测试桩</h1>
      <div class="header-actions">
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新增设备</el-button>
        <el-button @click="resetAll" :loading="resetting">清空</el-button>
        <span class="hint">当前目标：{{ baseURL }}</span>
      </div>
    </div>

    <el-collapse v-model="helpActive" class="help-collapse">
      <el-collapse-item name="help">
        <template #title>
          <span>用户帮助（如何配置为 OMC 模拟测试桩）</span>
        </template>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="配置为 OMC 模拟测试桩：后端调用 OMC API 的 base_url 需要指向 mock-omc 服务（默认 9000 端口）。"
          class="mb12"
        />
        <div class="help-body">
          <div class="help-section">
            <div class="help-title">1）先后台启动测试桩（默认 9000 端口）</div>
            <pre class="help-code">cd mock-omc
python3 -m venv venv &amp;&amp; ./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn main:app --reload --port 9000</pre>
          </div>

          <div class="help-section">
            <div class="help-title">2）在 Web 管理端 系统管理 -&gt; OMC API 配置 填写</div>
            <ul class="help-list">
              <li>
                OMC 基础地址(base_url)：<code>http://127.0.0.1:9000</code>
                <div class="help-tip">注意：后端会在此基础上拼接 <code>/northboundApi/v1/...</code>，所以这里不要再带 <code>/northboundApi/...</code></div>
              </li>
              <li>API 用户名(username)：任意非空（mock 不校验）</li>
              <li>API 密码(password)：任意非空（mock 不校验）</li>
              <li>超时时间(timeout_seconds)：按需（默认 10）</li>
            </ul>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>

    <el-card>
      <div class="filter-bar">
        <el-input v-model="keyword" placeholder="按 SN 过滤" clearable style="width: 240px" @keyup.enter.native="reload" />
        <el-button @click="reload"><el-icon><Search /></el-icon>刷新</el-button>
      </div>
      <el-table :data="filtered" stripe>
        <el-table-column prop="sn" label="SN" min-width="180" />
        <el-table-column label="在线" width="120">
          <template #default="{ row }">
            <el-switch v-model="row.online" @change="v => updateState(row, { online: v })" />
          </template>
        </el-table-column>
        <el-table-column label="激活" width="120">
          <template #default="{ row }">
            <el-switch v-model="row.activated" @change="v => updateState(row, { activated: v })" />
          </template>
        </el-table-column>
        <el-table-column prop="cell_name" label="Cell Name" min-width="160">
          <template #default="{ row }">
            <el-input v-model="row.cell_name" size="small" placeholder="未设置" @change="v => updateState(row, { cell_name: v })" />
          </template>
        </el-table-column>
        <el-table-column prop="description" label="备注" min-width="200" />
        <el-table-column prop="updated_at" label="更新时间" width="180">
          <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除?" @confirm="remove(row)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editing ? '编辑设备' : '新增设备'" width="480px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="SN">
          <el-input v-model="form.sn" :disabled="editing" />
        </el-form-item>
        <el-form-item label="在线">
          <el-switch v-model="form.online" />
        </el-form-item>
        <el-form-item label="激活">
          <el-switch v-model="form.activated" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { mockOmcApi } from '@/api/mockOmc'

const loading = ref(false)
const resetting = ref(false)
const items = ref([])
const keyword = ref('')
const dialogVisible = ref(false)
const saving = ref(false)
const editing = ref(false)
const form = ref({ sn: '', online: false, activated: false, description: '' })
const baseURL = import.meta.env.VITE_MOCK_OMC_BASE || '/api/mock-omc'
const helpActive = ref([])

const filtered = computed(() => {
  if (!keyword.value) return items.value
  return items.value.filter(x => (x.sn || '').includes(keyword.value))
})

const reload = async () => {
  try {
    loading.value = true
    const res = await mockOmcApi.list()
    items.value = Array.isArray(res?.data) ? res.data : res
  } catch (e) {
    console.error(e)
    ElMessage.error('加载失败，请确认已启动 mock-omc 服务')
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editing.value = false
  form.value = { sn: '', online: false, activated: false, description: '', cell_name: '' }
  dialogVisible.value = true
}

const openEdit = (row) => {
  editing.value = true
  form.value = { ...row }
  dialogVisible.value = true
}

const save = async () => {
  try {
    saving.value = true
    if (!form.value.sn) {
      ElMessage.warning('SN 不能为空')
      return
    }
    if (editing.value) {
      await mockOmcApi.update(form.value.sn, {
        online: form.value.online,
        activated: form.value.activated,
        cell_name: form.value.cell_name,
        description: form.value.description
      })
    } else {
      await mockOmcApi.create(form.value)
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await reload()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

const updateState = async (row, payload) => {
  try {
    await mockOmcApi.setState(row.sn, payload)
    ElMessage.success('已更新')
  } catch (e) {
    console.error(e)
    ElMessage.error('更新失败')
    reload()
  }
}

const remove = async (row) => {
  try {
    await mockOmcApi.remove(row.sn)
    ElMessage.success('已删除')
    reload()
  } catch (e) {
    console.error(e)
    ElMessage.error('删除失败')
  }
}

const resetAll = async () => {
  try {
    resetting.value = true
    await mockOmcApi.reset()
    ElMessage.success('已清空')
    reload()
  } catch (e) {
    console.error(e)
    ElMessage.error('清空失败')
  } finally {
    resetting.value = false
  }
}

const formatDate = (v) => v ? new Date(v).toLocaleString() : '-'

onMounted(reload)
</script>

<style scoped>
.page { padding: 16px; }
.page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.header-actions { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.help-collapse { margin-bottom: 12px; }
.help-body { padding: 4px 0 8px; }
.help-section { margin-bottom: 12px; }
.help-title { font-weight: 600; margin-bottom: 8px; }
.help-code {
  margin: 0;
  padding: 10px 12px;
  background: #0b1020;
  color: #e5e7eb;
  border-radius: 6px;
  overflow: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.5;
}
.help-list { margin: 0; padding-left: 18px; }
.help-list li { margin: 6px 0; }
.help-tip { margin-top: 4px; color: #909399; font-size: 12px; }
.mb12 { margin-bottom: 12px; }
.filter-bar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.hint { color: #909399; }
</style>
