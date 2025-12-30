<template>
  <div class="renderer" :class="{ 'renderer--template': variant === 'template' }">
    <div v-for="cat in content.check_categories || []" :key="cat.category_id" class="cat">
      <h3 class="cat-title">
        <span class="cat-name">{{ categoryName(cat) }}</span>
        <el-tag
          v-if="variant === 'template'"
          size="small"
          effect="light"
          :type="levelTagType(cat)"
        >
          {{ levelLabel(cat) }}
        </el-tag>
      </h3>
      <div v-if="variant === 'template' && categoryDesc(cat)" class="cat-desc">
        {{ categoryDesc(cat) }}
      </div>
      <el-card v-for="it in cat.items || []" :key="`${cat.category_id}-${it.item_id}`" class="item">
        <div class="item-header">
          <div class="item-title">
            <strong>{{ displayItemName(it) }}</strong>
            <el-tag v-if="it.required_type" size="small" effect="plain">{{ requiredTypeLabel(it.required_type) }}</el-tag>
            <el-tag
              v-if="variant === 'template'"
              size="small"
              effect="plain"
              :type="levelTagType(cat)"
            >
              {{ levelLabel(cat) }}
            </el-tag>
          </div>
          <template v-if="itemDesc(it)">
            <div v-if="variant === 'template'" class="desc-block" role="note" aria-label="检查说明">
              <div class="desc-block__title">
                <el-icon><InfoFilled /></el-icon>
                <span>检查说明</span>
              </div>
              <div class="desc-block__content">{{ itemDesc(it) }}</div>
            </div>
            <div v-else class="item-desc">{{ itemDesc(it) }}</div>
          </template>
        </div>

	        <!-- 站点级字段 -->
	        <div v-if="(it.fields || []).length" class="fields">
	          <div v-for="fd in (it.fields || [])" :key="fd.field_id" class="field">
	            <label class="field-label">
	              <span class="field-label__text">{{ fieldDisplayLabel(fd) }}</span>
              <el-popover
                v-if="String(fieldHelpText(fd) || '').trim()"
                placement="top-start"
                trigger="click"
                width="360"
                :title="`${fieldDisplayLabel(fd)} 描述/注意事项`"
              >
                <template #reference>
                  <el-icon class="field-help-icon" :title="`${fieldDisplayLabel(fd)} 描述/注意事项`">
                    <QuestionFilled />
                  </el-icon>
	                </template>
	                <div class="field-help-text">{{ fieldHelpText(fd) }}</div>
	              </el-popover>
	              <el-upload
	                v-if="!disabled && canUploadFieldPhoto(it, fd)"
	                :show-file-list="false"
	                :http-request="(opt) => onUploadForField(cat, it, { fieldId: fd.field_id, level: 'site' }, opt)"
	                accept="image/*"
	              >
	                <el-button link size="small" type="primary" class="field-upload-btn" @click.stop>
	                  <el-icon><Upload /></el-icon>
	                </el-button>
	              </el-upload>
	            </label>
            <!-- number -->
            <el-input-number
              v-if="(fd.type || 'text').toLowerCase() === 'number'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :min="fd?.constraints?.min"
              :max="fd?.constraints?.max"
              :disabled="disabled"
            />
            <!-- boolean -->
            <el-switch
              v-else-if="(fd.type || 'text').toLowerCase() === 'boolean'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            />
            <!-- select (single) -->
            <el-select
              v-else-if="(fd.type || 'text').toLowerCase() === 'select_single'"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            >
              <el-option v-for="o in (fd?.options || [])" :key="o.value" :label="optionLabel(o)" :value="o.value" />
            </el-select>
            <!-- select (multi) -->
            <el-select
              v-else-if="(fd.type || 'text').toLowerCase() === 'select_multi'"
              multiple
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            >
              <el-option v-for="o in (fd?.options || [])" :key="o.value" :label="optionLabel(o)" :value="o.value" />
            </el-select>
            <!-- date/time/datetime -->
            <el-date-picker
              v-else-if="['date','time','datetime'].includes((fd.type || '').toLowerCase())"
              :type="(fd.type || 'date').toLowerCase()"
              :value-format="dateValueFormat(fd.type)"
              :format="dateDisplayFormat(fd.type)"
              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
            />
            <!-- text/default -->
	            <el-input
	              v-else
	              :placeholder="fieldPlaceholder(fd)"
	              :model-value="getValue(cat, it, fd)"
              @update:modelValue="val => setValue(cat, it, fd, val)"
              :disabled="disabled"
              :maxlength="fd?.constraints?.max_length || null"
	              :minlength="fd?.constraints?.min_length || null"
	              show-word-limit
	            />
	
	            <div
	              v-if="getPhotosForField(it.photos, fd.field_id).length"
	              class="field-photos"
	            >
	              <div
	                v-for="(p, idx) in getPhotosForField(it.photos, fd.field_id)"
	                :key="p.id"
	                class="field-photo-thumb"
	              >
	                <ProgressImage
	                  :src="fileUrl(p.file_path)"
	                  fit="cover"
	                  @click.stop="openPhotoPreview(getPhotosForField(it.photos, fd.field_id), idx)"
	                />
	                <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                <div class="thumb-actions">
	                  <el-button
	                    v-if="!disabled"
	                    link
	                    type="danger"
	                    size="small"
	                    @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'site', fieldId: fd.field_id, photoId: p.id, photo: p })"
	                    title="删除"
	                  >
	                    <el-icon><Delete /></el-icon>
	                  </el-button>
	                </div>
	              </div>
	            </div>
	          </div>
	        </div>
	        <!-- 扇区级数据 -->
	        <div v-if="(it.sectors || []).length" class="sub-block">
	          <div class="sub-title">扇区级</div>
	          <div class="card-grid">
	            <el-card v-for="sec in it.sectors" :key="sec.sector_id" shadow="never" class="mini-card">
	              <div class="mini-header">
	                <el-tag size="small" type="info">扇区 {{ sec.sector_id }}</el-tag>
	              </div>
	              <div v-if="getSubFieldIds(it, sec).length" class="kv-list">
	                <div v-for="fid in getSubFieldIds(it, sec)" :key="fid" class="kv-item kv-item--block">
	                  <div class="kv-line">
	                    <span class="kv-key">{{ fieldLabel(it, fid) }}</span>
	                    <span class="kv-val">{{ renderVal((sec.values || {})[fid]) }}</span>
	                    <el-upload
	                      v-if="!disabled && canUploadFieldPhotoById(it, fid)"
	                      :show-file-list="false"
	                      :http-request="(opt) => onUploadForField(cat, it, { fieldId: fid, level: 'sector', sectorId: sec.sector_id }, opt)"
	                      accept="image/*"
	                    >
	                      <el-button link size="small" type="primary" class="field-upload-btn" @click.stop>
	                        <el-icon><Upload /></el-icon>
	                      </el-button>
	                    </el-upload>
	                  </div>
	                  <div
	                    v-if="getPhotosForField(sec.photos, fid).length"
	                    class="field-photos field-photos--compact"
	                  >
	                    <div
	                      v-for="(p, idx) in getPhotosForField(sec.photos, fid)"
	                      :key="p.id"
	                      class="field-photo-thumb"
	                    >
	                      <ProgressImage
	                        :src="fileUrl(p.file_path)"
	                        fit="cover"
	                        @click.stop="openPhotoPreview(getPhotosForField(sec.photos, fid), idx)"
	                      />
	                      <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                      <div class="thumb-actions">
	                        <el-button
	                          v-if="!disabled"
	                          link
	                          type="danger"
	                          size="small"
	                          @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'sector', sectorId: sec.sector_id, fieldId: fid, photoId: p.id, photo: p })"
	                          title="删除"
	                        >
	                          <el-icon><Delete /></el-icon>
	                        </el-button>
	                      </div>
	                    </div>
	                  </div>
	                </div>
	              </div>
	
	              <div
	                v-if="getUnlinkedPhotos(sec.photos).length"
	                class="sub-extra-photos"
	              >
	                <el-divider class="photos-divider" />
	                <div class="field-photos field-photos--compact">
	                  <div
	                    v-for="(p, idx) in getUnlinkedPhotos(sec.photos)"
	                    :key="p.id"
	                    class="field-photo-thumb"
	                  >
	                    <ProgressImage
	                      :src="fileUrl(p.file_path)"
	                      fit="cover"
	                      @click.stop="openPhotoPreview(getUnlinkedPhotos(sec.photos), idx)"
	                    />
	                    <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                    <div class="thumb-actions">
	                      <el-button
	                        v-if="!disabled"
	                        link
	                        type="danger"
	                        size="small"
	                        @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'sector', sectorId: sec.sector_id, photoId: p.id, photo: p })"
	                        title="删除"
	                      >
	                        <el-icon><Delete /></el-icon>
	                      </el-button>
	                    </div>
	                  </div>
	                </div>
	              </div>
	
	              <div
	                v-if="(!it.fields || !(it.fields || []).length) && ((sec.photos && sec.photos.length) || (!disabled && needsPhoto(it)))"
	                class="photos"
	              >
	                <div class="photos-header" v-if="sec.photos && sec.photos.length">照片</div>
	                <div class="grid" v-if="sec.photos && sec.photos.length">
	                  <div v-for="(p, idx) in sec.photos" :key="p.id" class="item photo-card">
	                    <ProgressImage class="photo-card-image" :src="fileUrl(p.file_path)" fit="cover" @click.stop="openPhotoPreview(sec.photos, idx)" />
	                    <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                    <div class="meta compact">
	                      <div class="meta-actions">
	                        <el-button
	                          v-if="!disabled"
	                          link
	                          type="danger"
	                          size="small"
	                          @click="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'sector', sectorId: sec.sector_id, photoId: p.id, photo: p })"
	                          title="删除"
	                          aria-label="删除"
	                        >
	                          <el-icon><Delete /></el-icon>
	                        </el-button>
	                      </div>
	                    </div>
	                  </div>
	                </div>
	                <div class="upload-bar" v-if="!disabled && needsPhoto(it)">
	                  <el-upload
	                    :show-file-list="false"
	                    :http-request="(opt) => onUploadForField(cat, it, { level: 'sector', sectorId: sec.sector_id }, opt)"
	                    accept="image/*"
	                  >
	                    <el-button size="small" type="primary"><el-icon><Upload /></el-icon>选择图片</el-button>
	                  </el-upload>
	                </div>
	              </div>
	            </el-card>
	          </div>
	        </div>

	        <!-- 小区级数据 -->
	        <div v-if="(it.cells || []).length" class="sub-block">
	          <div class="sub-title">小区级</div>
	          <div class="card-grid">
	            <el-card v-for="cell in it.cells" :key="cell.cell_id" shadow="never" class="mini-card">
	              <div class="mini-header">
	                <el-tag size="small" type="success">小区 {{ cell.cell_id }}</el-tag>
	                <el-tag size="small" effect="plain" style="margin-left:6px">扇区 {{ cell.sector_id }}</el-tag>
	                <el-tag v-if="cell.band" size="small" effect="plain" style="margin-left:6px">Band {{ cell.band }}</el-tag>
	              </div>
	              <div v-if="getSubFieldIds(it, cell).length" class="kv-list">
	                <div v-for="fid in getSubFieldIds(it, cell)" :key="fid" class="kv-item kv-item--block">
	                  <div class="kv-line">
	                    <span class="kv-key">{{ fieldLabel(it, fid) }}</span>
	                    <span class="kv-val">{{ renderVal((cell.values || {})[fid]) }}</span>
	                    <el-upload
	                      v-if="!disabled && canUploadFieldPhotoById(it, fid)"
	                      :show-file-list="false"
	                      :http-request="(opt) => onUploadForField(cat, it, { fieldId: fid, level: 'cell', cellId: cell.cell_id }, opt)"
	                      accept="image/*"
	                    >
	                      <el-button link size="small" type="primary" class="field-upload-btn" @click.stop>
	                        <el-icon><Upload /></el-icon>
	                      </el-button>
	                    </el-upload>
	                  </div>
	                  <div
	                    v-if="getPhotosForField(cell.photos, fid).length"
	                    class="field-photos field-photos--compact"
	                  >
	                    <div
	                      v-for="(p, idx) in getPhotosForField(cell.photos, fid)"
	                      :key="p.id"
	                      class="field-photo-thumb"
	                    >
	                      <ProgressImage
	                        :src="fileUrl(p.file_path)"
	                        fit="cover"
	                        @click.stop="openPhotoPreview(getPhotosForField(cell.photos, fid), idx)"
	                      />
	                      <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                      <div class="thumb-actions">
	                        <el-button
	                          v-if="!disabled"
	                          link
	                          type="danger"
	                          size="small"
	                          @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'cell', cellId: cell.cell_id, fieldId: fid, photoId: p.id, photo: p })"
	                          title="删除"
	                        >
	                          <el-icon><Delete /></el-icon>
	                        </el-button>
	                      </div>
	                    </div>
	                  </div>
	                </div>
	              </div>
	
	              <div
	                v-if="getUnlinkedPhotos(cell.photos).length"
	                class="sub-extra-photos"
	              >
	                <el-divider class="photos-divider" />
	                <div class="field-photos field-photos--compact">
	                  <div
	                    v-for="(p, idx) in getUnlinkedPhotos(cell.photos)"
	                    :key="p.id"
	                    class="field-photo-thumb"
	                  >
	                    <ProgressImage
	                      :src="fileUrl(p.file_path)"
	                      fit="cover"
	                      @click.stop="openPhotoPreview(getUnlinkedPhotos(cell.photos), idx)"
	                    />
	                    <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                    <div class="thumb-actions">
	                      <el-button
	                        v-if="!disabled"
	                        link
	                        type="danger"
	                        size="small"
	                        @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'cell', cellId: cell.cell_id, photoId: p.id, photo: p })"
	                        title="删除"
	                      >
	                        <el-icon><Delete /></el-icon>
	                      </el-button>
	                    </div>
	                  </div>
	                </div>
	              </div>
	
	              <div
	                v-if="(!it.fields || !(it.fields || []).length) && ((cell.photos && cell.photos.length) || (!disabled && needsPhoto(it)))"
	                class="photos"
	              >
	                <div class="photos-header" v-if="cell.photos && cell.photos.length">照片</div>
	                <div class="grid" v-if="cell.photos && cell.photos.length">
	                  <div v-for="(p, idx) in cell.photos" :key="p.id" class="item photo-card">
	                    <ProgressImage class="photo-card-image" :src="fileUrl(p.file_path)" fit="cover" @click.stop="openPhotoPreview(cell.photos, idx)" />
	                    <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	                    <div class="meta compact">
	                      <div class="meta-actions">
	                        <el-button
	                          v-if="!disabled"
	                          link
	                          type="danger"
	                          size="small"
	                          @click="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'cell', cellId: cell.cell_id, photoId: p.id, photo: p })"
	                          title="删除"
	                          aria-label="删除"
	                        >
	                          <el-icon><Delete /></el-icon>
	                        </el-button>
	                      </div>
	                    </div>
	                  </div>
	                </div>
	                <div class="upload-bar" v-if="!disabled && needsPhoto(it)">
	                  <el-upload
	                    :show-file-list="false"
	                    :http-request="(opt) => onUploadForField(cat, it, { level: 'cell', cellId: cell.cell_id }, opt)"
	                    accept="image/*"
	                  >
	                    <el-button size="small" type="primary"><el-icon><Upload /></el-icon>选择图片</el-button>
	                  </el-upload>
	                </div>
	              </div>
	            </el-card>
	          </div>
	        </div>
	
	        <div v-if="getExtraPhotos(it).length" class="sub-extra-photos">
	          <el-divider class="photos-divider" />
	          <div class="field-photos">
	            <div
	              v-for="(p, idx) in getExtraPhotos(it)"
	              :key="p.id"
	              class="field-photo-thumb"
	            >
	              <ProgressImage
	                :src="fileUrl(p.file_path)"
	                fit="cover"
	                @click.stop="openPhotoPreview(getExtraPhotos(it), idx)"
	              />
	              <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	              <div class="thumb-actions">
	                <el-button
	                  v-if="!disabled"
	                  link
	                  type="danger"
	                  size="small"
	                  @click.stop="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'site', photoId: p.id, photo: p })"
	                  title="删除"
	                >
	                  <el-icon><Delete /></el-icon>
	                </el-button>
	              </div>
	            </div>
	          </div>
	        </div>
	
	        <!-- 照片类检查项但无字段定义：按检查项展示照片 -->
	        <div
	          v-if="(!(it.fields || []).length) && ((it.photos && it.photos.length) || (!disabled && needsPhoto(it)))"
	          class="photos"
	        >
	          <div class="photos-header" v-if="it.photos && it.photos.length">照片</div>
	          <div class="grid" v-if="it.photos && it.photos.length">
	            <div v-for="(p, idx) in it.photos" :key="p.id" class="item photo-card">
	              <ProgressImage class="photo-card-image" :src="fileUrl(p.file_path)" fit="cover" @click.stop="openPhotoPreview(it.photos, idx)" />
	              <el-tag v-if="p.pending" size="small" type="warning" class="badge-pending">未保存</el-tag>
	              <div class="meta compact">
	                <div class="meta-actions">
	                  <el-button
	                    v-if="!disabled"
	                    link
	                    type="danger"
	                    size="small"
	                    @click="$emit('delete-photo', { categoryId: cat.category_id, itemId: it.item_id, level: 'site', photoId: p.id, photo: p })"
	                    title="删除"
	                    aria-label="删除"
	                  >
	                    <el-icon><Delete /></el-icon>
	                  </el-button>
	                </div>
	              </div>
	            </div>
	          </div>
	          <div class="upload-bar" v-if="!disabled && needsPhoto(it)">
	            <el-upload
	              :show-file-list="false"
	              :http-request="(opt) => onUploadForField(cat, it, { level: 'site' }, opt)"
	              accept="image/*"
	            >
	              <el-button size="small" type="primary"><el-icon><Upload /></el-icon>选择图片</el-button>
	            </el-upload>
	          </div>
	        </div>
	      </el-card>
	    </div>
	  </div>

	  <!-- 预览准备进度（下载/缓存） -->
	  <div v-if="previewPreparing" class="preview-loading-overlay" @click.stop>
	    <div class="preview-loading-card" @click.stop>
	      <div class="preview-loading-title">加载中</div>
	      <div class="preview-loading-sub">{{ previewProgress.done }}/{{ previewProgress.total }}</div>
	      <div class="preview-loading-bar">
	        <div class="preview-loading-bar-fill" :style="{ width: previewProgress.percent + '%' }"></div>
	      </div>
	      <div class="preview-loading-percent">{{ previewProgress.percent }}%</div>
	    </div>
	  </div>

	  <!-- 全屏图片预览 -->
	  <ElImageViewer
	    v-if="previewVisible"
	    :url-list="previewUrls"
	    :initial-index="previewIndex"
	    :hide-on-click-modal="true"
	    :teleported="true"
	    @close="closePreview"
	  />
	</template>

