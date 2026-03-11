<template>
  <div class="page workorder-execute-page" v-loading="pageLoading">
    <div class="page-header">
      <div>
        <h1>工单执行台</h1>
        <div class="page-subtitle">{{ pageSubtitle }}</div>
      </div>
      <div class="header-actions">
        <el-button @click="goBack">返回我的执行工单</el-button>
        <el-button @click="loadPage"><el-icon><Refresh /></el-icon>刷新</el-button>
      </div>
    </div>

    <el-result
      v-if="pageError"
      icon="warning"
      title="执行页不可用"
      :sub-title="pageError"
    >
      <template #extra>
        <el-button type="primary" @click="goBack">返回我的执行工单</el-button>
      </template>
    </el-result>

    <template v-else-if="order">
      <el-card class="hero-card mb16">
        <div class="hero-card__main">
          <div class="hero-card__left">
            <div class="hero-card__eyebrow">{{ typeText(order.type) }}</div>
            <div class="hero-card__title-row">
              <h2>{{ order.title }}</h2>
              <el-tag :type="workOrderStatusTagType(order.status)">{{ statusText(order.status) }}</el-tag>
            </div>
            <div class="hero-card__meta">
              <span>站点：{{ order.site_name || order.site_code || order.site_id }}</span>
              <span>执行人：{{ order.assignee_name || '-' }}</span>
              <span>截止：{{ formatDateTime(order.due_date) || '未设置' }}</span>
            </div>
            <div class="hero-card__progress">
              <div class="hero-card__progress-label">
                <span>执行进度</span>
                <strong>{{ `${Math.round(progressPercent)}%` }}</strong>
              </div>
              <el-progress :percentage="progressPercent" :stroke-width="10" />
            </div>
            <div class="hero-card__flags">
              <el-tag v-if="permissions.is_readonly_type" type="info" effect="plain">该类型仅支持 App 执行</el-tag>
              <el-tag v-if="!effectiveSettings.allow_photo_upload" type="info" effect="plain">照片上传已关闭</el-tag>
              <el-tag
                v-if="effectiveSettings.allow_photo_upload"
                :type="localUploadPolicyHint.type"
                effect="plain"
              >
                无定位上传：{{ localUploadPolicyHint.text }}
              </el-tag>
              <el-tag v-if="!effectiveSettings.allow_device_binding" type="info" effect="plain">设备绑定已关闭</el-tag>
              <el-tag v-if="!effectiveSettings.allow_submit" type="warning" effect="plain">仅允许补录，不允许提交</el-tag>
              <el-tag v-if="!effectiveSettings.allow_recall" type="info" effect="plain">撤回已关闭</el-tag>
            </div>
          </div>

          <div class="hero-card__right">
            <div class="hero-card__stat">
              <span>检查项</span>
              <strong>{{ items.length }}</strong>
            </div>
            <div class="hero-card__stat">
              <span>已完成</span>
              <strong>{{ completedCount }}</strong>
            </div>
            <div class="hero-card__stat">
              <span>待处理</span>
              <strong>{{ pendingCount }}</strong>
            </div>
            <div class="hero-card__actions">
              <el-button
                v-if="permissions.can_accept"
                type="primary"
                :loading="accepting"
                @click="acceptWorkOrder"
              >
                接受工单
              </el-button>
              <el-button
                v-if="permissions.can_submit"
                type="primary"
                :disabled="items.length === 0"
                :loading="submitting"
                @click="openSubmitDialog"
              >
                提交工单
              </el-button>
              <el-button
                v-if="permissions.can_recall"
                type="warning"
                plain
                :loading="recalling"
                @click="recallWorkOrder"
              >
                撤回工单
              </el-button>
            </div>
          </div>
        </div>
      </el-card>

      <el-alert
        v-if="permissions.is_readonly_type"
        class="mb16"
        type="info"
        show-icon
        :closable="false"
        title="该工单类型在 Web 端仅可查看"
        description="接受工单、填写检查项、上传照片、绑定设备和提交工单都需要在 App 端完成。"
      />

      <el-alert
        v-if="order.status === 'REJECTED' && order.review_comments"
        class="mb16"
        type="error"
        show-icon
        :closable="false"
        title="工单已驳回，请按驳回意见修改后重新提交"
        :description="order.review_comments"
      />

      <el-alert
        v-if="order.status === 'VOIDED'"
        class="mb16"
        type="warning"
        show-icon
        :closable="false"
        title="该工单已作废"
        :description="order.void_reason || '已作废工单不可继续填写。'"
      />

      <el-alert
        v-if="inspectionMissingButShouldExist"
        class="mb16"
        type="warning"
        show-icon
        :closable="false"
        :title="inspectionMissingAlert.title"
        :description="inspectionMissingAlert.description"
      />

      <div class="execute-layout">
        <el-card class="execute-sidebar">
          <template #header>
            <div class="sidebar-header">
              <span>检查项导航</span>
              <el-radio-group v-model="itemFilter" size="small">
                <el-radio-button label="all">全部</el-radio-button>
                <el-radio-button label="todo">未完成</el-radio-button>
                <el-radio-button label="photo">缺照片</el-radio-button>
                <el-radio-button label="binding">待绑定</el-radio-button>
              </el-radio-group>
            </div>
          </template>

          <el-scrollbar class="sidebar-scroll" max-height="var(--sidebar-scroll-max-height)">
            <div v-for="group in groupedItems" :key="group.key" class="sidebar-group">
              <div class="sidebar-group__title">
                <span>{{ group.label }}</span>
                <el-tag size="small" effect="plain">{{ group.completed }}/{{ group.items.length }}</el-tag>
              </div>
              <button
                v-for="item in group.items"
                :key="item.id"
                class="item-nav-card"
                :class="{ 'item-nav-card--active': item.id === selectedItemId }"
                @click="selectItem(item.id)"
              >
                <div class="item-nav-card__head">
                  <span>{{ item.item_name }}</span>
                  <el-tag size="small" :type="itemStatusTagType(item.status)">{{ itemStatusText(item.status) }}</el-tag>
                </div>
                <div class="item-nav-card__meta">
                  <span v-if="item.sector_id">S{{ item.sector_id }} / {{ item.band || '-' }}</span>
                  <span v-if="item.required_type">{{ requiredTypeText(item.required_type) }}</span>
                </div>
                <div class="item-nav-card__flags">
                  <span v-if="item.photos?.length">图 {{ item.photos.length }}</span>
                  <span v-if="item.equipment_sn">SN 已绑</span>
                  <span v-else-if="isDeviceSlotItem(item)">待绑</span>
                </div>
              </button>
            </div>
            <el-empty v-if="!groupedItems.length" description="暂无可展示的检查项" />
          </el-scrollbar>
        </el-card>

        <div class="execute-main">
          <el-card v-if="selectedItem" class="mb16">
            <template #header>
              <div class="editor-header">
                <div>
                  <div class="editor-title">{{ selectedItem.item_name }}</div>
                  <div class="editor-subtitle">
                    <span>{{ selectedItem.category_name || '未分类' }}</span>
                    <span v-if="selectedItem.sector_id">S{{ selectedItem.sector_id }} / {{ selectedItem.band || '-' }}</span>
                    <span v-if="selectedItem.cell_id">Cell {{ selectedItem.cell_id }}</span>
                  </div>
                </div>
                <el-tag :type="itemStatusTagType(selectedItem.status)">{{ itemStatusText(selectedItem.status) }}</el-tag>
              </div>
            </template>

            <div v-if="selectedItem.description" class="item-description">
              {{ selectedItem.description }}
            </div>

            <el-form label-position="top" class="item-form" :disabled="!canEditCurrentItem">
              <div v-if="visibleFields.length" class="field-grid">
                <el-form-item
                  v-for="field in visibleFields"
                  :key="field.field_id"
                  :label="field.label"
                  :required="Boolean(field.required)"
                >
                  <template v-if="field.type === 'text'">
                    <el-input
                      :model-value="fieldValue(field.field_id)"
                      :placeholder="field.placeholder || `请输入${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'rich_text'">
                    <el-input
                      type="textarea"
                      :rows="4"
                      :model-value="fieldValue(field.field_id)"
                      :placeholder="field.placeholder || `请输入${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'number'">
                    <el-input
                      :model-value="fieldValue(field.field_id)"
                      type="number"
                      :placeholder="field.placeholder || `请输入${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'boolean'">
                    <el-switch
                      :model-value="Boolean(fieldValue(field.field_id))"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'select_single'">
                    <el-select
                      :model-value="fieldValue(field.field_id)"
                      clearable
                      style="width: 100%"
                      :placeholder="field.placeholder || `请选择${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    >
                      <el-option
                        v-for="option in field.options || []"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </template>
                  <template v-else-if="field.type === 'select_multi'">
                    <el-select
                      :model-value="Array.isArray(fieldValue(field.field_id)) ? fieldValue(field.field_id) : []"
                      multiple
                      clearable
                      filterable
                      collapse-tags
                      collapse-tags-tooltip
                      style="width: 100%"
                      :placeholder="field.placeholder || `请选择${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    >
                      <el-option
                        v-for="option in field.options || []"
                        :key="option.value"
                        :label="option.label"
                        :value="option.value"
                      />
                    </el-select>
                  </template>
                  <template v-else-if="field.type === 'date'">
                    <el-date-picker
                      :model-value="fieldValue(field.field_id)"
                      type="date"
                      value-format="YYYY-MM-DD"
                      style="width: 100%"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'time'">
                    <el-time-picker
                      :model-value="fieldValue(field.field_id)"
                      value-format="HH:mm:ss"
                      style="width: 100%"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else-if="field.type === 'datetime'">
                    <el-date-picker
                      :model-value="fieldValue(field.field_id)"
                      type="datetime"
                      value-format="YYYY-MM-DDTHH:mm:ss"
                      style="width: 100%"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <template v-else>
                    <el-input
                      :model-value="fieldValue(field.field_id)"
                      :placeholder="field.placeholder || `请输入${field.label}`"
                      @update:model-value="value => updateFieldValue(field.field_id, value)"
                    />
                  </template>
                  <div v-if="field.help_text" class="field-help">{{ field.help_text }}</div>
                </el-form-item>
              </div>
              <el-empty
                v-else
                description="当前检查项没有可填写字段，若需要可直接上传照片或填写备注。"
              />

              <el-form-item label="备注">
                <el-input
                  v-model="editorNotes"
                  type="textarea"
                  :rows="3"
                  placeholder="可填写补充说明、现场异常或驳回修正说明"
                />
              </el-form-item>
            </el-form>

            <div class="editor-actions">
              <el-button
                v-if="canEditCurrentItem"
                :loading="itemSaving === 'draft'"
                @click="saveSelectedItem('in_progress')"
              >
                保存草稿
              </el-button>
              <el-button
                v-if="canEditCurrentItem"
                type="primary"
                :loading="itemSaving === 'completed'"
                @click="saveSelectedItem('completed')"
              >
                {{ selectedItem.status === 'completed' ? '更新并保持完成' : '保存并标记完成' }}
              </el-button>
            </div>
          </el-card>

          <el-card v-if="selectedItem" class="mb16">
            <template #header>
              <div class="card-header">
                <span>现场照片</span>
                <span class="hint">支持字段照片与检查项照片共存，仍然写入同一套检查图片数据。</span>
              </div>
            </template>

            <div class="photo-section-grid">
              <div v-for="section in photoSections" :key="section.key" class="photo-section">
                <div class="photo-section__header">
                  <div>
                    <div class="photo-section__title">
                      {{ section.label }}
                      <el-tag v-if="section.required" size="small" type="danger" effect="plain">必拍</el-tag>
                    </div>
                    <div class="hint">{{ photoList(section).length }} 张</div>
                  </div>
                  <el-button
                    v-if="canUploadPhoto"
                    type="primary"
                    text
                    :loading="photoUploadingKey === section.key"
                    @click="triggerPhotoUpload(section)"
                  >
                    上传照片
                  </el-button>
                </div>

                <div v-if="photoList(section).length" class="photo-grid">
                  <div v-for="photo in photoList(section)" :key="photo.id" class="photo-card">
                    <el-image
                      class="photo-card__image"
                      :src="resolveImageUrl(photo.file_path)"
                      :preview-src-list="[resolveImageUrl(photo.file_path)]"
                      preview-teleported
                      fit="cover"
                    />
                    <div class="photo-card__meta">
                      <div class="photo-card__name">{{ photo.original_name }}</div>
                      <div class="hint">{{ formatFileSize(photo.file_size) }} · {{ formatDateTime(photo.taken_at) }}</div>
                    </div>
                    <div class="photo-card__actions">
                      <el-button
                        v-if="canUploadPhoto"
                        type="danger"
                        text
                        size="small"
                        @click="removePhoto(photo)"
                      >
                        删除
                      </el-button>
                    </div>
                  </div>
                </div>
                <el-empty v-else description="暂无照片" />
              </div>
            </div>
          </el-card>

          <el-card v-if="selectedItem && isDeviceSlotItem(selectedItem)" class="mb16">
            <template #header>
              <div class="card-header">
                <span>设备绑定</span>
                <span class="hint">按扇区 + 频段绑定，修改后 Web 与 App 会读取同一设备绑定结果。</span>
              </div>
            </template>

            <el-descriptions :column="2" border size="small" class="mb16">
              <el-descriptions-item label="设备位">S{{ selectedItem.sector_id }} / {{ selectedItem.band || '-' }}</el-descriptions-item>
              <el-descriptions-item label="当前绑定">{{ selectedItem.equipment_sn || '未绑定' }}</el-descriptions-item>
            </el-descriptions>

            <div v-if="canBindEquipment" class="binding-panel">
              <el-select
                v-model="equipmentSelection"
                filterable
                remote
                clearable
                allow-create
                default-first-option
                :remote-method="searchEquipmentOptions"
                :loading="equipmentLoading"
                style="width: 360px"
                placeholder="搜索或输入设备 SN"
              >
                <el-option
                  v-for="option in equipmentOptions"
                  :key="option.value"
                  :label="option.label"
                  :value="option.value"
                />
              </el-select>
              <el-button type="primary" :loading="bindingLoading" @click="bindEquipment">绑定设备</el-button>
              <el-button
                v-if="selectedItem.equipment_sn"
                type="danger"
                plain
                :loading="bindingLoading"
                @click="unbindEquipment"
              >
                解绑设备
              </el-button>
            </div>
            <div v-else class="hint">当前账号在 Web 端不能修改设备绑定。</div>
          </el-card>

          <el-card v-if="order.type === 'equipment_replacement' && replacementHistory.length" class="mb16">
            <template #header>
              <div class="card-header">
                <span>换机记录</span>
              </div>
            </template>
            <el-table :data="replacementHistory" size="small" stripe>
              <el-table-column label="时间" min-width="160">
                <template #default="{ row }">{{ formatDateTime(row.replaced_at) }}</template>
              </el-table-column>
              <el-table-column label="设备位" width="160">
                <template #default="{ row }">S{{ row.sector_id }} / {{ row.band || '-' }}</template>
              </el-table-column>
              <el-table-column prop="old_sn" label="旧 SN" min-width="180" />
              <el-table-column prop="new_sn" label="新 SN" min-width="180" />
            </el-table>
          </el-card>

          <el-empty v-if="!selectedItem && items.length" description="请先从左侧选择一个检查项" />
        </div>
      </div>

      <input
        ref="photoInputRef"
        class="hidden-input"
        type="file"
        accept="image/*"
        @change="handlePhotoFileChange"
      />

      <el-dialog v-model="submitDialogVisible" title="提交前检查" width="680px">
        <div class="submit-summary">
          <div class="submit-summary__row">
            <span>未完成检查项</span>
            <strong>{{ submitChecks.incomplete.length }}</strong>
          </div>
          <div class="submit-summary__row">
            <span>缺设备绑定</span>
            <strong>{{ submitChecks.missingBindings.length }}</strong>
          </div>
          <div class="submit-summary__row">
            <span>缺必拍照片</span>
            <strong>{{ submitChecks.missingPhotos.length }}</strong>
          </div>
        </div>

        <el-alert
          v-if="submitChecks.incomplete.length"
          type="warning"
          show-icon
          :closable="false"
          :title="`还有 ${submitChecks.incomplete.length} 个检查项未完成，当前不能提交。`"
        />
        <el-alert
          v-else
          type="success"
          show-icon
          :closable="false"
          title="所有检查项已完成，可以提交工单。"
        />

        <div v-if="submitChecks.incomplete.length" class="mt16">
          <div class="dialog-section-title">未完成项</div>
          <el-space wrap>
            <el-tag v-for="item in submitChecks.incomplete" :key="item.id" effect="plain">{{ item.item_name }}</el-tag>
          </el-space>
        </div>

        <div v-if="submitChecks.missingBindings.length" class="mt16">
          <div class="dialog-section-title">仍未绑定设备</div>
          <el-space wrap>
            <el-tag v-for="item in submitChecks.missingBindings" :key="item.id" type="warning" effect="plain">
              {{ item.item_name }}
            </el-tag>
          </el-space>
        </div>

        <div v-if="submitChecks.missingPhotos.length" class="mt16">
          <div class="dialog-section-title">缺必拍照片</div>
          <el-space wrap>
            <el-tag v-for="item in submitChecks.missingPhotos" :key="item.id" type="danger" effect="plain">
              {{ item.item_name }}
            </el-tag>
          </el-space>
        </div>

        <template #footer>
          <el-button @click="submitDialogVisible = false">关闭</el-button>
          <el-button
            type="primary"
            :disabled="submitChecks.incomplete.length > 0"
            :loading="submitting"
            @click="confirmSubmit"
          >
            确认提交
          </el-button>
        </template>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { stockApi } from '@/api/stock'
