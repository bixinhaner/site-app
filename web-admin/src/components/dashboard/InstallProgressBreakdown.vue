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
          @click="gotoGroupSettings"
        >
          <el-icon><Setting /></el-icon>
          分组设置
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
        @click="gotoGroupSettings"
      >
        前往分组设置
      </el-button>
    </el-empty>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Setting } from '@element-plus/icons-vue'
import { fetchInstallProgressBreakdown } from '@/api/dashboard'
import { useUserStore } from '@/stores/user'

const emit = defineEmits(['goto'])
const userStore = useUserStore()

const loading = ref(false)
const categories = ref([])
const selectedCategoryId = ref(null)
const rows = ref([])

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

const gotoGroupSettings = () => {
  emit('goto', { name: 'SiteGroupSettings' })
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
}
</style>