<script setup>
import { onBeforeUnmount, reactive, ref, watch } from 'vue'
import { ElImageViewer, ElMessage } from 'element-plus'
import { QuestionFilled } from '@element-plus/icons-vue'
import ProgressImage from '@/components/common/ProgressImage.vue'
import { createObjectUrl, loadImageBlob, revokeObjectUrl, resolveImageUrl } from '@/utils/imageLoader'

const props = defineProps({
  content: { type: Object, required: true },
  disabled: { type: Boolean, default: false },
  variant: { type: String, default: 'archive' },
  locale: { type: String, default: 'zh' },
})
const emit = defineEmits(['change', 'upload-photo', 'delete-photo'])

const normalizeLocale = (value) => {
  const s = String(value || '').trim().toLowerCase().replace('_', '-')
  if (!s) return 'zh'
  if (s === 'zh' || s === 'zh-cn' || s === 'zh-hans') return 'zh'
  if (s === 'en' || s === 'en-us' || s === 'en-gb') return 'en'
  if (s === 'id' || s === 'id-id') return 'id'
  return s
}

const pickText = (base, i18nMap) => {
  const loc = normalizeLocale(props.locale)
  const baseText = base === null || base === undefined ? '' : String(base)
  if (!loc || loc === 'zh') return baseText
  if (i18nMap && typeof i18nMap === 'object' && !Array.isArray(i18nMap)) {
    const v = i18nMap[loc]
    if (v !== null && v !== undefined && String(v).trim() !== '') return String(v)
  }
  return baseText
}

