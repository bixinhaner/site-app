<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    :remote-method="search"
    :loading="loading"
    :placeholder="placeholder || t('stockTrace.targetSitePlaceholder')"
    style="width: 100%"
    @update:model-value="onChange"
    @visible-change="onVisibleChange"
  >
    <el-option v-for="s in options" :key="s.id" :label="siteLabel(s)" :value="s.id">
      <div class="site-option">
        <span class="name">{{ siteLabel(s) }}</span>
        <span class="meta">
          <span v-if="s.lld_cell_count" class="lld">{{ lldText(s) }}</span>
          <el-tag v-if="s.recent" size="small" type="warning" effect="plain">{{ t('stockTrace.recent') }}</el-tag>
          <span v-else-if="s.city" class="city">{{ s.city }}</span>
        </span>
      </div>
    </el-option>
    <template v-if="noLldMatches.length && options.length" #footer>
      <div class="no-lld">{{ noLldText }}</div>
    </template>
    <template #empty>
      <div class="empty">
        <div v-if="noLldMatches.length" class="no-lld">{{ noLldText }}</div>
        <span v-else>{{ loading ? t('stockTrace.loadingSites') : t('stockTrace.noSites') }}</span>
      </div>
    </template>
  </el-select>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { stockApi } from '../../api/stock'

const props = defineProps({
  modelValue: { type: [Number, null], default: null },
  // 已选站点的展示信息（编辑/回显时传入，避免远程列表中不存在导致只显示 id）
  initialSite: { type: Object, default: null },
  // 为空时使用默认文案（stockTrace.targetSitePlaceholder）
  placeholder: { type: String, default: '' },
  // 为空时自动带出最近一次使用的站点
  autofillLastUsed: { type: Boolean, default: false },
  // 筛选场景（如出入库记录）需要全部站点，不受“目标站点必须有 LLD 规划”限制
  includeUnplanned: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue', 'change'])
const { t, locale } = useI18n()

const loading = ref(false)
const options = ref([])
const noLldMatches = ref([])

const siteLabel = (s) => {
  if (!s) return ''
  const name = s.site_name || ''
  const code = s.site_code || ''
  if (!(name && code && name !== code)) return name || code
  return locale.value === 'zh-CN' ? `${name}（${code}）` : `${name} (${code})`
}

const noLldText = computed(() =>
  t('stockTrace.noLldSites', { codes: noLldMatches.value.map((x) => x.site_code).join(', ') })
)

const lldText = (s) =>
  [(s.lld_bands || []).join('/'), t('stockTrace.lldCells', { count: s.lld_cell_count })].filter(Boolean).join(' · ')

const ensureInitialOption = () => {
  const init = props.initialSite
  if (init?.id && !options.value.some((x) => x.id === init.id)) {
    options.value = [init, ...options.value]
  }
}

const search = async (keyword = '') => {
  loading.value = true
  try {
    const params = { keyword: (keyword || '').trim(), limit: 30 }
    if (props.includeUnplanned) params.include_unplanned = true
    const res = await stockApi.getSiteOptions(params)
    options.value = res?.sites || []
    noLldMatches.value = res?.no_lld_matches || []
    ensureInitialOption()
    return res
  } catch (error) {
    console.error('load site options failed:', error)
    return null
  } finally {
    loading.value = false
  }
}

const onChange = (val) => {
  const id = val || null
  emit('update:modelValue', id)
  emit('change', options.value.find((x) => x.id === id) || null)
}

const onVisibleChange = (visible) => {
  if (visible && options.value.length === 0) search('')
}

watch(() => props.initialSite, ensureInitialOption)

onMounted(async () => {
  ensureInitialOption()
  if (!props.autofillLastUsed || props.modelValue) return
  const res = await search('')
  const lastId = res?.last_used_site_id
  if (lastId && !props.modelValue) onChange(lastId)
})

defineExpose({ reload: () => search('') })
</script>

<style scoped>
.site-option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.site-option .meta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.site-option .city,
.site-option .lld {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
.no-lld {
  color: var(--el-color-warning);
  font-size: 12px;
  line-height: 1.5;
}
.empty {
  padding: 10px 12px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
