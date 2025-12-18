<template>
  <el-drawer
    :model-value="modelValue"
    @update:modelValue="(val) => emit('update:modelValue', val)"
    :title="title"
    :size="size"
    append-to-body
  >
    <div v-loading="loading">
      <el-alert
        v-if="error"
        type="error"
        :title="error"
        :closable="false"
        show-icon
        class="mb12"
      />

      <archive-form-renderer
        v-if="modelValue && content"
        :content="content"
        :disabled="disabled"
      />
      <el-empty
        v-else-if="modelValue && !loading && !error"
        description="暂无可预览内容"
      />
    </div>
  </el-drawer>
</template>

<script setup>
import ArchiveFormRenderer from '@/components/archives/ArchiveFormRenderer.vue'

defineProps({
  modelValue: { type: Boolean, default: false },
  content: { type: Object, default: null },
  title: { type: String, default: '模板预览' },
  size: { type: String, default: '80%' },
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue'])
</script>