const categoryName = (cat) => {
  const base = (cat?.category_name || '').trim()
  const picked = pickText(base, cat?.category_name_i18n)
  return picked || cat?.category_id || ''
}

const categoryDesc = (cat) => {
  return pickText(cat?.description || '', cat?.description_i18n)
}

const itemDesc = (it) => {
  return pickText(it?.description || '', it?.description_i18n)
}

const fieldDisplayLabel = (fd) => {
  const base = fd?.label || fd?.field_id || ''
  return pickText(base, fd?.label_i18n) || fd?.field_id || ''
}

const fieldPlaceholder = (fd) => {
  return pickText(fd?.placeholder || '', fd?.placeholder_i18n)
}

const fieldHelpText = (fd) => {
  return pickText(fd?.help_text || '', fd?.help_text_i18n)
}

const optionLabel = (o) => {
  const base = o?.label ?? o?.value ?? ''
  return pickText(base, o?.label_i18n)
}

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

const levelLabel = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return '站点级'
    case 'sector':
      return '扇区级'
    case 'device':
      return '设备级'
    case 'cell_earfcn':
      return '小区级'
    default:
      return '站点级'
  }
}

const levelTagType = (category) => {
  const lt = normalizeLevelType(category)
  switch (lt) {
    case 'site':
      return 'success'
    case 'sector':
      return 'warning'
    case 'device':
      return 'info'
    case 'cell_earfcn':
      return 'danger'
    default:
      return 'success'
  }
}