import { inspectionExecutionApi, workOrderAPI } from '@/api/workorder'
import { useUserStore } from '@/stores/user'
import { resolveImageUrl } from '@/utils/imageLoader'
import {
  buildFieldValueMap,
  buildLocalUploadWatermarkFile,
  computeFileSha256,
  formatFileSize,
  getPhotoFieldSections,
  isDeviceSlotItem,
  isFieldVisible,
  isPhotoRequirementSatisfied,
  serializeDataValue,
} from '@/utils/workOrderExecute'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()

const pageLoading = ref(false)
const pageError = ref('')
const accepting = ref(false)
const recalling = ref(false)
const submitting = ref(false)
const itemSaving = ref('')
const bindingLoading = ref(false)
const equipmentLoading = ref(false)
const photoUploadingKey = ref('')

const context = ref(null)
const items = ref([])
const itemFilter = ref('all')
const selectedItemId = ref('')
const editorFieldValues = ref({})
const editorNotes = ref('')

const equipmentOptions = ref([])
const equipmentSelection = ref('')
const submitDialogVisible = ref(false)
const photoInputRef = ref(null)
const pendingPhotoSection = ref(null)
const cachedGeo = ref(null)

const workOrderId = computed(() => String(route.params.id || ''))
const order = computed(() => context.value?.work_order || null)
const inspection = computed(() => context.value?.inspection || null)
const permissions = computed(() => context.value?.permissions || {})
const effectiveSettings = computed(() => context.value?.effective_settings || {})
const progressInfo = computed(() => context.value?.progress || {})
const progressPercent = computed(() => Number(progressInfo.value?.progress || inspection.value?.completion_rate || 0))
const LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY = 'deny'
const LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK = 'allow_with_watermark'
const LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK = 'allow_without_watermark'

