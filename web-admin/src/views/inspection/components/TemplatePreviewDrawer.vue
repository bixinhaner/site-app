<template>
  <el-drawer
    :model-value="modelValue"
    @update:modelValue="(val) => emit('update:modelValue', val)"
    :title="title"
    :size="size"
    append-to-body
  >
    <div v-loading="loading" class="preview-wrap">
      <el-alert
        v-if="error"
        type="error"
        :title="error"
        :closable="false"
        show-icon
        class="mb12"
      />

      <div v-if="modelValue && content" class="preview-body">
        <div class="preview-toolbar">
          <div class="preview-meta" v-if="templateName">
            <el-tag size="small" effect="plain">{{ templateName }}</el-tag>
            <el-tag v-if="templateVersion" size="small" effect="plain" type="info">v{{ templateVersion }}</el-tag>
          </div>
          <div class="preview-locale">
            <el-select v-model="previewLocale" size="small" style="width: 140px;">
              <el-option label="中文(zh)" value="zh" />
              <el-option label="English(en)" value="en" />
              <el-option label="Bahasa(id)" value="id" />
            </el-select>
          </div>
        </div>

        <el-tabs v-model="activeLevel" class="level-tabs">
          <el-tab-pane
            v-for="tab in levelTabs"
            :key="tab.key"
            :name="tab.key"
            :label="tab.label"
          >
            <el-alert
              type="info"
              :closable="false"
              show-icon
              class="mb12"
            >
              <template #title>
                <span>{{ tab.hint }}</span>
              </template>
            </el-alert>

            <div v-if="activeLevel === tab.key && tab.hasData" class="phone-frame">
              <archive-form-renderer
                v-if="filteredContent"
                :content="filteredContent"
                :disabled="disabled"
                variant="template"
                :locale="previewLocale"
              />
            </div>

            <el-empty
              v-if="activeLevel === tab.key && !tab.hasData"
              description="该级别暂无检查分类"
            />
          </el-tab-pane>
        </el-tabs>
      </div>
      <el-empty
        v-else-if="modelValue && !loading && !error"
        description="暂无可预览内容"
      />
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import ArchiveFormRenderer from '@/components/archives/ArchiveFormRenderer.vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  content: { type: Object, default: null },
  title: { type: String, default: '模板预览' },
  size: { type: String, default: '80%' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])

const normalizeLevelType = (category) => {
  const lt = category?.level_type
  if (lt === 'cell') return 'device'
  if (!lt) {
    if (category?.cell_specific) return 'device'
    if (category?.sector_specific) return 'sector'
    return 'site'
  }
  return lt
}

const levelGroups = computed(() => {
  const cats = props.content?.check_categories || []
  const groups = { site: [], sector: [], device: [], cell_earfcn: [] }
  cats.forEach((c) => {
    const lt = normalizeLevelType(c)
    if (lt === 'sector') groups.sector.push(c)
    else if (lt === 'device') groups.device.push(c)
    else if (lt === 'cell_earfcn') groups.cell_earfcn.push(c)
    else groups.site.push(c)
  })
  return groups
})

const levelTabs = computed(() => {
  const siteCount = levelGroups.value.site.length
  const sectorCount = levelGroups.value.sector.length
  const deviceCount = levelGroups.value.device.length
  const cellCount = levelGroups.value.cell_earfcn.length

  return [
    {
      key: 'site',
      label: `站点（${siteCount}）`,
      hint: '站点级：整个站点只检查一次（如：供电、环境）。',
      hasData: siteCount > 0,
    },
    {
      key: 'sector',
      label: `扇区（${sectorCount}）`,
      hint: '扇区级：每个扇区各检查一次（如：天线安装）。',
      hasData: sectorCount > 0,
    },
    {
      key: 'device',
      label: `设备（${deviceCount}）`,
      hint: '设备级：每个设备（扇区×Band）各检查一次；实际工单中需要扫码绑定设备。',
      hasData: deviceCount > 0,
    },
    {
      key: 'cell_earfcn',
      label: `小区（${cellCount}）`,
      hint: '小区级：每个小区（扇区×Band×EARFCN）各检查一次；不需要扫码绑定。',
      hasData: cellCount > 0,
    },
  ]
})

const templateName = computed(() => props.content?.meta?.template?.name || '')
const templateVersion = computed(() => props.content?.meta?.template?.version || '')

const activeLevel = ref('site')
const chooseDefaultLevel = () => {
  const order = ['site', 'sector', 'device', 'cell_earfcn']
  for (const key of order) {
    if ((levelGroups.value[key] || []).length > 0) return key
  }
  return 'site'
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    activeLevel.value = chooseDefaultLevel()
  },
  { immediate: true }
)

watch(
  () => props.content,
  () => {
    if (!props.modelValue) return
    const currentCats = levelGroups.value[activeLevel.value] || []
    if (currentCats.length > 0) return
    activeLevel.value = chooseDefaultLevel()
  }
)

const filteredContent = computed(() => {
  if (!props.content) return null
  const cats = levelGroups.value[activeLevel.value] || []
  return { ...props.content, check_categories: cats }
})

const previewLocale = ref('zh')
</script>

<style scoped>
.preview-wrap {
  height: 100%;
}

.preview-toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.preview-body {
  background: #f7f8fb;
  padding: 12px;
  border-radius: 10px;
}

.preview-meta {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.preview-locale {
  display: flex;
  justify-content: flex-end;
}

.phone-frame {
  max-width: 460px;
  margin: 0 auto;
}

.level-tabs :deep(.el-tabs__header) {
  margin: 0 0 10px 0;
}
</style>