const needsPhoto = (it) => {
  const t = (it?.required_type || '').toLowerCase()
  // 需要拍照：包含 photo 或 both 关键字（兼容 photo, photo_and_data, photo+data, both 等写法）
  return t.includes('photo') || t.includes('both')
}

const requiredTypeLabel = (value) => {
  const t = String(value || '').trim().toLowerCase()
  if (!t) return ''
  if (t === 'both' || t.includes('photo') && t.includes('data')) return '照片+数据'
  if (t === 'photo' || t.includes('photo')) return '照片'
  if (t === 'data' || t.includes('data')) return '数据'
  return String(value)
}

const state = reactive({ values: {} })

const buildKey = (cat, it, fd) => `${cat.category_id}.${it.item_id}.${fd.field_id}`
const ptr = (cat, it, fd) => buildKey(cat, it, fd)

function coerceBool(v) {
  if (v === true || v === false) return v
  const s = String(v ?? '').trim().toLowerCase()
  if (['1','true','yes','y','是','有'].includes(s)) return true
  if (['0','false','no','n','否','无'].includes(s)) return false
  return null
}

function coerceNumber(v) {
  if (v === null || v === undefined || v === '') return null
  const n = Number(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function coerceByType(fd, val) {
  const t = String(fd?.type || '').toLowerCase()
  if (t === 'number') return coerceNumber(val)
  if (t === 'boolean') return coerceBool(val)
  if (t === 'select_multi') {
    if (Array.isArray(val)) return val
    if (val === null || val === undefined || val === '') return []
    return [val]
  }
  // date/time/datetime 走字符串 + value-format，由控件处理
  return val
}

watch(() => props.content, (val) => {
  // 初始化局部表单值（保持同一引用，避免丢失响应性）
  for (const k of Object.keys(state.values)) delete state.values[k]
  const cats = (val?.check_categories || [])
  cats.forEach((c) => (c.items || []).forEach((it) => {
    const values = it.values || {}
    ;(it.fields || []).forEach((fd) => {
      const k = buildKey(c, it, fd)
      state.values[k] = coerceByType(fd, values[fd.field_id])
    })
  }))
}, { immediate: true })

function emitChange(cat, it, fd) {
  emit('change', { categoryId: cat.category_id, itemId: it.item_id, fieldId: fd.field_id, value: state.values[buildKey(cat, it, fd)] })
}

function _safeArray(v) {
  return Array.isArray(v) ? v : []
}

function _normId(v) {
  return String(v ?? '').trim()
}

function getPhotosForField(photos, fieldId) {
  const fid = _normId(fieldId)
  if (!fid) return []
  return _safeArray(photos).filter((p) => _normId(p?.field_id) === fid)
}

function getUnlinkedPhotos(photos) {
  return _safeArray(photos).filter((p) => !_normId(p?.field_id))
}

function getExtraPhotos(it) {
  const photos = _safeArray(it?.photos)
  if (!photos.length) return []
  const known = new Set(_safeArray(it?.fields).map((f) => _normId(f?.field_id)).filter(Boolean))
  return photos.filter((p) => {
    const fid = _normId(p?.field_id)
    return !fid || !known.has(fid)
  })
}

function getSubFieldIds(it, rec) {
  const allowPhotoIds = _safeArray(it?.fields)
    .filter((f) => f?.allow_photo === true)
    .map((f) => _normId(f?.field_id))
    .filter(Boolean)

  const values = (rec && typeof rec.values === 'object' && !Array.isArray(rec.values)) ? rec.values : {}
  const valueKeys = Object.keys(values || {}).map(_normId).filter(Boolean)

  const photoKeys = _safeArray(rec?.photos).map((p) => _normId(p?.field_id)).filter(Boolean)

  const union = new Set([...allowPhotoIds, ...valueKeys, ...photoKeys])

  const ordered = []
  const used = new Set()
  _safeArray(it?.fields).forEach((f) => {
    const fid = _normId(f?.field_id)
    if (!fid || !union.has(fid) || used.has(fid)) return
    used.add(fid)
    ordered.push(fid)
  })
  for (const fid of union) {
    if (!used.has(fid)) {
      used.add(fid)
      ordered.push(fid)
    }
  }
  return ordered
}

function canUploadFieldPhoto(it, fd) {
  if (!needsPhoto(it)) return false
  const fid = _normId(fd?.field_id)
  if (!fid) return false
  return fd?.allow_photo === true
}

function canUploadFieldPhotoById(it, fieldId) {
  if (!needsPhoto(it)) return false
  const fid = _normId(fieldId)
  if (!fid) return false
  const f = _safeArray(it?.fields).find((x) => _normId(x?.field_id) === fid)
  return f?.allow_photo === true
}

function photoPreviewList(photos) {
  return _safeArray(photos).map((p) => fileUrl(p?.file_path)).filter(Boolean)
}

function onUploadForField(cat, it, meta, opt) {
  const payload = {
    categoryId: cat.category_id,
    itemId: it.item_id,
    file: opt.file,
  }
  const fieldId = _normId(meta?.fieldId)
  const level = _normId(meta?.level)
  const sectorId = _normId(meta?.sectorId)
  const cellId = _normId(meta?.cellId)
  if (fieldId) payload.fieldId = fieldId
  if (level) payload.level = level
  if (sectorId) payload.sectorId = sectorId
  if (cellId) payload.cellId = cellId
  emit('upload-photo', payload)
}

function getValue(cat, it, fd) {
  const k = buildKey(cat, it, fd)
  if (Object.prototype.hasOwnProperty.call(state.values, k)) {
    return state.values[k]
  }
  const raw = (it?.values || {})[fd.field_id]
  return coerceByType(fd, raw)
}

function setValue(cat, it, fd, val) {
  if (props.disabled) return
  const k = buildKey(cat, it, fd)
  state.values[k] = val
  emitChange(cat, it, fd)
}

function fieldLabel(it, key) {
  const f = (it.fields || []).find(x => x.field_id === key)
  const base = (f && (f.label || f.field_id)) || key
  return pickText(base, f?.label_i18n) || base
}

function renderVal(v) {
  if (v === null || v === undefined) return '-'
  if (Array.isArray(v)) return v.join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return v
}

function fileUrl(filePath) {
  return resolveImageUrl(filePath)
}

const previewVisible = ref(false)
const previewPreparing = ref(false)
const previewUrls = ref([])
const previewIndex = ref(0)
const previewProgress = reactive({
  total: 0,
  done: 0,
  percent: 0,
})

let previewLoadToken = 0
let previewObjectUrls = []

const cleanupPreviewObjectUrls = () => {
  previewObjectUrls.forEach((u) => revokeObjectUrl(u))
  previewObjectUrls = []
  previewUrls.value = []
}

const closePreview = () => {
  previewLoadToken += 1
  previewVisible.value = false
  previewPreparing.value = false
  previewProgress.total = 0
  previewProgress.done = 0
  previewProgress.percent = 0
  cleanupPreviewObjectUrls()
}

const openPhotoPreview = async (photos, startIndex = 0) => {
  const list = Array.isArray(photos) ? photos : []
  if (list.length === 0) return

  const token = ++previewLoadToken
  previewPreparing.value = true
  previewProgress.total = list.length
  previewProgress.done = 0
  previewProgress.percent = 0
  cleanupPreviewObjectUrls()

  let failed = 0
  const urls = []

  try {
    for (let i = 0; i < list.length; i++) {
      if (token !== previewLoadToken) return
      const p = list[i]
      const src = fileUrl(p?.file_path)
      previewProgress.done = i
      previewProgress.percent = 0

      const res = await loadImageBlob({
        url: src,
        onProgress: (percent) => {
          if (token !== previewLoadToken) return
          previewProgress.percent = percent
        },
      })

      if (token !== previewLoadToken) return

      if (res?.ok && res.blob) {
        const objUrl = createObjectUrl(res.blob)
        if (objUrl) {
          previewObjectUrls.push(objUrl)
          urls.push(objUrl)
        } else {
          failed += 1
          urls.push(src)
        }
      } else {
        failed += 1
        urls.push(src)
      }

      previewProgress.done = i + 1
      previewProgress.percent = 100
    }

    if (token !== previewLoadToken) return

    previewUrls.value = urls.filter(Boolean)
    previewIndex.value = Math.min(
      Math.max(0, Number(startIndex) || 0),
      Math.max(0, previewUrls.value.length - 1)
    )
    previewVisible.value = true

    if (failed > 0) {
      ElMessage.warning(`有 ${failed} 张图片加载失败，将尝试直接预览原始链接`)
    }
  } finally {
    if (token === previewLoadToken) previewPreparing.value = false
  }
}

onBeforeUnmount(() => {
  closePreview()
})

function displayItemName(it) {
  const base = it.item_name || it.item_id || ''
  const name = pickText(base, it?.item_name_i18n)
  if (normalizeLocale(props.locale) === 'zh' && ((it.cells || []).length > 1 || (it.sectors || []).length > 1)) {
    // 去掉尾部含“小区/扇区”描述，避免暗示只对应单个单元
    return name.replace(/[-\s]*小区.*$/u, '').replace(/[-\s]*扇区.*$/u, '')
  }
  return name
}

function dateValueFormat(type) {
  const t = String(type || 'date').toLowerCase()
  if (t === 'date') return 'YYYY-MM-DD'
  if (t === 'time') return 'HH:mm:ss'
  return 'YYYY-MM-DD HH:mm'
}
function dateDisplayFormat(type) {
  const t = String(type || 'date').toLowerCase()
  if (t === 'date') return 'YYYY-MM-DD'
  if (t === 'time') return 'HH:mm:ss'
  return 'YYYY-MM-DD HH:mm'
}
</script>

<style scoped>
.cat { margin-bottom: 16px; }
.item { margin-bottom: 12px; border: 1px solid #eee; border-radius: 10px; overflow: hidden; background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.06); padding: 12px; }
.item-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.item-title { display: flex; align-items: center; gap: 8px; }
.item-desc { white-space: pre-wrap; }
.fields { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 8px 16px; margin-top: 8px; }
.field label { display: block; font-size: 12px; color: #888; margin-bottom: 4px; }
.field-label { display: flex; align-items: center; gap: 6px; }
.field-label__text { flex: 1 1 auto; min-width: 0; }
.field-help-icon { cursor: pointer; color: #909399; font-size: 14px; }
.field-help-text { white-space: pre-line; line-height: 1.6; }
.field-upload-btn { padding: 0; }
.field-photos { margin-top: 6px; display: flex; flex-wrap: wrap; gap: 6px; }
.field-photos--compact { gap: 6px; }
.field-photo-thumb { position: relative; width: 64px; height: 64px; border: 1px solid #ebeef5; border-radius: 8px; overflow: hidden; background: #fff; }
.field-photo-thumb :deep(.progress-image) { width: 100%; height: 100%; }
.field-photo-thumb :deep(img) { width: 100%; height: 100%; object-fit: cover; }
.field-photo-thumb .badge-pending { top: 4px; right: 4px; }
.thumb-actions { position: absolute; top: 2px; left: 2px; display: flex; gap: 4px; }
.thumb-actions :deep(.el-button) { padding: 0; }
.sub-block { margin-top: 12px; border: 1px dashed #e4e7ed; padding: 8px; border-radius: 6px; background: #fafbfc; }
.sub-title { font-weight: 600; color: #606266; margin-bottom: 6px; }
.sub-extra-photos { margin-top: 8px; }
.photos-divider { margin: 8px 0; }
.kv-list { display: flex; flex-direction: column; gap: 4px; }
.kv-item { display: flex; gap: 6px; font-size: 13px; line-height: 1.5; flex-wrap: wrap; }
.kv-item--block { flex-direction: column; align-items: stretch; gap: 6px; padding: 6px 0; border-bottom: 1px dashed #ebeef5; }
.kv-item--block:last-child { border-bottom: none; }
.kv-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.kv-key { color: #606266; font-weight: 600; }
.kv-val { color: #303133; }
.photos { margin-top: 12px; }
.upload-bar { margin-top: 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 16px; }
.photo-card { position: relative; border: 1px solid #f0f0f0; border-radius: 8px; overflow: hidden; background: #fff; }
.photo-card-image { width: 100%; height: auto !important; aspect-ratio: 4 / 3; }
.badge-pending { position: absolute; top: 8px; right: 8px; pointer-events: none; }
.meta { display:flex; justify-content: flex-end; align-items:center; padding:6px 8px; font-size:12px; background:#fafafa; }
.meta.compact { gap: 8px; }
.muted { color: #999; font-weight: normal; }

/* 预览准备进度 */
.preview-loading-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.35);
  z-index: 3000;
}

.preview-loading-card {
  width: 280px;
  border-radius: 12px;
  padding: 14px 16px;
  background: #fff;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.22);
  text-align: center;
}

.preview-loading-title {
  font-size: 14px;
  font-weight: 700;
  color: #303133;
}

.preview-loading-sub {
  margin-top: 6px;
  font-size: 12px;
  color: #909399;
}

.preview-loading-bar {
  margin-top: 10px;
  height: 8px;
  border-radius: 999px;
  background: #ebeef5;
  overflow: hidden;
}

.preview-loading-bar-fill {
  height: 100%;
  width: 0;
  background: #409eff;
}

.preview-loading-percent {
  margin-top: 8px;
  font-size: 18px;
  font-weight: 800;
  color: #409eff;
}

.cat-title {
  margin: 0 0 8px 0;
}

.renderer--template .cat-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.renderer--template .cat-desc {
  margin: -6px 0 10px 0;
  font-size: 12px;
  color: #909399;
}

.renderer--template .item {
  box-shadow: none;
  border: 1px solid #ebeef5;
  border-radius: 12px;
}

.renderer--template .item-header {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.renderer--template .fields {
  grid-template-columns: 1fr;
  gap: 10px;
}

.renderer--template .field label {
  color: #606266;
}

.renderer--template .desc-block {
  width: 100%;
  border-radius: 10px;
  padding: 10px 12px;
  background: #f5f7fa;
  border: 1px solid #ebeef5;
}

.renderer--template .desc-block__title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #606266;
  font-weight: 600;
  margin-bottom: 6px;
}

.renderer--template .desc-block__content {
  font-size: 13px;
  color: #303133;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