const normalizeLocalUploadWithoutGeoPolicy = (value, fallback = LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY) => {
  const text = String(value || '').trim()
  if (text === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK) return text
  if (text === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK) return text
  if (text === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY) return text
  return fallback
}

const localUploadWithoutGeoPolicy = computed(() => normalizeLocalUploadWithoutGeoPolicy(
  effectiveSettings.value?.local_upload_without_geo_policy,
  effectiveSettings.value?.allow_local_upload_without_geo
    ? LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK
    : LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY,
))

const localUploadPolicyHint = computed(() => {
  const policy = localUploadWithoutGeoPolicy.value
  if (policy === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK) {
    return { type: 'warning', text: '允许，且必须加水印' }
  }
  if (policy === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITHOUT_WATERMARK) {
    return { type: 'success', text: '允许，原图直传' }
  }
  return { type: 'info', text: '禁止' }
})
const pageSubtitle = computed(() => {
  if (permissions.value?.is_readonly_type) {
    return '该工单类型仅支持在 App 端接受和执行，Web 端当前只用于查看工单进度、检查结果和历史照片。'
  }
  return 'Web 端可接受、填写、上传现场照片并提交工单，所有数据仍与 App 共用同一套检查记录。'
})

const selectedItem = computed(() => items.value.find(item => item.id === selectedItemId.value) || null)
const completedCount = computed(() => items.value.filter(item => item.status === 'completed').length)
const pendingCount = computed(() => items.value.length - completedCount.value)
const inspectionMissingButShouldExist = computed(() => {
  if (!order.value) return false
  return order.value.status !== 'PENDING' && !inspection.value?.inspection_id
})
const inspectionMissingAlert = computed(() => {
  if (permissions.value?.is_readonly_type) {
    return {
      title: '当前还没有可供 Web 查看的检查记录',
      description: '该工单类型只能在 App 端接受和填写。请先在 App 完成接受后，再回到 Web 查看当前进度。',
    }
  }
  return {
    title: '当前工单缺少关联检查实例',
    description: '请先接受工单；如果工单已经处于已分配状态但仍未生成检查记录，请联系管理员处理历史数据。',
  }
})

