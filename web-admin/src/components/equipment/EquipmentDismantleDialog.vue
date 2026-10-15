<template>
  <el-dialog
    :model-value="modelValue"
    title="设备拆除/移机"
    width="1000px"
    top="6vh"
    @update:model-value="emit('update:modelValue', $event)"
    @open="handleOpen"
  >
    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="用于已验收站点的设备拆除或换站安装：解绑原站点后，设备回到领料人名下（已出库），可在新站点工单中重新扫码绑定。原站点的检查、照片和审核记录保留不变。"
      class="dismantle-tip"
    />

    <el-form label-position="top">
      <el-form-item label="设备SN" required>
        <el-input
          v-model="snText"
          type="textarea"
          :rows="5"
          placeholder="每行一个SN，也可用逗号或空格分隔"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="previewing" @click="runPreview">预览</el-button>
        <span v-if="previewItems.length" class="dismantle-summary">
          共 {{ previewItems.length }} 台，可拆除 {{ eligibleItems.length }} 台
        </span>
      </el-form-item>
    </el-form>

    <el-table v-if="previewItems.length" :data="previewItems" size="small" max-height="360" border>
      <el-table-column prop="sn" label="SN" width="190" />
      <el-table-column label="设备" min-width="120">
        <template #default="{ row }">{{ row.equipment_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="当前站点" min-width="180">
        <template #default="{ row }">
          <span v-if="row.site_name">{{ row.site_name }} - {{ row.cell_id || '-' }}</span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="检查状态" width="100">
        <template #default="{ row }">{{ inspectionStatusLabel(row.inspection_status) }}</template>
      </el-table-column>
      <el-table-column label="领料人" width="120">
        <template #default="{ row }">{{ row.issued_to_name || '-' }}</template>
      </el-table-column>
      <el-table-column label="结果" min-width="200">
        <template #default="{ row }">
          <el-tag v-if="row.eligible" type="success" size="small">可拆除</el-tag>
          <el-tag v-else type="danger" size="small">{{ row.reason }}</el-tag>
        </template>
      </el-table-column>
    </el-table>

    <el-form v-if="eligibleItems.length" label-position="top" class="dismantle-reason">
      <el-form-item label="拆除原因" required>
        <el-input v-model="reason" maxlength="200" show-word-limit placeholder="例如：原站点安装错误，拆除后换站安装" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取消</el-button>
      <el-button
        type="danger"
        :loading="submitting"
        :disabled="!eligibleItems.length"
        @click="submit"
      >
        确认拆除
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { stockApi } from '@/api/stock'
import { getApiErrorMessage } from '@/utils/apiError'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  initialSns: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue', 'done'])

const snText = ref('')
const reason = ref('')
const previewItems = ref([])
const previewing = ref(false)
const submitting = ref(false)

const eligibleItems = computed(() => previewItems.value.filter(item => item.eligible))

const INSPECTION_STATUS_LABELS = {
  draft: '草稿',
  in_progress: '进行中',
  submitted: '已提交',
  under_review: '审核中',
  approved: '已通过',
  rejected: '已驳回',
  completed: '已完成',
  voided: '已作废',
}
const inspectionStatusLabel = (status) => INSPECTION_STATUS_LABELS[String(status || '').toLowerCase()] || '-'

const parseSns = () => [...new Set(
  String(snText.value || '').split(/[\s,，]+/).map(s => s.trim()).filter(Boolean),
)]

const handleOpen = () => {
  snText.value = (props.initialSns || []).join('\n')
  reason.value = ''
  previewItems.value = []
  if (props.initialSns?.length) runPreview()
}

const runPreview = async () => {
  const sns = parseSns()
  if (!sns.length) {
    ElMessage.warning('请填写设备SN')
    return
  }
  try {
    previewing.value = true
    const res = await stockApi.previewDismantle({ sns })
    previewItems.value = res?.items || []
  } catch (e) {
    console.error(e)
    ElMessage.error(getApiErrorMessage(e, '预览失败'))
  } finally {
    previewing.value = false
  }
}

const submit = async () => {
  const sns = eligibleItems.value.map(item => item.sn)
  if (!sns.length) return
  if (!reason.value.trim()) {
    ElMessage.warning('请填写拆除原因')
    return
  }
  const skipped = previewItems.value.length - sns.length
  try {
    await ElMessageBox.confirm(
      skipped > 0
        ? `将拆除 ${sns.length} 台设备，另有 ${skipped} 台不满足条件将跳过。确认继续？`
        : `将拆除 ${sns.length} 台设备，确认继续？`,
      '确认拆除',
      { type: 'warning', confirmButtonText: '确认拆除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    submitting.value = true
    const res = await stockApi.dismantleEquipment({ sns, reason: reason.value.trim() })
    ElMessage.success(`已拆除 ${res?.dismantled_count ?? sns.length} 台设备`)
    emit('update:modelValue', false)
    emit('done', res)
  } catch (e) {
    console.error(e)
    ElMessage.error(getApiErrorMessage(e, '拆除失败'))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.dismantle-tip { margin-bottom: 16px; }
.dismantle-summary { margin-left: 12px; color: var(--el-text-color-secondary); }
.dismantle-reason { margin-top: 16px; }
</style>
