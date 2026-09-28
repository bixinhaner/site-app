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
        <el-tag v-if="s.recent" size="small" type="warning" effect="plain">{{ t('stockTrace.recent') }}</el-tag>
        <span v-else-if="s.city" class="city">{{ s.city }}</span>
      </div>
    </el-option>
  </el-select>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
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
})
const emit = defineEmits(['update:modelValue', 'change'])
const { t, locale } = useI18n()

const loading = ref(false)
const options = ref([])

const siteLabel = (s) => {
  if (!s) return ''
  const name = s.site_name || ''
  const code = s.site_code || ''
  if (!(name && code && name !== code)) return name || code
  return locale.value === 'zh-CN' ? `${name}（${code}）` : `${name} (${code})`
}

const ensureInitialOption = () => {
  const init = props.initialSite
  if (init?.id && !options.value.some((x) => x.id === init.id)) {
    options.value = [init, ...options.value]
  }
}

const search = async (keyword = '') => {
  loading.value = true
  try {
    const res = await stockApi.getSiteOptions({ keyword: (keyword || '').trim(), limit: 30 })
    options.value = res?.sites || []
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
.site-option .city {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}
</style>