const canEditCurrentItem = computed(() => {
  if (!selectedItem.value) return false
  if (!permissions.value?.can_edit) return false
  return true
})

const canUploadPhoto = computed(() => canEditCurrentItem.value && Boolean(effectiveSettings.value?.allow_photo_upload))
const canBindEquipment = computed(() => canEditCurrentItem.value && Boolean(effectiveSettings.value?.allow_device_binding))

const replacementHistory = computed(() => {
  const raw = order.value?.extra_data?.replacement_history
  return Array.isArray(raw) ? raw : []
})

const visibleFields = computed(() => {
  const fields = Array.isArray(selectedItem.value?.fields) ? selectedItem.value.fields : []
  return fields.filter(field => isFieldVisible(field, editorFieldValues.value))
})

const photoSections = computed(() => getPhotoFieldSections(selectedItem.value, editorFieldValues.value))

const groupedItems = computed(() => {
  const groups = []
  const filtered = items.value.filter((item) => {
    if (itemFilter.value === 'todo') return item.status !== 'completed'
    if (itemFilter.value === 'photo') {
      return (item.required_type === 'photo' || item.required_type === 'both')
        && !isPhotoRequirementSatisfied(item, buildFieldValueMap(item.data_value))
    }
    if (itemFilter.value === 'binding') return isDeviceSlotItem(item) && !item.equipment_sn
    return true
  })

  filtered.forEach((item) => {
    const key = String(item.category_id || item.category_name || 'default')
    let group = groups.find(entry => entry.key === key)
    if (!group) {
      group = {
        key,
        label: item.category_name || '未分类',
        items: [],
        completed: 0,
      }
      groups.push(group)
    }
    group.items.push(item)
    if (item.status === 'completed') group.completed += 1
  })

  return groups
})

