<template>
  <section class="install-breakdown">
    <div class="section-head">
      <div>
        <h2 class="section-title">安装进度分组</h2>
        <p class="section-subtitle">
          {{ categoryName ? `按「${categoryName}」查看站点安装状态` : '按业务分组查看站点安装状态' }}
        </p>
      </div>
      <div class="head-actions">
        <el-select
          v-if="categories.length"
          v-model="selectedCategoryId"
          size="small"
          placeholder="选择分组维度"
          style="width: 180px"
          @change="load"
        >
          <el-option
            v-for="category in categories"
            :key="category.id"
            :label="category.name"
            :value="category.id"
          />
        </el-select>
        <el-button size="small" :loading="loading" @click="load">
          <el-icon><Refresh /></el-icon>
        </el-button>
        <el-button
          v-if="canManageGroups"
          size="small"
          type="primary"
          plain
          :loading="seedLoading"
          @click="openSeedPreview"
        >
          <el-icon><Operation /></el-icon>
          生成交付范围
        </el-button>
      </div>
    </div>

    <el-table
      v-if="rows.length"
      :data="rows"
      v-loading="loading"
      size="small"
      border
      class="breakdown-table"
    >
      <el-table-column label="分组" min-width="150">
        <template #default="{ row }">
          <div class="group-cell">
            <span class="group-dot" :style="{ background: row.option_color || '#64748b' }" />
            <span>{{ row.option_name }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="total" label="总站点" width="90" align="right" />
      <el-table-column prop="install_started" label="已开始" width="90" align="right" />
      <el-table-column prop="installed" label="安装完成" width="100" align="right" />
      <el-table-column prop="not_installed" label="未安装" width="90" align="right" />
      <el-table-column prop="online" label="上线" width="80" align="right" />
      <el-table-column prop="activated" label="激活" width="80" align="right" />
      <el-table-column label="完成率" min-width="170">
        <template #default="{ row }">
          <div class="rate-cell">
            <el-progress
              :percentage="Number(row.completion_rate || 0)"
              :stroke-width="8"
              :show-text="false"
            />
            <span>{{ formatRate(row.completion_rate) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="96" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="gotoSites(row)">查看站点</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else :description="loading ? '正在加载...' : '暂无分组统计'">
      <el-button
        v-if="canManageGroups"
        type="primary"
        :loading="seedLoading"
        @click="openSeedPreview"
      >
        从 LLD 生成交付范围
      </el-button>
    </el-empty>

    <el-dialog
      v-model="seedDialogVisible"
      title="生成交付范围"
      width="720px"
      :close-on-click-modal="false"
    >
      <div v-if="seedPlan" class="seed-summary">
        <el-alert
          type="info"
          :closable="false"
          title="系统会从当前 LLD 的 Duplex Mode 生成交付范围，TDD-only 归入 TDD，FDD-only 归入 FDD，同时包含 TDD/FDD 的站点保留人工确认。"
        />
        <div class="seed-metrics">
          <div><span>总站点</span><strong>{{ seedPlan.requested_count }}</strong></div>
          <div><span>可建议</span><strong>{{ seedPlan.suggested_count }}</strong></div>
          <div><span>TDD</span><strong>{{ seedPlan.by_option?.TDD || 0 }}</strong></div>
          <div><span>FDD</span><strong>{{ seedPlan.by_option?.FDD || 0 }}</strong></div>
          <div><span>需人工确认</span><strong>{{ seedPlan.skipped_count + seedPlan.conflict_count }}</strong></div>
        </div>
        <el-table :data="seedPlan.samples || []" size="small" border max-height="260">
          <el-table-column prop="site_code" label="站点编码" width="150" />
          <el-table-column prop="site_name" label="站点名称" min-width="180" />
          <el-table-column prop="target" label="建议分组" width="110">
            <template #default="{ row }">{{ row.target || '-' }}</template>
          </el-table-column>
          <el-table-column prop="action" label="动作" width="110" />
          <el-table-column prop="reason" label="说明" min-width="180" />
        </el-table>
        <div v-if="seedPlan.warnings?.length" class="warning-list">
          <div v-for="item in seedPlan.warnings" :key="item">{{ item }}</div>
        </div>
      </div>
      <template #footer>
        <el-button @click="seedDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="seedLoading" @click="executeSeed">确认生成</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Operation, Refresh } from '@element-plus/icons-vue'
import { fetchInstallProgressBreakdown } from '@/api/dashboard'
import siteGroupsApi from '@/api/siteGroups'
import { useUserStore } from '@/stores/user'

const emit = defineEmits(['goto'])
const userStore = useUserStore()

const loading = ref(false)
const seedLoading = ref(false)
const seedDialogVisible = ref(false)
const categories = ref([])
const selectedCategoryId = ref(null)
const rows = ref([])
const seedPlan = ref(null)

const canManageGroups = computed(() => (
  userStore.isAdmin
  || userStore.isManager
  || userStore.hasPermission('sites:update:write')
))
const categoryName = computed(() => {
  const category = categories.value.find(item => item.id === selectedCategoryId.value)
  return category?.name || ''
})

const load = async () => {
  try {
    loading.value = true
    const params = selectedCategoryId.value ? { category_id: selectedCategoryId.value } : {}
    const res = await fetchInstallProgressBreakdown(params)
    categories.value = Array.isArray(res?.categories) ? res.categories : []
    if (!selectedCategoryId.value && res?.category?.id) {
      selectedCategoryId.value = res.category.id
    }
    rows.value = Array.isArray(res?.rows) ? res.rows : []
  } catch (e) {
    console.error(e)
    ElMessage.error('加载安装进度分组失败')
  } finally {
    loading.value = false
  }
}

const formatRate = (value) => `${Number(value || 0).toFixed(1)}%`

const gotoSites = (row) => {
  const query = {
    group_category_id: row.filter?.group_category_id,
  }
  if (row.filter?.group_unassigned) {
    query.group_unassigned = '1'
  } else if (row.filter?.group_option_id) {
    query.group_option_id = row.filter.group_option_id
  }
  emit('goto', { name: 'SiteList', query })
}

const openSeedPreview = async () => {
  try {
    seedLoading.value = true
    seedPlan.value = await siteGroupsApi.seedDeliveryScopeFromLld({ dry_run: true, overwrite: false })
    seedDialogVisible.value = true
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '生成预览失败')
  } finally {
    seedLoading.value = false
  }
}

const executeSeed = async () => {
  try {
    seedLoading.value = true
    const res = await siteGroupsApi.seedDeliveryScopeFromLld({ dry_run: false, overwrite: false })
    ElMessage.success(`已生成交付范围，更新 ${res.assigned_count || 0} 个站点`)
    seedDialogVisible.value = false
    selectedCategoryId.value = res.category_id || selectedCategoryId.value
    await load()
  } catch (e) {
    console.error(e)
    ElMessage.error(e?.response?.data?.detail || '生成交付范围失败')
  } finally {
    seedLoading.value = false
  }
}

onMounted(load)

defineExpose({ refresh: load })
</script>

<style scoped>
.install-breakdown {
  margin: 20px 0;
}
.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}
.section-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}
.section-subtitle {
  margin: 4px 0 0;
  color: var(--text-light);
  font-size: 13px;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.breakdown-table {
  background: #fff;
}
.group-cell,
.rate-cell {
  display: flex;
  align-items: center;
  gap: 8px;
}
.group-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: 0 0 auto;
}
.rate-cell :deep(.el-progress) {
  flex: 1;
  min-width: 72px;
}
.rate-cell span {
  width: 48px;
  text-align: right;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}
.seed-summary {
  display: grid;
  gap: 12px;
}
.seed-metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}
.seed-metrics div {
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 10px;
  background: #fff;
}
.seed-metrics span {
  display: block;
  color: var(--text-light);
  font-size: 12px;
}
.seed-metrics strong {
  display: block;
  margin-top: 4px;
  color: var(--text-primary);
  font-size: 20px;
}
.warning-list {
  max-height: 120px;
  overflow: auto;
  color: #92400e;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}
@media (max-width: 768px) {
  .section-head {
    align-items: stretch;
    flex-direction: column;
  }
  .head-actions {
    align-items: stretch;
  }
  .head-actions .el-select,
  .head-actions .el-button {
    width: 100%;
  }
  .seed-metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
