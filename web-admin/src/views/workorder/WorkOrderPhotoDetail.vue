<template>
  <div class="page">
    <div class="page-header">
      <h1>{{ t('workOrderPhotoDetail.title') }}</h1>
      <div>
        <el-button @click="goBack">{{
          t('workOrderPhotoDetail.buttons.back')
        }}</el-button>
        <el-button type="primary" @click="loadDetail">{{
          t('workOrderPhotoDetail.buttons.refresh')
        }}</el-button>
      </div>
    </div>

    <el-card v-loading="loading">
      <template v-if="photo">
        <el-row :gutter="20">
          <el-col :span="16">
            <div class="photo-wrap">
              <el-image
                v-if="imageUrl"
                :src="imageUrl"
                :preview-src-list="[imageUrl]"
                fit="contain"
                preview-teleported
                class="photo-image"
              >
                <template #error>
                  <div class="photo-image-error">
                    {{ t('workOrderPhotoDetail.imageLoadFailed') }}
                  </div>
                </template>
              </el-image>
              <el-empty
                v-else
                :description="t('workOrderPhotoDetail.imageNotFound')"
              />
            </div>
          </el-col>

          <el-col :span="8">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.photoId')">
                {{ photo.id || '-' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.fileName')">
                {{ photo.original_name || '-' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.takenAt')">
                {{ formatDateTime(photo.taken_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.fileSize')">
                {{ formatFileSize(photo.file_size) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.latitude')">
                {{ formatCoordinate(photo.latitude) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.longitude')">
                {{ formatCoordinate(photo.longitude) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.gpsAccuracy')">
                {{
                  Number.isFinite(Number(photo.gps_accuracy))
                    ? `${Number(photo.gps_accuracy).toFixed(1)} m`
                    : '-'
                }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.address')">
                {{ photo.address || '-' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.site')">
                {{ siteText }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.workOrder')">
                <template v-if="context.work_order_id">
                  <el-link
                    type="primary"
                    @click="openWorkOrderReview(context.work_order_id)"
                  >
                    {{ workOrderText }}
                  </el-link>
                </template>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.checkItem')">
                {{ checkItemText }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('workOrderPhotoDetail.labels.field')">
                {{ fieldText }}
              </el-descriptions-item>
              <el-descriptions-item
                v-if="sourcePhotoId"
                :label="t('workOrderPhotoDetail.labels.sourcePhotoId')"
              >
                {{ sourcePhotoId }}
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </template>

      <el-empty
        v-else
        :description="t('workOrderPhotoDetail.detailNotFound')"
      />
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { ElMessage } from 'element-plus';
import { inspectionExecutionApi } from '@/api/workorder';
import { resolveImageUrl } from '@/utils/imageLoader';

const route = useRoute();
const router = useRouter();
const { t, locale } = useI18n();

const loading = ref(false);
const detail = ref(null);

const photoId = computed(() => String(route.params.photoId || '').trim());
const photo = computed(() => detail.value?.photo || null);
const context = computed(() => detail.value?.context || {});
const sourcePhotoId = computed(() => String(route.query.sourcePhotoId || '').trim());
const fromWorkOrderId = computed(() => String(route.query.fromWorkOrderId || '').trim());

const imageUrl = computed(() => {
  const filePath = String(photo.value?.file_path || '').trim();
  if (!filePath) return '';
  return resolveImageUrl(filePath) || '';
});

const siteText = computed(() => {
  const siteName = String(context.value.site_name || '').trim();
  const siteId = context.value.site_id;
  if (siteName && siteId !== null && siteId !== undefined) {
    return t('workOrderPhotoDetail.siteText.withId', { siteName, siteId });
  }
  if (siteName) return siteName;
  if (siteId !== null && siteId !== undefined) {
    return t('workOrderPhotoDetail.siteText.idFallback', { siteId });
  }
  return '-';
});

const workOrderText = computed(() => {
  const workOrderId = String(context.value.work_order_id || '').trim();
  if (!workOrderId) return '-';
  const title = String(context.value.work_order_title || '').trim();
  const type = String(context.value.work_order_type || '').trim();
  const status = String(context.value.work_order_status || '').trim();
  const parts = [
    title
      ? title
      : t('workOrderPhotoDetail.workOrderText.idFallback', { workOrderId }),
    type ? t('workOrderPhotoDetail.workOrderText.typePart', { type }) : '',
    status
      ? t('workOrderPhotoDetail.workOrderText.statusPart', {
          status:
            status ||
            t('workOrderPhotoDetail.status.unknown'),
        })
      : '',
  ].filter(Boolean);
  return parts.join(' / ');
});

const checkItemText = computed(() => {
  const name = String(context.value.check_item_name || '').trim();
  const itemId = String(context.value.check_item_id || '').trim();
  if (name && itemId) return `${name} (ID:${itemId})`;
  return name || itemId || '-';
});

const fieldText = computed(() => {
  const label = String(context.value.field_label || '').trim();
  const fieldId = String(context.value.field_id || '').trim();
  if (label && fieldId && label !== fieldId) return `${label} (${fieldId})`;
  return label || fieldId || '-';
});

const loadDetail = async () => {
  const id = photoId.value;
  if (!id) {
    detail.value = null;
    return;
  }
  loading.value = true;
  try {
    detail.value = await inspectionExecutionApi.getInspectionPhotoDetail(id);
  } catch (error) {
    console.error('Failed to load photo detail:', error);
    detail.value = null;
    const backendDetail = error?.response?.data?.detail;
    const backendMessage =
      typeof backendDetail === 'string'
        ? backendDetail
        : backendDetail?.message || backendDetail?.detail;
    ElMessage.error(backendMessage || t('workOrderPhotoDetail.messages.loadFailed'));
  } finally {
    loading.value = false;
  }
};

const openWorkOrderReview = (workOrderId) => {
  const id = String(workOrderId || '').trim();
  if (!id) return;
  router.push({ name: 'WorkOrderReview', query: { id } });
};

const goBack = () => {
  if (fromWorkOrderId.value) {
    router.push({
      name: 'WorkOrderReview',
      query: { id: fromWorkOrderId.value },
    });
    return;
  }
  if (window.history.length > 1) {
    router.back();
    return;
  }
  router.push({ name: 'WorkOrderReview' });
};

const formatDateTime = (value) => {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return '-';
  const localeKey = String(locale.value || '').trim();
  if (localeKey === 'en-US') return dt.toLocaleString('en-US');
  if (localeKey === 'id-ID') return dt.toLocaleString('id-ID');
  return dt.toLocaleString('zh-CN');
};

const formatFileSize = (size) => {
  const value = Number(size);
  if (!Number.isFinite(value) || value <= 0) return '-';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(2)} KB`;
  return `${(value / (1024 * 1024)).toFixed(2)} MB`;
};

const formatCoordinate = (value) => {
  const v = Number(value);
  return Number.isFinite(v) ? v.toFixed(6) : '-';
};

watch(photoId, () => {
  loadDetail();
});

onMounted(() => {
  loadDetail();
});
</script>

<style scoped>
.page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.page-header h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
}

.photo-wrap {
  min-height: 520px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #f8fafc;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
}

.photo-image {
  width: 100%;
  max-height: 72vh;
}

.photo-image :deep(img) {
  width: 100%;
  max-height: 72vh;
  object-fit: contain;
}

.photo-image-error {
  color: #909399;
  font-size: 13px;
}
</style>