const submitChecks = computed(() => {
  const incomplete = []
  const missingBindings = []
  const missingPhotos = []

  items.value.forEach((item) => {
    const itemValues = buildFieldValueMap(item.data_value)
    if (item.status !== 'completed') incomplete.push(item)
    if (isDeviceSlotItem(item) && !item.equipment_sn) missingBindings.push(item)
    if ((item.required_type === 'photo' || item.required_type === 'both') && !isPhotoRequirementSatisfied(item, itemValues)) {
      missingPhotos.push(item)
    }
  })

  return { incomplete, missingBindings, missingPhotos }
})

const workOrderStatusTagType = (status) => {
  if (status === 'COMPLETED' || status === 'APPROVED' || status === 'ACTIVATED') return 'success'
  if (status === 'REJECTED') return 'danger'
  if (status === 'UNDER_REVIEW') return 'warning'
  if (status === 'VOIDED') return 'info'
  return 'primary'
}

const itemStatusTagType = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'in_progress') return 'warning'
  return 'info'
}

const itemStatusText = (status) => ({
  pending: '待处理',
  in_progress: '填写中',
  completed: '已完成',
  failed: '失败',
  skipped: '跳过',
}[status] || status)

const statusText = (status) => ({
  PENDING: '待分配',
  ACTIVE: '已分配',
  SUBMITTED: '已提交',
  UNDER_REVIEW: '审核中',
  APPROVED: '已通过',
  ACTIVATED: '已激活',
  REJECTED: '已驳回',
  COMPLETED: '已完成',
  VOIDED: '已作废',
}[status] || status)

const typeText = (type) => ({
  site_survey: '站点勘查',
  opening_inspection: '新站安装',
  equipment_replacement: '设备更换',
  ssv: 'SSV 验收',
  maintenance: '维护检查',
  power_issue: '断电问题',
  transmission_issue: '传输问题',
  gps_issue: 'GPS问题',
  signal_issue: '信号问题',
}[type] || type)

const requiredTypeText = (type) => ({
  photo: '仅照片',
  data: '仅数据',
  both: '照片 + 数据',
}[type] || type)

const formatDateTime = (value) => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

