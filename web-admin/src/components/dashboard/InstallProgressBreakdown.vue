<template>
  <section class="install-breakdown">
    <div class="section-head">
      <div>
        <h2 class="section-title">{{ t('dashboard.installBreakdown.title') }}</h2>
        <p class="section-subtitle">
          {{ categoryName
            ? t('dashboard.installBreakdown.subtitleWithCategory', { category: categoryName })
            : t('dashboard.installBreakdown.subtitle')
          }}
        </p>
      </div>
      <div class="head-actions">
        <el-select
          v-if="categories.length"
          v-model="selectedCategoryId"
          size="small"
          :placeholder="t('dashboard.installBreakdown.categoryPlaceholder')"
          style="width: 180px"
          @change="load"
        >
          <el-option
            v-for="category in categories"
            :key="category.id"
            :label="categoryLabel(category)"
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
          {{ t('dashboard.installBreakdown.settings') }}
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
      <el-table-column :label="t('dashboard.installBreakdown.columns.group')" min-width="150">
        <template #default="{ row }">
          <div class="group-cell">
            <span class="group-dot" :style="{ background: row.option_color || '#64748b' }" />
            <span>{{ optionLabel(row) }}</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="total" :label="t('dashboard.installBreakdown.columns.total')" width="90" align="right" />
      <el-table-column prop="install_started" :label="t('dashboard.installBreakdown.columns.installStarted')" width="90" align="right" />
      <el-table-column prop="installed" :label="t('dashboard.installBreakdown.columns.installed')" width="100" align="right" />
      <el-table-column prop="not_installed" :label="t('dashboard.installBreakdown.columns.notInstalled')" width="90" align="right" />
      <el-table-column :label="t('dashboard.installBreakdown.columns.partialOnline')" width="112" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <span class="metric-value">{{ row.partial_online || 0 }}</span>
            <span v-if="deviceFraction(row, 'partial_online', 'online')" class="metric-fraction">
              {{ deviceFraction(row, 'partial_online', 'online') }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('dashboard.installBreakdown.columns.fullyOnline')" width="112" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <span class="metric-value">{{ valueWithFallback(row, 'fully_online', 'online') }}</span>
            <span v-if="deviceFraction(row, 'fully_online', 'online')" class="metric-fraction">
              {{ deviceFraction(row, 'fully_online', 'online') }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('dashboard.installBreakdown.columns.partialActivated')" width="112" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <span class="metric-value">{{ row.partial_activated || 0 }}</span>
            <span v-if="deviceFraction(row, 'partial_activated', 'activated')" class="metric-fraction">
              {{ deviceFraction(row, 'partial_activated', 'activated') }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column :label="t('dashboard.installBreakdown.columns.fullyActivated')" width="112" align="right">
        <template #default="{ row }">
          <div class="metric-cell">
            <span class="metric-value">{{ valueWithFallback(row, 'fully_activated', 'activated') }}</span>
            <span v-if="deviceFraction(row, 'fully_activated', 'activated')" class="metric-fraction">
              {{ deviceFraction(row, 'fully_activated', 'activated') }}
            </span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="ssv" :label="t('dashboard.installBreakdown.columns.ssv')" width="100" align="right" />
      <el-table-column :label="t('dashboard.installBreakdown.columns.actions')" width="96" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="gotoSites(row)">
            {{ t('dashboard.installBreakdown.viewSites') }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-else :description="loading ? t('dashboard.installBreakdown.loading') : t('dashboard.installBreakdown.empty')">
      <el-button
        v-if="canManageGroups"
        type="primary"
        @click="gotoGroupSettings"
      >
        {{ t('dashboard.installBreakdown.goSettings') }}
      </el-button>
    </el-empty>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Setting } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { fetchInstallProgressBreakdown } from '@/api/dashboard'
import { useUserStore } from '@/stores/user'

const emit = defineEmits(['goto'])
const userStore = useUserStore()
const { t } = useI18n()

const loading = ref(false)
const categories = ref([])
const selectedCategoryId = ref(null)
const rows = ref([])

const canManageGroups = computed(() => (
  userStore.isAdmin
  || userStore.isManager
  || userStore.hasPermission('sites:update:write')
))
const categoryLabel = (category) => {
  if (category?.code === 'delivery_scope') {
    return t('dashboard.installBreakdown.knownCategories.delivery_scope')
  }
  return category?.name || ''
}
const optionLabel = (row) => {
  if (row?.filter?.group_unassigned || row?.option_id === null) {
    return t('dashboard.installBreakdown.unassigned')
  }
  return row?.option_name || '-'
}
const categoryName = computed(() => {
  const category = categories.value.find(item => item.id === selectedCategoryId.value)
  return categoryLabel(category)
})
const valueWithFallback = (row, key, fallbackKey) => {
  if (row?.[key] === undefined || row?.[key] === null) {
    return Number(row?.[fallbackKey] || 0)
  }
  return Number(row?.[key] || 0)
}
const deviceFraction = (row, key, type) => {
  const bucket = row?.device_progress?.[key]
  const denominator = Number(bucket?.denominator || 0)
  if (!denominator) return ''
  const numerator = Number(bucket?.numerator || 0)
  const fractionKey = type === 'activated' ? 'activated' : 'online'
  return t(`dashboard.installBreakdown.deviceFraction.${fractionKey}`, { numerator, denominator })
}

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
    ElMessage.error(t('dashboard.installBreakdown.loadFailed'))
  } finally {
    loading.value = false
  }
}

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
.group-cell {
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
.metric-cell {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: center;
  gap: 2px;
  min-height: 34px;
}
.metric-value {
  color: var(--text-primary);
  font-weight: 600;
  line-height: 1;
}
.metric-fraction {
  color: var(--text-light);
  font-size: 12px;
  line-height: 1.2;
  white-space: nowrap;
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
