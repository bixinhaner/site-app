<template>
  <div class="voucher-gallery">
    <div v-if="voucher?.remark" class="remark">{{ t('quickOut.voucherNo') }}：{{ voucher.remark }}</div>
    <div class="tiles">
      <template v-for="f in items" :key="f.id">
        <a v-if="f.isPdf" class="tile pdf" :href="f.url" target="_blank" rel="noopener" :title="f.name">
          <el-icon :size="24"><Document /></el-icon>
          <span class="pdf-name">{{ f.name }}</span>
        </a>
        <el-image
          v-else
          class="tile"
          :src="f.url"
          fit="cover"
          :preview-src-list="imageUrls"
          :initial-index="imageUrls.indexOf(f.url)"
          preview-teleported
        />
      </template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { resolveImageUrl } from '../../utils/imageLoader'

// 只读展示出入库单关联的出库凭证（后端 offline_document 摘要）
const props = defineProps({
  voucher: { type: Object, default: null },
})
const { t } = useI18n()

const items = computed(() =>
  (props.voucher?.files || []).map((f) => ({
    id: f.id,
    name: f.original_name || 'PDF',
    url: resolveImageUrl(f.file_path),
    isPdf: f.mime_type === 'application/pdf' || /\.pdf$/i.test(f.file_path || ''),
  }))
)
const imageUrls = computed(() => items.value.filter((f) => !f.isPdf).map((f) => f.url))
</script>

<style scoped>
.remark {
  margin-bottom: 8px;
  color: var(--el-text-color-regular);
  font-size: 13px;
}
.tiles {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tile {
  width: 84px;
  height: 84px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-lighter);
}
.pdf {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 6px;
  color: var(--el-color-danger);
  text-decoration: none;
}
.pdf-name {
  width: 100%;
  font-size: 11px;
  color: var(--el-text-color-regular);
  text-align: center;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
</style>