const selectItem = (itemId) => {
  selectedItemId.value = itemId
}

const syncEditorFromItem = (item) => {
  if (!item) {
    editorFieldValues.value = {}
    editorNotes.value = ''
    equipmentSelection.value = ''
    return
  }
  editorFieldValues.value = buildFieldValueMap(item.data_value)
  editorNotes.value = item.notes || ''
  equipmentSelection.value = item.equipment_sn || ''
}

const ensureSelectedItem = () => {
  if (selectedItemId.value && items.value.some(item => item.id === selectedItemId.value)) return
  selectedItemId.value = items.value[0]?.id || ''
}

const loadItems = async (inspectionId) => {
  if (!inspectionId) {
    items.value = []
    selectedItemId.value = ''
    return
  }
  items.value = await inspectionExecutionApi.getInspectionItems(inspectionId)
  ensureSelectedItem()
}

const loadPage = async () => {
  if (!workOrderId.value) {
    pageError.value = '缺少工单 ID'
    return
  }

  pageLoading.value = true
  pageError.value = ''
  try {
    context.value = await workOrderAPI.getExecutionContext(workOrderId.value)
    const inspectionId = context.value?.inspection?.inspection_id
    await loadItems(inspectionId)
    syncEditorFromItem(selectedItem.value)
  } catch (error) {
    console.error(error)
    pageError.value = error.response?.data?.detail || '加载工单执行页失败'
  } finally {
    pageLoading.value = false
  }
}

const goBack = () => {
  router.push({ name: 'MyExecutionWorkOrders' })
}

const acceptWorkOrder = async () => {
  accepting.value = true
  try {
    await workOrderAPI.acceptWorkOrder(workOrderId.value)
    ElMessage.success('工单已接受，可以开始填写')
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '接受工单失败')
  } finally {
    accepting.value = false
  }
}

const recallWorkOrder = async () => {
  recalling.value = true
  try {
    await workOrderAPI.recallWorkOrder(workOrderId.value)
    ElMessage.success('工单已撤回，可继续编辑')
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '撤回工单失败')
  } finally {
    recalling.value = false
  }
}

const openSubmitDialog = () => {
  submitDialogVisible.value = true
}

const confirmSubmit = async () => {
  submitting.value = true
  try {
    await workOrderAPI.submitWorkOrder(workOrderId.value)
    submitDialogVisible.value = false
    ElMessage.success('工单已提交')
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '提交工单失败')
  } finally {
    submitting.value = false
  }
}

const fieldValue = (fieldId) => editorFieldValues.value?.[fieldId]

const updateFieldValue = (fieldId, value) => {
  editorFieldValues.value = {
    ...editorFieldValues.value,
    [fieldId]: value,
  }
}

const extractApiErrorMessage = (error, fallback = '操作失败') => {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item) return ''
        if (typeof item === 'string') return item
        const path = Array.isArray(item.loc) ? item.loc.join('.') : ''
        const message = item.msg || item.message || ''
        if (path && message) return `${path}: ${message}`
        return message || path
      })
      .filter(Boolean)
    if (parts.length) return parts.join('；')
  }
  if (typeof detail === 'string' && detail.trim()) return detail
  if (detail && typeof detail === 'object') {
    const objectMessage = detail.message || detail.error || detail.detail
    if (typeof objectMessage === 'string' && objectMessage.trim()) return objectMessage
  }
  if (typeof error?.message === 'string' && error.message.trim()) return error.message
  return fallback
}

const saveSelectedItem = async (targetStatus) => {
  if (!selectedItem.value || !inspection.value?.inspection_id) return
  itemSaving.value = targetStatus
  try {
    const payload = {
      status: targetStatus,
      notes: editorNotes.value || null,
      data_value: serializeDataValue(selectedItem.value.fields, editorFieldValues.value),
    }
    await inspectionExecutionApi.updateInspectionItem(
      inspection.value.inspection_id,
      selectedItem.value.id,
      payload,
    )
    ElMessage.success(targetStatus === 'completed' ? '检查项已保存并标记完成' : '检查项已保存')
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(extractApiErrorMessage(error, '保存检查项失败'))
  } finally {
    itemSaving.value = ''
  }
}

const photoList = (section) => {
  const photos = Array.isArray(selectedItem.value?.photos) ? selectedItem.value.photos : []
  if (!section?.fieldId) return photos.filter(photo => !photo.field_id)
  return photos.filter(photo => String(photo.field_id || '') === section.fieldId)
}

const triggerPhotoUpload = (section) => {
  pendingPhotoSection.value = section
  if (photoInputRef.value) photoInputRef.value.click()
}

const resolveCurrentLocation = async () => {
  const cached = cachedGeo.value
  if (cached && (Date.now() - cached.timestamp) < 60 * 1000) return cached.value

  if (!navigator.geolocation) throw new Error('当前浏览器不支持定位')

  const position = await new Promise((resolve, reject) => {
    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 12000,
      maximumAge: 30000,
    })
  })

  const value = {
    latitude: Number(position.coords.latitude),
    longitude: Number(position.coords.longitude),
    accuracy: Number(position.coords.accuracy || 0),
  }
  cachedGeo.value = { timestamp: Date.now(), value }
  return value
}

const buildLocalUploadWatermarkLines = () => {
  const now = formatDateTime(new Date())
  return [
    '本地上传照片',
    now,
    `执行人: ${userStore.currentUser?.full_name || userStore.currentUser?.username || '未知用户'}`,
    `站点: ${order.value?.site_name || order.value?.site_code || order.value?.site_id || '-'}`,
    `检查项: ${selectedItem.value?.item_name || '-'}`,
  ]
}

const describeUploadBlock = (detail) => {
  if (!detail) return '上传被系统阻断'
  if (typeof detail === 'string') return detail
  return detail.message || detail.detail || '上传被系统阻断'
}

const handlePhotoFileChange = async (event) => {
  const file = event.target?.files?.[0]
  if (!file || !selectedItem.value || !inspection.value?.inspection_id || !pendingPhotoSection.value) return

  const section = pendingPhotoSection.value
  photoUploadingKey.value = section.key
  try {
    const originalHash = await computeFileSha256(file)
    const precheck = await inspectionExecutionApi.precheckPhotoUpload(inspection.value.inspection_id, {
      check_item_id: selectedItem.value.id,
      field_id: section.fieldId || null,
      original_content_hash: originalHash,
    })
    if (precheck?.should_block) {
      throw new Error(describeUploadBlock(precheck?.duplicate_warning))
    }

    let uploadFile = file
    let localUploadWithoutGeo = false
    let hasFrontendWatermark = false
    let location

    try {
      location = await resolveCurrentLocation()
    } catch (geoError) {
      const policy = localUploadWithoutGeoPolicy.value
      if (policy === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_DENY) {
        throw new Error('浏览器定位不可用，且当前策略禁止无定位上传')
      }
      localUploadWithoutGeo = true
      if (policy === LOCAL_UPLOAD_WITHOUT_GEO_POLICY_ALLOW_WITH_WATERMARK) {
        uploadFile = await buildLocalUploadWatermarkFile(file, buildLocalUploadWatermarkLines())
        hasFrontendWatermark = true
      }
    }

    const formData = new FormData()
    formData.append('file', uploadFile)
    formData.append('check_item_id', selectedItem.value.id)
    if (section.fieldId) formData.append('field_id', section.fieldId)
    formData.append('has_watermark', hasFrontendWatermark ? 'true' : 'false')
    formData.append('local_upload_without_geo', localUploadWithoutGeo ? 'true' : 'false')
    formData.append('original_content_hash', originalHash)
    formData.append('upload_ticket', precheck?.upload_ticket || '')

    if (localUploadWithoutGeo) {
      formData.append('gps_latitude', '0')
      formData.append('gps_longitude', '0')
    } else {
      formData.append('gps_latitude', String(location.latitude))
      formData.append('gps_longitude', String(location.longitude))
      formData.append('gps_accuracy', String(location.accuracy || 0))
    }

    const response = await inspectionExecutionApi.uploadPhoto(inspection.value.inspection_id, formData)
    if (response?.duplicate_warning) {
      ElMessage.warning(describeUploadBlock(response.duplicate_warning))
    } else if (response?.similar_warning) {
      ElMessage.warning(describeUploadBlock(response.similar_warning))
    } else {
      ElMessage.success('照片上传成功')
    }
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.message || error.response?.data?.detail || '上传照片失败')
  } finally {
    photoUploadingKey.value = ''
    pendingPhotoSection.value = null
    if (event.target) event.target.value = ''
  }
}

const removePhoto = async (photo) => {
  try {
    await ElMessageBox.confirm('删除后该照片将立即从工单和检查记录中移除，是否继续？', '删除照片', {
      type: 'warning',
    })
    await inspectionExecutionApi.deletePhoto(photo.id)
    ElMessage.success('照片已删除')
    await loadPage()
  } catch (error) {
    if (error === 'cancel') return
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '删除照片失败')
  }
}

const searchEquipmentOptions = async (keyword) => {
  const sn = String(keyword || '').trim()
  if (!sn) {
    equipmentOptions.value = []
    return
  }
  equipmentLoading.value = true
  try {
    const response = await stockApi.searchEquipmentInstancesBySn({ sn, limit: 20 })
    equipmentOptions.value = (response?.instances || []).map((item) => ({
      value: item.serial_number,
      label: `${item.serial_number} · ${item.status || 'unknown'}`,
    }))
  } catch (error) {
    console.error(error)
    equipmentOptions.value = []
  } finally {
    equipmentLoading.value = false
  }
}

const bindEquipment = async () => {
  if (!selectedItem.value || !inspection.value?.inspection_id) return
  const sn = String(equipmentSelection.value || '').trim()
  if (!sn) {
    ElMessage.warning('请先选择或输入设备 SN')
    return
  }
  bindingLoading.value = true
  try {
    await inspectionExecutionApi.bindEquipment(inspection.value.inspection_id, {
      equipment_sn: sn,
      sector_id: selectedItem.value.sector_id,
      band: selectedItem.value.band,
    })
    ElMessage.success(`设备 ${sn} 已绑定`)
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '绑定设备失败')
  } finally {
    bindingLoading.value = false
  }
}

const unbindEquipment = async () => {
  if (!selectedItem.value || !inspection.value?.inspection_id) return
  bindingLoading.value = true
  try {
    await inspectionExecutionApi.bindEquipment(inspection.value.inspection_id, {
      equipment_sn: '',
      sector_id: selectedItem.value.sector_id,
      band: selectedItem.value.band,
    })
    ElMessage.success('设备已解绑')
    await loadPage()
  } catch (error) {
    console.error(error)
    ElMessage.error(error.response?.data?.detail || '解绑设备失败')
  } finally {
    bindingLoading.value = false
  }
}

watch(
  () => selectedItem.value?.id,
  () => {
    syncEditorFromItem(selectedItem.value)
  },
)

onMounted(() => {
  loadPage()
})
</script>

<style scoped>
.page {
  padding: 24px;
  box-sizing: border-box;
}

.workorder-execute-page {
  min-height: calc(100vh - 120px);
}

.page-subtitle {
  color: #909399;
  font-size: 13px;
  margin-top: 6px;
}

.header-actions {
  display: flex;
  gap: 12px;
}

.mb16 {
  margin-bottom: 16px;
}

.mt16 {
  margin-top: 16px;
}

.hint {
  color: #909399;
  font-size: 12px;
}

.hero-card {
  border: none;
  background:
    radial-gradient(circle at top left, rgba(34, 197, 94, 0.16), transparent 34%),
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.18), transparent 28%),
    linear-gradient(135deg, #ffffff 0%, #f7fbff 100%);
}

.hero-card__main {
  display: grid;
  grid-template-columns: minmax(0, 1.8fr) minmax(280px, 0.9fr);
  gap: 24px;
}

.hero-card__eyebrow {
  color: #0f766e;
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-weight: 700;
}

.hero-card__title-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 10px;
}

.hero-card__title-row h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
}

.hero-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  color: #606266;
  font-size: 13px;
  margin-top: 14px;
}

.hero-card__progress {
  margin-top: 18px;
}

.hero-card__progress-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  color: #303133;
}

.hero-card__flags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.hero-card__right {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-content: start;
}

.hero-card__stat {
  border: 1px solid #dce7f7;
  border-radius: 14px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.9);
}

.hero-card__stat span {
  display: block;
  color: #909399;
  font-size: 12px;
}

.hero-card__stat strong {
  display: block;
  font-size: 22px;
  margin-top: 6px;
}

.hero-card__actions {
  grid-column: 1 / -1;
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.execute-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 16px;
  align-items: start;
}

.execute-sidebar {
  position: sticky;
  top: 12px;
}

.sidebar-header {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sidebar-scroll {
  --sidebar-scroll-max-height: calc(100vh - 290px);
}

.sidebar-group + .sidebar-group {
  margin-top: 16px;
}

.sidebar-group__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  color: #606266;
  font-weight: 600;
}

.item-nav-card {
  width: 100%;
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 12px;
  text-align: left;
  background: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.item-nav-card + .item-nav-card {
  margin-top: 10px;
}

.item-nav-card:hover,
.item-nav-card--active {
  border-color: #7cc3ff;
  box-shadow: 0 10px 18px rgba(28, 87, 142, 0.08);
  transform: translateY(-1px);
}

.item-nav-card__head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.item-nav-card__meta,
.item-nav-card__flags {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 12px;
  font-size: 12px;
  color: #909399;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.editor-title {
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.editor-subtitle {
  margin-top: 8px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
  color: #606266;
  font-size: 13px;
}

.item-description {
  margin-bottom: 18px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #f7f9fc;
  color: #606266;
  line-height: 1.7;
}

.field-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0 16px;
}

.field-help {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.editor-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.photo-section-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.photo-section {
  border: 1px solid #ebeef5;
  border-radius: 14px;
  padding: 14px;
  background: #fcfdff;
}

.photo-section__header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.photo-section__title {
  font-weight: 600;
  color: #303133;
  display: flex;
  align-items: center;
  gap: 8px;
}

.photo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
}

.photo-card {
  border: 1px solid #ebeef5;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.photo-card__image {
  width: 100%;
  height: 140px;
  display: block;
}

.photo-card__meta {
  padding: 10px 12px 6px;
}

.photo-card__name {
  font-size: 13px;
  color: #303133;
  word-break: break-all;
}

.photo-card__actions {
  padding: 0 12px 10px;
}

.binding-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}

.submit-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.submit-summary__row {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #ebeef5;
  background: #f8fafc;
}

.submit-summary__row span {
  display: block;
  color: #909399;
  font-size: 12px;
}

.submit-summary__row strong {
  display: block;
  font-size: 22px;
  margin-top: 6px;
}

.dialog-section-title {
  font-weight: 600;
  margin-bottom: 10px;
}

.hidden-input {
  display: none;
}

@media (max-width: 1200px) {
  .execute-layout {
    grid-template-columns: 1fr;
  }

  .execute-sidebar {
    position: static;
  }

  .sidebar-scroll {
    --sidebar-scroll-max-height: none;
  }
}

@media (max-width: 900px) {
  .page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .header-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .hero-card__main {
    grid-template-columns: 1fr;
  }

  .hero-card__right,
  .submit-summary {
    grid-template-columns: 1fr;
  }
}
</style>
